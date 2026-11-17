"""Decision test items built from the card banks and the graph (Era 2, Step 7).

An :class:`Item` is one closed question with its gold option. The options and the
gold come from the card, the graph and the generated question, never from a
person, so every item carries over to any graph a card describes.

Phase A builders:
- :func:`relation_items` (D4): which card relation from the known entity answers it;
- :func:`grounding_items` (D2, D3): which candidate the question refers to, or none.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

NONE = "none"
REPO = Path(__file__).resolve().parents[2]


@dataclass
class Item:
    id: str
    decision: str
    group: str                      # the anchor: splits never put one group in both halves
    stratum: str
    context: str
    question: str
    prompt: str
    options: dict[str, str]         # key -> description
    gold: str
    tags: dict[str, Any] = field(default_factory=dict)

    def option_text(self, key: str) -> str:
        return self.options[key]

    def orders(self, seed: int = 20261116) -> list[list[str]]:
        """Two seeded option orders; "none of these" always last, as a person would list it."""
        keys = [k for k in self.options if k != NONE]
        out = []
        for i in range(2):
            rng = random.Random(f"{seed}|{self.id}|{i}")
            k = keys[:]
            rng.shuffle(k)
            if i == 1 and len(k) > 1 and k == out[0][: len(k)]:
                k = k[1:] + k[:1]            # make sure the second order differs
            out.append(k + ([NONE] if NONE in self.options else []))
        return out

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> Item:
        return cls(**d)


def _h(*parts: Any) -> float:
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest(), 16) / 2 ** 256


def tuning_questions(bank_root: Path | None = None, name: str = "card-sonnet-2026-11-16") -> list[dict]:
    """Every question in the Sonnet-worded tuning banks (the sealed held-out banks are never read)."""
    root = bank_root or REPO / "docs/evaluation/banks"
    out = []
    for p in sorted(root.glob(f"{name}-*-tuning/bank.json")):
        body = json.loads(p.read_text())
        assert body["meta"]["split"] == "tuning" and not body["meta"]["sealed"], p
        out += body["questions"]
    return out


def _entities(ds: str) -> dict[str, tuple[str, str]]:
    """public id -> (label, name), from the dataset's name index."""
    from utils.specialists.schema.namesearch import index_for

    return {d[0]: (d[1], d[2]) for d in index_for(ds)._docs}


def _first_sentence(text: str, n: int = 160) -> str:
    import re

    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", " ".join(str(text or "").split()))   # markdown links
    t = re.sub(r"\(Citation:[^)]*\)", "", t).strip()
    cut = t.find(". ")
    t = t[: cut + 1] if 0 < cut < n else t
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


# --------------------------------------------------------------------------- #
# D4: relation choice
# --------------------------------------------------------------------------- #

def relation_options(card: dict, registry: Any, label: str) -> dict[str, str]:
    from utils.specialists.evalset.card_generator import relation_gloss

    opts = {}
    for f in registry.label_facets(label, dataset=card["dataset"]) or []:
        key = f"{f.rel_type}|{f.direction}|{f.neighbour_label}"
        arrow = f"{label} -{f.rel_type}-> {f.neighbour_label}" if f.direction == "out" \
            else f"{label} <-{f.rel_type}- {f.neighbour_label}"
        opts[key] = f"{arrow}: {relation_gloss(card, f.rel_type)}"
    return opts


def relation_items(questions: list[dict], registry: Any, *, none_share: float = 0.25,
                   seed: int = 20261116) -> list[Item]:
    cards: dict[str, dict] = {}
    ents: dict[str, dict] = {}
    items = []
    for q in questions:
        cg = q["card_gen"]
        if cg["kind"] != "answerable":
            continue
        ds, s = q["task"]["source"], cg["slot"]
        card = cards.setdefault(ds, json.loads((REPO / "data/source_cards" / f"{ds}.json").read_text()))
        ent = ents.setdefault(ds, _entities(ds))
        opts = relation_options(card, registry, s["label"])
        gold = f"{s['rel']}|{s['direction']}|{s['target']}"
        assert gold in opts, (q["id"], gold)
        name = ent.get(cg["anchor"], (s["label"], ""))[1]
        base = dict(decision="D4", group=f"{ds}:{cg['anchor']}",
                    context=f"Graph: {ds}. The question is about this known entity: {cg['anchor']} "
                            f"({s['label']}){': ' + name if name else ''}.",
                    question=q["question"],
                    prompt="Which relation from the known entity answers the question?")
        real = len(opts)
        strat = f"{cg['tier']}|{'1' if real == 1 else '2+'}"
        items.append(Item(id=f"D4:{q['id']}", stratum=strat, options={**opts, NONE: "none of these relations"},
                          gold=gold, tags={"tier": cg["tier"], "dataset": ds, "real_options": real}, **base))
        if _h(seed, "d4none", q["id"]) < none_share:
            o2 = {k: v for k, v in opts.items() if k != gold}
            items.append(Item(id=f"D4N:{q['id']}", stratum=f"none|{cg['tier']}",
                              options={**o2, NONE: "none of these relations"}, gold=NONE,
                              tags={"tier": cg["tier"], "dataset": ds, "real_options": len(o2),
                                    "removed": gold}, **base))
    return items


# --------------------------------------------------------------------------- #
# D2 / D3: grounding and "none of these"
# --------------------------------------------------------------------------- #

GROUNDING_TIERS = ("identifier", "name", "reworded_name", "description")


def grounding_items(questions: list[dict], *, k: int = 8, none_share: float = 0.5,
                    seed: int = 20261116) -> tuple[list[Item], dict[str, Any]]:
    from utils.specialists.schema.namesearch import descriptions_for, index_for

    items, recall = [], {"hit": 0, "n": 0, "by_tier": {}}
    for q in questions:
        cg = q["card_gen"]
        if cg["kind"] != "answerable" or cg["tier"] not in GROUNDING_TIERS:
            continue
        ds, label, gold = q["task"]["source"], cg["slot"]["label"], cg["anchor"]
        ix, desc = index_for(ds), descriptions_for(ds)
        hits = ix.search(q["question"], top_k=k + 1, labels=[label])
        ids = [h.entity_id for h in hits]
        found = gold in ids[:k]
        recall["n"] += 1
        recall["hit"] += found
        bt = recall["by_tier"].setdefault(cg["tier"], [0, 0])
        bt[0] += found
        bt[1] += 1
        names = {h.entity_id: (h.label, h.name) for h in hits}
        if gold not in names:
            label_name = {d[0]: (d[1], d[2]) for d in ix._docs if d[0] == gold}
            names[gold] = label_name.get(gold, (label, ""))
        cands = ids[:k] if found else [*ids[: k - 1], gold]
        extra = next((i for i in ids if i not in cands), None)

        def opt(i: str) -> str:
            lab, nm = names[i]
            d = _first_sentence(desc.get(i, ""))
            return f"{i} — {nm} ({lab}){': ' + d if d else ''}"

        base = dict(group=f"{ds}:{gold}", question=q["question"],
                    context=f"Graph: {ds}. The question mentions one {label}. These {label} entries matched "
                            f"its words in the graph's name index.",
                    prompt=f"Which {label} does the question refer to?")
        items.append(Item(id=f"D2:{q['id']}", decision="D2", stratum=cg["tier"],
                          options={**{i: opt(i) for i in cands}, NONE: "none of these"}, gold=gold,
                          tags={"tier": cg["tier"], "dataset": ds, "bm25_hit": found}, **base))
        if extra and _h(seed, "d3none", q["id"]) < none_share:
            c2 = [i for i in cands if i != gold] + [extra]
            names.setdefault(extra, (label, ""))
            items.append(Item(id=f"D3:{q['id']}", decision="D3", stratum=f"none|{cg['tier']}",
                              options={**{i: opt(i) for i in c2}, NONE: "none of these"}, gold=NONE,
                              tags={"tier": cg["tier"], "dataset": ds, "removed": gold}, **base))
    recall["recall_at_k"] = round(recall["hit"] / recall["n"], 4) if recall["n"] else None
    recall["by_tier"] = {t: f"{a}/{b}" for t, (a, b) in sorted(recall["by_tier"].items())}
    return items, recall


__all__ = ["GROUNDING_TIERS", "NONE", "Item", "grounding_items", "relation_items", "relation_options",
           "tuning_questions"]
