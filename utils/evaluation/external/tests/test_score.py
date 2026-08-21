#!/usr/bin/env python3
"""The scorer, which is the whole reason this experiment needs no grader.

Every number EXP-2026-08-010 reports comes out of this module, so its failure
modes are worth more than its happy path: an identifier form it silently
mis-reads becomes a system defect in the write-up.
"""

from __future__ import annotations

import pytest

from utils.evaluation.external.score import Score, extract_ids, pool, to_parents


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("T1047", {"T1047"}),
        ("T1027.001 and T1027", {"T1027.001", "T1027"}),
        # A tactic is not a technique. Reading TA0009 as T0009 would invent an
        # identifier that is not in the answer at all.
        ("TA0009: Collection", {"TA0009"}),
        ("'S0066: 3PARA RAT', 'G0034: Sandworm'", {"S0066", "G0034"}),
        ("C0028 and M1017 and DS0009", {"C0028", "M1017", "DS0009"}),
        ("no identifiers here", set()),
        ("", set()),
    ],
)
def test_the_extractor_reads_each_identifier_form(text: str, expected: set[str]) -> None:
    assert extract_ids(text) == expected


@pytest.mark.parametrize("text", ["T104", "T104777", "XT1047", "T1047.0001"])
def test_a_near_miss_is_not_an_identifier(text: str) -> None:
    """Loose boundaries would credit an arm for a number that means nothing."""
    assert extract_ids(text) == set() or text not in extract_ids(text)


def test_sub_techniques_roll_up_to_parents() -> None:
    assert to_parents({"T1027.001", "T1027.002", "T1083"}) == {"T1027", "T1083"}


def test_a_perfect_answer_scores_one_everywhere() -> None:
    s = Score(frozenset({"T1", "T2"}), frozenset({"T1", "T2"}))
    assert (s.recall, s.precision, s.f1, s.exact) == (1.0, 1.0, 1.0, True)


def test_an_over_broad_answer_keeps_recall_and_loses_precision() -> None:
    """The version-drift signature: everything gold, plus more."""
    s = Score(frozenset({"T1", "T2"}), frozenset({"T1", "T2", "T3", "T4"}))
    assert s.recall == 1.0
    assert s.precision == 0.5
    assert not s.exact


def test_an_empty_answer_scores_zero_rather_than_raising() -> None:
    s = Score(frozenset({"T1"}), frozenset())
    assert (s.recall, s.precision, s.f1) == (0.0, 0.0, 0.0)


def test_macro_and_micro_disagree_when_item_sizes_do() -> None:
    """Why both are reported. One item with 1 gold id, one with 9.

    The small item is answered perfectly and the large one not at all. Macro
    calls that 0.5; micro calls it 0.1. Quoting either alone misreports a
    long-tailed benchmark, and both benchmarks here are long-tailed.
    """
    rolled = pool([
        Score(frozenset({"T1"}), frozenset({"T1"})),
        Score(frozenset(f"T{n}" for n in range(10, 19)), frozenset()),
    ])
    assert rolled["macro_recall"] == 0.5
    assert rolled["micro_recall"] == 0.1
    assert rolled["exact_match"] == 0.5


def test_an_empty_pool_reports_nothing_rather_than_zero() -> None:
    """A cell that did not run must not look like a cell that scored zero."""
    assert pool([]) == {"n": 0}
