#!/usr/bin/env python3
"""Pair the rewrite arm against the baseline, and count what it fixed and broke.

    uv run python docs/research/experiments/EXP-2026-09-021-.../data/paired_rewrite.py

A tier mean nets a gain against a loss and hides both. The `fixed`/`broken`
counts are what the Step 4 ship rule is actually about: a stage that fixes 21 and
breaks 7 at one tier while fixing 3 and breaking 17 at another is not "a small
net effect", it is two large opposite effects on different populations.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
RUNS = REPO / "docs/evaluation/variants-2026-09-15"
OUT = Path(__file__).resolve().parent / "metrics_paired_rewrite.json"


def _key(r: dict) -> tuple[str, str, str]:
    return (str(r.get("case_id")), str(r.get("tier")), str(r.get("question")))


def _rung(r: dict) -> str:
    return str(r.get("rung") or (r.get("rewrite") or {}).get("rung") or "off")


def main() -> int:
    base = {_key(r): r for r in json.loads((RUNS / "scored_baseline.json").read_text())}
    rw = {_key(r): r for r in json.loads((RUNS / "scored_rewrite.json").read_text())}
    shared = sorted(set(base) & set(rw))

    cells: dict[str, dict[str, int]] = defaultdict(
        lambda: {"n": 0, "both": 0, "baseline_only": 0, "rewrite_only": 0,
                 "neither": 0, "model_rung": 0}
    )
    for k in shared:
        a, b = bool(base[k].get("records_exact")), bool(rw[k].get("records_exact"))
        c = cells[k[1]]
        c["n"] += 1
        c["both" if a and b else "baseline_only" if a else "rewrite_only" if b else "neither"] += 1
        if _rung(rw[k]) == "model":
            c["model_rung"] += 1

    tiers = {}
    for tier, c in sorted(cells.items()):
        n = c["n"]
        bs = (c["both"] + c["baseline_only"]) / n
        rs = (c["both"] + c["rewrite_only"]) / n
        tiers[tier] = {
            **c,
            "baseline": round(bs, 4),
            "rewrite": round(rs, 4),
            "rewrite_minus_baseline": round(rs - bs, 4),
            "fixed": c["rewrite_only"],
            "broken": c["baseline_only"],
        }

    payload = {
        "what": "rewrite (model rung) vs baseline, paired per variant, records_exact",
        "n_paired": len(shared),
        "tiers": tiers,
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    for tier, row in tiers.items():
        print(f"{tier}  n={row['n']:>4}  base={row['baseline']:.4f}  rw={row['rewrite']:.4f}  "
              f"delta={row['rewrite_minus_baseline']:+.4f}  fixed={row['fixed']:>3}  broken={row['broken']:>3}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
