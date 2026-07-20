#!/usr/bin/env python3
"""Hermetic tests for the end-to-end scorer's pure metric functions.

No database: real ``FederatedEvidence`` / ``SynthesizedAnswer`` objects are
built from the synthesis fixtures and verified, then fed to the scoring
functions. Each of the four e2e metrics is checked on a known-good and a
known-bad case, plus the aggregate roll-up and the ``live=False`` short-circuit.
"""

from __future__ import annotations

import os

import pytest

from utils.evaluation.llm_judge import EvalConfig, JudgeReport, judge_run
from utils.evaluation.score_e2e import (
    aggregate,
    build_e2e,
    evaluate_case,
    score_answer_coverage,
    score_correlation,
    score_e2e,
    score_inspectability,
    score_mapping_recall,
    score_provenance,
)
from utils.specialists.contracts import EvidenceRecord, Provenance
from utils.synthesis.contracts import Citation, Claim, SynthesizedAnswer
from utils.synthesis.tests._fixtures import make_evidence, make_record, make_result
from utils.synthesis.verifier import verify_answer


def _federated_evidence(join_value="T1021"):
    """Two sources sharing one join value → one cross-source correlation."""
    attack = make_result(
        sub_question_id="q2",
        records=[make_record(join_value, join_values=(join_value,))],
    )
    capec = make_result(
        source="capec",
        sub_question_id="q1",
        records=[
            make_record(
                "CAPEC-555",
                source="capec",
                label="AttackPattern",
                join_values=(join_value,),
            )
        ],
    )
    return make_evidence([attack, capec])


def _federated_answer(evidence, join_value="T1021"):
    claim = Claim(
        text=f"{join_value} is corroborated across attack and capec.",
        citations=(
            Citation(source="attack", primary_id=join_value),
            Citation(source="capec", primary_id="CAPEC-555"),
        ),
        entity_ids=(join_value,),
        kind="correlation",
        sub_question_id="q2",
    )
    return verify_answer(SynthesizedAnswer(request="q", claims=[claim]), evidence)


def _entry(must_correlate, **kw):
    base = {"id": "F-CTM-01", "tier": "hard", "assertions": {"must_correlate": must_correlate}}
    base.update(kw)
    return base


# -- cross-source answer accuracy -------------------------------------------


def test_correlation_exact_match():
    evidence = _federated_evidence()
    result = score_correlation(_entry(["T1021"]), evidence)
    assert result["exact"] is True
    assert result["precision"] == result["recall"] == result["f1"] == 1.0


def test_correlation_partial_recall():
    evidence = _federated_evidence()  # live surfaces only T1021
    result = score_correlation(_entry(["T1021", "T1055"]), evidence)
    assert result["exact"] is False
    assert result["recall"] == 0.5
    assert result["precision"] == 1.0


def test_correlation_negative_no_fabrication():
    # Single source only → no cross-source join values.
    evidence = make_evidence([make_result(records=[make_record("T1047")])])
    entry = _entry([], assertions={"expect_no_correlation": True, "must_correlate": []})
    result = score_correlation(entry, evidence)
    assert result["negative"] is True
    assert result["exact"] is True  # correctly surfaced nothing


def test_correlation_negative_detects_fabrication():
    evidence = _federated_evidence()  # this DOES produce a correlation
    entry = _entry([], assertions={"expect_no_correlation": True, "must_correlate": []})
    result = score_correlation(entry, evidence)
    assert result["exact"] is False  # a correlation was fabricated


# -- CAPEC→ATT&CK mapping recall --------------------------------------------


def test_mapping_recall_full():
    evidence = _federated_evidence("T1021")
    result = score_mapping_recall(_entry(["T1021"]), evidence)
    assert result["recall"] == 1.0
    assert result["found"] == result["gold"] == 1


def test_mapping_recall_partial():
    evidence = _federated_evidence("T1021")
    result = score_mapping_recall(_entry(["T1021", "T9999"]), evidence)
    assert result["gold"] == 2
    assert result["found"] == 1
    assert result["recall"] == 0.5
    assert result["missing"] == ["T9999"]


def test_mapping_recall_none_for_negatives():
    evidence = _federated_evidence()
    entry = _entry([], assertions={"expect_no_correlation": True, "must_correlate": []})
    assert score_mapping_recall(entry, evidence) is None


# -- provenance correctness --------------------------------------------------


def test_provenance_clean_answer_fully_provenanced():
    evidence = _federated_evidence()
    answer = _federated_answer(evidence)
    result = score_provenance(answer, evidence)
    assert result["citation_provenance_rate"] == 1.0
    assert result["fully_provenanced"] is True


def test_provenance_flags_query_not_executed():
    # A record whose recorded provenance query was never the executed query.
    rec = EvidenceRecord(
        primary_id="T1047",
        id_scheme="attack-id",
        label="Technique",
        name="WMI",
        properties={},
        related=[],
        join_values=("T1047",),
        provenance=Provenance(
            source="attack",
            dataset="attack",
            backend="neo4j",
            query="MATCH (fabricated) RETURN 1",  # != result.query
            record_id="attack:T1047",
            timestamp="2026-07-04T00:00:00Z",
        ),
    )
    result = make_result(records=[rec], query="MATCH (t:Technique) RETURN t")
    evidence = make_evidence([result])
    claim = Claim(
        text="T1047 found.",
        citations=(Citation(source="attack", primary_id="T1047"),),
        entity_ids=("T1047",),
    )
    answer = verify_answer(SynthesizedAnswer(request="q", claims=[claim]), evidence)
    scored = score_provenance(answer, evidence)
    assert scored["citation_provenance_rate"] == 0.0
    assert scored["fully_provenanced"] is False


# -- analyst inspectability --------------------------------------------------


def test_inspectability_clean_answer():
    evidence = _federated_evidence()
    answer = _federated_answer(evidence)
    result = score_inspectability(answer, evidence)
    assert result["citation_coverage"] == 1.0
    assert result["traceability"] == 1.0
    assert result["abstention_proofs"] == 1.0
    assert result["inspectability"] == 1.0


def test_inspectability_abstention_proof():
    empty = make_result(sub_question_id="q1", records=[], ok=True, query="MATCH ...")
    evidence = make_evidence([empty])
    answer = verify_answer(SynthesizedAnswer(request="q", claims=[]), evidence)
    result = score_inspectability(answer, evidence)
    # The verifier repairs an abstention carrying the executed query as proof.
    assert result["abstention_proofs"] == 1.0
    assert result["inspectability"] == 1.0


# -- answer coverage (under-enumeration yardstick) --------------------------


def _coverage_entry(**asserts):
    return {"id": "A-MIT-05", "tier": "hard", "assertions": asserts}


def test_answer_coverage_full():
    """All gold ids surfaced (here via the narrative prose) → coverage 1.0."""
    entry = _coverage_entry(must_include_related=["M1041", "M1015", "M1043", "M1028"])
    answer = SynthesizedAnswer(
        request="q", narrative="Mitigations: M1041, M1015, M1043, M1028."
    )
    result = score_answer_coverage(entry, answer)
    assert result["gold"] == 4
    assert result["found"] == 4
    assert result["coverage"] == 1.0
    assert result["missing"] == []


def test_answer_coverage_partial_under_enumeration():
    """The exact defect: retrieval fine, answer names only a sample of the gold."""
    entry = _coverage_entry(must_include_related=["M1041", "M1015", "M1043", "M1028"])
    # answer states only two of the four required mitigations (structured claim)
    answer = SynthesizedAnswer(
        request="q",
        claims=[Claim(text="Mitigations include M1041, M1015.", entity_ids=("M1041", "M1015"))],
    )
    result = score_answer_coverage(entry, answer)
    assert result["gold"] == 4
    assert result["found"] == 2
    assert result["coverage"] == 0.5
    assert result["missing"] == ["M1028", "M1043"]


def test_answer_coverage_union_of_ids_and_related():
    """Gold pools must_include_ids and must_include_related together."""
    entry = _coverage_entry(must_include_ids=["T1003"], must_include_related=["M1041"])
    answer = SynthesizedAnswer(request="q", narrative="T1003 is mitigated by M1041.")
    result = score_answer_coverage(entry, answer)
    assert result["gold"] == 2
    assert result["coverage"] == 1.0


def test_answer_coverage_none_when_no_enumerable_gold():
    """Negatives / property-only entries have nothing to enumerate → None."""
    entry = _coverage_entry(expect_no_correlation=True, must_correlate=[])
    answer = SynthesizedAnswer(request="q", narrative="No correlation found.")
    assert score_answer_coverage(entry, answer) is None


def test_aggregate_reports_answer_completeness():
    """The roll-up surfaces micro/mean coverage so under-enumeration is visible."""
    entry = _coverage_entry(must_include_related=["M1041", "M1015", "M1043", "M1028"])
    evidence = make_evidence([make_result(records=[make_record("T1003")])])
    answer = verify_answer(
        SynthesizedAnswer(
            request="q", narrative="Mitigations include M1041 and M1015 only."
        ),
        evidence,
    )
    case = evaluate_case(entry, evidence, answer, kind="single")
    assert case.coverage["coverage"] == 0.5
    overall = aggregate([case], JudgeReport())
    assert overall["answer_completeness"]["entries"] == 1
    assert overall["answer_completeness"]["micro_coverage"] == 0.5


# -- evaluate_case + aggregate ----------------------------------------------


def test_evaluate_case_federated():
    evidence = _federated_evidence()
    answer = _federated_answer(evidence)
    case = evaluate_case(_entry(["T1021"]), evidence, answer, kind="federated")
    assert case.kind == "federated"
    assert case.category == "F-CTM"
    assert case.correlation["exact"] is True
    assert case.mapping_recall["recall"] == 1.0
    assert case.provenance["fully_provenanced"] is True


def test_aggregate_and_build_report():
    evidence = _federated_evidence()
    answer = _federated_answer(evidence)
    case = evaluate_case(_entry(["T1021"]), evidence, answer, kind="federated")
    judge = judge_run([("F-CTM-01", answer, evidence)], EvalConfig())
    overall = aggregate([case], judge)
    assert overall["cross_source_accuracy"]["exact_match"]["rate"] == 1.0
    assert overall["mapping_recall"]["micro_recall"] == 1.0
    assert overall["provenance_correctness"]["fully_provenanced"]["rate"] == 1.0
    assert overall["analyst_inspectability"]["mean_inspectability"] == 1.0
    assert overall["llm_judge"]["source"] == "deterministic"

    report = build_e2e([case], judge)
    assert report["cases"][0]["id"] == "F-CTM-01"
    assert "hard" in report["by_tier"]


def test_score_e2e_not_live_short_circuits():
    report = score_e2e(live=False)
    assert report["live"] is False
    assert report["cases"] == []


# -- live path (needs both backends up; skips otherwise) --------------------


@pytest.mark.live
@pytest.mark.integration
def test_score_e2e_live_subset():
    from utils.config import load_env

    load_env()
    from utils.specialists.tests.test_cypher_specialist import _neo4j_reachable
    from utils.specialists.tests.test_gremlin_specialist import _gremlin_reachable

    uri = os.environ.get("GREMLIN_URI", "ws://localhost:6455/gremlin")
    if not _neo4j_reachable() or not _gremlin_reachable(uri):
        pytest.skip("e2e live subset needs BOTH backends live")

    report = score_e2e(live=True, limit=2, include_single=True)
    assert report["live"] is True
    assert report["cases"]  # produced at least the federated pair
    overall = report["overall"]
    # The committed golden set passes the pass/fail suites, so the scored metrics
    # must sit at ceiling on this subset.
    assert overall["cross_source_accuracy"]["exact_match"]["rate"] == 1.0
    assert overall["mapping_recall"]["micro_recall"] == 1.0
    assert overall["provenance_correctness"]["fully_provenanced"]["rate"] == 1.0
    assert overall["analyst_inspectability"]["mean_inspectability"] == 1.0
