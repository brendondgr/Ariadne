"""End-to-end proof of the iterative-retrieval loop through the super-graph.

Hermetic: fixture cards, a fixed probe, a scripted initial plan that
*under-routes* (only the CAPEC producer side, with the join declared), and fake
specialists. Single-pass leaves the cross-source join open; the loop re-plans
the ATT&CK consumer, seeds it from the producer, closes the join, and
terminates — well within the hop cap.
"""

from __future__ import annotations

from pathlib import Path

from utils.orchestration.main import run_pipeline
from utils.planner.agent import PlanningAgent
from utils.planner.config import PlannerConfig
from utils.planner.schema import JoinDeclaration, Limits, Plan, SubQuestion
from utils.planner.tests._fixtures import load_fixture_cards, make_live_view
from utils.specialists.config import SpecialistConfig
from utils.specialists.contracts import (
    EvidenceRecord,
    Provenance,
    SpecialistResult,
    SpecialistTask,
)
from utils.synthesis.config import SynthesisConfig

CARDS = load_fixture_cards()
GOOD = Limits(max_traversal_depth=3, max_result_rows=1000, query_timeout_ms=5000)
SHARED_KEY = "T1000"


class FixedProbe:
    def __init__(self, view) -> None:
        self._view = view

    def get_live_sources(self, cards, force: bool = False):
        return self._view


class CapecOnlyDrafter:
    """Initial plan: only the CAPEC producer, but the join is declared."""

    def draft(self, request, cards, live_view, feedback=None) -> Plan:
        return Plan(
            request=request,
            sub_questions=[
                SubQuestion("q1", "capec", "CAPEC patterns", ["AttackPattern", "MAPS_TO"],
                            GOOD, join_key="attack-technique-id"),
            ],
            joins=[JoinDeclaration(key="attack-technique-id", sources=["capec", "attack"])],
        )


class FakeSpecialist:
    def __init__(self, source: str, join_values: tuple[str, ...]) -> None:
        self._source, self._join_values = source, join_values
        self.tasks: list[SpecialistTask] = []

    def run(self, task: SpecialistTask) -> SpecialistResult:
        self.tasks.append(task)
        backend = "neo4j" if self._source == "attack" else "gremlin"
        prov = Provenance(source=self._source, dataset=self._source, backend=backend,
                          query="q", record_id="r1", timestamp="2026-07-06T00:00:00+00:00")
        records = [
            EvidenceRecord(primary_id=v, id_scheme=f"{self._source}-id", label="X",
                           name=v, join_values=(v,), provenance=prov)
            for v in self._join_values
        ]
        return SpecialistResult(task=task, query="q", records=records, summary="s",
                                ok=True, partial=False)


def _agent() -> PlanningAgent:
    return PlanningAgent(
        PlannerConfig(data_dir="data"),
        cards=CARDS,
        drafter=CapecOnlyDrafter(),
        probe=FixedProbe(make_live_view(live=("attack", "capec"))),
    )


def _run(max_hops: int, monkeypatch):
    monkeypatch.setenv("ORCH_MAX_HOPS", str(max_hops))
    specialists = {
        "capec": FakeSpecialist("capec", (SHARED_KEY,)),
        "attack": FakeSpecialist("attack", (SHARED_KEY,)),
    }
    return run_pipeline(
        "Which techniques do these CAPEC patterns map to?",
        agent=_agent(),
        specialists=specialists,
        specialist_config=SpecialistConfig(data_dir=Path("data"), llm_enabled=False),
        synthesis_config=SynthesisConfig(llm_enabled=False),
    ), specialists


def test_single_pass_leaves_the_cross_source_join_open(monkeypatch):
    run, specialists = _run(max_hops=1, monkeypatch=monkeypatch)
    sources = set(run.evidence.by_source())
    assert sources == {"capec"}, "single pass must never query the ATT&CK consumer"
    assert run.evidence.cross_source_join_values() == []
    assert not specialists["attack"].tasks


def test_loop_replans_the_consumer_and_closes_the_join(monkeypatch):
    run, specialists = _run(max_hops=5, monkeypatch=monkeypatch)
    sources = set(run.evidence.by_source())
    # The loop discovered the CAPEC join keys and chased them into ATT&CK.
    assert sources == {"capec", "attack"}
    assert run.evidence.cross_source_join_values() == [SHARED_KEY]
    # The consumer ran exactly once, seeded from the producer's join value.
    assert len(specialists["attack"].tasks) == 1
    assert specialists["attack"].tasks[0].seed_ids == (SHARED_KEY,)


def test_loop_terminates_within_the_hop_cap(monkeypatch):
    run, _ = _run(max_hops=5, monkeypatch=monkeypatch)
    # Reaching here means the graph terminated (no recursion-limit blow-up).
    max_hop = max((sq.hop for sq in run.plan.sub_questions), default=0)
    assert 1 <= max_hop <= 5
    assert run.answer is not None  # synthesis was reached


def test_replanned_subquestion_is_hop_tagged(monkeypatch):
    run, _ = _run(max_hops=5, monkeypatch=monkeypatch)
    attack_sqs = [sq for sq in run.plan.sub_questions if sq.source == "attack"]
    assert attack_sqs and attack_sqs[0].hop >= 2, "chased sub-question carries its hop tag"
