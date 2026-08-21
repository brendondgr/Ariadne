#!/usr/bin/env python3
"""Grader-free scoring: pull ATT&CK identifiers out of an answer, compare sets.

No language model participates in any number this module produces (D-019). That
is the point of the experiment -- every other headline figure in this project
went through a local judge that has never been checked against a human.

The extractor is deliberately generous: an identifier anywhere in the text
counts as asserted. That inflates recall for a verbose answer, so exact-set
match is reported beside it as the unforgiving counterpart, and the oracle is
put through the identical extractor so no arm is advantaged by formatting.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: ATT&CK public identifiers. Ordered so the longer forms win: `TA0009` must not
#: be read as a technique, and `T1548.002` must not be truncated to `T1548`.
_ID = re.compile(r"\b(?:TA\d{4}|T\d{4}(?:\.\d{3})?|S\d{4}|G\d{4}|C\d{4}|M\d{4}|DS\d{4})\b")


def extract_ids(text: str) -> set[str]:
    """Every ATT&CK identifier appearing anywhere in ``text``."""
    return set(_ID.findall(text or ""))


def to_parents(ids: set[str]) -> set[str]:
    """Roll sub-techniques up to their parent technique.

    cti-ate's gold is parent techniques only -- its prompt says so explicitly --
    so both sides of that comparison are rolled up (D-022). AttackQA's gold keeps
    sub-techniques and is never passed through this.
    """
    return {i.split(".")[0] for i in ids}


@dataclass(frozen=True)
class Score:
    """One item's set comparison. Every field is arithmetic over two sets."""

    gold: frozenset[str]
    predicted: frozenset[str]

    @property
    def hit(self) -> int:
        return len(self.gold & self.predicted)

    @property
    def recall(self) -> float:
        return self.hit / len(self.gold) if self.gold else 0.0

    @property
    def precision(self) -> float:
        return self.hit / len(self.predicted) if self.predicted else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0

    @property
    def exact(self) -> bool:
        return self.gold == self.predicted

    def as_dict(self) -> dict:
        return {
            "gold_n": len(self.gold), "predicted_n": len(self.predicted),
            "hit": self.hit, "recall": round(self.recall, 4),
            "precision": round(self.precision, 4), "f1": round(self.f1, 4),
            "exact": self.exact,
            "missed": sorted(self.gold - self.predicted),
            "extra": sorted(self.predicted - self.gold),
        }


def pool(scores: list[Score]) -> dict:
    """Roll up a list of item scores.

    Both a macro average (each item counts once) and a micro average (each gold
    identifier counts once) are reported. They answer different questions and
    quoting only one is how a long-tailed set gets misread: macro is dominated by
    items with a single gold id, micro by the handful with nineteen.
    """
    if not scores:
        return {"n": 0}
    n = len(scores)
    hit = sum(s.hit for s in scores)
    gold = sum(len(s.gold) for s in scores)
    pred = sum(len(s.predicted) for s in scores)
    micro_p = hit / pred if pred else 0.0
    micro_r = hit / gold if gold else 0.0
    return {
        "n": n,
        "macro_recall": round(sum(s.recall for s in scores) / n, 4),
        "macro_precision": round(sum(s.precision for s in scores) / n, 4),
        "macro_f1": round(sum(s.f1 for s in scores) / n, 4),
        "micro_recall": round(micro_r, 4),
        "micro_precision": round(micro_p, 4),
        "micro_f1": round(2 * micro_p * micro_r / (micro_p + micro_r), 4) if micro_p + micro_r else 0.0,
        "exact_match": round(sum(1 for s in scores if s.exact) / n, 4),
        "gold_ids": gold,
        "predicted_ids": pred,
        "hits": hit,
    }
