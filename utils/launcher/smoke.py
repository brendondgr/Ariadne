#!/usr/bin/env python3
"""The startup smoke query: prove the pipeline, not just the processes.

Streams one question through ``POST /api/query`` — the same SSE contract the
UI consumes — and asserts the expected frames arrive in order. Plan mode by
default (probe → LangGraph planner → answer, no graph query load, no LLM);
``--smoke full`` runs one complete federated query.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable, Iterator

SMOKE_QUESTION = (
    "Which CAPEC patterns related to credential theft map to ATT&CK techniques, "
    "and what mitigations appear for those techniques?"
)

# Frames every successful stream must contain, in this relative order.
_EXPECTED_ORDER = ["status", "plan", "answer", "done"]


@dataclass(frozen=True)
class SmokeResult:
    ok: bool
    detail: str
    events: tuple[str, ...] = ()


def _sse_events(lines: Iterator[str]) -> Iterator[tuple[str, dict]]:
    """Parse ``event:``/``data:`` SSE frames from an iterator of lines."""
    event, data = None, ""
    for raw in lines:
        line = raw.rstrip("\n")
        if line.startswith("event:"):
            event = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            data = line.split(":", 1)[1].strip()
        elif line == "" and event is not None:
            try:
                payload = json.loads(data) if data else {}
            except ValueError:
                payload = {}
            yield event, payload
            event, data = None, ""


def _stream_query(api_port: int, mode: str, timeout_s: float) -> Iterator[str]:
    """Default transport: httpx streaming against the local API."""
    import httpx

    with httpx.stream(
        "POST",
        f"http://127.0.0.1:{api_port}/api/query",
        json={"question": SMOKE_QUESTION, "mode": mode, "use_llm": False},
        timeout=timeout_s,
    ) as response:
        response.raise_for_status()
        yield from response.iter_lines()


def run_smoke(
    api_port: int,
    *,
    mode: str = "plan",
    timeout_s: float = 60.0,
    stream_fn: Callable[[int, str, float], Iterator[str]] = _stream_query,
) -> SmokeResult:
    """Stream one smoke question; verify the event contract end-to-end.

    Never raises: any transport or contract failure comes back as a
    ``SmokeResult`` naming what broke.
    """
    try:
        events: list[tuple[str, dict]] = list(_sse_events(stream_fn(api_port, mode, timeout_s)))
    except Exception as exc:  # noqa: BLE001 - the failure IS the result
        return SmokeResult(False, f"query stream failed: {type(exc).__name__}: {exc}")

    names = [e for e, _ in events]
    if not events:
        return SmokeResult(False, "no SSE frames arrived", tuple(names))
    if "error" in names:
        message = next((p.get("message", "") for e, p in events if e == "error"), "")
        return SmokeResult(False, f"pipeline emitted an error event: {message}", tuple(names))

    cursor = 0
    for name in names:
        if cursor < len(_EXPECTED_ORDER) and name == _EXPECTED_ORDER[cursor]:
            cursor += 1
    if cursor < len(_EXPECTED_ORDER):
        missing = _EXPECTED_ORDER[cursor:]
        return SmokeResult(
            False, f"stream ended without {' → '.join(missing)}", tuple(names)
        )

    done = next(p for e, p in events if e == "done")
    status = done.get("status", "?")
    detail = f"{mode} query answered ({status})"
    if mode == "query":
        exit_code = done.get("exit_code")
        if status not in {"answered", "partial"}:
            return SmokeResult(False, f"unexpected terminal status {status!r}", tuple(names))
        detail = f"full query completed: {status} (exit {exit_code})"
    return SmokeResult(True, detail, tuple(names))
