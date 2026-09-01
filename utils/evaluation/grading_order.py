#!/usr/bin/env python3
"""Counterbalanced grading order for paired judged comparisons.

**The problem this exists for, measured rather than assumed.**
EXP-2026-08-022 graded two conditions whose answers were byte-identical on 29 of
60 cases, in one session, old first and new second. Those identical answers came
back **0.0088 apart, consistently negative**. A fourth session with the order
reversed flipped the sign on both banks (+0.0071, +0.0167). **The condition
graded second scores about 0.01 lower, whichever condition it is.**

That is the same magnitude as several differences this project reports, so a
fixed-order paired comparison cannot resolve them and will systematically favour
whatever it grades first.

**EXP-2026-08-009's rule is necessary and not sufficient.** Grading every cell of
a comparison in one session cancels *between*-session drift — which it was
written for, and which EXP-2026-08-021 H7 confirmed by measurement — and it
*creates* within-session position bias. Both have to be handled, and they pull in
opposite directions: one wants everything together, the other wants order varied.

The resolution is to keep the single session and **counterbalance the order
inside it**, so each condition spends equal time in each position and the bias
cancels from the pooled estimate rather than loading onto one arm.
"""

from __future__ import annotations

from collections.abc import Sequence

__all__ = ["counterbalanced", "position_of"]


def counterbalanced(arms: Sequence[str], block: int) -> list[str]:
    """Arm order for one block (a bank, a pass — any repeated unit).

    Alternates the sequence on odd blocks, so over an even number of blocks every
    arm occupies each position equally often and the position effect cancels in
    the pooled mean.

    A rotation is deliberately *not* used. With two arms — the case that matters,
    because a paired comparison has two — rotation and reversal agree; with more,
    reversal keeps the first and last positions balanced, which is where the
    effect was measured, while a rotation spreads arms thinly across middle
    positions whose bias is unmeasured.

    >>> counterbalanced(["merged", "generic_composed"], 0)
    ['merged', 'generic_composed']
    >>> counterbalanced(["merged", "generic_composed"], 1)
    ['generic_composed', 'merged']
    """
    ordered = list(arms)
    return ordered if block % 2 == 0 else ordered[::-1]


def position_of(arm: str, arms: Sequence[str], block: int) -> int:
    """Zero-based position ``arm`` occupies in ``block``'s grading order.

    Recorded alongside each judgment so a comparison stays correctable after the
    fact even when the order was not counterbalanced — which is the situation
    every figure recorded before 2026-08-31 is in.
    """
    return counterbalanced(arms, block).index(arm)
