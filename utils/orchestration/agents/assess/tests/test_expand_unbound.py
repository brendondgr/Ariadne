"""The unbound-relation fallback expands an anchor's smallest facets, once (EXP-2026-09-024).

Pure-function tests on the facet policy and the deterministic verdict: no
catalogue name appears here, only a made-up schema, so the mechanism is shown
to read nothing but the facet block.
"""

from __future__ import annotations

from utils.orchestration.agents.assess.facets import relevant_facets
from utils.orchestration.agents.assess.frontier import extract_facet_frontier, facet_counts
from utils.orchestration.agents.assess.policy import deterministic_assessment
from utils.planner.schema import Limits, Plan, SubQuestion
from utils.specialists.contracts import EvidenceRecord, SpecialistResult, SpecialistTask
from utils.specialists.federation import FederatedEvidence

_LIMITS = Limits(max_traversal_depth=2, max_result_rows=50, query_timeout_ms=5000)


def _describe_result(anchor: str, facets: list[tuple[str, str, str, int]]) -> SpecialistResult:
    task = SpecialistTask(sub_question_id="q1", source="library", text=f"describe {anchor}",
                          entities=("Book",), limits=_LIMITS, seed_ids=(anchor,))
    record = EvidenceRecord(
        primary_id=anchor, id_scheme="x", label="Book", name=anchor,
        facets=[{"rel": r, "direction": d, "label": l, "count": c} for r, d, l, c in facets],
    )
    return SpecialistResult(task=task, ok=True, records=[record])


def _plan(request: str) -> Plan:
    return Plan(request=request, sub_questions=[
        SubQuestion(id="q1", source="library", text=request, entities=["Book"], limits=_LIMITS),
    ])


# no facet label repeats the anchor's own label, or the relevance scorer would
# claim it through the plan's declared entity
FACETS = [("COVERS", "out", "Topic", 3), ("CITES", "out", "Paper", 12), ("SHELVED_IN", "out", "Room", 1),
          ("BORROWED_BY", "in", "Reader", 400), ("PRAISED_BY", "in", "Critic", 7)]


def test_counts_are_read_off_the_facet_block():
    counts = facet_counts([_describe_result("b1", FACETS)])
    assert counts[("b1", "COVERS", "out", "Topic", "library")] == 3
    assert counts[("b1", "BORROWED_BY", "in", "Reader", "library")] == 400


def test_no_fallback_means_no_facet_when_nothing_scores():
    res = _describe_result("b1", FACETS)
    picks = relevant_facets(extract_facet_frontier([res]), request="how do I get into b1",
                            plan=_plan("how do I get into b1"), limit=4)
    assert picks == []


def test_fallback_picks_the_smallest_facets_first_and_caps_the_count():
    res = _describe_result("b1", FACETS)
    frontier = extract_facet_frontier([res])
    picks = relevant_facets(frontier, request="how do I get into b1", plan=_plan("how do I get into b1"),
                            limit=4, counts=facet_counts([res]), fallback=True, fallback_max_members=50)
    assert [p[1] for p in picks] == ["SHELVED_IN", "COVERS", "PRAISED_BY", "CITES"]
    assert all(p[1] != "BORROWED_BY" for p in picks), "a 400-member facet is a count, not an expansion"


def test_fallback_respects_the_limit():
    res = _describe_result("b1", FACETS)
    picks = relevant_facets(extract_facet_frontier([res]), request="how do I get into b1",
                            plan=_plan("how do I get into b1"), limit=2, counts=facet_counts([res]),
                            fallback=True)
    assert [p[1] for p in picks] == ["SHELVED_IN", "COVERS"]


def test_a_relevant_facet_wins_over_the_fallback():
    res = _describe_result("b1", FACETS)
    picks = relevant_facets(extract_facet_frontier([res]), request="which topics does b1 cover",
                            plan=_plan("which topics does b1 cover"), limit=4,
                            counts=facet_counts([res]), fallback=True)
    assert [p[1] for p in picks] == ["COVERS"]


def test_a_definitional_request_is_never_expanded():
    res = _describe_result("b1", FACETS)
    picks = relevant_facets(extract_facet_frontier([res]), request="what is b1?", plan=_plan("what is b1?"),
                            limit=4, counts=facet_counts([res]), fallback=True)
    assert picks == []


def test_an_already_expanded_facet_is_not_picked_again():
    res = _describe_result("b1", FACETS)
    picks = relevant_facets(extract_facet_frontier([res]), request="how do I get into b1",
                            plan=_plan("how do I get into b1"), limit=4, counts=facet_counts([res]),
                            fallback=True, already_expanded={("b1", "SHELVED_IN", "out"), ("b1", "COVERS", "out")})
    assert [p[1] for p in picks] == ["PRAISED_BY", "CITES"]


def test_the_verdict_reports_a_gap_on_the_first_hop_only():
    res = _describe_result("b1", FACETS)
    plan = _plan("how do I get into b1")
    evidence = FederatedEvidence(request=plan.request, results=[res])
    first = deterministic_assessment(evidence=evidence, plan=plan, prior_frontier=set(), prior_visited=set(),
                                     hop=1, chase_facets=True, expand_unbound=True)
    assert not first.sufficient and first.gaps
    second = deterministic_assessment(evidence=evidence, plan=plan, prior_frontier=set(), prior_visited=set(),
                                      hop=2, chase_facets=True, expand_unbound=True)
    assert second.sufficient
    off = deterministic_assessment(evidence=evidence, plan=plan, prior_frontier=set(), prior_visited=set(),
                                   hop=1, chase_facets=True, expand_unbound=False)
    assert off.sufficient, "the flag off reproduces the shipped verdict"


def test_config_reads_the_environment(monkeypatch):
    from utils.orchestration.config import OrchestrationConfig

    monkeypatch.delenv("ORCH_EXPAND_UNBOUND", raising=False)
    assert OrchestrationConfig.from_env().expand_unbound is False
    monkeypatch.setenv("ORCH_EXPAND_UNBOUND", "true")
    monkeypatch.setenv("ORCH_EXPAND_UNBOUND_MAX_MEMBERS", "25")
    cfg = OrchestrationConfig.from_env()
    assert cfg.expand_unbound is True and cfg.expand_unbound_max_members == 25
