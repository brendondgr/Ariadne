#!/usr/bin/env python3
"""Hermetic tests for the deterministic proxy judge.

The proxy must produce stable, reproducible scores from evidence alone and
double as a cross-check on the verifier. These tests use the same in-memory
fixtures the synthesis verifier tests use — real contracts, no database.
"""

from __future__ import annotations

from utils.evaluation.llm_judge import DeterministicJudge, EvalConfig, judge_run
from utils.synthesis.contracts import Citation, Claim, SynthesizedAnswer
from utils.synthesis.tests._fixtures import make_evidence, make_record, make_result
from utils.synthesis.verifier import verify_answer


def _clean_answer_and_evidence():
    record = make_record(
        "T1047",
        name="Windows Management Instrumentation",
        related=[{"id": "M1038", "name": "Execution Prevention"}],
    )
    evidence = make_evidence([make_result(records=[record], summary="T1047 found.")])
    claim = Claim(
        text="T1047 is mitigated by M1038.",
        citations=(Citation(source="attack", primary_id="T1047"),),
        entity_ids=("T1047", "M1038"),
    )
    answer = verify_answer(SynthesizedAnswer(request="q", claims=[claim]), evidence)
    return answer, evidence


def test_clean_answer_scores_perfect():
    answer, evidence = _clean_answer_and_evidence()
    verdict = DeterministicJudge().judge("q1", answer, evidence)
    assert verdict.source == "deterministic"
    assert verdict.faithfulness == 1.0
    assert verdict.groundedness == 1.0
    assert verdict.evidence_sufficiency == 1.0
    assert verdict.unsupported_claim_rate == 0.0


def test_unsupported_claim_lowers_faithfulness():
    record = make_record("T1047")
    evidence = make_evidence([make_result(records=[record])])
    good = Claim(
        text="T1047 found.",
        citations=(Citation(source="attack", primary_id="T1047"),),
        entity_ids=("T1047",),
    )
    bad = Claim(  # fabricated mitigation — verifier will cut it
        text="T1047 mitigated by M9999.",
        citations=(Citation(source="attack", primary_id="T1047"),),
        entity_ids=("M9999",),
    )
    answer = verify_answer(
        SynthesizedAnswer(request="q", claims=[good, bad]), evidence
    )
    verdict = DeterministicJudge().judge("q1", answer, evidence)
    assert verdict.faithfulness == 0.5
    assert verdict.unsupported_claim_rate == 0.5
    # Only the supported claim is rendered, so groundedness of the shown answer
    # stays perfect.
    assert verdict.groundedness == 1.0


def test_unused_evidence_lowers_sufficiency():
    used = make_result(sub_question_id="q1", records=[make_record("T1047")])
    ignored = make_result(  # ran ok, returned records, but no claim uses it
        source="capec",
        sub_question_id="q2",
        records=[make_record("CAPEC-555", source="capec", label="AttackPattern")],
    )
    evidence = make_evidence([used, ignored])
    claim = Claim(
        text="T1047 found.",
        citations=(Citation(source="attack", primary_id="T1047"),),
        entity_ids=("T1047",),
        sub_question_id="q1",
    )
    answer = verify_answer(SynthesizedAnswer(request="q", claims=[claim]), evidence)
    verdict = DeterministicJudge().judge("q1", answer, evidence)
    assert verdict.evidence_sufficiency == 0.5  # 1 of 2 answerable results used


def test_honest_abstention_is_fully_sufficient():
    empty = make_result(sub_question_id="q1", records=[], ok=True, query="MATCH ...")
    evidence = make_evidence([empty])
    answer = verify_answer(SynthesizedAnswer(request="q", claims=[]), evidence)
    verdict = DeterministicJudge().judge("q1", answer, evidence)
    assert verdict.faithfulness == 1.0  # nothing asserted → nothing false
    assert verdict.evidence_sufficiency == 1.0
    assert verdict.groundedness == 1.0


def test_proxy_is_reproducible():
    answer, evidence = _clean_answer_and_evidence()
    a = DeterministicJudge().judge("q1", answer, evidence).to_dict()
    b = DeterministicJudge().judge("q1", answer, evidence).to_dict()
    assert a == b


def test_judge_run_off_by_default_uses_proxy():
    answer, evidence = _clean_answer_and_evidence()
    report = judge_run([("q1", answer, evidence)], EvalConfig())
    assert report.source == "deterministic"
    assert report.llm_covered == 0
    assert report.to_dict()["mean_faithfulness"] == 1.0
    assert report.to_dict()["answers_scored"] == 1
