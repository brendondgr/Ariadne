#!/usr/bin/env python3
"""Tests for the classifier over loss that survives complete retrieval."""

from __future__ import annotations

from utils.evaluation.answer_gap import classify


def _artifact(gold: list[str] | None = None) -> dict:
    return {
        "gold": {"assertions": {"must_include_ids": gold or []}},
        "logic_flow": {"results": []},
        "answer": {"claims": [], "narrative": ""},
    }


def _judgment(**kw) -> dict:
    base = {
        "correctness": 0.5,
        "faithfulness": 1.0,
        "groundedness": 1.0,
        "gold_expected": 0,
        "gold_present": 0,
        "abstained": False,
        "hallucinations": [],
    }
    base.update(kw)
    return base


def test_wrongful_abstention_takes_hard_precedence() -> None:
    """Declining while the evidence held the answer is categorical, not a degree."""
    reason = classify(
        _artifact(), _judgment(abstained=True, gold_expected=3, gold_present=0)
    )

    assert reason == "wrongful_abstention"


def test_under_enumeration_beats_a_small_faithfulness_deduction() -> None:
    """One defect must not be filed under its own symptom.

    H-PRE-01 states 1 of 4 gold ids and carries a 0.1 faithfulness deduction. A
    fixed ladder ranking unfaithful first would file a 0.75 failure under a 0.1
    one, and the fix list would point at the wrong thing.
    """
    reason = classify(
        _artifact(), _judgment(gold_expected=4, gold_present=1, faithfulness=0.9)
    )

    assert reason == "under_enumeration"


def test_a_large_faithfulness_deficit_still_wins() -> None:
    """Ranking by magnitude cuts both ways."""
    reason = classify(
        _artifact(), _judgment(gold_expected=4, gold_present=4, faithfulness=0.3)
    )

    assert reason == "unfaithful"


def test_groundedness_is_named_when_it_dominates() -> None:
    reason = classify(
        _artifact(), _judgment(gold_expected=2, gold_present=2, groundedness=0.4)
    )

    assert reason == "ungrounded"


def test_a_clean_answer_scoring_below_one_is_judge_nuance() -> None:
    """No observable deficit means presentation or judge disagreement, not a bug."""
    reason = classify(_artifact(), _judgment(gold_expected=3, gold_present=3))

    assert reason == "judge_nuance"


def test_a_hallucination_registers_even_at_full_faithfulness() -> None:
    """A recorded hallucination is a defect the faithfulness score may not show."""
    reason = classify(
        _artifact(),
        _judgment(gold_expected=1, gold_present=1, hallucinations=[{"text": "x"}]),
    )

    assert reason == "unfaithful"
