#!/usr/bin/env python3
"""Does a question's gold-set size predict its judged score? (Q29)

Thin CLI over `utils.evaluation.gold_width`, which carries the joining rules and
the reason width must be read from the committed bank rather than from the
grader's own estimate.

Usage:
    uv run python scripts/gold_width_effect.py
    uv run python scripts/gold_width_effect.py --json out.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from utils.evaluation.gold_width import (
    ASKABLE_P90,
    analyse,
    federated_ids,
    load,
    load_banks,
    run_bank_map,
    verify_grader_field_unused,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()

    # The mistake this analysis was written after making, kept closed.
    verify_grader_field_unused(Path(__file__))

    excluded = federated_ids()
    banks, bank_ids = load_banks(excluded)
    runs = run_bank_map(bank_ids)
    rows, skipped = load(banks, runs, excluded)
    result = analyse(rows, skipped)

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, indent=1) + "\n")

    print(f"banks: {', '.join(f'{k}({len(v)})' for k, v in sorted(banks.items()))}")
    print(f"runs mapped to a bank: {len(runs)}")
    print(f"\n{result['n_judgments_joined']} judgments joined to a committed gold set; "
          f"{result['n_answerable']} answerable, "
          f"{result['n_abstention_probes']} abstention probes excluded")
    print(f"skipped: {result['skipped']}")

    width = result["width"]
    print(f"\n{result['distinct_questions']} distinct questions; "
          f"gold width median {width['median']:g}, p90 {width['p90']}, max {width['max']}")
    print(f"  questions with gold > 20: {result['questions_over_20']}; "
          f"> 50: {result['questions_over_50']}")

    print(f"\npooled r(width, correctness)  = {result['pooled_r']:+.4f}")
    cell = result["within_cell_r"]
    print(f"within-cell r over {cell['cells']} cells  = {cell['mean_r']:+.4f} "
          f"(sd {cell['sd_r']:.4f}; negative in {cell['negative_cells']}/{cell['cells']})")
    for key in (f"narrow_vs_wide_at_{ASKABLE_P90}", "narrow_vs_wide_at_20", "narrow_vs_wide_at_10"):
        delta = result[key]
        if delta.get("cells"):
            print(f"{key:<24} = {delta['mean_delta']:+.4f} ± {delta['se']:.4f} se over "
                  f"{delta['cells']} cells; negative in {delta['negative_cells']}/{delta['cells']}")

    print("\nbin        n  cases  correctness  completeness")
    for row in result["bins"]:
        comp = f"{row['completeness']:.4f}" if row["completeness"] is not None else "  —   "
        print(f"{row['bin']:>8} {row['n']:6} {row['cases']:6}    {row['correctness']:.4f}      {comp}")

    print("\nwidest question categories")
    print("category           n  cases  median   max   correctness")
    for row in result["widest_categories"]:
        print(f"{row['category']:<16} {row['n']:5} {row['cases']:6} {row['median_width']:7g} "
              f"{row['max_width']:5}   {row['correctness']:.4f}")


if __name__ == "__main__":
    main()
