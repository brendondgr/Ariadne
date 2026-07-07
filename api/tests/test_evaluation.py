"""Contract tests for /api/evaluation (read) and /api/eval-run (SSE).

The read endpoint serves the committed report JSON and never raises (missing
files degrade to ``available: false``). The run endpoint streams
``status → (log)* → done`` with the runner stubbed so no live stack is needed.
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from api.main import app
from api.services import evaluation as eval_service

client = TestClient(app)


def _parse_sse(text: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    event = None
    for line in text.splitlines():
        if line.startswith("event: "):
            event = line[len("event: "):]
        elif line.startswith("data: ") and event is not None:
            events.append((event, json.loads(line[len("data: "):])))
            event = None
    return events


def test_get_evaluation_shape() -> None:
    resp = client.get("/api/evaluation")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"component_available", "e2e_available", "component", "e2e"}
    assert isinstance(body["component_available"], bool)
    assert isinstance(body["e2e_available"], bool)
    # When a report is available its block is the full report file, whose own
    # score block is keyed "e2e" and carries the live flag.
    if body["e2e_available"]:
        assert body["e2e"]["e2e"]["live"] in (True, False)


def test_get_evaluation_degrades_when_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        eval_service,
        "read_evaluation_report",
        lambda: {
            "component_available": False,
            "e2e_available": False,
            "component": None,
            "e2e": None,
        },
    )
    # Patch the name the route imported.
    import api.main as main

    monkeypatch.setattr(main, "read_evaluation_report", eval_service.read_evaluation_report)
    resp = client.get("/api/evaluation")
    assert resp.status_code == 200
    body = resp.json()
    assert body["component_available"] is False
    assert body["e2e"] is None


def test_eval_run_streams_status_then_done(monkeypatch) -> None:
    # Stub the heavy runner so the SSE contract is tested without a live stack.
    import utils.evaluation.run_e2e_eval as runner

    monkeypatch.setattr(runner, "main", lambda argv=None: 0)
    monkeypatch.setattr(
        eval_service,
        "read_evaluation_report",
        lambda: {"e2e": {"live": False}},
    )

    resp = client.post("/api/eval-run", json={"live": False, "judge": False})
    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    kinds = [e for e, _ in events]
    assert kinds[0] == "status"
    assert kinds[-1] == "done"
    assert events[-1][1]["ok"] is True
