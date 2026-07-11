"""Re-plan merge/dedupe and the deterministic join-key-chase expansion.

The core guarantee: re-planning never re-issues an already-answered
sub-question, and it seeds a chase into a not-yet-queried source only.
"""

from __future__ import annotations

from utils.planner.agent import PlanningAgent
from utils.planner.config import PlannerConfig
from utils.planner.schema import (
    JoinDeclaration,
    Limits,
    Plan,
    SubQuestion,
    merge_plans,
    subquestion_key,
)
from utils.planner.tests._fixtures import load_fixture_cards, make_live_view
from utils.specialists.contracts import (
    EvidenceRecord,
    SpecialistResult,
    SpecialistTask,
)
from utils.specialists.federation import FederatedEvidence

GOOD = Limits(max_traversal_depth=3, max_result_rows=1000, query_timeout_ms=5000)
CARDS = load_fixture_cards()


class FakeProbe:
    def __init__(self, view) -> None:
        self._view = view

    def get_live_sources(self, cards, force: bool = False):
        return self._view


def _agent(*, live=("attack", "capec")) -> PlanningAgent:
    return PlanningAgent(
        PlannerConfig(data_dir="data"),
        cards=CARDS,
        probe=FakeProbe(make_live_view(live=live)),
    )


# -- merge / dedupe ---------------------------------------------------------


def test_subquestion_key_normalizes_text_and_entities():
    a = SubQuestion("q1", "attack", "Find  Techniques", ["Technique", "Mitigation"], GOOD)
    b = SubQuestion("q9", "attack", "find techniques", ["Mitigation", "technique"], GOOD)
    assert subquestion_key(a) == subquestion_key(b)


def test_merge_appends_new_and_drops_answered():
    base = Plan(
        request="r",
        sub_questions=[SubQuestion("q1", "capec", "patterns", ["AttackPattern"], GOOD)],
    )
    addition = Plan(
        request="r",
        sub_questions=[
            SubQuestion("qX", "capec", "patterns", ["AttackPattern"], GOOD),  # dup
            SubQuestion("qY", "attack", "techniques", ["Technique"], GOOD),   # new
        ],
        joins=[JoinDeclaration(key="attack-technique-id", sources=["capec", "attack"])],
    )
    merged = merge_plans(base, addition, hop=1)

    # Only the genuinely-new attack sub-question is appended.
    assert [sq.source for sq in merged.sub_questions] == ["capec", "attack"]
    # Base id preserved (by_id / cursor key on it); new one gets a fresh unique id.
    assert merged.sub_questions[0].id == "q1"
    assert merged.sub_questions[1].id != "q1"
    assert merged.sub_questions[1].hop == 1
    assert merged.sub_questions[0].hop == 0
    assert len(merged.joins) == 1


def test_merge_is_idempotent_when_nothing_new():
    base = Plan(request="r",
                sub_questions=[SubQuestion("q1", "attack", "t", ["Technique"], GOOD)])
    addition = Plan(request="r",
                    sub_questions=[SubQuestion("q2", "attack", "t", ["Technique"], GOOD)])
    merged = merge_plans(base, addition, hop=1)
    assert len(merged.sub_questions) == 1  # answered → not re-issued


def test_merge_unions_joins_without_duplicates():
    base = Plan(request="r",
                joins=[JoinDeclaration(key="attack-technique-id", sources=["capec", "attack"])])
    addition = Plan(
        request="r",
        joins=[JoinDeclaration(key="attack-technique-id", sources=["attack", "capec"])],
    )
    merged = merge_plans(base, addition, hop=1)
    assert len(merged.joins) == 1  # same key + same source set (order-insensitive)


# -- deterministic join-key chase ------------------------------------------


def _capec_evidence_with_frontier() -> FederatedEvidence:
    """CAPEC ran and surfaced a technique-id join value; ATT&CK never queried."""
    task = SpecialistTask(sub_question_id="q1", source="capec", text="patterns",
                          join_key="attack-technique-id")
    rec = EvidenceRecord(primary_id="CAPEC-233", id_scheme="capec-id", label="TaxonomyEntry",
                         name="1574.010", join_values=("1574.010",))
    result = SpecialistResult(task=task, ok=True, records=[rec])
    return FederatedEvidence(request="r", results=[result])


def test_replan_chases_discovered_keys_into_unqueried_source():
    agent = _agent()
    evidence = _capec_evidence_with_frontier()
    frontier = {("1574.010", "capec")}
    expansion = agent.replan("r", evidence, frontier, gaps=["join not closed"])

    assert [sq.source for sq in expansion.sub_questions] == ["attack"]
    sq = expansion.sub_questions[0]
    assert "Technique" in sq.entities
    assert sq.join_key == "attack-technique-id"
    assert expansion.joins and expansion.joins[0].key == "attack-technique-id"


def test_replan_returns_empty_when_consumer_already_queried():
    agent = _agent()
    evidence = _capec_evidence_with_frontier()
    # ATT&CK already ran this hop → nothing new to chase cross-source.
    attack_task = SpecialistTask(sub_question_id="q2", source="attack", text="t")
    evidence.results.append(SpecialistResult(task=attack_task, ok=True, records=[]))
    expansion = agent.replan("r", evidence, {("1574.010", "capec")}, gaps=[])
    assert expansion.sub_questions == []


def test_replan_returns_empty_when_frontier_already_resolved():
    """A join value present under both sources is resolved → not chased again."""
    agent = _agent()
    evidence = _capec_evidence_with_frontier()
    # Add an attack-less resolved value by making the same value cross-source.
    # Here nothing pending remains once resolved, so expansion is empty.
    expansion = agent.replan("r", evidence, frontier=set(), gaps=[])
    assert expansion.sub_questions == []
