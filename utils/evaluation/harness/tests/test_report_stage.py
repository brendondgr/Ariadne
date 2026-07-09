#!/usr/bin/env python3
"""Reporter-agent tests (hermetic: synthetic judgments, no DB/LLM)."""

from __future__ import annotations

import json

from utils.evaluation.harness.contracts import (
    AnswerRecord,
    CorrectnessVerdict,
    write_jsonl,
)
from utils.evaluation.harness.report_stage import (
    ReporterAgent,
    build_report,
    render_markdown,
)


def _answer(qid, set_name, tier, source) -> AnswerRecord:
    return AnswerRecord(
        question_id=qid,
        set_name=set_name,
        tier=tier,
        kind="single" if set_name != "federated" else "federated",
        source=source,
        question=f"question {qid}",
    )


def _verdict(qid, correctness, label, source="llm", recall=1.0, precision=1.0) -> CorrectnessVerdict:
    return CorrectnessVerdict(
        question_id=qid,
        source=source,
        correctness=correctness,
        label=label,
        id_recall=recall,
        id_precision=precision,
    )


def _fixture():
    answers = {
        "A1": _answer("A1", "attack", "easy", "attack"),
        "A2": _answer("A2", "attack", "hard", "attack"),
        "C1": _answer("C1", "capec", "easy", "capec"),
        "F1": _answer("F1", "federated", "hard", "federated"),
    }
    verdicts = [
        _verdict("A1", 1.0, "correct"),
        _verdict("A2", 0.5, "partial"),
        _verdict("C1", 1.0, "correct", source="deterministic"),
        _verdict("F1", 0.0, "incorrect", recall=0.0, precision=0.0),
    ]
    return verdicts, answers


def test_build_report_aggregates_overall_and_groups():
    verdicts, answers = _fixture()
    report = build_report(verdicts, answers)
    o = report["overall"]
    assert o["n"] == 4
    assert o["correct"] == 2
    assert o["partial"] == 1
    assert o["incorrect"] == 1
    assert o["pass_rate"] == 0.5
    assert o["mean_correctness"] == 0.625  # (1+0.5+1+0)/4
    assert set(report["by_set"]) == {"attack", "capec", "federated"}
    assert report["by_set"]["attack"]["n"] == 2
    assert report["by_tier"]["hard"]["n"] == 2
    assert report["meta"]["llm_graded"] == 3


def test_worst_lists_non_correct_sorted():
    verdicts, answers = _fixture()
    report = build_report(verdicts, answers)
    worst = report["worst"]
    assert worst[0]["question_id"] == "F1"  # lowest correctness first
    assert all(w["label"] != "correct" for w in worst)


def test_render_markdown_has_sections():
    verdicts, answers = _fixture()
    md = render_markdown(build_report(verdicts, answers))
    assert "# Golden Evaluation" in md
    assert "## Overall" in md
    assert "## By set" in md
    assert "Pass rate" in md


def test_reporter_run_files_writes_both(tmp_path):
    verdicts, answers = _fixture()
    answers_path = str(tmp_path / "answers.jsonl")
    judgments_path = str(tmp_path / "judgments.jsonl")
    md_path = str(tmp_path / "golden-eval.md")
    json_path = str(tmp_path / "golden-eval.json")
    write_jsonl(answers_path, list(answers.values()))
    write_jsonl(judgments_path, verdicts)

    rc = ReporterAgent().run_files(answers_path, judgments_path, md_path, json_path)
    assert rc == 0
    data = json.load(open(json_path))
    assert data["overall"]["n"] == 4
    assert "# Golden Evaluation" in open(md_path).read()


def test_reporter_missing_judgments_errors(tmp_path):
    rc = ReporterAgent().run_files(
        str(tmp_path / "a.jsonl"),
        str(tmp_path / "nope.jsonl"),
        str(tmp_path / "r.md"),
        str(tmp_path / "r.json"),
    )
    assert rc == 1
