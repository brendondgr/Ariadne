#!/usr/bin/env python3
"""Counterbalancing must actually balance, or it is decoration.

EXP-2026-08-022 measured the bias this defends against: on byte-identical
answers, the condition graded second scored ~0.01 lower, and reversing the order
flipped the sign on both banks.
"""

from __future__ import annotations

from collections import Counter

from utils.evaluation.grading_order import counterbalanced, position_of

PAIR = ["merged", "generic_composed"]


def test_alternate_blocks_reverse():
    assert counterbalanced(PAIR, 0) == ["merged", "generic_composed"]
    assert counterbalanced(PAIR, 1) == ["generic_composed", "merged"]


def test_each_arm_holds_each_position_equally_over_even_blocks():
    seen = {a: Counter() for a in PAIR}
    for block in range(4):
        for pos, arm in enumerate(counterbalanced(PAIR, block)):
            seen[arm][pos] += 1
    for arm in PAIR:
        assert seen[arm][0] == seen[arm][1] == 2, f"{arm} is not balanced: {seen[arm]}"


def test_position_of_matches_the_order():
    assert position_of("merged", PAIR, 0) == 0
    assert position_of("merged", PAIR, 1) == 1


def test_more_than_two_arms_keeps_first_and_last_balanced():
    arms = ["a", "b", "c", "d"]
    first = Counter(counterbalanced(arms, b)[0] for b in range(2))
    last = Counter(counterbalanced(arms, b)[-1] for b in range(2))
    assert first == Counter({"a": 1, "d": 1})
    assert last == Counter({"d": 1, "a": 1})


def test_a_single_arm_is_unaffected():
    assert counterbalanced(["only"], 0) == counterbalanced(["only"], 1) == ["only"]
