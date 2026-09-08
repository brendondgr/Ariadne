#!/usr/bin/env python3
"""Fold an arm's per-run metrics into one mean-and-spread record.

Each run of a model arm is written separately, because the point of running it
three times is to see the three figures rather than an average of them. This
folds them for reporting: mean and **population standard deviation across the
runs**, not a confidence interval, because three runs is three runs.

It also carries the numbers that make a spread interpretable and that this
experiment learned the hard way to demand: the model-consulted rate and the
**call-failure rate**. A run in which a third of the calls timed out and
abstained looks, in `records_exact` alone, exactly like a run in which the model
answered and was wrong.

    uv run python scripts/rewrite_aggregate.py --arm R2 --runs 3
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
EXP = REPO / "docs" / "research" / "experiments" / "EXP-2026-09-014-hybrid-rewrite-stage"
SCORED = REPO / "docs" / "evaluation" / "variants-2026-08-29"

METRICS = (
    "records_exact", "records_recall", "records_recall_no_dump", "queries_exact",
    "abstained", "wrong_entity", "catalogue_dump",
    "slot_anchor", "slot_anchor_label", "slot_target_label", "slot_relation",
    "form_exact", "model_consulted", "cache_hit",
)


def _spread(draws: list[float]) -> dict[str, Any] | None:
    if not draws:
        return None
    mean = sum(draws) / len(draws)
    if len(draws) == 1:
        return {"mean": round(mean, 4), "sd": None, "n": 1}
    var = sum((d - mean) ** 2 for d in draws) / len(draws)
    return {"mean": round(mean, 4), "sd": round(var ** 0.5, 4), "n": len(draws),
            "draws": [round(d, 4) for d in draws]}


def _call_failures(path: Path) -> dict[str, Any]:
    """How many model calls never reached the model, from the scored rows."""
    if not path.exists():
        return {}
    rows = json.loads(path.read_text())
    attempted = sum(1 for r in rows if r.get("rung") in {"model", "abstain"})
    failed = sum(
        1 for r in rows
        for x in ((r.get("rewrite") or {}).get("rejected") or [])
        if str(x).startswith("model unavailable")
    )
    declined = sum(
        1 for r in rows
        for x in ((r.get("rewrite") or {}).get("rejected") or [])
        if "declined" in str(x)
    )
    gated = sum(
        1 for r in rows
        for x in ((r.get("rewrite") or {}).get("rejected") or [])
        if "not an index" in str(x) or "not declared" in str(x)
    )
    return {
        "attempted": attempted,
        "unavailable": failed,
        "unavailable_rate": round(failed / attempted, 4) if attempted else None,
        "declined": declined,
        "gate_rejected_picks": gated,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", required=True)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    per_run = []
    for i in range(1, args.runs + 1):
        path = EXP / "data" / f"metrics_{args.arm}_run{i}.json"
        if path.exists():
            per_run.append(json.loads(path.read_text()))
    if not per_run:
        raise SystemExit(f"no per-run metrics for {args.arm}")

    tiers = sorted(per_run[0]["tiers"])
    folded: dict[str, Any] = {"arm": args.arm, "runs": len(per_run), "tiers": {}}
    for tier in tiers:
        cells: dict[str, Any] = {"n": per_run[0]["tiers"][tier]["n"]}
        for metric in METRICS:
            draws = [
                m["tiers"][tier][metric]["mean"]
                for m in per_run
                if m["tiers"].get(tier, {}).get(metric)
            ]
            cells[metric] = _spread(draws)
        folded["tiers"][tier] = cells

    folded["served_models"] = sorted(
        {s for m in per_run for s in m.get("served_models", [])}
    )
    folded["per_run_call_health"] = [
        _call_failures(SCORED / f"scored_{args.arm}_tune.run{i}.json")
        for i in range(1, len(per_run) + 1)
    ]
    cached = EXP / "data" / f"metrics_{args.arm}_cached.json"
    if cached.exists():
        m = json.loads(cached.read_text())
        folded["cached_replay"] = {
            tier: {
                "records_exact": m["tiers"][tier]["records_exact"]["mean"],
                "cache_hit": m["tiers"][tier]["cache_hit"]["mean"],
            }
            for tier in sorted(m["tiers"])
        }

    out = Path(args.out) if args.out else EXP / "data" / f"metrics_{args.arm}.json"
    out.write_text(json.dumps(folded, indent=2, sort_keys=True) + "\n")
    print(f"wrote {out}")
    for tier in tiers:
        c = folded["tiers"][tier]["records_exact"]
        sd = "—" if c is None or c["sd"] is None else f"{c['sd']:.4f}"
        mean = "—" if c is None else f"{c['mean']:.4f}"
        print(f"  {tier} records_exact mean={mean} sd={sd}")
    for i, health in enumerate(folded["per_run_call_health"], 1):
        print(f"  run{i} call health: {health}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
