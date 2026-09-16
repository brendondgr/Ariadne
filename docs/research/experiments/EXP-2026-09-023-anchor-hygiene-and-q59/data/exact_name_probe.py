#!/usr/bin/env python3
"""H1's direct instrument: what the exact-name matcher binds, per tier, per bank.

No pipeline run. For every variant of both banks, ``exact_name_matches`` is
asked across **every** live source with schema words removed — the same call
``deterministic_fill`` makes, minus the routing that today decides which source
gets asked. Each variant is then one of:

* ``0``            — no complete name in the text;
* ``1&gold``       — exactly one, and it is the question's gold anchor;
* ``1&notgold``    — exactly one, and it is not (the incidental-name trap);
* ``>1``           — more than one (an ambiguity the form must surface).

``--arm baseline`` measures the shipped matcher; ``--arm distinct`` sets
``ARIADNE_EXACT_NAME_DISTINCT=1`` before anything is imported, so the rule under
test is read the way the pipeline reads it. Writes ``data/metrics.json`` under
``exact_name.<arm>`` and ``tables/exact_name_<arm>.md``.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
REPO = EXP.parents[3]
sys.path.insert(0, str(REPO))

BANKS = {
    "exposed": REPO / "docs/evaluation/variants-2026-08-29",
    "sealed": REPO / "docs/evaluation/variants-holdout-2026-09",
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--arm", choices=("baseline", "distinct"), required=True)
    args = ap.parse_args()
    os.environ["ARIADNE_EXACT_NAME_DISTINCT"] = "1" if args.arm == "distinct" else "0"

    from utils.planner.cards import SourceCardView
    from utils.specialists.resolve import _schema_word_set
    from utils.specialists.schema.namesearch import exact_name_matches
    from utils.synthesis.grounding import normalize_id

    cards = {}
    for card_path in sorted((REPO / "data/source_cards").glob("*.json")):
        card = SourceCardView.from_card_dict(json.loads(card_path.read_text()))
        cards[card.dataset] = card
    schema_words = {ds: _schema_word_set(card) for ds, card in cards.items()}

    def exact_all(text: str) -> dict[tuple[str, str], str]:
        out: dict[tuple[str, str], str] = {}
        for ds, card in cards.items():
            for c in exact_name_matches(ds, text):
                if c.name.strip().lower() in schema_words[ds]:
                    continue
                out[(ds, normalize_id(c.entity_id))] = c.name
        return out

    result: dict[str, dict] = {}
    lines = ["| bank | tier | n | 0 | 1&gold | 1&notgold | >1 | single wrong names (top 5) |",
             "|---|---|---:|---:|---:|---:|---:|---|"]
    for bank_name, bank_dir in BANKS.items():
        variants = json.loads((bank_dir / "variants.json").read_text())
        gold = {r["case_id"]: {normalize_id(a) for a in r.get("anchors") or []}
                for r in json.loads((bank_dir / "slot_gold.json").read_text())}
        tally: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
        wrong_names: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
        for v in variants:
            tier = v["tier"]
            if tier not in ("T3", "T4", "T5", "T6"):
                continue
            hits = exact_all(v["question"])
            tally[tier]["n"] += 1
            if not hits:
                tally[tier]["0"] += 1
            elif len(hits) > 1:
                tally[tier][">1"] += 1
            else:
                (ds, eid), name = next(iter(hits.items()))
                anchors = gold.get(v["case_id"], set()) if tier != "T6" else set()
                if eid in anchors:
                    tally[tier]["1&gold"] += 1
                else:
                    tally[tier]["1&notgold"] += 1
                    wrong_names[tier][name] += 1
        result[bank_name] = {}
        for tier in ("T3", "T4", "T5", "T6"):
            t = tally[tier]
            result[bank_name][tier] = {k: t[k] for k in ("n", "0", "1&gold", "1&notgold", ">1")}
            result[bank_name][tier]["single_wrong_names"] = wrong_names[tier].most_common(10)
            top = ", ".join(f"{n} ×{c}" for n, c in wrong_names[tier].most_common(5))
            lines.append(f"| {bank_name} | {tier} | {t['n']} | {t['0']} | {t['1&gold']} | "
                         f"{t['1&notgold']} | {t['>1']} | {top} |")

    (EXP / "tables").mkdir(exist_ok=True)
    (EXP / f"tables/exact_name_{args.arm}.md").write_text("\n".join(lines) + "\n")
    metrics_path = EXP / "data/metrics.json"
    metrics = json.loads(metrics_path.read_text()) if metrics_path.exists() else {}
    metrics.setdefault("exact_name", {})[args.arm] = {
        "what": "exact_name_matches across every live source, schema words removed, per variant",
        "banks": result,
    }
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
