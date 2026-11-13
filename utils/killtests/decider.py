"""Client for the decision model on ``:7500`` (``pplx-decider`` protocol v3).

The protocol, as probed on 2026-11-13 (it is not documented elsewhere):

    POST /v1/decisions
    {"state": <text>, "temperature": <float|null>,
     "questions": {"<qid>": {"type": "choice", "question": <text>,
                             "criteria": {"<option>": <description>, ...}}}}
    -> {"answers": {"<qid>": {"type": "choice", "probabilities": {...},
                              "choice": <option>, "confidence": <float>}}}

Other types are ``score`` (``criteria`` a list of level descriptions) and
``noul``. The server's default temperature is 1.55; every call here passes an
explicit temperature (1.0 unless overridden) so probabilities are comparable
across runs and recorded with the result.

Option names are short opaque keys (``c1``, ``c2``, ...): a key that looks like
a real answer leaks meaning into the readout. The description carries the
content.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

NONE_KEY = "none"


@dataclass(frozen=True)
class Choice:
    probabilities: dict[str, float]
    choice: str
    temperature: float


class DeciderClient:
    def __init__(self, base_url: str = "http://localhost:7500", *, temperature: float = 1.0,
                 timeout_s: float = 120.0, retries: int = 4) -> None:
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.timeout_s = timeout_s
        self.retries = retries

    def _post(self, path: str, payload: dict) -> dict:
        data = json.dumps(payload).encode()
        last: Exception | None = None
        for attempt in range(self.retries + 1):
            req = urllib.request.Request(self.base_url + path, data=data,
                                         headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:  # noqa: S310 - local
                    return json.loads(resp.read().decode())
            except urllib.error.HTTPError as exc:
                body = exc.read().decode(errors="replace")[:300]
                if 400 <= exc.code < 500:
                    raise ValueError(f"decider rejected request ({exc.code}): {body}") from exc
                last = exc
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                last = exc
            time.sleep(min(30.0, 2.0 ** attempt))
        raise ConnectionError(f"decider unreachable after {self.retries + 1} attempts: {last}")

    def choose(self, state: str, question: str, options: dict[str, str], *,
               temperature: float | None = None) -> Choice:
        """Probabilities over ``options`` (key -> description)."""
        if len(options) < 2:
            raise ValueError("a choice needs at least two options")
        t = self.temperature if temperature is None else temperature
        out = self._post("/v1/decisions", {
            "state": state,
            "temperature": t,
            "questions": {"q": {"type": "choice", "question": question, "criteria": options}},
        })
        ans = out["answers"]["q"]
        probs = {k: float(v) for k, v in ans["probabilities"].items()}
        return Choice(probabilities=probs, choice=ans.get("choice") or max(probs, key=probs.get), temperature=t)

    def health(self) -> dict:
        with urllib.request.urlopen(self.base_url + "/health", timeout=10) as resp:  # noqa: S310
            return json.loads(resp.read().decode())


def keyed(descriptions: list[str], *, none_option: str | None = None) -> tuple[dict[str, str], list[str]]:
    """Opaque keys ``c1..cN`` for ``descriptions`` (+ an optional none option).

    Returns ``(options, keys)`` where ``keys[i]`` is the key of ``descriptions[i]``.
    """
    keys = [f"c{i + 1}" for i in range(len(descriptions))]
    options = dict(zip(keys, descriptions))
    if none_option is not None:
        options[NONE_KEY] = none_option
    return options, keys
