"""Contract tests for the /api/query SSE pipeline.

The pipeline itself is exercised against stubbed agent + specialists so the tests
are deterministic and need no live graph backend. They assert the *event order*
and each event's JSON shape — the contract the front end's run machine consumes —
plus the plan-only, no-cards, partial, and empty-question paths.
"""

from __future__ import annotations

import json
from typing import Iterator

from fastapi.testclient import TestClient

import api.main as main
from api.main import app
from api.services import query as query_service
from utils.planner.discovery import LiveSource, LiveSourceView
from utils.planner.schema import Limits, Plan, SubQuestion, UnsupportedPart
from utils.specialists.contracts import (
    EvaluatorTrace,
    EvidenceRecord,
    Provenance,
    SpecialistResult,
    SpecialistTask,
)

client = TestClient(app)


# --------------------------------------------------------------------------- #
# Stubs
# --------------------------------------------------------------------------- #


class _StubAgent:
    def __init__(self, cards, live_view, plan):
        self.cards = cards
        self._live_view = live_view
        self._plan = plan

    def live_sources(self):
        return self._live_view

    def plan(self, _question):
        return self._plan


class _StubSpecialist:
    def __init__(self, result):
        self._result = result

    def run(self, _task):
        return self._result


def _result(source: str, primary_id: str, join_value: str, backend: str, *, ok=True, partial=False):
    prov = Provenance(
        source=source, dataset=source, backend=backend,
        query="MATCH …", record_id="n1", timestamp="2026-01-01T00:00:00Z",
    )
    rec = EvidenceRecord(
        primary_id=primary_id, id_scheme="external-id", label="Technique",
        name=f"name-{primary_id}", join_values=(join_value,), provenance=prov,
    )
    task = SpecialistTask(sub_question_id=f"sq-{source}", source=source, text="t",
                          limits={"max_result_rows": 50}, join_key="external_id")
    return SpecialistResult(
        task=task, query="MATCH …", records=[rec], summary=f"{source} grounded summary",
        traces=[EvaluatorTrace(step="normalize", ok=True)], ok=ok, partial=partial,
    )


def _two_source_plan(*, partial=False, unsupported=()):
    return Plan(
        request="Which ATT&CK techniques map to CAPEC patterns?",
        sub_questions=[
            SubQuestion(id="sq-attack", source="attack", text="techniques",
                        entities=["Technique"], limits=Limits(2, 50, 5000), join_key="external_id"),
            SubQuestion(id="sq-capec", source="capec", text="patterns",
                        entities=["AttackPattern"], limits=Limits(2, 50, 5000), join_key="external_id"),
        ],
        unsupported=[UnsupportedPart(description=d, reason=r) for d, r in unsupported],
        partial=partial,
        trace=[{"iteration": 1, "drafter": "DeterministicDrafter", "gate_ok": True,
                "reasons": [], "sub_questions": 2, "unsupported": len(unsupported)}],
    )


def _live_view(live=("attack", "capec")):
    sources = {
        "attack": LiveSource("attack", "neo4j", "bolt://x:5456", "attack" in live,
                             node_count=120, observed_labels=("Technique",), reason="live"),
        "capec": LiveSource("capec", "gremlin", "ws://x:6455/gremlin", "capec" in live,
                            node_count=80, observed_labels=("AttackPattern",), reason="live"),
    }
    return LiveSourceView(sources)


def _collect(gen: Iterator[str]) -> list[tuple[str, dict]]:
    events = []
    for frame in gen:
        assert frame.endswith("\n\n")
        head, _, body = frame.partition("\n")
        event = head.removeprefix("event: ")
        data = json.loads(body.removeprefix("data: ").strip())
        events.append((event, data))
    return events


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #


def test_query_mode_event_order_and_shapes() -> None:
    agent = _StubAgent(
        cards={"attack": object(), "capec": object()},
        live_view=_live_view(),
        plan=_two_source_plan(),
    )
    specialists = {
        "attack": _StubSpecialist(_result("attack", "T1047", "T1047", "neo4j")),
        "capec": _StubSpecialist(_result("capec", "CAPEC-549", "T1047", "gremlin")),
    }
    events = _collect(
        query_service.stream_query_events("q", mode="query", agent=agent, specialists=specialists)
    )
    types = [e for e, _ in events]

    # Ordered sequence the run machine relies on.
    assert types == [
        "status", "probe", "status", "plan", "status",
        "specialist", "specialist", "evidence", "status", "answer", "done",
    ]

    probe = dict(events)["probe"]
    assert len(probe["live_sources"]) == 2
    assert probe["live_sources"][0]["node_count"] == 120

    plan = dict(events)["plan"]
    assert len(plan["plan"]["sub_questions"]) == 2
    assert plan["plan"]["trace"]  # planner sub-stage animation source
    assert plan["target_sources"] == ["attack", "capec"]

    specialist_events = [d for e, d in events if e == "specialist"]
    assert [d["index"] for d in specialist_events] == [0, 1]
    first = specialist_events[0]["result"]
    assert set(first) >= {"task", "query", "records", "record_count", "summary", "traces", "ok", "join_values"}

    evidence = dict(events)["evidence"]["evidence"]
    assert evidence["cross_source_join_values"] == ["T1047"]
    assert "T1047" in evidence["join_index"]

    answer = dict(events)["answer"]
    assert answer["status"] == "answered" and answer["exit_code"] == 0
    assert len(answer["sections"]) == 2
    assert len(answer["cross_source"]) == 1 and answer["cross_source"][0]["value"] == "T1047"

    done = dict(events)["done"]
    assert done == {"status": "answered", "exit_code": 0}


def test_plan_mode_skips_specialists() -> None:
    agent = _StubAgent({"attack": object(), "capec": object()}, _live_view(), _two_source_plan())
    events = _collect(query_service.stream_query_events("q", mode="plan", agent=agent))
    types = [e for e, _ in events]
    assert types == ["status", "probe", "status", "plan", "status", "answer", "done"]
    assert "specialist" not in types and "evidence" not in types
    assert "Routed to" in dict(events)["answer"]["headline"]


def test_no_source_cards_is_no_sources_exit_2() -> None:
    agent = _StubAgent(cards={}, live_view=_live_view(), plan=_two_source_plan())
    events = _collect(query_service.stream_query_events("q", agent=agent))
    assert events[-1][0] == "done"
    assert events[-1][1]["status"] == "no_sources"
    assert events[-1][1]["exit_code"] == 2


def test_partial_when_a_specialist_fails() -> None:
    agent = _StubAgent({"attack": object(), "capec": object()}, _live_view(), _two_source_plan())
    specialists = {
        "attack": _StubSpecialist(_result("attack", "T1047", "T1047", "neo4j")),
        "capec": _StubSpecialist(_result("capec", "CAPEC-549", "T1047", "gremlin", ok=False, partial=True)),
    }
    events = _collect(
        query_service.stream_query_events("q", mode="query", agent=agent, specialists=specialists)
    )
    done = dict(events)["done"]
    assert done["status"] == "partial" and done["exit_code"] == 1
    assert dict(events)["evidence"]["evidence"]["partial"] is True


def test_skipped_when_no_specialist_for_source() -> None:
    # Plan routes to a source with no injected/built specialist and no card.
    plan = Plan(
        request="q",
        sub_questions=[SubQuestion(id="sq-x", source="attack", text="t",
                                   entities=[], limits=Limits(2, 50, 5000))],
    )
    agent = _StubAgent(cards={"attack": None}, live_view=_live_view(), plan=plan)
    # No injected specialists; build_specialist would need a real card → skipped.
    events = _collect(query_service.stream_query_events("q", mode="query", agent=agent, specialists={}))
    types = [e for e, _ in events]
    assert "skipped" in types
    assert dict(events)["done"]["status"] == "partial"


def test_empty_question_emits_error() -> None:
    events = _collect(query_service.stream_query_events("   ", mode="query"))
    assert events == [("error", {"message": "Question must not be empty."})]


def test_endpoint_rejects_empty_question() -> None:
    assert client.post("/api/query", json={"question": ""}).status_code == 422


def test_endpoint_streams_event_stream(monkeypatch) -> None:
    def _fake_stream(*_args, **_kwargs):
        yield "event: done\ndata: {\"status\": \"answered\", \"exit_code\": 0}\n\n"

    monkeypatch.setattr(main, "stream_query_events", _fake_stream)
    resp = client.post("/api/query", json={"question": "hello", "mode": "query"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert "event: done" in resp.text
