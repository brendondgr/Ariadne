#!/usr/bin/env python3
"""Compare two grading passes over byte-identical saved answers.

The question this answers is **grader-model sensitivity**, and this project has
never been able to ask it. The recorded 0.0050 "grader spread" was measured
*within one model over three passes* (EXP-2026-08-007) and says nothing about
what happens when the weights behind the relay alias change — which they have,
three times (`D-028`, `Q12`).

Because the answers on disk do not move, a difference between two passes is
attributable to the grader alone. What matters is not the level, which was never
quotable, but whether **arm ordering** survives. If it does not, no judged
comparison in this record survives either, and that is the finding.

Two disciplines are built in rather than left to the caller:

* **Dropout is reported, never silently absorbed.** A case graded by one pass and
  not the other is excluded from the paired statistics *and* counted, because a
  pass that drops its hardest cases reports a flattering mean. That is not
  hypothetical here: an earlier `.cross` pass over `llm_query` failed on exactly
  the three lowest-scoring answers and read 0.24 higher as a result.
* **Every comparison is paired on case id.** Comparing two means over different
  case sets measures the case sets.

Usage:

    uv run python scripts/grader_sensitivity.py \
        --root docs/evaluation/experiments/bank20260819 \
        --reference-suffix "" --candidate-suffix .qwen38 \
        --arms deterministic generic gold_loop_llm llm_query
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean, pstdev

FIELDS = ("correctness", "faithfulness", "groundedness", "completeness")


def _judgments(answers: Path, suffix: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for path in sorted(answers.glob(f"*.judgment{suffix}.json")):
        case = path.name.split(".judgment")[0]
        try:
            out[case] = json.loads(path.read_text())
        except (ValueError, OSError):
            continue
    return out


def _pearson(a: list[float], b: list[float]) -> float | None:
    if len(a) < 2:
        return None
    ma, mb = mean(a), mean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = sum((x - ma) ** 2 for x in a) ** 0.5
    db = sum((y - mb) ** 2 for y in b) ** 0.5
    return round(num / (da * db), 4) if da and db else None


def compare(root: Path, arm: str, reference_suffix: str, candidate_suffix: str) -> dict:
    answers = root / arm / "answers"
    ref = _judgments(answers, reference_suffix)
    cand = _judgments(answers, candidate_suffix)
    paired = sorted(set(ref) & set(cand))

    ref_vals = [float(ref[c]["correctness"]) for c in paired]
    cand_vals = [float(cand[c]["correctness"]) for c in paired]
    deltas = [b - a for a, b in zip(ref_vals, cand_vals)]
    moved = [
        {"case": c, "reference": r, "candidate": k, "delta": round(k - r, 4)}
        for c, r, k in zip(paired, ref_vals, cand_vals)
        if abs(k - r) >= 0.05
    ]
    served = {j.get("judge", {}).get("served_model") for j in cand.values()}

    return {
        "arm": arm,
        "n_paired": len(paired),
        "reference_only": sorted(set(ref) - set(cand)),
        "candidate_only": sorted(set(cand) - set(ref)),
        "reference_mean": round(mean(ref_vals), 4) if paired else None,
        "candidate_mean": round(mean(cand_vals), 4) if paired else None,
        "mean_delta": round(mean(deltas), 4) if paired else None,
        "mean_abs_delta": round(mean(abs(d) for d in deltas), 4) if paired else None,
        "sd_delta": round(pstdev(deltas), 4) if len(deltas) > 1 else None,
        "pearson_r": _pearson(ref_vals, cand_vals),
        "verdict_agreement": round(
            sum(ref[c]["verdict"] == cand[c]["verdict"] for c in paired) / len(paired), 4
        ) if paired else None,
        "improved": sum(1 for d in deltas if d > 0),
        "regressed": sum(1 for d in deltas if d < 0),
        "unchanged": sum(1 for d in deltas if d == 0),
        "moved_by_0.05_or_more": moved,
        "candidate_served_model": sorted(m for m in served if m),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--arms", nargs="+", required=True)
    parser.add_argument("--reference-suffix", default="", help='"" for the base .judgment.json pass')
    parser.add_argument("--candidate-suffix", default=".qwen38")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    cells = [compare(args.root, a, args.reference_suffix, args.candidate_suffix) for a in args.arms]
    usable = [c for c in cells if c["n_paired"]]

    # Ordering is the load-bearing question, so it is computed rather than eyeballed.
    ref_order = [c["arm"] for c in sorted(usable, key=lambda c: -c["reference_mean"])]
    cand_order = [c["arm"] for c in sorted(usable, key=lambda c: -c["candidate_mean"])]

    result = {
        "root": str(args.root),
        "reference_suffix": args.reference_suffix or "(base)",
        "candidate_suffix": args.candidate_suffix,
        "cells": cells,
        "arm_order_reference": ref_order,
        "arm_order_candidate": cand_order,
        "arm_order_preserved": ref_order == cand_order,
    }

    if args.out:
        args.out.write_text(json.dumps(result, indent=1) + "\n")

    print(f"{args.root.name}: reference {result['reference_suffix']} vs candidate {args.candidate_suffix}\n")
    print(f"  {'arm':<18} {'n':>3}  {'ref':>7} {'new':>7} {'delta':>7} {'|d|':>6} {'r':>7} {'verdict':>8}  dropout")
    for c in cells:
        if not c["n_paired"]:
            print(f"  {c['arm']:<18}   —  (no paired cases)")
            continue
        drop = len(c["reference_only"]) + len(c["candidate_only"])
        print(
            f"  {c['arm']:<18} {c['n_paired']:>3}  {c['reference_mean']:>7.4f} {c['candidate_mean']:>7.4f} "
            f"{c['mean_delta']:>+7.4f} {c['mean_abs_delta']:>6.4f} "
            f"{(c['pearson_r'] if c['pearson_r'] is not None else float('nan')):>7.4f} "
            f"{c['verdict_agreement']:>8.4f}  {drop or '-'}"
        )
    print(f"\n  arm ordering preserved: {result['arm_order_preserved']}")
    print(f"    reference: {' > '.join(ref_order)}")
    print(f"    candidate: {' > '.join(cand_order)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
