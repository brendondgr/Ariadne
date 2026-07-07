#!/usr/bin/env python3
"""Hermetic tests for the e2e report builders.

The JSON/Markdown builders must be pure and byte-stable given fixed input (the
reproducibility guarantee the LLM-off build relies on), and the hermetic
``live=False`` path must still produce a valid, honest report.
"""

from __future__ import annotations

from utils.evaluation.e2e_report import (
    build_json,
    build_markdown,
    collect_e2e,
    _diagnose,
)
from utils.evaluation.llm_judge import EvalConfig, judge_run
from utils.evaluation.score_e2e import build_e2e, evaluate_case
from utils.synthesis.contracts import Citation, Claim, SynthesizedAnswer
from utils.synthesis.tests._fixtures import make_evidence, make_record, make_result
from utils.synthesis.verifier import verify_answer

_META = {"attack_version": "19.0", "capec_version": "3.9", "generated_note": "test"}


def _one_case_report():
    attack = make_result(
        sub_question_id="q2", records=[make_record("T1021", join_values=("T1021",))]
    )
    capec = make_result(
        source="capec",
        sub_question_id="q1",
        records=[
            make_record("CAPEC-555", source="capec", label="AttackPattern",
                        join_values=("T1021",))
        ],
    )
    evidence = make_evidence([attack, capec])
    claim = Claim(
        text="T1021 corroborated across sources.",
        citations=(
            Citation(source="attack", primary_id="T1021"),
            Citation(source="capec", primary_id="CAPEC-555"),
        ),
        entity_ids=("T1021",),
        kind="correlation",
        sub_question_id="q2",
    )
    answer = verify_answer(SynthesizedAnswer(request="q", claims=[claim]), evidence)
    entry = {"id": "F-CTM-01", "tier": "hard", "assertions": {"must_correlate": ["T1021"]}}
    case = evaluate_case(entry, evidence, answer, kind="federated")
    judge = judge_run([("F-CTM-01", answer, evidence)], EvalConfig())
    return build_e2e([case], judge)


def test_build_json_shape():
    data = build_json(_one_case_report(), _META)
    assert set(data) == {"meta", "definitions", "e2e", "diagnosis"}
    assert "cross_source_answer_accuracy" in data["definitions"]
    assert data["e2e"]["overall"]["mapping_recall"]["micro_recall"] == 1.0


def test_markdown_is_pure_and_stable():
    data = build_json(_one_case_report(), _META)
    md1 = build_markdown(data)
    md2 = build_markdown(data)
    assert md1 == md2  # byte-stable
    assert "# End-to-End Evaluation" in md1
    assert "Cross-source answer accuracy" in md1
    assert "LLM Evaluator (judge)" in md1
    assert "deterministic proxy — reproducible" in md1  # off by default


def test_diagnose_flags_missing_mapping():
    e2e = _one_case_report()
    # Corrupt the aggregate to simulate a mapping miss.
    e2e["overall"]["mapping_recall"] = {
        "micro_recall": 0.5, "gold_mappings": 2, "found_mappings": 1,
    }
    findings = _diagnose(e2e)
    assert any("mapping recall" in f.lower() for f in findings)


def test_hermetic_report_is_valid():
    e2e = collect_e2e(live=False)
    data = build_json(e2e, {"attack_version": "19.0", "capec_version": "3.9",
                            "generated_note": "hermetic-only (nothing scored)"})
    md = build_markdown(data)
    assert "Hermetic run" in md
    assert data["e2e"]["live"] is False
