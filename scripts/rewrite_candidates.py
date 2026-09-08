#!/usr/bin/env python3
"""Recall@k of the gold anchor in the candidate lists — the ceiling on Step 4.

    uv run python scripts/rewrite_candidates.py --split tune

The name index "works as a component and fails as a router": EXP-2026-08-020
measured its accept decision at 68% precision on a frozen half, and no threshold
over the available signals fixed it. This stage uses it only as a **list
producer** — no accept decision, no threshold, nothing here can be over-fitted —
and hands the list to a chooser.

Which makes recall@k the number that has to be known first. It is the ceiling on
what any chooser can achieve: if the gold anchor is not in the list, no prompt,
no model and no amount of gating will put it in the answer. Measuring it before
the model runs is what lets Step 7 say whether the model was the problem.

**Tune half only by default.** The 2026-08-31 `report` half was spent once on
the name-index margin threshold; this script reads it only when explicitly asked.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from utils.config import load_env  # noqa: E402

load_env()

from utils.planner.canonical import (  # noqa: E402
    DEFAULT_TOP_K,
    SLOT_ANCHORS,
    candidate_lists_all,
    deterministic_fill,
    load_slot_gold,
)
from utils.planner.cards import load_source_cards  # noqa: E402

EVAL = REPO / "docs" / "evaluation" / "variants-2026-08-29"
DEFAULT_VARIANTS = EVAL / "variants.json"
DEFAULT_SLOT_GOLD = EVAL / "slot_gold.json"
DEFAULT_SPLIT = EVAL / "split.json"
DEFAULT_REFERENCE = EVAL / "reference_2026-09-08.json"


def _gold_anchors(path: Path) -> dict[str, set[str]]:
    return {
        str(r.get("case_id") or ""): {str(a).upper() for a in (r.get("anchors") or ())}
        for r in load_slot_gold(path)
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variants", default=str(DEFAULT_VARIANTS))
    parser.add_argument("--slot-gold", default=str(DEFAULT_SLOT_GOLD))
    parser.add_argument("--split-file", default=str(DEFAULT_SPLIT))
    parser.add_argument("--reference", default=str(DEFAULT_REFERENCE))
    parser.add_argument("--split", choices=("tune", "report", "all"), default="tune")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    cards = load_source_cards()
    gold = _gold_anchors(Path(args.slot_gold))
    assignment = json.loads(Path(args.split_file).read_text())["assignment"]

    # T0 is the gold questions themselves, which the variant bank does not carry.
    rows: list[dict[str, Any]] = [
        {"tier": "T0", "case_id": r["case_id"], "question": r["question"]}
        for r in json.loads(Path(args.reference).read_text())
    ]
    rows += [
        {"tier": v["tier"], "case_id": v["case_id"], "question": v["question"]}
        for v in json.loads(Path(args.variants).read_text())
    ]
    if args.split != "all":
        rows = [r for r in rows if assignment.get(r["case_id"]) == args.split]
    print(f"== {len(rows)} question(s) on the {args.split} half, k={args.top_k}")

    per: dict[str, dict[str, int]] = defaultdict(
        lambda: {"n": 0, "scorable": 0, "unbound": 0, "hit": 0, "hit_at_1": 0, "bound_ok": 0}
    )
    detail: list[dict[str, Any]] = []
    for row in rows:
        want = gold.get(row["case_id"]) or set()
        bucket = per[row["tier"]]
        bucket["n"] += 1
        if not want:
            continue  # no gold anchor recorded — nothing to be right about
        bucket["scorable"] += 1
        form = deterministic_fill(row["question"], cards)
        if not (SLOT_ANCHORS in form.unbound or not (form.anchors or form.anchor_titles)):
            bucket["bound_ok"] += int(bool({a.upper() for a in form.anchors} & want))
            continue
        bucket["unbound"] += 1
        lists = candidate_lists_all(row["question"], form, cards, top_k=args.top_k)
        ranked = [
            (ds, c.index, c.value.upper())
            for ds, cl in sorted(lists.items())
            for c in cl.anchors
        ]
        values = [v for _ds, _i, v in ranked]
        hit = bool(set(values) & want)
        bucket["hit"] += int(hit)
        # recall@1 is per list: a chooser is offered each source's best guess.
        firsts = {v for ds, i, v in ranked if i == 0}
        bucket["hit_at_1"] += int(bool(firsts & want))
        detail.append(
            {
                **row,
                "gold_anchors": sorted(want),
                "datasets": sorted(lists),
                "candidates": ranked,
                "hit": hit,
            }
        )

    print(f"{'tier':<5} {'n':>4} {'scored':>6} {'det-bound':>9} {'unbound':>7} "
          f"{'recall@k':>9} {'recall@1':>9} {'ceiling':>8}")
    summary: dict[str, Any] = {}
    for tier in sorted(per):
        b = per[tier]
        unbound = b["unbound"]
        recall = b["hit"] / unbound if unbound else None
        at1 = b["hit_at_1"] / unbound if unbound else None
        # What the whole stage could reach: anchors the deterministic pass got
        # right, plus anchors a perfect chooser could pick out of the lists.
        ceiling = (b["bound_ok"] + b["hit"]) / b["scorable"] if b["scorable"] else None
        summary[tier] = {
            "n": b["n"], "scorable": b["scorable"], "deterministically_bound": b["scorable"] - unbound,
            "deterministically_correct": b["bound_ok"], "unbound": unbound,
            "recall_at_k": None if recall is None else round(recall, 4),
            "recall_at_1": None if at1 is None else round(at1, 4),
            "anchor_ceiling": None if ceiling is None else round(ceiling, 4),
        }
        fmt = lambda v: "     —" if v is None else f"{v:9.4f}"  # noqa: E731
        print(f"{tier:<5} {b['n']:>4} {b['scorable']:>6} "
              f"{b['scorable'] - unbound:>9} {unbound:>7} {fmt(recall)} {fmt(at1)}"
              f"{'' if ceiling is None else f'{ceiling:9.4f}'}")

    if args.out:
        Path(args.out).write_text(
            json.dumps(
                {"split": args.split, "top_k": args.top_k, "summary": summary,
                 "detail": detail},
                indent=2, sort_keys=True,
            ) + "\n"
        )
        print(f"   wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
