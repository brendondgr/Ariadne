#!/usr/bin/env python3
"""Persisted contracts for the golden-evaluation harness.

The three agents are decoupled: they only share these JSON-serialisable
dataclasses and the JSONL files that carry them between stages. Keeping the IO
here means the runner, judge, and reporter never import one another.

* ``AnswerRecord``      one golden question run through the pipeline (persisted
                        by the runner, consumed by the judge and reporter).
* ``CorrectnessVerdict`` one correctness ruling on one answer (persisted by the
                        judge, consumed by the reporter).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Iterator

# Correctness labels, ordered best -> worst.
LABELS = ("correct", "partial", "incorrect")


@dataclass
class AnswerRecord:
    """A single golden question after it was run through the pipeline.

    ``produced_ids`` is precomputed (the union of every rendered claim's
    ``entity_ids`` and citation ``primary_id``) so the judge can score id
    recall/precision without re-deriving it, and the record stays self-contained.
    """

    question_id: str
    set_name: str  # "attack" | "capec" | "federated"
    tier: str
    kind: str  # "single" | "federated"
    source: str  # "attack" | "capec" | "federated"
    question: str
    narrative: str = ""
    claims: list[dict[str, Any]] = field(default_factory=list)
    abstentions: list[dict[str, Any]] = field(default_factory=list)
    produced_ids: list[str] = field(default_factory=list)
    gold_expected_ids: list[str] = field(default_factory=list)
    gold_kind: str = "ids"  # "ids" | "correlate"
    expect_empty: bool = False
    exit_code: int | None = None
    timings: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "set_name": self.set_name,
            "tier": self.tier,
            "kind": self.kind,
            "source": self.source,
            "question": self.question,
            "narrative": self.narrative,
            "claims": self.claims,
            "abstentions": self.abstentions,
            "produced_ids": list(self.produced_ids),
            "gold_expected_ids": list(self.gold_expected_ids),
            "gold_kind": self.gold_kind,
            "expect_empty": self.expect_empty,
            "exit_code": self.exit_code,
            "timings": self.timings,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AnswerRecord":
        return cls(
            question_id=data["question_id"],
            set_name=data["set_name"],
            tier=data.get("tier", ""),
            kind=data.get("kind", "single"),
            source=data.get("source", ""),
            question=data.get("question", ""),
            narrative=data.get("narrative", ""),
            claims=list(data.get("claims", [])),
            abstentions=list(data.get("abstentions", [])),
            produced_ids=list(data.get("produced_ids", [])),
            gold_expected_ids=list(data.get("gold_expected_ids", [])),
            gold_kind=data.get("gold_kind", "ids"),
            expect_empty=bool(data.get("expect_empty", False)),
            exit_code=data.get("exit_code"),
            timings=dict(data.get("timings", {})),
            error=data.get("error"),
        )


@dataclass(frozen=True)
class CorrectnessVerdict:
    """One correctness ruling on one answer, graded against the golden answer.

    ``correctness`` is a float in ``[0, 1]``; ``label`` is one of ``LABELS``.
    ``id_recall`` / ``id_precision`` are the deterministic backstop even when the
    ``source`` is ``"llm"`` (the LLM sets ``correctness``/``label``/``rationale``;
    the id math is always computed mechanically so it is never model-invented).
    """

    question_id: str
    source: str  # "deterministic" | "llm"
    correctness: float = 0.0
    label: str = "incorrect"
    id_recall: float = 0.0
    id_precision: float = 0.0
    missing_ids: list[str] = field(default_factory=list)
    extra_ids: list[str] = field(default_factory=list)
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "source": self.source,
            "correctness": round(self.correctness, 4),
            "label": self.label,
            "id_recall": round(self.id_recall, 4),
            "id_precision": round(self.id_precision, 4),
            "missing_ids": list(self.missing_ids),
            "extra_ids": list(self.extra_ids),
            "rationale": self.rationale,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CorrectnessVerdict":
        return cls(
            question_id=data["question_id"],
            source=data.get("source", "deterministic"),
            correctness=float(data.get("correctness", 0.0)),
            label=data.get("label", "incorrect"),
            id_recall=float(data.get("id_recall", 0.0)),
            id_precision=float(data.get("id_precision", 0.0)),
            missing_ids=list(data.get("missing_ids", [])),
            extra_ids=list(data.get("extra_ids", [])),
            rationale=data.get("rationale", ""),
        )


def write_jsonl(path: str, records: Iterable[Any]) -> int:
    """Write dataclass records (anything with ``to_dict``) as one JSON per line.

    Returns the number of rows written. Creates parent directories as needed.
    """
    import os

    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    count = 0
    with open(path, "w", encoding="utf-8") as handle:
        for record in records:
            payload = record.to_dict() if hasattr(record, "to_dict") else record
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
            count += 1
    return count


def read_jsonl(path: str) -> Iterator[dict[str, Any]]:
    """Yield each non-blank line of a JSONL file as a parsed dict."""
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)
