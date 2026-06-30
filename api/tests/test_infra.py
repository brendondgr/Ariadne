"""Contract tests for the admin action SSE stream (/api/admin).

The underlying docker/graph functions are stubbed so no real Docker daemon,
network, or graph backend is touched. The tests assert the event shape (status →
log* → done) and that dispatch/validation errors surface as a failed done event
rather than an exception.
"""

from __future__ import annotations

import json
import logging
from typing import Iterator

from fastapi.testclient import TestClient

import api.main as main
from api.main import app
from api.services import infra

client = TestClient(app)


def _collect(gen: Iterator[str]) -> list[tuple[str, dict]]:
    events = []
    for frame in gen:
        head, _, body = frame.partition("\n")
        events.append((head.removeprefix("event: "), json.loads(body.removeprefix("data: ").strip())))
    return events


def test_docker_status_streams_status_and_done(monkeypatch) -> None:
    monkeypatch.setattr(infra, "docker_status", lambda: {"neo4j": "Running", "gremlin": "Not running"})
    events = _collect(infra.stream_admin_action("docker-status"))
    types = [e for e, _ in events]
    assert types[0] == "status"
    assert types[-1] == "done"
    done = events[-1][1]
    assert done["ok"] is True
    assert done["services"] == {"neo4j": "Running", "gremlin": "Not running"}


def test_action_forwards_module_logs_as_log_events(monkeypatch) -> None:
    def fake_start(**_kw):
        logging.getLogger("utils.infrastructure.docker_manager").info("Pulling images")
        logging.getLogger("utils.infrastructure.docker_manager").info("Containers up")

    monkeypatch.setattr(infra, "docker_start", fake_start)
    events = _collect(infra.stream_admin_action("docker-start"))
    logs = [d["line"] for e, d in events if e == "log"]
    assert any("Pulling images" in line for line in logs)
    assert any("Containers up" in line for line in logs)
    assert events[-1][1]["ok"] is True


def test_graph_load_requires_dataset_and_graph() -> None:
    events = _collect(infra.stream_admin_action("graph-load"))
    done = events[-1][1]
    assert done["ok"] is False
    assert "requires" in done["message"]


def test_graph_load_dispatches_with_args(monkeypatch) -> None:
    calls = {}
    monkeypatch.setattr(infra, "run_graph_command", lambda *, dataset, graph: calls.update(dataset=dataset, graph=graph))
    events = _collect(infra.stream_admin_action("graph-load", dataset="attack", graph="neo4j"))
    assert calls == {"dataset": "attack", "graph": "neo4j"}
    assert events[-1][1]["ok"] is True


def test_unknown_action_fails_cleanly() -> None:
    events = _collect(infra.stream_admin_action("not-a-real-action"))
    done = events[-1][1]
    assert done["ok"] is False
    assert "unknown admin action" in done["message"]


def test_root_logger_handler_is_removed_after_action(monkeypatch) -> None:
    monkeypatch.setattr(infra, "docker_status", lambda: {})
    before = len(logging.getLogger().handlers)
    _collect(infra.stream_admin_action("docker-status"))
    assert len(logging.getLogger().handlers) == before  # no handler leak


def test_admin_endpoint_streams_event_stream(monkeypatch) -> None:
    def _fake(*_a, **_k):
        yield "event: done\ndata: {\"ok\": true, \"message\": \"x\"}\n\n"

    monkeypatch.setattr(main, "stream_admin_action", _fake)
    resp = client.post("/api/admin", json={"action": "docker-status"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert "event: done" in resp.text


def test_admin_endpoint_rejects_bad_action() -> None:
    assert client.post("/api/admin", json={"action": "rm-rf"}).status_code == 422


# ---------------------------------------------------------------------------
# graph-stop
# ---------------------------------------------------------------------------


def test_graph_stop_calls_docker_stop_service(monkeypatch) -> None:
    calls = {}
    monkeypatch.setattr(infra, "docker_stop_service", lambda service: calls.update(service=service))
    events = _collect(infra.stream_admin_action("graph-stop", graph="neo4j"))
    assert calls == {"service": "neo4j"}
    done = events[-1][1]
    assert done["ok"] is True
    assert done["service"] == "neo4j"


def test_graph_stop_all_target(monkeypatch) -> None:
    calls = {}
    monkeypatch.setattr(infra, "docker_stop_service", lambda service: calls.update(service=service))
    events = _collect(infra.stream_admin_action("graph-stop", graph="all"))
    assert calls == {"service": "all"}
    assert events[-1][1]["ok"] is True


def test_graph_stop_requires_graph_param() -> None:
    events = _collect(infra.stream_admin_action("graph-stop"))
    done = events[-1][1]
    assert done["ok"] is False
    assert "requires" in done["message"]


# ---------------------------------------------------------------------------
# yolo-all
# ---------------------------------------------------------------------------


def test_yolo_all_streams_done_ok(monkeypatch) -> None:
    from utils.yolo import StepResult

    fake_results = [
        StepResult("1. Download Datasets", status="ok"),
        StepResult("2. Build Artifacts", status="skipped"),
        StepResult("3. Configure Credentials", status="skipped"),
        StepResult("4. Start Docker Infrastructure", status="ok"),
        StepResult("5. Load ATT&CK → Neo4j", status="ok"),
        StepResult("6. Load CAPEC → Gremlin", status="ok"),
        StepResult("7. Verify Graphs", status="ok"),
    ]

    class FakeYoloRunner:
        def __init__(self):
            pass

        def run(self):
            return fake_results

    monkeypatch.setattr(infra, "YoloRunner", FakeYoloRunner, raising=False)

    # Patch inside the module so the lazy import picks it up
    import utils.yolo as yolo_mod
    monkeypatch.setattr(yolo_mod, "YoloRunner", FakeYoloRunner)

    events = _collect(infra.stream_admin_action("yolo-all"))
    types = [e for e, _ in events]
    assert types[0] == "status"
    assert types[-1] == "done"
    done = events[-1][1]
    assert done["ok"] is True
    assert done["steps"] == 7
    assert done["failed"] == []
    assert done["needs_input"] == []


def test_yolo_all_reports_failed_steps(monkeypatch) -> None:
    from utils.yolo import StepResult

    fake_results = [
        StepResult("1. Download Datasets", status="failed", detail="network error"),
        StepResult("2. Build Artifacts", status="skipped", detail="Earlier step failed"),
        StepResult("3. Configure Credentials", status="skipped", detail="Earlier step failed"),
        StepResult("4. Start Docker Infrastructure", status="skipped", detail="Earlier step failed"),
        StepResult("5. Load ATT&CK → Neo4j", status="skipped", detail="Earlier step failed"),
        StepResult("6. Load CAPEC → Gremlin", status="skipped", detail="Earlier step failed"),
        StepResult("7. Verify Graphs", status="skipped", detail="Earlier step failed"),
    ]

    class FakeYoloRunner:
        def __init__(self):
            pass

        def run(self):
            return fake_results

    import utils.yolo as yolo_mod
    monkeypatch.setattr(yolo_mod, "YoloRunner", FakeYoloRunner)

    events = _collect(infra.stream_admin_action("yolo-all"))
    done = events[-1][1]
    assert done["ok"] is True  # stream completed; step failures are in the payload
    assert "1. Download Datasets" in done["failed"]
    assert done["needs_input"] == []
