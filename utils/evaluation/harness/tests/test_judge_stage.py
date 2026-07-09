#!/usr/bin/env python3
"""Judge-agent tests (hermetic: deterministic backstop, no HTTP)."""

from __future__ import annotations

import types

from utils.evaluation.harness.contracts import (
    AnswerRecord,
    CorrectnessVerdict,
    read_jsonl,
    write_jsonl,
)
from utils.evaluation.harness.judge_stage import JudgeAgent


def _answer(qid: str, produced, gold) -> AnswerRecord:
    return AnswerRecord(
        question_id=qid,
        set_name="attack",
        tier="easy",
        kind="single",
        source="attack",
        question="q?",
        claims=[{"text": " ".join(produced)}],
        produced_ids=list(produced),
        gold_expected_ids=list(gold),
        gold_kind="ids",
    )


def test_judge_agent_grades_batch_deterministic(tmp_path):
    answers = str(tmp_path / "answers.jsonl")
    judgments = str(tmp_path / "judgments.jsonl")
    write_jsonl(
        answers,
        [
            _answer("A1", ["T1", "M1"], ["T1", "M1"]),  # full recall -> correct
            _answer("A2", ["T1"], ["T1", "M1"]),          # partial
            _answer("A3", ["X9"], ["T1"]),                # incorrect
        ],
    )
    rc = JudgeAgent(use_llm=False).run_files(answers, judgments)
    assert rc == 0
    verdicts = [CorrectnessVerdict.from_dict(d) for d in read_jsonl(judgments)]
    by_id = {v.question_id: v for v in verdicts}
    assert by_id["A1"].label == "correct"
    assert by_id["A2"].label == "partial"
    assert by_id["A3"].label == "incorrect"
    assert all(v.source == "deterministic" for v in verdicts)


def test_judge_agent_missing_answers_returns_error(tmp_path):
    rc = JudgeAgent().run_files(str(tmp_path / "nope.jsonl"), str(tmp_path / "out.jsonl"))
    assert rc == 1


def test_judge_agent_empty_answers_writes_empty(tmp_path):
    answers = str(tmp_path / "answers.jsonl")
    judgments = str(tmp_path / "judgments.jsonl")
    write_jsonl(answers, [])
    rc = JudgeAgent().run_files(answers, judgments)
    assert rc == 0
    assert list(read_jsonl(judgments)) == []


def test_from_args_enables_llm_config():
    args = types.SimpleNamespace(llm=True, judge_sample=5)
    agent = JudgeAgent.from_args(args)
    assert agent._use_llm is True
    assert agent._config.llm_enabled is True
    assert agent._sample_size == 5
