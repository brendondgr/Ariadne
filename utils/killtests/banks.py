"""The real question sets T2 and T3 run on, joined to their slot gold.

Two banks, single-source cases only (federated cases need a two-store join that
neither kill test is about):

- ``dev``     — ``docs/evaluation/variants-2026-08-29`` (exposed; tiers T1–T6)
- ``confirm`` — ``docs/evaluation/variants-holdout-2026-09`` (opened once
  before; tiers T3–T6)

Each item carries its tier, its question, and the gold slots of the case it was
written from (anchor id and label, relation, target labels). T6 items name an
invented entity: they have no gold answer, only a gold *abstention*.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from .config import REPO

BANKS = {
    "dev": REPO / "docs/evaluation/variants-2026-08-29",
    "confirm": REPO / "docs/evaluation/variants-holdout-2026-09",
}


@dataclass(frozen=True)
class Item:
    key: str            # "<split>:<case_id>:<tier>"
    split: str
    case_id: str
    tier: str
    dataset: str        # "attack" | "capec"
    question: str
    gold_anchor: str | None
    gold_anchor_label: str | None
    gold_relation: str | None
    gold_target_labels: tuple[str, ...]
    reference_ids: tuple[str, ...] = field(default=())

    @property
    def negative(self) -> bool:
        return self.tier == "T6"

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key, "split": self.split, "case_id": self.case_id, "tier": self.tier,
            "dataset": self.dataset, "question": self.question, "gold_anchor": self.gold_anchor,
            "gold_anchor_label": self.gold_anchor_label, "gold_relation": self.gold_relation,
            "gold_target_labels": list(self.gold_target_labels),
        }


def _load(path) -> Any:
    with open(path) as fh:
        return json.load(fh)


@lru_cache(maxsize=None)
def load_items(split: str) -> tuple[Item, ...]:
    root = BANKS[split]
    variants = _load(root / "variants.json")
    slots = {s["case_id"]: s for s in _load(root / "slot_gold.json")}
    refs = {r["case_id"]: r for r in _load(root / "reference.json")}
    out: list[Item] = []
    for v in variants:
        if v["bank"] not in ("attack", "capec"):
            continue
        s = slots.get(v["case_id"])
        if s is None or len(s.get("anchors") or []) != 1:
            continue
        ref = refs.get(v["case_id"]) or {}
        out.append(Item(
            key=f"{split}:{v['case_id']}:{v['tier']}",
            split=split,
            case_id=v["case_id"],
            tier=v["tier"],
            dataset=v["bank"],
            question=v["question"],
            gold_anchor=None if v["tier"] == "T6" else s["anchors"][0],
            gold_anchor_label=(s.get("anchor_labels") or [None])[0],
            gold_relation=s.get("relation"),
            gold_target_labels=tuple(s.get("target_labels") or ()),
            reference_ids=tuple(str(x) for x in (ref.get("entity_ids") or [])),
        ))
    return tuple(out)


def all_items() -> list[Item]:
    return [*load_items("dev"), *load_items("confirm")]
