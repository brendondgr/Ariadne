"""Scoring for EXP-2026-11-013 (Era 2, Step 7): the same measurements for every decision.

Inputs are the items and one record per (item, arm, order) with the arm's
probabilities. Every function here is pure, so the fixture tests pin it.

The role rule (agreed with the operator, PROTOCOL "The role rule"):
- alone:  median test coverage >= 0.70, median test wrong <= 0.05,
          90th-percentile test wrong <= 0.075, flip rate <= 0.05;
- gate:   not alone; the threshold region holds (median test wrong <= 0.05)
          at median coverage >= 0.20, flip rate <= 0.10;
- second opinion: AUROC of confidence (right vs wrong) >= 0.70 and accuracy
          >= 0.8 x the baseline's;
- not used: otherwise.
"""

from __future__ import annotations

import random
from collections import defaultdict
from statistics import median
from typing import Any, Iterable

WRONG_TARGET = 0.05


def top_of(probs: dict[str, float]) -> tuple[str | None, float]:
    if not probs or max(probs.values()) <= 0:
        return None, 0.0
    k = max(probs, key=lambda x: (probs[x], x))
    return k, probs[k]


def accuracy(rows: list[tuple[str | None, float, str]]) -> float | None:
    """rows: (prediction, confidence, gold)."""
    return round(sum(p == g for p, _, g in rows) / len(rows), 4) if rows else None


def ece(rows: list[tuple[str | None, float, str]], bins: int = 10) -> float | None:
    if not rows:
        return None
    b: dict[int, list] = defaultdict(list)
    for p, c, g in rows:
        b[min(bins - 1, int(c * bins))].append((c, p == g))
    return round(sum(len(v) / len(rows) * abs(sum(c for c, _ in v) / len(v) - sum(r for _, r in v) / len(v))
                     for v in b.values()), 4)


def wrong_at_coverage(rows: list[tuple[str | None, float, str]], coverage: float) -> float | None:
    if not rows:
        return None
    n = max(1, round(coverage * len(rows)))
    kept = sorted(rows, key=lambda r: -r[1])[:n]
    return round(sum(p != g for p, _, g in kept) / n, 4)


def auroc(rows: list[tuple[str | None, float, str]]) -> float | None:
    """How well confidence separates right answers from wrong ones (0.5 = not at all)."""
    pos = [c for p, c, g in rows if p == g]
    neg = [c for p, c, g in rows if p != g]
    if not pos or not neg:
        return None
    wins = sum((a > b) + 0.5 * (a == b) for a in pos for b in neg)
    return round(wins / (len(pos) * len(neg)), 4)


def none_pr(rows: list[tuple[str | None, float, str]], none: str = "none") -> dict[str, float | None]:
    tp = sum(p == none and g == none for p, _, g in rows)
    pp = sum(p == none for p, _, _ in rows)
    gp = sum(g == none for _, _, g in rows)
    return {"precision": round(tp / pp, 4) if pp else None, "recall": round(tp / gp, 4) if gp else None,
            "predicted": pp, "gold": gp}


def threshold_for(rows: list[tuple[str | None, float, str]], target: float = WRONG_TARGET) -> float:
    """The lowest confidence threshold whose answered items are at most ``target`` wrong.

    Walks the items from most to least confident and keeps the largest prefix
    that stays within the target; ties are kept or dropped together. Returns
    +inf when even the most confident items miss the target.
    """
    srt = sorted(rows, key=lambda r: -r[1])
    best, wrong = float("inf"), 0
    i = 0
    while i < len(srt):
        j = i
        while j < len(srt) and srt[j][1] == srt[i][1]:
            wrong += srt[j][0] != srt[j][2]
            j += 1
        if wrong / j <= target:
            best = srt[j - 1][1]
        i = j
    return best


def transfer(rows_by_group: dict[str, list[tuple[str | None, float, str]]], *, splits: int = 200,
             seed: int = 20261116, target: float = WRONG_TARGET) -> dict[str, Any]:
    """Calibration transfer over random halves of the groups (anchors)."""
    groups = sorted(rows_by_group)
    rng = random.Random(seed)
    cov, wrong = [], []
    for _ in range(splits):
        g = groups[:]
        rng.shuffle(g)
        a, b = g[: len(g) // 2], g[len(g) // 2:]
        cal = [r for x in a for r in rows_by_group[x]]
        test = [r for x in b for r in rows_by_group[x]]
        if not cal or not test:
            continue
        t = threshold_for(cal, target)
        ans = [r for r in test if r[1] >= t]
        cov.append(len(ans) / len(test))
        wrong.append(sum(p != gd for p, _, gd in ans) / len(ans) if ans else 0.0)
    if not cov:
        return {"splits": 0}
    q90 = sorted(wrong)[int(0.9 * (len(wrong) - 1))]
    return {"splits": len(cov), "coverage_median": round(median(cov), 4), "wrong_median": round(median(wrong), 4),
            "wrong_p90": round(q90, 4), "coverage_p10": round(sorted(cov)[int(0.1 * (len(cov) - 1))], 4)}


def role(t: dict[str, Any], flip: float | None, au: float | None, acc: float | None,
         base_acc: float | None, *, cap: str | None = None) -> str:
    alone = (t.get("splits") and t["coverage_median"] >= 0.70 and t["wrong_median"] <= 0.05
             and t["wrong_p90"] <= 0.075 and flip is not None and flip <= 0.05)
    gate = (t.get("splits") and t["wrong_median"] <= 0.05 and t["coverage_median"] >= 0.20
            and flip is not None and flip <= 0.10)
    second = (au is not None and au >= 0.70 and acc is not None and base_acc is not None
              and acc >= 0.8 * base_acc)
    r = "alone" if alone else "gate" if gate else "second opinion" if second else "not used"
    if cap == "gate" and r == "alone":
        r = "gate"
    return r


def flip_rate(first: dict[str, str | None], second: dict[str, str | None]) -> float | None:
    common = [i for i in first if i in second]
    return round(sum(first[i] != second[i] for i in common) / len(common), 4) if common else None


def latency(ms: Iterable[float]) -> dict[str, float | None]:
    v = sorted(ms)
    if not v:
        return {"median_ms": None, "p90_ms": None}
    return {"median_ms": round(median(v), 1), "p90_ms": round(v[int(0.9 * (len(v) - 1))], 1)}


__all__ = ["accuracy", "auroc", "ece", "flip_rate", "latency", "none_pr", "role", "threshold_for", "top_of",
           "transfer", "wrong_at_coverage"]
