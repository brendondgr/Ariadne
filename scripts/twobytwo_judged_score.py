#!/usr/bin/env python3
"""The 2x2 on the judged `correctness` scale, paired per question.

`twobytwo_score.py` reports deterministic gold coverage, which is what the
answer *enumerates*. This reports what the grader scored, which is the metric
every other figure in this project uses — and, unlike coverage, it reads the
narrative prose, so it is the only measurement that can see whether a small
model's writing helps or hurts.

A case's score is the mean of its grading positions. Reading one position would
confound the result with the order the cells happened to be graded in
(`EXP-2026-08-022`), which is why both are graded and why the counterbalancing
exists. `Q46` records this grader moving 0.0503 between sessions with near-zero
spread inside each; pairing per question cancels exactly that.

`separable` is `|difference| > 2 * standard_error`, the rule the Step 6 metrics
used, and it is coarse. With n=284 and a paired SD near 0.24 the standard error
is about 0.014, so a difference under roughly 0.03 is not resolvable here.

    uv run python scripts/twobytwo_judged_score.py --out <judged.json>
"""

from __future__ import annotations

import argparse
import collections
import json
import statistics
from pathlib import Path
from typing import Any

BASE = "docs/evaluation/experiments/small-model-generic-2026-09-13/twobytwo"
CELLS: dict[tuple[str, str], str] = {
    ("authored", "none"): "generic_narrator_off",
    ("authored", "2B"): "generic_local_narrator",
    ("planner", "none"): "generic_planned",
    ("planner", "2B"): "generic_planned_local",
}

#: Judge-reported flags worth counting beside the score. A cell that scores well
#: while hallucinating is not the same result as one that scores well without.
FLAGS = ("abstained", "fabricated_mapping", "hallucinations")


def scores(directory: Path) -> dict[str, float]:
    """Case id -> mean correctness across grading positions."""
    per_case: dict[str, list[float]] = collections.defaultdict(list)
    for path in sorted(directory.glob("*.judgment*.json")):
        judgment = json.loads(path.read_text())
        case = judgment.get("case_id") or path.name.split(".judgment")[0]
        value = judgment.get("correctness")
        if value is not None:
            per_case[str(case)].append(float(value))
    return {case: statistics.fmean(v) for case, v in per_case.items()}


def positions(directory: Path) -> dict[str, int]:
    """How many grading positions each case actually got.

    Reported because a partially-graded cell averages fewer positions than its
    neighbours, and a mean over one position is not comparable with a mean over
    two. An overnight run that lost an endpoint mid-pass produces exactly that.
    """
    counts: collections.Counter = collections.Counter()
    for path in sorted(directory.glob("*.judgment*.json")):
        judgment = json.loads(path.read_text())
        case = judgment.get("case_id") or path.name.split(".judgment")[0]
        counts[str(case)] += 1
    return dict(counts)


def flags(directory: Path) -> dict[str, int]:
    out = {f: 0 for f in FLAGS}
    for path in sorted(directory.glob("*.judgment*.json")):
        judgment = json.loads(path.read_text())
        for field in FLAGS:
            value = judgment.get(field)
            if isinstance(value, list):
                out[field] += len(value)
            elif value:
                out[field] += 1
    return out


def paired(a: dict[str, float], b: dict[str, float]) -> dict[str, Any]:
    """b minus a, per question."""
    cases = sorted(set(a) & set(b))
    if len(cases) < 2:
        return {"n": len(cases), "mean": None, "sd": None,
                "standard_error": None, "separable": None, "per_tier": {}}
    diffs = [b[c] - a[c] for c in cases]
    per_tier: dict[str, list[float]] = collections.defaultdict(list)
    for case, d in zip(cases, diffs):
        per_tier[case.split("-")[0]].append(d)
    mean = statistics.fmean(diffs)
    sd = statistics.stdev(diffs)
    se = sd / len(diffs) ** 0.5
    return {
        "n": len(cases),
        "mean": round(mean, 4),
        "sd": round(sd, 4),
        "standard_error": round(se, 4),
        "separable": bool(abs(mean) > 2 * se),
        "per_tier": {
            t: {"n": len(v), "mean": round(statistics.fmean(v), 4)}
            for t, v in sorted(per_tier.items())
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=BASE)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    root = Path(args.root)
    cell_scores: dict[tuple[str, str], dict[str, float]] = {}
    cells_out: dict[str, Any] = {}
    for key, arm in CELLS.items():
        directory = root / arm / "answers"
        sc = scores(directory)
        cell_scores[key] = sc
        pos = positions(directory)
        n_answers = len([p for p in directory.glob("*.json") if ".judgment" not in p.name])
        cells_out[f"{key[0]}/{key[1]}"] = {
            "arm": arm,
            "answers": n_answers,
            "judged_cases": len(sc),
            "fully_graded_cases": sum(1 for v in pos.values() if v >= 2),
            "correctness_mean": round(statistics.fmean(sc.values()), 4) if sc else None,
            "flags": flags(directory),
        }

    graded = [k for k, v in cell_scores.items() if v]
    result: dict[str, Any] = {
        "metric": "judged correctness, mean of both grading positions",
        "root": str(root),
        "cells": cells_out,
        "plan_effect": {
            model: paired(cell_scores[("authored", model)], cell_scores[("planner", model)])
            for model in ("none", "2B")
            if ("authored", model) in graded and ("planner", model) in graded
        },
        "model_effect": {
            plan: paired(cell_scores[(plan, "none")], cell_scores[(plan, "2B")])
            for plan in ("authored", "planner")
            if (plan, "none") in graded and (plan, "2B") in graded
        },
    }
    pe = result["plan_effect"]
    if "none" in pe and "2B" in pe and pe["none"]["mean"] is not None:
        result["interaction"] = {
            "plan_effect_without_model": pe["none"]["mean"],
            "plan_effect_with_2B": pe["2B"]["mean"],
            "difference": round(pe["2B"]["mean"] - pe["none"]["mean"], 4),
        }

    text = json.dumps(result, indent=2) + "\n"
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text)
        print(f"written: {args.out}")

    print(f"{'cell':22} {'judged':>7} {'both pos':>9} {'correctness':>12}")
    for name, cell in result["cells"].items():
        print(f"{name:22} {cell['judged_cases']:>7} {cell['fully_graded_cases']:>9} "
              f"{str(cell['correctness_mean']):>12}")
    print()
    for model, eff in result["plan_effect"].items():
        print(f"plan effect  ({model:>4} model): {eff['mean']} "
              f"(se {eff['standard_error']}, separable={eff['separable']}, n={eff['n']})")
    for plan, eff in result["model_effect"].items():
        print(f"model effect ({plan:>8} plan): {eff['mean']} "
              f"(se {eff['standard_error']}, separable={eff['separable']}, n={eff['n']})")
    if "interaction" in result:
        print(f"\ninteraction: {result['interaction']['difference']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
