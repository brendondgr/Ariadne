"""Contract tests for /api/health and the live-source health service.

The key invariant: the endpoint must return a structured per-backend verdict and
never raise, even when both graph backends are unreachable (the underlying
``run_graph_health`` raises ``ConnectionError`` in that case — the service layer
must absorb it).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

import api.main as main
from api.main import app
from api.services import health
from api.services.health import SourceHealth

client = TestClient(app)


def test_endpoint_from_uri_parses_bolt_ws_and_fallback() -> None:
    assert health._endpoint_from_uri("bolt://localhost:5456", ("x", 1)) == ("localhost", 5456)
    assert health._endpoint_from_uri("ws://host:6455/gremlin", ("x", 1)) == ("host", 6455)
    assert health._endpoint_from_uri("bolt://only-host", ("x", 1)) == ("only-host", 7687)
    # Unrecognised scheme falls back to the provided default.
    assert health._endpoint_from_uri("http://nope", ("fb", 9)) == ("fb", 9)


def test_live_sources_never_raises_when_backends_down() -> None:
    # Real probe against (almost certainly) closed ports: must return verdicts,
    # not raise, and must cover both backends.
    sources = health.live_sources()
    backends = {s.backend for s in sources}
    assert backends == {"neo4j", "gremlin"}
    for s in sources:
        assert s.status in {"live", "down", "starting"}
        if s.status == "down":
            assert s.reason  # a down source explains why


def test_reachable_but_empty_graph_reads_as_down(monkeypatch) -> None:
    # The core fix: a backend whose port is open but whose graph is NOT loaded
    # must read as down (not a false "live"), carrying the reason and node count.
    monkeypatch.setattr(health, "_tcp_reachable", lambda host, port, timeout=2.0: True)
    monkeypatch.setattr(health, "docker_state", lambda: (True, {}, None))
    monkeypatch.setattr(
        health,
        "_content_verdicts",
        lambda: {
            "neo4j": health._ContentVerdict(loaded=True, nodes=2611, reason=None),
            "gremlin": health._ContentVerdict(
                loaded=False, nodes=0, reason="backend up but graph empty (nodes=0 < 1)"
            ),
        },
    )

    sources = {s.backend: s for s in health.live_sources()}
    assert sources["neo4j"].status == "live" and sources["neo4j"].nodes == 2611
    assert sources["gremlin"].status == "down"
    assert sources["gremlin"].nodes == 0
    assert "empty" in (sources["gremlin"].reason or "")


def test_content_probe_failure_degrades_to_tcp(monkeypatch) -> None:
    # If the content probe can't run, a reachable port still reports live so the
    # endpoint never regresses to a hard failure.
    monkeypatch.setattr(health, "_tcp_reachable", lambda host, port, timeout=2.0: True)
    monkeypatch.setattr(health, "docker_state", lambda: (True, {}, None))
    monkeypatch.setattr(health, "_content_verdicts", lambda: None)

    for s in health.live_sources():
        assert s.status == "live"


def test_health_endpoint_shape_is_well_formed(monkeypatch) -> None:
    monkeypatch.setattr(
        main,
        "live_sources",
        lambda: [
            SourceHealth(backend="neo4j", status="live", uri="bolt://localhost:5456"),
            SourceHealth(
                backend="gremlin",
                status="down",
                uri="ws://localhost:6455/gremlin",
                reason="no TCP connection to 127.0.0.1:6455",
            ),
        ],
    )
    monkeypatch.setattr(
        main, "docker_state", lambda: (True, {"neo4j": "Running (ariadne-neo4j)", "gremlin": "Not running"}, None)
    )

    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()

    assert {s["backend"] for s in body["sources"]} == {"neo4j", "gremlin"}
    neo = next(s for s in body["sources"] if s["backend"] == "neo4j")
    grem = next(s for s in body["sources"] if s["backend"] == "gremlin")
    assert neo["status"] == "live"
    assert grem["status"] == "down" and grem["reason"]
    assert body["docker"]["available"] is True
    assert body["docker"]["services"]["neo4j"].startswith("Running")
    assert "checked_at" in body and body["checked_at"]


def test_health_endpoint_handles_docker_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(
        main,
        "live_sources",
        lambda: [
            SourceHealth(backend="neo4j", status="down", uri="bolt://localhost:5456", reason="x"),
            SourceHealth(backend="gremlin", status="down", uri="ws://localhost:6455/gremlin", reason="y"),
        ],
    )
    monkeypatch.setattr(main, "docker_state", lambda: (False, {}, "docker executable not found"))

    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["docker"]["available"] is False
    assert body["docker"]["reason"]
    assert all(s["status"] == "down" for s in body["sources"])


def test_health_endpoint_real_call_does_not_raise() -> None:
    # End-to-end through the real service (DBs down in CI): still a clean 200.
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert len(resp.json()["sources"]) == 2
