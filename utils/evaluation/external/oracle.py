#!/usr/bin/env python3
"""The ceiling: what the graph itself holds, with no retrieval in the way.

Both benchmarks predate the loaded ATT&CK 19.0. When Ariadne misses a gold
identifier that is either Ariadne's failure or the benchmark's staleness, and
nothing in a score distinguishes them. The oracle does: it is the answer a
perfect retriever over this data would give, so Ariadne is read against *it*
rather than against 1.0, and the oracle's own shortfall against gold is the size
of the drift (D-018).

It reads the canonical artifacts directly -- no plan, no specialist, no query
engine -- because anything in that path would make it a measurement of the
retrieval it is supposed to bound.
"""

from __future__ import annotations

from utils.evaluation.external.families import FAMILIES
from utils.evaluation.external.graph import AttackIndex, load_attack
from utils.evaluation.external.items import Item


def answer(item: Item, index: AttackIndex | None = None) -> set[str]:
    """Every identifier the graph holds for this item's lookup."""
    index = index or load_attack()
    family = FAMILIES[item.family]
    return index.neighbours(item.anchor, family.rel, family.direction, family.target_labels)


def as_text(item: Item, index: AttackIndex | None = None) -> str:
    """The oracle's answer as prose, so the shared extractor can read it.

    Deliberately run through the same regex as every arm's answer rather than
    compared as a set directly: if the extractor has a defect, the ceiling must
    carry it too, or the gap between Ariadne and the ceiling would include the
    scorer's own error.
    """
    index = index or load_attack()
    found = sorted(answer(item, index))
    if not found:
        return "No records found."
    parts = ", ".join(f"{i}: {index.name_of.get(i, '')}".strip(": ") for i in found)
    return f"The graph records {len(found)} for {item.anchor}: {parts}."
