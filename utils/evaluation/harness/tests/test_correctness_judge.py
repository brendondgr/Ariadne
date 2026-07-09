#!/usr/bin/env python3
"""Correctness-judge tests (hermetic: no HTTP)."""

from __future__ import annotations

from utils.evaluation.harness.contracts import AnswerRecord
from utils.evaluation.harness.correctness_judge import (
    CorrectnessUnavailable,
    DeterministicCorrectness,
    HybridCorrectness,
    build_correctness_messages,
    grade_ids,
    judge_answers,
    parse_correctness,
)


def _record(**over) -> AnswerRecord:
    base = dict(
        question_id="A-MIT-01",
        set_name="attack",
        tier="easy",
        kind="single",
        source="attack",
        question="What mitigations for T1047?",
        narrative="Found 4 items related to T1047 (e.g. M1038, M1040, M1018).",
        claims=[{"text": "T1047 relates to M1038, M1040, M1018", "entity_ids": [], "citations": []}],
        produced_ids=["T1047", "M1038", "M1040", "M1018"],
        gold_expected_ids=["T1047", "M1018", "M1026", "M1038", "M1040"],
        gold_kind="ids",
    )
    base.update(over)
    return AnswerRecord(**base)


def test_grade_ids_partial_recall():
    g = grade_ids(_record())
    # 4 of 5 gold produced -> partial, recall 0.8
    assert g["label"] == "partial"
    assert round(g["id_recall"], 2) == 0.8
    assert g["missing_ids"] == ["M1026"]
    assert g["extra_ids"] == []


def test_grade_ids_full_recall_is_correct():
    rec = _record(produced_ids=["T1047", "M1018", "M1026", "M1038", "M1040"])
    g = grade_ids(rec)
    assert g["label"] == "correct"
    assert g["id_recall"] == 1.0


def test_grade_ids_zero_recall_is_incorrect():
    rec = _record(produced_ids=["T9999"])
    g = grade_ids(rec)
    assert g["label"] == "incorrect"
    assert g["id_recall"] == 0.0


def test_grade_ids_expect_empty_honest_abstention():
    rec = _record(expect_empty=True, gold_expected_ids=[], claims=[], produced_ids=[])
    g = grade_ids(rec)
    assert g["label"] == "correct"
    assert g["correctness"] == 1.0


def test_grade_ids_expect_empty_but_fabricated():
    rec = _record(
        expect_empty=True,
        gold_expected_ids=[],
        claims=[{"text": "T1047 relates to X"}],
        produced_ids=["T1047"],
    )
    g = grade_ids(rec)
    assert g["label"] == "incorrect"
    assert g["extra_ids"] == ["T1047"]


def test_grade_ids_run_failure_is_incorrect():
    rec = _record(error="RuntimeError: neo4j down")
    g = grade_ids(rec)
    assert g["label"] == "incorrect"
    assert "neo4j down" in g["rationale"]


def test_deterministic_grader_returns_verdict():
    verdict = DeterministicCorrectness().judge(_record())
    assert verdict.source == "deterministic"
    assert verdict.label == "partial"
    assert verdict.question_id == "A-MIT-01"


def test_build_messages_includes_key_and_answer():
    messages = build_correctness_messages(_record())
    assert messages[0]["role"] == "system"
    user = messages[1]["content"]
    assert "EXPECTED ANSWER KEY" in user
    assert "M1026" in user  # gold id present
    assert "What mitigations for T1047?" in user


def test_parse_correctness_keeps_id_math_deterministic():
    # LLM claims correctness but the id recall/precision must stay mechanical.
    verdict = parse_correctness(
        {"correctness": 0.9, "label": "correct", "rationale": "names the mitigations"},
        _record(),
    )
    assert verdict.source == "llm"
    assert verdict.correctness == 0.9
    assert verdict.label == "correct"
    assert round(verdict.id_recall, 2) == 0.8  # mechanical, not from the model
    assert verdict.missing_ids == ["M1026"]


def test_parse_correctness_derives_label_when_missing():
    v = parse_correctness({"correctness": 0.2}, _record())
    assert v.label == "incorrect"
    v2 = parse_correctness({"correctness": 0.95}, _record())
    assert v2.label == "correct"


def test_hybrid_falls_back_to_deterministic():
    class _Boom:
        name = "llm"

        def judge(self, record):
            raise CorrectnessUnavailable("endpoint down")

    hybrid = HybridCorrectness(_Boom(), DeterministicCorrectness())
    verdict = hybrid.judge(_record())
    assert verdict.source == "deterministic"
    assert hybrid.last_used == "deterministic"


def test_judge_answers_deterministic_batch():
    verdicts = judge_answers([_record(), _record()], use_llm=False)
    assert len(verdicts) == 2
    assert all(v.source == "deterministic" for v in verdicts)
