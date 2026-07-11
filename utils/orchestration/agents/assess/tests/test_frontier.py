"""Frontier / visited extraction on a minimal specialist-evidence fixture."""

from utils.orchestration.agents.assess.frontier import (
    extract_frontier,
    update_visited,
)
from utils.planner.schema import JoinDeclaration, Limits, Plan, SubQuestion
from utils.specialists.contracts import (
    EvidenceRecord,
    SpecialistResult,
    SpecialistTask,
)

_LIMITS = Limits(max_traversal_depth=2, max_result_rows=50, query_timeout_ms=5000)


def _record(primary_id: str, join_values: tuple[str, ...]) -> EvidenceRecord:
    return EvidenceRecord(
        primary_id=primary_id,
        id_scheme="attack-id",
        label="Technique",
        name=primary_id,
        join_values=join_values,
    )


def _result(source: str, records: list[EvidenceRecord]) -> SpecialistResult:
    task = SpecialistTask(sub_question_id=f"q-{source}", source=source, text="q")
    return SpecialistResult(task=task, ok=True, records=records)


def _plan_with_join() -> Plan:
    return Plan(
        request="r",
        sub_questions=[
            SubQuestion(id="q1", source="capec", text="c", entities=["AttackPattern"],
                        limits=_LIMITS, join_key="attack-technique-id"),
            SubQuestion(id="q2", source="attack", text="a", entities=["Technique"],
                        limits=_LIMITS, join_key="attack-technique-id"),
        ],
        joins=[JoinDeclaration(key="attack-technique-id", sources=["capec", "attack"])],
    )


def test_extract_frontier_collects_join_values_for_joined_sources():
    plan = _plan_with_join()
    results = [
        _result("capec", [_record("CAPEC-233", ("T1574.010",))]),
        _result("attack", [_record("T1047", ("T1047",))]),
    ]
    assert extract_frontier(results, plan) == {
        ("T1574.010", "capec"),
        ("T1047", "attack"),
    }


def test_extract_frontier_skips_sources_without_a_declared_join():
    """No declared join → nothing to chase, so the frontier stays empty."""
    plan = Plan(
        request="r",
        sub_questions=[SubQuestion(id="q1", source="attack", text="a",
                                   entities=["Technique"], limits=_LIMITS)],
        joins=[],
    )
    results = [_result("attack", [_record("T1047", ("T1047",))])]
    assert extract_frontier(results, plan) == set()


def test_update_visited_returns_only_the_new_delta():
    results = [_result("attack", [_record("T1047", ("T1047",)),
                                  _record("T1021", ("T1021",))])]
    visited = {("T1047", "attack")}
    # Only the genuinely-new entity comes back — T1047 is already settled.
    assert update_visited(visited, results) == {("T1021", "attack")}


def test_update_visited_empty_when_nothing_new():
    results = [_result("attack", [_record("T1047", ("T1047",))])]
    assert update_visited({("T1047", "attack")}, results) == set()


def test_update_visited_ignores_records_without_primary_id():
    results = [_result("capec", [_record("", ("T1047",))])]
    assert update_visited(set(), results) == set()
