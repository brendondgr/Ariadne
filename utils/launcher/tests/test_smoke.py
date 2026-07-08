"""The startup smoke check against stubbed SSE streams. Hermetic."""

from __future__ import annotations

import json
from typing import Iterator

from utils.launcher.smoke import SmokeResult, run_smoke


def _frames(*events: tuple[str, dict]) -> list[str]:
    lines: list[str] = []
    for name, payload in events:
        lines.append(f"event: {name}")
        lines.append(f"data: {json.dumps(payload)}")
        lines.append("")
    return lines


def _stub(lines: list[str]):
    def stream(api_port: int, mode: str, timeout_s: float) -> Iterator[str]:
        return iter(lines)

    return stream


GOOD_PLAN = _frames(
    ("status", {"phase": "probing"}), ("probe", {}), ("status", {"phase": "planning"}),
    ("plan", {}), ("status", {"phase": "answering"}),
    ("answer", {"status": "answered"}),
    ("done", {"status": "answered", "exit_code": 0, "timings": {}}),
)


def test_good_plan_stream_passes():
    result = run_smoke(1, mode="plan", stream_fn=_stub(GOOD_PLAN))
    assert result.ok, result.detail
    assert "answered" in result.detail


def test_error_event_fails_with_message():
    lines = _frames(("status", {"phase": "probing"}),
                    ("error", {"message": "no graph backends"}))
    result = run_smoke(1, stream_fn=_stub(lines))
    assert not result.ok
    assert "no graph backends" in result.detail


def test_truncated_stream_names_missing_frames():
    lines = _frames(("status", {"phase": "probing"}), ("probe", {}), ("plan", {}))
    result = run_smoke(1, stream_fn=_stub(lines))
    assert not result.ok
    assert "answer" in result.detail and "done" in result.detail


def test_transport_failure_is_a_result_not_an_exception():
    def broken(api_port: int, mode: str, timeout_s: float) -> Iterator[str]:
        raise ConnectionError("refused")

    result = run_smoke(1, stream_fn=broken)
    assert isinstance(result, SmokeResult) and not result.ok
    assert "refused" in result.detail


def test_full_mode_accepts_partial_but_rejects_no_sources():
    partial = _frames(
        ("status", {}), ("plan", {}), ("answer", {}),
        ("done", {"status": "partial", "exit_code": 1, "timings": {}}))
    assert run_smoke(1, mode="query", stream_fn=_stub(partial)).ok
    no_sources = _frames(
        ("status", {}), ("plan", {}), ("answer", {}),
        ("done", {"status": "no_sources", "exit_code": 2, "timings": {}}))
    result = run_smoke(1, mode="query", stream_fn=_stub(no_sources))
    assert not result.ok and "no_sources" in result.detail
