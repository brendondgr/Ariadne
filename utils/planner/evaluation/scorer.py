#!/usr/bin/env python3
"""Plan-level scoring.

Scores a produced ``Plan`` against an ``ExpectedCase`` using metrics that look
only at the plan (not at any eventual downstream answer):

* source-selection precision / recall (did it pick the right sources?)
* unnecessary source calls (sources targeted that should not be)
* sub-question quality = expected-entity recall (did sub-questions name the
  entities the answer needs?)
* schema adherence = did the plan pass the deterministic gate?
* honesty = did it correctly mark unsupported / partial when expected?

This isolates the planner from the phases after it (briefing §6.1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..cards import SourceCardView
from ..discovery import LiveSourceView
from ..gate import evaluate
from ..schema import Plan

if TYPE_CHECKING:
    from .corpus import ExpectedCase


def _safe_div(num: float, den: float) -> float:
    return num / den if den else 1.0


@dataclass
class CaseScore:
    """The plan-level metrics for one case."""

    name: str
    split: str
    origin: str
    tier: str
    source_precision: float
    source_recall: float
    unnecessary_source_calls: int
    missing_sources: list[str]
    entity_recall: float
    schema_adherent: bool
    join_correct: bool
    unsupported_correct: bool
    partial_correct: bool
    # Sub-question-quality decomposition: does the plan break the request into
    # the right number of sub-questions, each routed to the right source, with
    # the cross-source dependency declared when the question is multi-hop?
    sub_question_count: int = 0
    expected_sub_question_count: int = 0
    count_correct: bool = True
    routing_correct: bool = True
    dependency_correct: bool = True
    decomposition_score: float = 1.0
    sub_question_quality: float = 1.0
    gate_reasons: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """A case passes when the planner is correct on the load-bearing axes:
        no expected source missed, every expected entity well covered, the plan
        is schema-adherent, and the honesty flags match."""
        return (
            self.source_recall >= 1.0
            and self.entity_recall >= 0.6
            and self.schema_adherent
            and self.join_correct
            and self.unsupported_correct
            and self.partial_correct
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "split": self.split,
            "origin": self.origin,
            "tier": self.tier,
            "passed": self.passed,
            "source_precision": round(self.source_precision, 3),
            "source_recall": round(self.source_recall, 3),
            "unnecessary_source_calls": self.unnecessary_source_calls,
            "missing_sources": self.missing_sources,
            "entity_recall": round(self.entity_recall, 3),
            "schema_adherent": self.schema_adherent,
            "join_correct": self.join_correct,
            "unsupported_correct": self.unsupported_correct,
            "partial_correct": self.partial_correct,
            "sub_question_count": self.sub_question_count,
            "expected_sub_question_count": self.expected_sub_question_count,
            "count_correct": self.count_correct,
            "routing_correct": self.routing_correct,
            "dependency_correct": self.dependency_correct,
            "decomposition_score": round(self.decomposition_score, 3),
            "sub_question_quality": round(self.sub_question_quality, 3),
            "gate_reasons": self.gate_reasons,
        }


def score_plan(
    plan: Plan,
    case: "ExpectedCase",
    cards: dict[str, SourceCardView],
    live_view: LiveSourceView,
) -> CaseScore:
    selected = plan.target_sources()
    expected = set(case.expected_sources)

    true_positives = selected & expected
    source_precision = _safe_div(len(true_positives), len(selected)) if selected else (1.0 if not expected else 0.0)
    source_recall = _safe_div(len(true_positives), len(expected)) if expected else 1.0
    unnecessary = sorted(selected - expected)
    missing = sorted(expected - selected)

    # entity recall: of the entities the case expects per source, how many did
    # the plan's sub-questions for that source actually name?
    recalls: list[float] = []
    for source, expected_entities in case.expected_entities.items():
        want = set(expected_entities)
        if not want:
            continue
        got: set[str] = set()
        for sq in plan.sub_questions:
            if sq.source == source:
                got.update(sq.entities)
        recalls.append(len(want & got) / len(want))
    entity_recall = sum(recalls) / len(recalls) if recalls else 1.0

    gate = evaluate(plan, cards, live_view)
    has_join = bool(plan.joins)
    join_correct = has_join == case.expects_join
    unsupported_correct = bool(plan.unsupported) == case.expects_unsupported
    partial_correct = plan.partial == case.expects_partial

    # Sub-question-quality decomposition. The expected count defaults to one
    # sub-question per expected source (a single-source question decomposes to
    # one, the federated question to two); a case may override it explicitly.
    sub_question_count = len(plan.sub_questions)
    expected_count = (
        case.expected_sub_question_count
        if case.expected_sub_question_count is not None
        else len(expected)
    )
    routed = {sq.source for sq in plan.sub_questions}
    count_correct = sub_question_count == expected_count
    routing_correct = routed == expected
    dependency_correct = has_join == case.expects_join
    decomposition_score = (
        int(count_correct) + int(routing_correct) + int(dependency_correct)
    ) / 3.0
    sub_question_quality = (entity_recall + decomposition_score) / 2.0

    return CaseScore(
        name=case.name,
        split=case.split,
        origin=case.origin,
        tier=case.tier,
        source_precision=source_precision,
        source_recall=source_recall,
        unnecessary_source_calls=len(unnecessary),
        missing_sources=missing,
        entity_recall=entity_recall,
        schema_adherent=gate.ok,
        join_correct=join_correct,
        unsupported_correct=unsupported_correct,
        partial_correct=partial_correct,
        sub_question_count=sub_question_count,
        expected_sub_question_count=expected_count,
        count_correct=count_correct,
        routing_correct=routing_correct,
        dependency_correct=dependency_correct,
        decomposition_score=decomposition_score,
        sub_question_quality=sub_question_quality,
        gate_reasons=gate.reasons,
    )


def aggregate(scores: list[CaseScore]) -> dict:
    """Aggregate per-case scores into corpus-level metrics."""
    if not scores:
        return {"cases": 0}
    n = len(scores)
    return {
        "cases": n,
        "passed": sum(1 for s in scores if s.passed),
        "pass_rate": round(sum(1 for s in scores if s.passed) / n, 3),
        "mean_source_precision": round(sum(s.source_precision for s in scores) / n, 3),
        "mean_source_recall": round(sum(s.source_recall for s in scores) / n, 3),
        "mean_entity_recall": round(sum(s.entity_recall for s in scores) / n, 3),
        "mean_sub_question_quality": round(
            sum(s.sub_question_quality for s in scores) / n, 3
        ),
        "mean_decomposition_score": round(
            sum(s.decomposition_score for s in scores) / n, 3
        ),
        "routing_accuracy_rate": round(sum(1 for s in scores if s.routing_correct) / n, 3),
        "count_accuracy_rate": round(sum(1 for s in scores if s.count_correct) / n, 3),
        "dependency_accuracy_rate": round(
            sum(1 for s in scores if s.dependency_correct) / n, 3
        ),
        "total_unnecessary_source_calls": sum(s.unnecessary_source_calls for s in scores),
        "schema_adherence_rate": round(sum(1 for s in scores if s.schema_adherent) / n, 3),
        "honesty_rate": round(
            sum(1 for s in scores if s.unsupported_correct and s.partial_correct) / n, 3
        ),
    }
