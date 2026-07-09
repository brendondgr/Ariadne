#!/usr/bin/env python3
"""Round-trip and IO tests for the harness contracts (hermetic, no DB/LLM)."""

from __future__ import annotations

from utils.evaluation.harness.contracts import (
    AnswerRecord,
    CorrectnessVerdict,
    read_jsonl,
    write_jsonl,
)


def _sample_answer() -> AnswerRecord:
    return AnswerRecord(
        question_id="A-MIT-01",
        set_name="attack",
        tier="easy",
        kind="single",
        source="attack",
        question="What mitigations does ATT&CK list for T1047?",
        narrative="T1047 is mitigated by M1018, M1026.",
        claims=[
            {
                "text": "T1047 is mitigated by M1018",
                "entity_ids": ["T1047", "M1018"],
                "kind": "fact",
                "citations": [{"source": "attack", "primary_id": "T1047"}],
            }
        ],
        abstentions=[],
        produced_ids=["T1047", "M1018"],
        gold_expected_ids=["M1018", "M1026", "M1038", "M1040"],
        gold_kind="ids",
        expect_empty=False,
        exit_code=0,
        timings={"total": 1.2},
    )


def test_answer_record_round_trips_through_dict():
    record = _sample_answer()
    restored = AnswerRecord.from_dict(record.to_dict())
    assert restored == record


def test_verdict_round_trips_and_rounds():
    verdict = CorrectnessVerdict(
        question_id="A-MIT-01",
        source="llm",
        correctness=0.755555,
        label="partial",
        id_recall=0.5,
        id_precision=1.0,
        missing_ids=["M1038", "M1040"],
        extra_ids=[],
        rationale="Half the mitigations surfaced.",
    )
    data = verdict.to_dict()
    assert data["correctness"] == 0.7556  # rounded to 4 dp
    restored = CorrectnessVerdict.from_dict(data)
    assert restored.label == "partial"
    assert restored.missing_ids == ["M1038", "M1040"]


def test_jsonl_write_then_read(tmp_path):
    path = str(tmp_path / "answers.jsonl")
    records = [_sample_answer(), _sample_answer()]
    written = write_jsonl(path, records)
    assert written == 2
    rows = list(read_jsonl(path))
    assert len(rows) == 2
    assert rows[0]["question_id"] == "A-MIT-01"
    # dicts are passed through untouched by write_jsonl
    assert AnswerRecord.from_dict(rows[1]).produced_ids == ["T1047", "M1018"]


def test_jsonl_creates_parent_dirs(tmp_path):
    path = str(tmp_path / "nested" / "deep" / "verdicts.jsonl")
    write_jsonl(path, [CorrectnessVerdict(question_id="x", source="deterministic")])
    assert len(list(read_jsonl(path))) == 1
