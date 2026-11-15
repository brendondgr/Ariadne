"""Client for the OpenAI-compatible relay on ``:9090``.

Every completion records the model that *actually served it* (the response
envelope's ``model`` field), because the relay hot-swaps and an alias is not a
model. Budgets are never below 2,048 tokens: the local models reason before
answering and a small budget truncates to an empty reply that looks like a
model failure.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class Completion:
    text: str
    served_model: str
    alias: str
    finish_reason: str | None
    usage: dict
    latency_s: float
    #: The server's reasoning channel, kept apart from ``text`` (which stays
    #: ``content`` only, as every kill-test run read it). Added 2026-11-15: under
    #: MiniCPM 4.7 a short reply that never closes its think block arrives here.
    reasoning: str = ""


class RelayClient:
    def __init__(self, base_url: str = "http://localhost:9090/v1", *, max_tokens: int = 4096,
                 timeout_s: float = 600.0, retries: int = 3) -> None:
        self.base_url = base_url.rstrip("/")
        self.max_tokens = max(2048, int(max_tokens))
        self.timeout_s = timeout_s
        self.retries = retries

    def complete(self, alias: str, messages: list[dict], *, temperature: float = 0.0,
                 max_tokens: int | None = None, extra: dict | None = None) -> Completion:
        body = {
            "model": alias,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max(2048, int(max_tokens or self.max_tokens)),
            **(extra or {}),
        }
        data = json.dumps(body).encode()
        last: Exception | None = None
        for attempt in range(self.retries + 1):
            t0 = time.time()
            req = urllib.request.Request(self.base_url + "/chat/completions", data=data,
                                         headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:  # noqa: S310 - local
                    out = json.loads(resp.read().decode())
                choice = (out.get("choices") or [{}])[0]
                msg = choice.get("message") or {}
                return Completion(
                    text=msg.get("content") or "",
                    served_model=str(out.get("model") or "unknown"),
                    alias=alias,
                    finish_reason=choice.get("finish_reason"),
                    usage=out.get("usage") or {},
                    latency_s=round(time.time() - t0, 3),
                    reasoning=msg.get("reasoning") or msg.get("reasoning_content") or "",
                )
            except urllib.error.HTTPError as exc:
                body_txt = exc.read().decode(errors="replace")[:300]
                if exc.code in (400, 404, 422):
                    raise ValueError(f"relay rejected request ({exc.code}): {body_txt}") from exc
                last = exc
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                last = exc
            time.sleep(min(60.0, 3.0 * 2 ** attempt))
        raise ConnectionError(f"relay unreachable after {self.retries + 1} attempts: {last}")

    def healthy_aliases(self) -> list[str]:
        """Aliases the relay reports healthy right now (excluding the ``auto`` router)."""
        with urllib.request.urlopen(self.base_url + "/models", timeout=10) as resp:  # noqa: S310
            data = json.loads(resp.read().decode())["data"]
        return [m["id"] for m in data if (m.get("relay") or {}).get("health") == "healthy"]
