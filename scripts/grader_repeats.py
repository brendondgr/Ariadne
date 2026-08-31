#!/usr/bin/env python3
"""Aggregate repeated grading passes over one frozen answer set.

Written before any repeat existed, so its outputs cannot be chosen to suit them.

**What repeats measure, and what they do not.** Re-grading answers that do not
move measures the *precision of the grader*. It says nothing about the accuracy
of the arms and nothing about pipeline stability — `D-010` stays open for the
arms, and only re-running the pipeline can close it. Accuracy against an outside
reference is what a cross-model calibration measures, not this.

**Sessions, not cells, are the unit.** Every contrast is computed *within* a
session so that a session-level offset — the grader running warm, or a different
batching regime on the server — cancels out of it rather than inflating it.
`EXP-2026-08-009`'s protocol established that discipline for arm comparisons and
it applies identically here.

**The question this exists to settle** is whether a between-model offset measured
at n=1 survives the within-model spread. If sd across repeats is of the same
order as the offset, the offset was noise and must be withdrawn.

Usage:

    uv run python scripts/grader_repeats.py \
        --root docs/evaluation/experiments/bank20260819 \
        --arms deterministic llm_query merged generic_composed \
        --suffixes .qwen38 .qwen38r2 .qwen38r3 .qwen38r4 .qwen38r5 \
        --contrast deterministic:llm_query --contrast generic_composed:merged
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean, stdev


def _pass_means(answers: Path, suffix: str) -> tuple[dict[str, float], int]:
    """Correctness per case for one pass, plus the count that failed to grade."""
    vals: dict[str, float] = {}
    for path in sorted(answers.glob(f"*.judgment{suffix}.json")):
        case = path.name.split(".judgment")[0]
        try:
            vals[case] = float(json.loads(path.read_text())["correctness"])
        except (ValueError, OSError, KeyError):
            continue
    errors = len(list(answers.glob(f"*.judgment{suffix}.error.txt")))
    return vals, errors


def _sd(xs: list[float]) -> float | None:
    return round(stdev(xs), 4) if len(xs) > 1 else None


def collect(root: Path, arms: list[str], suffixes: list[str]) -> dict:
    """Per-arm, per-pass means over the cases graded by *every* pass.

    Restricting to the common case set is not tidiness — a pass that drops its
    hardest cases reports a flattering mean, so comparing passes over different
    case sets measures the dropout. Dropped cases are counted and reported.
    """
    cells: dict[str, dict] = {}
    for arm in arms:
        answers = root / arm / "answers"
        per_pass, errors = {}, {}
        for suffix in suffixes:
            per_pass[suffix], errors[suffix] = _pass_means(answers, suffix)
        graded_by_all = set.intersection(*(set(v) for v in per_pass.values())) if per_pass else set()
        common = sorted(graded_by_all)
        means = {s: round(mean([per_pass[s][c] for c in common]), 4) for s in suffixes} if common else {}
        vals = list(means.values())
        cells[arm] = {
            "n_common_cases": len(common),
            "dropped_by_some_pass": sorted(
                set().union(*(set(v) for v in per_pass.values())) - graded_by_all
            ) if per_pass else [],
            "errors_per_pass": errors,
            "mean_per_pass": means,
            "mean_of_means": round(mean(vals), 4) if vals else None,
            "sd_across_passes": _sd(vals),
            "range": round(max(vals) - min(vals), 4) if vals else None,
            "_per_case": {s: {c: per_pass[s][c] for c in common} for s in suffixes},
        }
    return cells


def contrasts(cells: dict, pairs: list[tuple[str, str]], suffixes: list[str]) -> list[dict]:
    """A contrast computed inside each session, then summarised across sessions."""
    out = []
    for high, low in pairs:
        if high not in cells or low not in cells:
            continue
        per_session = {}
        for s in suffixes:
            a, b = cells[high]["mean_per_pass"].get(s), cells[low]["mean_per_pass"].get(s)
            if a is not None and b is not None:
                per_session[s] = round(a - b, 4)
        vals = list(per_session.values())
        out.append({
            "contrast": f"{high} - {low}",
            "per_session": per_session,
            "mean": round(mean(vals), 4) if vals else None,
            "sd": _sd(vals),
            "range": round(max(vals) - min(vals), 4) if vals else None,
            "sign_stable": all(v > 0 for v in vals) or all(v < 0 for v in vals) if vals else None,
            "sum_of_component_sds": round(
                sum(x for x in (cells[high]["sd_across_passes"], cells[low]["sd_across_passes"]) if x), 4
            ),
        })
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--arms", nargs="+", required=True)
    parser.add_argument("--suffixes", nargs="+", required=True)
    parser.add_argument("--contrast", action="append", default=[], help="high:low, repeatable")
    parser.add_argument("--offset", type=float, default=None,
                        help="between-model offset measured at n=1, for the H5 comparison")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    cells = collect(args.root, args.arms, args.suffixes)
    pairs = [tuple(c.split(":", 1)) for c in args.contrast]
    cons = contrasts(cells, pairs, args.suffixes)

    printable = {a: {k: v for k, v in c.items() if k != "_per_case"} for a, c in cells.items()}
    result = {"root": str(args.root), "suffixes": args.suffixes,
              "cells": printable, "contrasts": cons}
    if args.out:
        args.out.write_text(json.dumps(result, indent=1) + "\n")

    print(f"{args.root.name}: {len(args.suffixes)} pass(es)\n")
    head = "  {:<18} {:>3}  ".format("arm", "n") + "".join(f"{s.replace('.qwen38','p'):>8}" for s in args.suffixes)
    print(head + f"{'mean':>9}{'sd':>8}{'range':>8}  drop")
    for arm, c in cells.items():
        if not c["mean_per_pass"]:
            print(f"  {arm:<18}   —  (nothing graded)")
            continue
        row = f"  {arm:<18} {c['n_common_cases']:>3}  "
        row += "".join(f"{c['mean_per_pass'][s]:>8.4f}" for s in args.suffixes)
        sd = c["sd_across_passes"]
        row += f"{c['mean_of_means']:>9.4f}{(sd if sd is not None else float('nan')):>8.4f}{c['range']:>8.4f}"
        row += f"  {len(c['dropped_by_some_pass']) or '-'}"
        print(row)

    if cons:
        print("\n  contrasts, computed within each session:")
        for c in cons:
            print(f"    {c['contrast']:<34} mean {c['mean']:+.4f}  sd {c['sd']}  "
                  f"range {c['range']}  sign stable: {c['sign_stable']}")
            print(f"      {'':<32} sum of component sds: {c['sum_of_component_sds']} "
                  f"(H7 wants the contrast sd below this)")

    if args.offset is not None:
        print(f"\n  H5: between-model offset at n=1 was {args.offset:+.4f}")
        for arm, c in cells.items():
            sd = c["sd_across_passes"]
            if sd is None:
                continue
            verdict = "SURVIVES the spread" if abs(args.offset) > 2 * sd else "INDISTINGUISHABLE from noise"
            print(f"    {arm:<18} within-model sd {sd:.4f}  ->  offset {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
