"""Fixture tests for Step 7's scoring and item builders (EXP-2026-11-013)."""

from __future__ import annotations

from utils.decision import score as S
from utils.decision.items import NONE, Item


def test_wrong_at_coverage_keeps_the_most_confident_items():
    rows = [("a", 0.9, "a"), ("b", 0.8, "a"), ("a", 0.7, "a"), ("a", 0.6, "b")]
    assert S.wrong_at_coverage(rows, 0.5) == 0.5      # top two: one right, one wrong
    assert S.wrong_at_coverage(rows, 0.25) == 0.0
    assert S.wrong_at_coverage(rows, 1.0) == 0.5


def test_threshold_is_the_lowest_one_within_the_target():
    rows = [("a", 0.99, "a")] * 19 + [("b", 0.98, "a")] + [("b", 0.5, "a")] * 5
    assert S.threshold_for(rows, 0.05) == 0.98            # 1 wrong in 20 = 0.05
    assert S.threshold_for([("b", 0.9, "a")], 0.05) == float("inf")


def test_ties_are_kept_or_dropped_together():
    rows = [("a", 0.9, "a"), ("b", 0.9, "a"), ("a", 0.9, "a")]
    assert S.threshold_for(rows, 0.05) == float("inf")    # can't keep two of three tied items


def test_auroc_and_ece():
    assert S.auroc([("a", 0.9, "a"), ("b", 0.2, "a")]) == 1.0
    assert S.auroc([("a", 0.2, "a"), ("b", 0.9, "a")]) == 0.0
    assert S.ece([("a", 1.0, "a"), ("b", 0.0, "a")]) == 0.0


def test_transfer_and_roles():
    good = {f"g{i}": [("a", 0.95, "a")] for i in range(100)}
    t = S.transfer(good, splits=20)
    assert t["coverage_median"] == 1.0 and t["wrong_median"] == 0.0
    assert S.role(t, 0.0, None, 1.0, 1.0) == "alone"
    assert S.role(t, 0.0, None, 1.0, 1.0, cap="gate") == "gate"
    assert S.role(t, 0.2, 0.9, 0.9, 1.0) == "second opinion"     # flips too much for a gate
    bad = {f"g{i}": [("b", 0.95, "a")] for i in range(100)}
    tb = S.transfer(bad, splits=20)
    assert S.role(tb, 0.0, None, 0.0, 1.0) == "not used"


def test_none_precision_recall():
    rows = [(NONE, 0.9, NONE), (NONE, 0.8, "a"), ("a", 0.7, NONE), ("a", 0.9, "a")]
    assert S.none_pr(rows) == {"precision": 0.5, "recall": 0.5, "predicted": 2, "gold": 2}


def test_item_orders_differ_and_keep_none_last():
    it = Item(id="x", decision="D4", group="g", stratum="s", context="", question="", prompt="",
              options={"a": "A", "b": "B", "c": "C", NONE: "none"}, gold="a")
    o1, o2 = it.orders()
    assert o1 != o2 and o1[-1] == NONE and o2[-1] == NONE and sorted(o1) == sorted(o2)
