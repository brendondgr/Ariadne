#!/usr/bin/env python3
"""The 2x2: {authored plan, real planner} x {no model, 2B narrator}.

The two variables interact, and the interesting cell is the one nobody had run —
a real planner *and* a small model, which is what a laptop deployment actually
is. Reporting the corners without the interaction would let a reader assume it
is additive, and there is no reason to think it is: a weaker plan and a weaker
narrator can fail on the same questions.

Every cell answers the same 284 development questions, so every comparison is
paired per question. Two are reported:

* **The plan effect**, down each column: real planner minus authored plan, at a
  fixed model setting. In the no-model column this is EXP-2026-09-019 Step 2's
  headline, recomputed here against `generic_narrator_off` rather than
  `generic_composed` — the two composers load different caps
  (`SynthesisConfig()` versus `.from_env()`), and the corrected control removes
  that confound from the number.
* **The model effect**, across each row: 2B narrator minus no narrator, at a
  fixed plan source.

The metric is deterministic gold coverage. It is a retrieval measure, which is
why the model effect is expected to be flat: Step 3 established that the
narrator changes no identifier, citation or verdict. A non-zero model effect
here would mean the narrator had reached something it must not reach, so the row
differences are a control on the experiment as much as a result of it.

    uv run python scripts/twobytwo_score.py --out <metrics.json>
"""

from __future__ import annotations

import argparse
import collections
import json
import statistics
from pathlib import Path
from typing import Any

#: (plan source, model) -> (run root, arm). Every root holds the same 284 cases.
BASE = "docs/evaluation/experiments/small-model-generic-2026-09-13"
CELLS: dict[tuple[str, str], tuple[str, str]] = {
    ("authored", "none"): (f"{BASE}/twobytwo", "generic_narrator_off"),
    ("authored", "2B"): (f"{BASE}/narrator-full", "generic_local_narrator"),
    ("planner", "none"): (f"{BASE}/twobytwo", "generic_planned"),
    ("planner", "2B"): (f"{BASE}/twobytwo", "generic_planned_local"),
}


def load(root: str, arm: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for path in sorted(Path(root, arm, "answers").glob("*.json")):
        if ".judgment" in path.name or path.name == "manifest.json":
            continue
        artifact = json.loads(path.read_text())
        out[artifact["id"]] = artifact
    return out


def coverage(artifact: dict) -> float | None:
    return ((artifact.get("deterministic_scores") or {}).get("coverage") or {}).get(
        "coverage"
    )


def _wall(artifact: dict) -> float | None:
    value = (artifact.get("run_meta") or {}).get("wall_s")
    return float(value) if value is not None else None


def cell_summary(cases: dict[str, dict]) -> dict[str, Any]:
    values = [c for c in (coverage(a) for a in cases.values()) if c is not None]
    walls = [w for w in (_wall(a) for a in cases.values()) if w is not None]
    fallbacks = sum(
        1 for a in cases.values() if (a.get("answer") or {}).get("fallback_reason")
    )
    return {
        "n": len(cases),
        "gold_coverage_mean": round(statistics.fmean(values), 4) if values else None,
        "scored": len(values),
        "fallbacks": fallbacks,
        "fallback_rate": round(fallbacks / len(cases), 4) if cases else 0.0,
        # Wall clock at the run's own concurrency, which is 4. Single-user
        # latency is a separate measurement and is not this number.
        "wall_s_mean_at_4_workers": round(statistics.fmean(walls), 3) if walls else None,
        "wall_s_median_at_4_workers": round(statistics.median(walls), 3) if walls else None,
    }


def paired(a: dict[str, dict], b: dict[str, dict]) -> dict[str, Any]:
    """b minus a, per question, over the cases both hold."""
    diffs: list[float] = []
    per_tier: dict[str, list[float]] = collections.defaultdict(list)
    for case in sorted(set(a) & set(b)):
        ca, cb = coverage(a[case]), coverage(b[case])
        if ca is None or cb is None:
            continue
        diffs.append(cb - ca)
        per_tier[case.split("-")[0]].append(cb - ca)
    n = len(diffs)
    mean = statistics.fmean(diffs) if n else 0.0
    sd = statistics.stdev(diffs) if n > 1 else 0.0
    se = sd / (n ** 0.5) if n else 0.0
    return {
        "n": n,
        "mean": round(mean, 4),
        "sd": round(sd, 4),
        "standard_error": round(se, 4),
        "separable": bool(abs(mean) > 2 * se),
        "per_tier": {
            tier: {"n": len(v), "mean": round(statistics.fmean(v), 4)}
            for tier, v in sorted(per_tier.items())
        },
    }


def single_user_latency(root: str) -> dict[str, Any]:
    """Wall clock per answer at ONE worker, per cell.

    Separate from the 2x2's own wall-clock column, which is measured at
    concurrency 4. That is throughput under load; this is what one analyst
    waits. Conflating them would understate the wait by the concurrency factor
    and overstate the throughput by it, in opposite directions.
    """
    out: dict[str, Any] = {}
    for (plan, model), (_, arm) in CELLS.items():
        cases = load(root, arm)
        walls = [w for w in (_wall(a) for a in cases.values()) if w is not None]
        out[f"{plan}/{model}"] = {
            "arm": arm,
            "n": len(walls),
            "mean_s": round(statistics.fmean(walls), 3) if walls else None,
            "median_s": round(statistics.median(walls), 3) if walls else None,
            "max_s": round(max(walls), 3) if walls else None,
        }
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=None)
    parser.add_argument(
        "--latency-root",
        default=None,
        help="run root holding every cell at --workers 1, for single-user latency",
    )
    parser.add_argument(
        "--seam",
        action="append",
        default=[],
        metavar="NAME=PATH",
        help="fold another seam's result file into metrics.json under `seams.NAME`. "
        "The record's validator requires every manifest metric to appear in "
        "metrics.json, and a number that lives only in a sibling file is a number "
        "the manifest was typed from rather than read from.",
    )
    args = parser.parse_args()

    cells = {key: load(root, arm) for key, (root, arm) in CELLS.items()}
    missing = [k for k, v in cells.items() if not v]
    if missing:
        raise SystemExit(f"no answers for cells: {missing}")

    result: dict[str, Any] = {
        "cells": {
            f"{plan}/{model}": {
                "arm": CELLS[(plan, model)][1],
                "root": CELLS[(plan, model)][0],
                **cell_summary(cases),
            }
            for (plan, model), cases in cells.items()
        },
        # Down the columns: what letting the planner run costs.
        "plan_effect": {
            model: paired(cells[("authored", model)], cells[("planner", model)])
            for model in ("none", "2B")
        },
        # Across the rows: what adding the 2B narrator costs. Expected ~0.
        "model_effect": {
            plan: paired(cells[(plan, "none")], cells[(plan, "2B")])
            for plan in ("authored", "planner")
        },
    }

    # Is the plan effect the same size in both model columns? If the two
    # variables were interacting, it would not be.
    none_effect = result["plan_effect"]["none"]["mean"]
    small_effect = result["plan_effect"]["2B"]["mean"]
    result["interaction"] = {
        "plan_effect_without_model": none_effect,
        "plan_effect_with_2B": small_effect,
        "difference": round(small_effect - none_effect, 4),
    }

    if args.seam:
        seams: dict[str, Any] = {}
        for entry in args.seam:
            name, _, path = entry.partition("=")
            if not path:
                raise SystemExit(f"--seam expects NAME=PATH, got {entry!r}")
            seams[name] = json.loads(Path(path).read_text())
        result["seams"] = seams

    if args.latency_root:
        result["single_user_latency_at_1_worker"] = single_user_latency(args.latency_root)
        result["single_user_latency_at_1_worker"]["_root"] = args.latency_root

    text = json.dumps(result, indent=2) + "\n"
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text)
        print(f"written: {args.out}")

    print(f"{'cell':22} {'n':>4} {'coverage':>9} {'fallback':>9} {'wall/ans':>9}")
    for name, cell in result["cells"].items():
        print(f"{name:22} {cell['n']:>4} {str(cell['gold_coverage_mean']):>9} "
              f"{cell['fallback_rate']:>9} {str(cell['wall_s_mean_at_4_workers']):>9}")
    print()
    for model, eff in result["plan_effect"].items():
        print(f"plan effect  ({model:>4} model): {eff['mean']:+.4f} "
              f"(se {eff['standard_error']}, separable={eff['separable']}, n={eff['n']})")
    for plan, eff in result["model_effect"].items():
        print(f"model effect ({plan:>8} plan): {eff['mean']:+.4f} "
              f"(se {eff['standard_error']}, separable={eff['separable']}, n={eff['n']})")
    print(f"\ninteraction (plan effect with 2B minus without): "
          f"{result['interaction']['difference']:+.4f}")
    latency = result.get("single_user_latency_at_1_worker")
    if latency:
        print("\nsingle-user latency at 1 worker (seconds per answer):")
        for name, row in latency.items():
            if name.startswith("_"):
                continue
            print(f"  {name:16} mean {str(row['mean_s']):>9}  "
                  f"median {str(row['median_s']):>9}  n={row['n']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
