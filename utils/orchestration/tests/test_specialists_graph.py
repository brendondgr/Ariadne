"""The specialist-execution subgraph in isolation.

Hermetic: fixture cards, a fixed probe, fake specialists. The pipeline-level
contract (``utils/specialists/tests/test_pipeline.py``) stays the source of
truth; these pin the subgraph's own semantics — dependency order, seeding,
honest skips, timings, and event emission — at the graph boundary.
"""

from __future__ import annotations

import time
from pathlib import Path

from utils.orchestration.agents.specialists.graph import build_specialists_graph
from utils.planner.agent import PlanningAgent
from utils.planner.config import PlannerConfig
from utils.planner.drafter import DeterministicDrafter
from utils.planner.tests._fixtures import load_fixture_cards, make_live_view
from utils.specialists.config import SpecialistConfig
from utils.specialists.contracts import EvidenceRecord, Provenance, SpecialistResult, SpecialistTask

CARDS = load_fixture_cards()
CONFIG = SpecialistConfig(data_dir=Path("data"), llm_enabled=False)
QUESTION = (
    "Which CAPEC patterns related to credential theft map to ATT&CK techniques, "
    "and what mitigations appear for those techniques?"
)


class FixedProbe:
    def __init__(self, view) -> None:
        self._view = view

    def get_live_sources(self, cards, force: bool = False):
        return self._view


def _plan():
    agent = PlanningAgent(
        PlannerConfig(data_dir="data"), cards=CARDS,
        drafter=DeterministicDrafter(),
        probe=FixedProbe(make_live_view(live=("attack", "capec"))),
    )
    plan = agent.plan(QUESTION)
    assert len(plan.sub_questions) == 2 and plan.joins, "fixture plan must be federated"
    return plan


def _prov(dataset: str, backend: str) -> Provenance:
    return Provenance(source=dataset, dataset=dataset, backend=backend,
                      query=f"query against {backend}", record_id="r1",
                      timestamp="2026-07-06T00:00:00+00:00")


class FakeSpecialist:
    def __init__(self, source: str, join_values: tuple[str, ...], *,
                 ok: bool = True, error: str | None = None) -> None:
        self._source, self._join_values = source, join_values
        self._ok, self._error = ok, error
        self.tasks: list[SpecialistTask] = []

    def run(self, task: SpecialistTask) -> SpecialistResult:
        self.tasks.append(task)
        backend = "neo4j" if self._source == "attack" else "gremlin"
        records = [
            EvidenceRecord(primary_id=v, id_scheme=f"{self._source}-id", label="X", name=v,
                           join_values=(v,), provenance=_prov(self._source, backend))
            for v in self._join_values
        ] if self._ok else []
        return SpecialistResult(task=task, query="q" if self._ok else "", records=records,
                                summary="s" if records else "", ok=self._ok,
                                partial=not self._ok, error=self._error)


def _invoke(specialists, *, deadline_offset: float = 60.0, plan=None):
    graph = build_specialists_graph(CARDS, CONFIG, specialists)
    return graph.invoke({
        "plan": plan if plan is not None else _plan(),
        "cursor": 0,
        "deadline": time.monotonic() + deadline_offset,
    }, config={"recursion_limit": 50})


def test_dependency_order_and_seed_propagation():
    capec = FakeSpecialist("capec", ("T1110.001", "T1555"))
    attack = FakeSpecialist("attack", ("T1110.001",))
    out = _invoke({"capec": capec, "attack": attack})

    assert [r.task.source for r in out["results"]] == ["capec", "attack"]
    assert attack.tasks[0].seed_ids == ("T1110.001", "T1555"), \
        "consumer must be seeded with the producer's sorted join values"
    seq = out["sequencing"]
    assert len(seq) == 1 and seq[0]["seed_count"] == 2 and seq[0]["skipped"] is None
    timings = out["specialist_timings"]
    assert {t["source"] for t in timings} == {"capec", "attack"}
    assert all(t["ms"] >= 0 for t in timings)


def test_failed_producer_skips_consumer_honestly():
    capec = FakeSpecialist("capec", (), ok=False, error="backend refused")
    attack = FakeSpecialist("attack", ("T1110.001",))
    out = _invoke({"capec": capec, "attack": attack})

    consumer = out["results"][1]
    assert consumer.ok and not consumer.records
    assert "it failed (backend refused)" in consumer.summary
    assert not attack.tasks, "the consumer must never run an unseeded query"
    assert out["sequencing"][0]["skipped"].startswith("it failed")


def test_empty_producer_yields_join_value_abstention():
    capec = FakeSpecialist("capec", ())  # ok but no records
    attack = FakeSpecialist("attack", ("T1110.001",))
    out = _invoke({"capec": capec, "attack": attack})

    consumer = out["results"][1]
    assert "it returned no join values" in consumer.summary
    assert not attack.tasks


def test_expired_deadline_skips_everything():
    capec = FakeSpecialist("capec", ("T1110.001",))
    attack = FakeSpecialist("attack", ("T1110.001",))
    out = _invoke({"capec": capec, "attack": attack}, deadline_offset=-1.0)

    assert not out.get("results")
    assert len(out["skipped"]) == 2
    assert all("timeout" in s["reason"] for s in out["skipped"])
    assert not capec.tasks and not attack.tasks


def test_missing_specialist_is_skipped_with_reason():
    attack = FakeSpecialist("attack", ("T1110.001",))
    # Inject only attack and hide the cards so capec cannot be built either.
    graph = build_specialists_graph({}, CONFIG, {"attack": attack})
    out = graph.invoke({"plan": _plan(), "cursor": 0,
                        "deadline": time.monotonic() + 60}, config={"recursion_limit": 50})
    skipped = out["skipped"]
    assert len(skipped) == 1 and "no specialist available" in skipped[0]["reason"]
    # The attack consumer then abstains: its producer was never run.
    consumer = out["results"][0]
    assert "it was not run" in consumer.summary


def test_events_stream_in_truthful_order():
    capec = FakeSpecialist("capec", ("T1110.001",))
    attack = FakeSpecialist("attack", ("T1110.001",))
    graph = build_specialists_graph(CARDS, CONFIG, {"capec": capec, "attack": attack})
    events = list(graph.stream(
        {"plan": _plan(), "cursor": 0, "deadline": time.monotonic() + 60},
        stream_mode="custom", config={"recursion_limit": 50},
    ))
    names = [e for e, _ in events]
    assert names == ["specialist-start", "specialist"] * 2
    starts = [p for e, p in events if e == "specialist-start"]
    assert starts[0]["source"] == "capec" and starts[1]["source"] == "attack"
    assert starts[1]["seed_count"] == 1 and starts[1]["producer"]
    results = [p for e, p in events if e == "specialist"]
    assert all(isinstance(p["result"], SpecialistResult) for p in results)
    assert [p["index"] for p in results] == [0, 1]
    assert all(p["total"] == 2 for p in results)
