"""One client per model type, all answering the same closed question (Era 2, Step 7).

Every arm takes an :class:`~utils.decision.items.Item` in a given option order and
returns a :class:`Decision`: a probability per option key, the top key and the
latency. The item text is identical across arms; only the wire format differs.

- ``qwen_reason``: the LLM thinks, then names a letter. One-hot "probabilities".
- ``qwen_prob``: the same LLM, thinking off, one letter; probabilities from the
  log-probabilities of the option letters (``top_logprobs=20``).
- ``pplx``: the vLLM decision server on ``:7500`` (``/v1/decisions``).
- ``d3``: GAIFA's d3-lite on ``:5107`` (``/v1/decide``).
"""

from __future__ import annotations

import json
import math
import re
import string
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from utils.decision.items import Item

LETTERS = string.ascii_uppercase


@dataclass
class Decision:
    probs: dict[str, float]
    top: str | None
    ms: float
    meta: dict[str, Any] = field(default_factory=dict)


def _post(url: str, payload: dict, *, timeout: float = 600.0, retries: int = 3) -> dict:
    data = json.dumps(payload).encode()
    last: Exception | None = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 - local servers
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")[:300]
            if 400 <= exc.code < 500:
                raise ValueError(f"{url} rejected the request ({exc.code}): {body}") from exc
            last = exc
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last = exc
        time.sleep(min(20.0, 2.0 ** attempt))
    raise ConnectionError(f"{url} unreachable: {last}")


def render(item: Item, order: list[str], *, lettered: bool) -> tuple[str, dict[str, str]]:
    """The item as text, options in ``order``. Returns (text, letter->key)."""
    lines = [item.context.strip(), "", f"Question: {item.question.strip()}", "", item.prompt.strip(), ""]
    to_key = {}
    for i, key in enumerate(order):
        tag = LETTERS[i] if lettered else key
        to_key[tag] = key
        lines.append(f"{tag}) {item.option_text(key)}")
    return "\n".join(lines).strip(), to_key


class QwenReason:
    name = "qwen_reason"

    def __init__(self, spec: Any) -> None:
        self.spec = spec

    def __call__(self, item: Item, order: list[str]) -> Decision:
        from utils.llm.toolcalls import chat

        text, to_key = render(item, order, lettered=True)
        msg = text + "\n\nThink it through, then end your reply with one line: Answer: <letter>"
        t = time.time()
        r = chat(self.spec, [{"role": "user", "content": msg}], reasoning="medium", max_tokens=16384,
                 temperature=0.0)
        ms = (time.time() - t) * 1000
        found = re.findall(r"Answer:\s*\**\s*([A-Z])\b", r.text or "")
        letter = found[-1] if found else None
        key = to_key.get(letter) if letter else None
        probs = {k: (1.0 if k == key else 0.0) for k in order}
        return Decision(probs, key, ms, {"status": r.status, "envelope_model": r.envelope_model,
                                         "repairs": [e.kind for e in r.repairs], "raw_tail": (r.text or "")[-200:]})


class QwenProb:
    name = "qwen_prob"

    def __init__(self, spec: Any) -> None:
        self.spec = spec
        self.url = spec.endpoint.rstrip("/") + "/chat/completions"

    def __call__(self, item: Item, order: list[str]) -> Decision:
        text, to_key = render(item, order, lettered=True)
        payload = {"model": self.spec.alias, "temperature": 0, "max_tokens": 4, "logprobs": True,
                   "top_logprobs": 20, self.spec.reasoning_param: self.spec.reasoning_off,
                   "messages": [{"role": "system", "content": "Reply with the letter of one option only."},
                                {"role": "user", "content": text}]}
        t = time.time()
        r = _post(self.url, payload)
        ms = (time.time() - t) * 1000
        content = r["choices"][0].get("logprobs", {}).get("content") or []
        logp: dict[str, float] = {}
        for tok in content[:1]:
            for alt in tok.get("top_logprobs", []):
                letter = alt["token"].strip().rstrip(")").strip()
                if letter in to_key and letter not in logp:
                    logp[letter] = alt["logprob"]
        if not logp:
            return Decision({k: 0.0 for k in order}, None, ms, {"error": "no option letter in top_logprobs",
                                                                "reply": r["choices"][0]["message"].get("content")})
        m = max(logp.values())
        z = sum(math.exp(v - m) for v in logp.values())
        probs = {to_key[letter]: math.exp(v - m) / z for letter, v in logp.items()}
        probs = {k: probs.get(k, 0.0) for k in order}
        return Decision(probs, max(probs, key=probs.get), ms, {"envelope_model": r.get("model")})


class Pplx:
    name = "pplx"

    def __init__(self, base: str = "http://127.0.0.1:7500", temperature: float = 1.0) -> None:
        self.url = base.rstrip("/") + "/v1/decisions"
        self.temperature = temperature

    def __call__(self, item: Item, order: list[str]) -> Decision:
        opaque = {f"c{i + 1}": k for i, k in enumerate(order)}
        state = item.context.strip() + "\n\nQuestion: " + item.question.strip()
        payload = {"state": state, "temperature": self.temperature,
                   "questions": {"q": {"type": "choice", "question": item.prompt.strip(),
                                       "criteria": {c: item.option_text(k) for c, k in opaque.items()}}}}
        t = time.time()
        r = _post(self.url, payload)
        ms = (time.time() - t) * 1000
        p = r["answers"]["q"]["probabilities"]
        probs = {opaque[c]: float(v) for c, v in p.items()}
        probs = {k: probs.get(k, 0.0) for k in order}
        return Decision(probs, max(probs, key=probs.get), ms, {"temperature": self.temperature})


class D3:
    name = "d3"

    def __init__(self, base: str = "http://127.0.0.1:5107") -> None:
        self.url = base.rstrip("/") + "/v1/decide"

    def __call__(self, item: Item, order: list[str]) -> Decision:
        labels = {f"{LETTERS[i]}) {item.option_text(k)}": k for i, k in enumerate(order)}
        state = item.context.strip() + "\n\nQuestion: " + item.question.strip()
        payload = {"input": state, "questions": [{"id": "q", "type": "choice", "question": item.prompt.strip(),
                                                  "options": list(labels)}]}
        t = time.time()
        r = _post(self.url, payload)
        ms = (time.time() - t) * 1000
        p = r["answers"]["q"]["probs"]
        probs = {labels[o]: float(v) for o, v in p.items() if o in labels}
        probs = {k: probs.get(k, 0.0) for k in order}
        return Decision(probs, max(probs, key=probs.get), ms, {"model_ms": r.get("model_ms"),
                                                              "revision": r.get("revision")})


def unload_d3(base: str = "http://127.0.0.1:5107") -> None:
    try:
        _post(base.rstrip("/") + "/v1/unload", {}, retries=0, timeout=60)
    except Exception:  # noqa: BLE001 - best effort
        pass


__all__ = ["D3", "Decision", "Pplx", "QwenProb", "QwenReason", "render", "unload_d3"]
