#!/usr/bin/env python3
"""External benchmark rows -> evaluable items.

An item carries the question exactly as the benchmark poses it (or, for cti-ate,
in the sibling benchmark's own wording -- see below), the gold identifier set the
benchmark asserts, and a replayed plan derived by one declared rule.

**What this module authors, and what it does not.** It authors the plan: anchor,
source, and the family's two endpoint labels. Nothing else. Question text is
verbatim and gold is the benchmark's, untouched apart from the granularity rule
in D-022.

**Why cti-ate's own prompt is not used.** That column is a 3-8 KB
text-extraction instruction which appends the complete list of ATT&CK technique
identifiers as reference material -- it hands over the answer key, and it asks
for extraction from prose rather than retrieval from a graph. cti-ate therefore
contributes its item selection and its gold; the wording comes from AttackQA's
own template for the identical lookup, which keeps the two benchmarks directly
comparable and keeps the phrasing external to this repository. Recorded in
ISSUES.md as I1.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from utils.evaluation.external.families import CTI_ATE_FAMILY, FAMILIES, Family
from utils.evaluation.external.graph import AttackIndex, load_attack
from utils.evaluation.external.score import extract_ids, to_parents

_SOFTWARE_URL = re.compile(r"/software/(S\d+)")


@dataclass
class Item:
    """One external question, its gold, and the plan a plan-given arm replays."""

    item_id: str
    benchmark: str
    family: str
    anchor: str
    question: str
    gold: frozenset[str]
    #: True when every gold identifier exists in the loaded ATT&CK. Items that
    #: fail this are kept and counted, never silently dropped (D-021).
    anchor_present: bool
    gold_present: bool
    roll_to_parents: bool = False
    notes: dict[str, Any] = field(default_factory=dict)

    def entry(self, plan_given: bool) -> dict[str, Any]:
        """A bank entry the existing runner understands.

        With ``plan_given`` false the entry carries the question and nothing
        else, so the planner must derive source, seeds and entities from the
        text -- the condition no published Ariadne figure has ever measured.
        """
        entry: dict[str, Any] = {"id": self.item_id, "question": self.question}
        if not plan_given:
            return entry
        family = FAMILIES[self.family]
        entry["task"] = {
            "sub_question_id": self.item_id,
            "source": "attack",
            "text": self.question,
            "entities": list(family.entities),
            "limits": {"max_traversal_depth": 3, "max_result_rows": 300,
                       "query_timeout_ms": 5000},
            "join_key": None,
            "seed_ids": [self.anchor],
            "rationale": f"derived from {self.benchmark} by the declared rule",
        }
        return entry


def _usable(index: AttackIndex, anchor: str, gold: Iterable[str]) -> tuple[bool, bool]:
    gold = set(gold)
    return index.has(anchor), bool(gold) and all(index.has(g) for g in gold)


def cti_ate_items(rows: list[dict[str, str]], index: AttackIndex | None = None) -> list[Item]:
    """The 60 cti-ate rows. Gold is parent techniques only, so both sides roll up."""
    index = index or load_attack()
    items: list[Item] = []
    for row in rows:
        match = _SOFTWARE_URL.search(row["URL"])
        if not match:
            continue
        anchor = match.group(1)
        gold = frozenset(t.strip() for t in row["GT"].split(",") if t.strip())
        anchor_ok, gold_ok = _usable(index, anchor, gold)
        name = index.name_of.get(anchor, "")
        label = f"{anchor}: {name}" if name else anchor
        items.append(Item(
            item_id=f"CTIATE-{anchor}",
            benchmark="cti-ate",
            family=CTI_ATE_FAMILY.name,
            anchor=anchor,
            question=f"What attack techniques are used by software '{label}'?",
            gold=gold,
            anchor_present=anchor_ok,
            gold_present=gold_ok,
            roll_to_parents=True,
            notes={"platform": row.get("Platform", "")},
        ))
    return items


def attackqa_items(
    rows: Iterable[dict[str, Any]],
    *,
    per_family: int,
    seed: int,
    index: AttackIndex | None = None,
) -> list[Item]:
    """A stratified sample of AttackQA's enumerative families.

    Stratified rather than uniform because the families are wildly unbalanced --
    8,534 rows in one, 8 in another -- and a uniform draw would measure the
    largest family and call it AttackQA. Every family contributes up to
    ``per_family`` items, drawn with a fixed seed.
    """
    index = index or load_attack()
    buckets: dict[str, list[Item]] = {name: [] for name in FAMILIES}

    for row in rows:
        family_name = row.get("source")
        family = FAMILIES.get(family_name or "")
        if family is None:
            continue
        anchor = str(row.get("subject_id") or "")
        if not anchor:
            continue
        # Gold is what the benchmark's own answer asserts, kept to the labels the
        # family targets. That filter is what stops the anchor -- which every
        # answer echoes back -- from counting as its own gold.
        gold = frozenset(
            i for i in extract_ids(str(row.get("answer") or ""))
            if index.label_of.get(i) in family.target_labels
        )
        if not gold:
            continue
        anchor_ok, gold_ok = _usable(index, anchor, gold)
        buckets[family.name].append(Item(
            item_id=f"AQA-{family.name}-{anchor}",
            benchmark="attackqa",
            family=family.name,
            anchor=anchor,
            question=str(row["question"]),
            gold=gold,
            anchor_present=anchor_ok,
            gold_present=gold_ok,
            notes={"human_question_flag": bool(row.get("human_question"))},
        ))

    rng = random.Random(seed)
    sampled: list[Item] = []
    for name in sorted(buckets):
        pool = buckets[name]
        # Sort before sampling: dict/parquet order is stable in practice but is
        # not a guarantee, and a seed that depends on input order is not a seed.
        pool.sort(key=lambda i: i.item_id)
        rng.shuffle(pool)
        # De-duplicate on anchor -- AttackQA asks the same enumeration of the
        # same entity more than once, and counting it twice weights that entity.
        seen: set[str] = set()
        for item in pool:
            if item.anchor in seen:
                continue
            seen.add(item.anchor)
            sampled.append(item)
            if len(seen) >= per_family:
                break
    return sampled


def coverage(items: list[Item]) -> dict[str, Any]:
    """How much of a benchmark this ATT&CK version can be held responsible for."""
    usable = [i for i in items if i.anchor_present and i.gold_present]
    return {
        "items": len(items),
        "anchor_present": sum(1 for i in items if i.anchor_present),
        "gold_fully_present": sum(1 for i in items if i.gold_present),
        "usable": len(usable),
        "excluded": len(items) - len(usable),
        "gold_ids_total": sum(len(i.gold) for i in items),
        "gold_ids_in_graph": sum(
            len({g for g in i.gold if load_attack().has(g)}) for i in items),
    }


def apply_granularity(item: Item, ids: set[str]) -> set[str]:
    """D-022: cti-ate rolls to parent techniques, AttackQA keeps sub-techniques."""
    return to_parents(ids) if item.roll_to_parents else ids
