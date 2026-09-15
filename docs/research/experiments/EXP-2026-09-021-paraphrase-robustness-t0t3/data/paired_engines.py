#!/usr/bin/env python3
"""Pair the two engines variant by variant, and bound what choosing between them is worth.

    uv run python docs/research/experiments/EXP-2026-09-021-.../data/paired_engines.py

Tier means say which engine is better on average. They cannot say whether the
engines are *complementary* -- `EXP-2026-09-020` `A-1`/`A-2` found two cases on the
development bank where union equalled oracle pick-best, so the aggregate hid the
real structure. This pairs every variant and counts the four cells, which is the
only reading that settles it.

`either` is an **oracle upper bound on selection**: the score a perfect
per-question chooser would reach. It is not a measured merge, and `A-4` is the
standing reminder that a bound reasoned rather than run can be badly wrong --
so it is reported as a bound and nothing is inferred from it beyond "choosing
cannot be worth more than this".
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
RUNS = REPO / "docs/evaluation/variants-2026-09-15"
OUT = Path(__file__).resolve().parent / "metrics_paired_engines.json"


def _key(row: dict) -> tuple[str, str, str]:
    return (str(row.get("case_id")), str(row.get("tier")), str(row.get("question")))


def main() -> int:
    base = {_key(r): r for r in json.loads((RUNS / "scored_baseline.json").read_text())}
    prim = {_key(r): r for r in json.loads((RUNS / "scored_primitives.json").read_text())}
    shared = sorted(set(base) & set(prim))

    cells: dict[str, dict[str, int]] = defaultdict(
        lambda: {"n": 0, "both": 0, "templates_only": 0, "primitives_only": 0, "neither": 0}
    )
    for k in shared:
        tier = k[1]
        a = bool(base[k].get("records_exact"))
        b = bool(prim[k].get("records_exact"))
        c = cells[tier]
        c["n"] += 1
        c["both" if a and b else "templates_only" if a else "primitives_only" if b else "neither"] += 1

    tiers: dict[str, dict[str, float | int]] = {}
    for tier, c in sorted(cells.items()):
        n = c["n"]
        tpl = (c["both"] + c["templates_only"]) / n
        pr = (c["both"] + c["primitives_only"]) / n
        either = (c["both"] + c["templates_only"] + c["primitives_only"]) / n
        tiers[tier] = {
            **c,
            "templates": round(tpl, 4),
            "primitives": round(pr, 4),
            "primitives_minus_templates": round(pr - tpl, 4),
            "either_oracle_bound": round(either, 4),
            "oracle_gain_over_templates": round(either - tpl, 4),
        }

    payload = {
        "what": "templates vs schema-derived primitives, paired per variant, records_exact",
        "n_paired": len(shared),
        "note": "either_oracle_bound is an upper bound on per-question SELECTION, not a measured merge",
        "tiers": tiers,
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    for tier, row in tiers.items():
        print(f"{tier}  n={row['n']:>4}  tpl={row['templates']:.4f}  prim={row['primitives']:.4f}  "
              f"delta={row['primitives_minus_templates']:+.4f}  prim_only={row['primitives_only']:>3}  "
              f"oracle={row['either_oracle_bound']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
