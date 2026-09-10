#!/usr/bin/env python3
"""Rescore ``slot_relation`` against a gold that the graph can actually satisfy.

`EXP-2026-09-014` reported `slot_relation` as the rewrite stage's worst slot.
`EXP-2026-09-015` found part of that figure is a property of the gold, not of
the system: 11 of the 36 `slot_gold.json` records that carry a full
`(anchor_label, relation, target_label)` name a relation that **does not exist
between their own two labels** in the canonical snapshot. A question about the
techniques a Group uses is gold-labelled `HAS_TECHNIQUE`, which this catalogue
declares only from `Tactic`; the edge the graph actually has is `USES`.

`utils.planner.canonical.form_from_slot_gold` already knew this — it marks such
a relation unbound rather than rendering a question from it, and its comment
names the cause: 39 of the 120 relations were matched from the template name,
and a template called `group_techniques` yields `HAS_TECHNIQUE`. But
`scripts.variant_harness.score_slots` reads `gold["relation"]` straight from the
raw record, so the protection never reaches the scorer and a system answering
`USES` is marked wrong for being right.

This prints both readings and never edits the gold:

``strict``
  gold's literal relation, exactly as `EXP-2026-09-014` scored it. Kept so the
  two experiments stay comparable.
``graph_consistent``
  a pick counts when it is a relation the snapshot declares between gold's own
  anchor and target labels. Where gold's own relation is declared, this is
  identical to ``strict``; it differs only on the records where gold names an
  edge the graph does not have.

Neither figure is authoritative on its own. The gap between them is the size of
the gold defect, and that is the number to report.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from utils.planner.canonical import load_slot_gold, neighbour_labels, relations_between

TIERS = ("T0", "T1", "T2", "T3", "T4", "T5", "T6")


def _tier(row: dict[str, Any]) -> str:
    return str(row.get("tier") or (row.get("case_id") or "").split(":")[-1] or "?")


def defective_records(gold_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Gold records whose relation is undeclared between their own two labels."""
    from utils.planner.canonical import _BANK_DATASETS

    out = []
    for g in gold_rows:
        rel = g.get("relation")
        als = g.get("anchor_labels") or ()
        tls = g.get("target_labels") or ()
        datasets = _BANK_DATASETS.get(str(g.get("bank") or ""), ())
        if not (rel and als and tls and datasets):
            continue
        allowed = relations_between(str(als[0]), str(tls[0]), datasets[0])
        if allowed and str(rel) not in allowed:
            out.append({
                "case_id": g.get("case_id"),
                "bank": g.get("bank"),
                "template": g.get("template"),
                "relation_source": g.get("relation_source"),
                "anchor_label": als[0],
                "target_label": tls[0],
                "gold_relation": rel,
                "graph_allows": list(allowed),
            })
    return out


def score(rows_path: Path, gold_path: Path) -> dict[str, Any]:
    rows = json.loads(rows_path.read_text())
    gold_rows = load_slot_gold(gold_path)
    gold = {g["case_id"]: g for g in gold_rows}
    from utils.planner.canonical import _BANK_DATASETS

    tally: dict[str, dict[str, list[bool]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        g = gold.get(row.get("case_id"))
        if not g or not g.get("relation"):
            continue
        form = ((row.get("rewrite") or {}).get("form")) or {}
        got = form.get("relation")
        if not got:
            continue
        tier = _tier(row)
        want = str(g["relation"]).upper()
        tally[tier]["strict"].append(str(got).upper() == want)

        als, tls = g.get("anchor_labels") or (), g.get("target_labels") or ()
        datasets = _BANK_DATASETS.get(str(g.get("bank") or ""), ())
        allowed = (
            {r.upper() for r in relations_between(str(als[0]), str(tls[0]), datasets[0])}
            if als and tls and datasets
            else set()
        )
        # No declared pair means the graph has nothing to say, so the strict
        # reading stands rather than being widened by an empty set.
        accept = allowed or {want}
        tally[tier]["graph_consistent"].append(str(got).upper() in accept)

        # The same defect has a second surface. 14 gold label cells name
        # `Technique`/`SubTechnique` on `capec` questions, where CAPEC has no
        # such label: the gold is written in conceptual vocabulary and the edge
        # that answers the question lands on CAPEC's own `TaxonomyEntry`. A
        # target label counts here when it is one the snapshot actually reaches
        # from gold's anchor label by gold's relation.
        want_t = {str(v).upper() for v in (g.get("target_labels") or ())}
        got_t = {str(v).upper() for v in (form.get("target_labels") or ())}
        if want_t and got_t:
            tally[tier]["target_label_strict"].append(bool(got_t & want_t))
            reachable = {
                lbl.upper()
                for rel in (allowed or {want})
                for lbl in neighbour_labels(str(als[0]), rel, None, datasets[0])
            } if als and datasets else set()
            tally[tier]["target_label_graph_consistent"].append(
                bool(got_t & (want_t | reachable))
            )

    out: dict[str, Any] = {"source": str(rows_path), "tiers": {}}
    for tier in TIERS:
        cells = tally.get(tier)
        if not cells:
            continue
        out["tiers"][tier] = {
            k: {"mean": round(sum(v) / len(v), 4), "n": len(v)} for k, v in cells.items()
        }
    every = defaultdict(list)
    for cells in tally.values():
        for k, v in cells.items():
            every[k] += v
    out["pooled"] = {
        k: {"mean": round(sum(v) / len(v), 4), "n": len(v)} for k, v in every.items()
    }
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("rows", nargs="+", help="scored row files from variant_harness compare")
    ap.add_argument("--gold", default="docs/evaluation/variants-2026-08-29/slot_gold.json")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    gold_rows = load_slot_gold(Path(args.gold))
    defects = defective_records(gold_rows)
    doc: dict[str, Any] = {
        "gold": args.gold,
        "gold_records_with_a_full_triple": sum(
            1
            for g in gold_rows
            if g.get("relation") and g.get("anchor_labels") and g.get("target_labels")
        ),
        "defective_gold_records": len(defects),
        "defects": defects,
        "runs": [score(Path(p), Path(args.gold)) for p in args.rows],
    }
    text = json.dumps(doc, indent=2) + "\n"
    if args.out:
        Path(args.out).write_text(text)
        print(f"   wrote {args.out}")
    print(
        f"gold records with a full triple: {doc['gold_records_with_a_full_triple']}; "
        f"relation undeclared between gold's own labels: {len(defects)}"
    )
    for run in doc["runs"]:
        print(f"\n{run['source']}")
        hdr = f"{'tier':6}{'relation':>32}{'target label':>32}"
        print(hdr)
        print(f"{'':6}{'strict':>16}{'graph-cons':>16}{'strict':>16}{'graph-cons':>16}")

        def _line(name: str, cells: dict) -> str:
            out = f"{name:6}"
            for key in ("strict", "graph_consistent",
                        "target_label_strict", "target_label_graph_consistent"):
                c = cells.get(key)
                out += f"{c['mean']:>16.4f}" if c else f"{'-':>16}"
            return out

        for tier, cells in run["tiers"].items():
            print(_line(tier, cells))
        print(_line("ALL", run["pooled"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
