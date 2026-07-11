"""Sufficiency policy: sufficient / insufficient / hop-cap / novelty / fallback."""

import pytest

from utils.orchestration.agents.assess.contracts import Assessment
from utils.orchestration.agents.assess.policy import assess, deterministic_assessment
from utils.planner.schema import JoinDeclaration, Limits, Plan, SubQuestion
from utils.specialists.contracts import (
    EvidenceRecord,
    SpecialistResult,
    SpecialistTask,
)
from utils.specialists.federation import FederatedEvidence

_LIMITS = Limits(max_traversal_depth=2, max_result_rows=50, query_timeout_ms=5000)


def _record(primary_id: str, join_values: tuple[str, ...]) -> EvidenceRecord:
    return EvidenceRecord(primary_id=primary_id, id_scheme="x", label="L",
                          name=primary_id, join_values=join_values)


def _result(source: str, records: list[EvidenceRecord]) -> SpecialistResult:
    task = SpecialistTask(sub_question_id=f"q-{source}", source=source, text="q")
    return SpecialistResult(task=task, ok=True, records=records)


def _joined_plan() -> Plan:
    return Plan(
        request="expand CAPEC patterns to techniques then mitigations",
        sub_questions=[
            SubQuestion(id="q1", source="capec", text="c", entities=["AttackPattern"],
                        limits=_LIMITS, join_key="attack-technique-id"),
            SubQuestion(id="q2", source="attack", text="a", entities=["Technique"],
                        limits=_LIMITS, join_key="attack-technique-id"),
        ],
        joins=[JoinDeclaration(key="attack-technique-id", sources=["capec", "attack"])],
    )


def _evidence(plan: Plan, results: list[SpecialistResult]) -> FederatedEvidence:
    return FederatedEvidence(request=plan.request, results=results)


def test_single_source_plan_is_immediately_sufficient():
    plan = Plan(request="what is T1047?",
                sub_questions=[SubQuestion(id="q1", source="attack", text="a",
                                           entities=["Technique"], limits=_LIMITS)],
                joins=[])
    ev = _evidence(plan, [_result("attack", [_record("T1047", ("T1047",))])])
    verdict = assess(evidence=ev, plan=plan, prior_frontier=set(), prior_visited=set(),
                     hop=1, max_hops=5)
    assert verdict.sufficient is True
    assert verdict.hop_capped is False


def test_open_join_is_insufficient_and_names_the_gap():
    plan = _joined_plan()
    # CAPEC surfaces T1574.010; ATT&CK surfaces a *different* technique → no match.
    ev = _evidence(plan, [
        _result("capec", [_record("CAPEC-233", ("T1574.010",))]),
        _result("attack", [_record("T1047", ("T1047",))]),
    ])
    verdict = assess(evidence=ev, plan=plan, prior_frontier=set(), prior_visited=set(),
                     hop=1, max_hops=5)
    assert verdict.sufficient is False
    assert any("attack-technique-id" in g for g in verdict.gaps)
    # Both surfaced-but-unresolved join values are offered to the re-planner.
    assert set(verdict.missing_entities) == {"T1047", "T1574.010"}


def test_closed_join_with_novelty_exhausted_is_sufficient():
    plan = _joined_plan()
    results = [
        _result("capec", [_record("CAPEC-233", ("T1574.010",))]),
        _result("attack", [_record("T1574.010", ("T1574.010",))]),  # shared value
    ]
    ev = _evidence(plan, results)
    # Re-assessing a hop whose keys/entities are already in the running sets:
    # no new frontier, no new visited → novelty exhausted.
    prior_frontier = {("T1574.010", "capec"), ("T1574.010", "attack")}
    prior_visited = {("CAPEC-233", "capec"), ("T1574.010", "attack")}
    verdict = assess(evidence=ev, plan=plan, prior_frontier=prior_frontier,
                     prior_visited=prior_visited, hop=2, max_hops=5)
    assert verdict.sufficient is True
    assert verdict.reason == "join closure reached and novelty exhausted"


def test_closed_join_but_still_discovering_keeps_going():
    """Join closed, but this hop surfaced a NEW key → not novelty-exhausted."""
    plan = _joined_plan()
    results = [
        _result("capec", [_record("CAPEC-233", ("T1574.010",))]),
        _result("attack", [_record("T1574.010", ("T1574.010",))]),
    ]
    ev = _evidence(plan, results)
    verdict = assess(evidence=ev, plan=plan, prior_frontier=set(), prior_visited=set(),
                     hop=1, max_hops=5)
    assert verdict.sufficient is False  # novelty present this hop


def test_hop_cap_forces_sufficiency():
    plan = _joined_plan()
    ev = _evidence(plan, [
        _result("capec", [_record("CAPEC-233", ("T1574.010",))]),
        _result("attack", [_record("T1047", ("T1047",))]),  # join still open
    ])
    verdict = assess(evidence=ev, plan=plan, prior_frontier=set(), prior_visited=set(),
                     hop=5, max_hops=5)
    assert verdict.sufficient is True
    assert verdict.hop_capped is True
    assert "hop cap reached" in verdict.reason


def test_max_hops_one_reproduces_single_pass():
    """Default cap = 1: even an open join is forced sufficient after hop 1."""
    plan = _joined_plan()
    ev = _evidence(plan, [
        _result("capec", [_record("CAPEC-233", ("T1574.010",))]),
        _result("attack", [_record("T1047", ("T1047",))]),
    ])
    verdict = assess(evidence=ev, plan=plan, prior_frontier=set(), prior_visited=set(),
                     hop=1, max_hops=1)
    assert verdict.sufficient is True
    assert verdict.hop_capped is True


def test_llm_mode_falls_back_when_llm_disabled():
    plan = _joined_plan()
    ev = _evidence(plan, [_result("attack", [_record("T1047", ("T1047",))])])
    verdict = assess(evidence=ev, plan=plan, prior_frontier=set(), prior_visited=set(),
                     hop=1, max_hops=5, assess_mode="llm", use_llm=False)
    assert verdict.mode == "deterministic (llm fallback)"


def test_llm_mode_falls_back_when_critic_raises():
    plan = _joined_plan()
    ev = _evidence(plan, [_result("attack", [_record("T1047", ("T1047",))])])

    def broken_critic(request, evidence, verdict):
        raise RuntimeError("endpoint down")

    verdict = assess(evidence=ev, plan=plan, prior_frontier=set(), prior_visited=set(),
                     hop=1, max_hops=5, assess_mode="llm", use_llm=True,
                     critic=broken_critic)
    assert verdict.mode == "deterministic (llm fallback)"


def test_llm_critic_result_is_used_when_available():
    plan = _joined_plan()
    ev = _evidence(plan, [_result("attack", [_record("T1047", ("T1047",))])])
    refined = Assessment(sufficient=False, gaps=["need mitigations"],
                         missing_entities=["T1047"], hop=1, mode="llm",
                         reason="critic says more needed")

    def critic(request, evidence, verdict):
        assert request == plan.request
        return refined

    verdict = assess(evidence=ev, plan=plan, prior_frontier=set(), prior_visited=set(),
                     hop=1, max_hops=5, assess_mode="llm", use_llm=True, critic=critic)
    assert verdict is refined
    assert verdict.mode == "llm"


def test_deterministic_assessment_ignores_hop_cap():
    """The bare predicate never forces sufficiency — that is the node/assess job."""
    plan = _joined_plan()
    ev = _evidence(plan, [
        _result("capec", [_record("CAPEC-233", ("T1574.010",))]),
        _result("attack", [_record("T1047", ("T1047",))]),
    ])
    verdict = deterministic_assessment(evidence=ev, plan=plan, prior_frontier=set(),
                                       prior_visited=set(), hop=99)
    assert verdict.sufficient is False
    assert verdict.hop_capped is False
