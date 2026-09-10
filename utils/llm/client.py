#!/usr/bin/env python3
"""The only place in ``utils/llm`` that opens a socket.

Adapters translate; this module transports. Keeping the split means timeout,
error mapping and the never-raise contract are decided once instead of ten
times, which is roughly how many hand-rolled ``requests.post(.../chat/
completions)`` call sites this replaces.

Three policies live here:

**Connect and read timeouts are separate numbers.** Local generation
legitimately runs for minutes; a local server that is not running should fail in
about two seconds. One value cannot be both, and the codebase has already lost a
run to a clock that cut off the reasoning a raised budget was meant to allow.

**Discovery never raises.** :func:`discover_models` returns a
:class:`~utils.llm.types.DiscoveryResult` carrying either models or a
human-readable reason. An unreachable GPU box is a normal operating state; the
settings modal renders an empty state, not an error banner.

**A passing probe means a real answer came back.** :func:`probe` sends an actual
completion and checks for non-empty content, because a port being open is not
readiness — the 2026-09-05 run got ten responses with no ``choices`` key at all
while vLLM was still loading weights.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any
from urllib.parse import urlparse

import requests

from utils.llm.adapters import adapter_for
from utils.llm.config import LLMSettings
from utils.llm.types import (
    ChatResult,
    DiscoveryResult,
    LLMUnavailable,
    Message,
    ModelInfo,
    ProbeResult,
)

logger = logging.getLogger("ariadne.llm.client")

#: Discovery runs on a UI event, so it may not sit on a long timeout. This is the
#: read budget; the connect budget comes from ``LLMSettings.connect_timeout_s``.
DISCOVERY_READ_TIMEOUT_S = 8.0

#: The probe sends one tiny completion. Generous enough for a cold local model to
#: load, short enough that a wrong port does not hang the modal.
PROBE_READ_TIMEOUT_S = 45.0


def _host(settings: LLMSettings) -> str:
    parsed = urlparse(settings.base_url)
    return parsed.netloc or settings.base_url


#: Process-wide token accounting. Every successful :func:`chat` adds to it, so
#: the cost of a run is a fact read off the transport rather than an estimate
#: reconstructed from question counts. Q38 asks for exactly this: C-012 claims
#: templates beat a model writing the queries "in correctness *and in cost*",
#: and until now only the correctness half had a number behind it.
#:
#: Every caller in this repository dispatches through a ThreadPoolExecutor in
#: one process, so a lock is sufficient; a process pool would need its workers
#: to report their own totals.
_METER_LOCK = threading.Lock()
_METER: dict[str, int] = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0}


def token_meter() -> dict[str, int]:
    """A snapshot of what this process has spent so far."""
    with _METER_LOCK:
        return dict(_METER)


def reset_token_meter() -> dict[str, int]:
    """Zero the meter and return what it held, so a run can be bracketed."""
    global _METER
    with _METER_LOCK:
        previous = dict(_METER)
        _METER = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0}
        return previous


def _record(result: ChatResult) -> None:
    """Add one reply's usage to the meter. A server that omits usage adds zero.

    Zero-filled usage is normal (see :class:`~utils.llm.types.Usage`), so a
    total of 0 across a run means "the server never told us", not "no tokens
    were spent" -- which is why ``calls`` is counted separately and reported
    beside the totals.
    """
    with _METER_LOCK:
        _METER["calls"] += 1
        _METER["prompt_tokens"] += int(getattr(result.usage, "prompt_tokens", 0) or 0)
        _METER["completion_tokens"] += int(
            getattr(result.usage, "completion_tokens", 0) or 0
        )


def chat(
    settings: LLMSettings,
    messages: list[Message] | list[dict[str, str]],
    *,
    max_tokens: int | None = None,
    temperature: float = 0.0,
    sampling: dict[str, Any] | None = None,
    timeout_s: float | None = None,
) -> ChatResult:
    """Run one completion against ``settings``' provider.

    Raises :class:`LLMUnavailable` on any transport, HTTP or decode failure, so
    every caller keeps the fall-back-to-deterministic contract the codebase was
    already built around. Note that an *empty answer is not an error here* — it
    is returned as a :class:`ChatResult` with empty content and a finish reason,
    because the caller needs to tell "the model was cut off at its budget" apart
    from "the model could not be reached", and collapsing both into one exception
    is what made truncation look like an outage for so long.
    """
    normalized = (
        Message.from_dicts(messages)  # type: ignore[arg-type]
        if messages and isinstance(messages[0], dict)
        else list(messages)  # type: ignore[arg-type]
    )
    adapter = adapter_for(settings.provider)
    url, headers, payload = adapter.chat_request(
        settings,
        normalized,
        max_tokens=max_tokens if max_tokens is not None else settings.max_tokens,
        temperature=temperature,
        sampling=sampling,
    )

    read_timeout = timeout_s if timeout_s is not None else settings.timeout_s
    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=(settings.connect_timeout_s, read_timeout),
        )
    except requests.RequestException as exc:
        raise LLMUnavailable(f"{adapter.name}: could not reach {_host(settings)}: {exc}") from exc

    if response.status_code >= 400:
        # The body carries the actionable part — a wrong model name, a missing
        # key, a budget over the window. Truncated rather than dropped.
        detail = (response.text or "").strip()[:500]
        raise LLMUnavailable(
            f"{adapter.name}: HTTP {response.status_code} from {_host(settings)}: {detail}"
        )

    try:
        body = response.json()
    except ValueError as exc:
        raise LLMUnavailable(f"{adapter.name}: response was not JSON: {exc}") from exc
    if not isinstance(body, dict):
        raise LLMUnavailable(f"{adapter.name}: unexpected response shape: {type(body).__name__}")

    result = adapter.parse_chat(body)
    if result.truncated:
        logger.warning(
            "%s stopped at its output budget (prompt=%d completion=%d). The reply is "
            "truncated, not complete.",
            settings.model,
            result.usage.prompt_tokens,
            result.usage.completion_tokens,
        )
    _record(result)
    return result


def discover_models(settings: LLMSettings) -> DiscoveryResult:
    """Ask the server what it serves. **Never raises.**

    The three empty states are kept distinct — unreachable, reachable-but-empty,
    and reachable-with-no-listing-endpoint — because they need three different
    fixes and telling someone to check their port when the server answered fine
    wastes their afternoon.
    """
    adapter = adapter_for(settings.provider)
    try:
        request = adapter.models_request(settings)
    except Exception as exc:  # noqa: BLE001 — a UI path must not raise
        return DiscoveryResult.no_listing(str(exc))
    if request is None:
        return DiscoveryResult.no_listing()

    url, headers = request
    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=(settings.connect_timeout_s, DISCOVERY_READ_TIMEOUT_S),
        )
    except requests.RequestException as exc:
        return DiscoveryResult.unreachable(_host(settings), str(exc))

    if response.status_code == 404:
        # A gateway that proxies completions but not listing. Not a fault.
        return DiscoveryResult.no_listing(f"{url} returned 404")
    if response.status_code in (401, 403):
        return DiscoveryResult(
            ok=False,
            state="unreachable",
            reason=f"{_host(settings)} rejected the credentials (HTTP {response.status_code}).",
        )
    if response.status_code >= 400:
        return DiscoveryResult.unreachable(
            _host(settings), f"HTTP {response.status_code}: {(response.text or '')[:200]}"
        )

    try:
        body = response.json()
    except ValueError as exc:
        return DiscoveryResult.no_listing(f"listing was not JSON: {exc}")
    if not isinstance(body, dict):
        return DiscoveryResult.no_listing("listing had an unexpected shape")

    try:
        models = adapter.parse_models(body)
    except Exception as exc:  # noqa: BLE001 — a UI path must not raise
        logger.warning("Could not parse the model listing from %s: %s", url, exc)
        return DiscoveryResult.no_listing(f"could not parse the listing: {exc}")

    return DiscoveryResult.found(sort_models(models))


def sort_models(models: list[ModelInfo]) -> list[ModelInfo]:
    """Order a listing for a dropdown: chat-shaped first, then by id.

    Embedding, audio, image and moderation models are pushed to the bottom rather
    than removed — a filter that hides something the operator knows is there
    reads as a bug, but one of them landing at index 0 would silently become the
    default.
    """
    def rank(model: ModelInfo) -> tuple[int, str]:
        lowered = model.id.lower()
        non_chat = any(
            token in lowered
            for token in ("embed", "whisper", "tts", "dall-e", "moderation", "rerank", "clip")
        )
        return (1 if non_chat else 0, lowered)

    return sorted(models, key=rank)


def probe(settings: LLMSettings, *, timeout_s: float | None = None) -> ProbeResult:
    """Prove the endpoint answers. **Never raises.**

    Deliberately not a TCP check and not a ``/models`` call: both of those pass
    against a server that cannot complete anything. This sends a real (tiny)
    completion and requires non-empty content back.
    """
    started = time.monotonic()
    try:
        result = chat(
            settings,
            [Message.user("Reply with the single word: ok")],
            # Small, but not so small a reasoning model spends the whole budget
            # thinking and returns empty — the exact trap documented in
            # utils/llm_sampling.py.
            max_tokens=max(64, min(settings.max_tokens, 256)),
            temperature=0.0,
            timeout_s=timeout_s if timeout_s is not None else PROBE_READ_TIMEOUT_S,
        )
    except LLMUnavailable as exc:
        return ProbeResult(ok=False, reason=str(exc))
    except Exception as exc:  # noqa: BLE001 — a UI path must not raise
        return ProbeResult(ok=False, reason=f"unexpected error: {exc}")

    latency_ms = int((time.monotonic() - started) * 1000)
    if not result.content.strip():
        # The vLLM-loading-weights case, and the reasoning-model-spent-it-all
        # case. Both look like success at the HTTP layer.
        detail = (
            "the server answered but returned no content"
            + (f" (finish_reason={result.finish_reason})" if result.finish_reason else "")
        )
        return ProbeResult(
            ok=False,
            latency_ms=latency_ms,
            model=result.model,
            reason=detail,
            usage=result.usage,
        )

    return ProbeResult(
        ok=True,
        latency_ms=latency_ms,
        model=result.model or settings.model,
        usage=result.usage,
    )
