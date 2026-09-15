#!/usr/bin/env python3
"""Compare August's tier table against today's on a target that did not move.

    uv run python docs/research/experiments/EXP-2026-09-021-.../data/stable_subset.py

`records_exact` asks whether a variant extracts what **its own gold question
extracts on the same tree**. `EXP-2026-09-018` changed what the gold questions
extract, so the August tier table and the 2026-09-15 baseline are scored against
different targets and their difference is not a system difference.

This restricts both runs to the gold cases whose captured behaviour is identical
in the two references -- same `entity_ids` **and** same emitted `queries` -- and
reports the per-tier means over that shared slice, where the comparison is
like-for-like. Every number is computed here from the four artifacts named below;
nothing is copied in.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
AUG = REPO / "docs/evaluation/variants-2026-08-29"
NOW = REPO / "docs/evaluation/variants-2026-09-15"
OUT = Path(__file__).resolve().parent / "metrics_stable_subset.json"


def _entity_ids(row: dict) -> set[str]:
    v = row.get("entity_ids") or []
    return set(map(str, v.keys() if isinstance(v, dict) else v))


def _tier_means(rows: list[dict], keep: set[str] | None) -> dict[str, dict[str, float | int]]:
    buckets: dict[str, list[float]] = {}
    for r in rows:
        if keep is not None and r.get("case_id") not in keep:
            continue
        buckets.setdefault(str(r.get("tier")), []).append(float(bool(r.get("records_exact"))))
    return {
        t: {"records_exact": round(statistics.fmean(v), 4), "n": len(v)}
        for t, v in sorted(buckets.items())
    }


def main() -> int:
    aug_ref = {r["case_id"]: r for r in json.loads((AUG / "reference.json").read_text())}
    now_ref = {r["case_id"]: r for r in json.loads((NOW / "reference.json").read_text())}
    shared = sorted(set(aug_ref) & set(now_ref))

    stable = {
        c for c in shared
        if _entity_ids(aug_ref[c]) == _entity_ids(now_ref[c])
        and aug_ref[c].get("queries") == now_ref[c].get("queries")
    }
    moved_ids = sum(1 for c in shared if _entity_ids(aug_ref[c]) != _entity_ids(now_ref[c]))
    moved_queries = sum(1 for c in shared if aug_ref[c].get("queries") != now_ref[c].get("queries"))

    aug_rows = json.loads((AUG / "scored_arm0.json").read_text())
    now_rows = json.loads((NOW / "scored_baseline.json").read_text())

    payload = {
        "what": "August (EXP-2026-08-020 Arm 0) vs 2026-09-15 baseline, restricted to gold "
                "cases whose captured behaviour is unchanged between the two references",
        "gold_cases_shared": len(shared),
        "gold_cases_stable": len(stable),
        "gold_cases_entity_ids_moved": moved_ids,
        "gold_cases_queries_moved": moved_queries,
        "all_variants": {"august": _tier_means(aug_rows, None), "now": _tier_means(now_rows, None)},
        "stable_subset": {"august": _tier_means(aug_rows, stable), "now": _tier_means(now_rows, stable)},
    }
    for scope in ("all_variants", "stable_subset"):
        a, n = payload[scope]["august"], payload[scope]["now"]
        payload[scope]["delta"] = {
            t: round(n[t]["records_exact"] - a[t]["records_exact"], 4)
            for t in sorted(set(a) & set(n))
        }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
