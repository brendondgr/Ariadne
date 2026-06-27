#!/usr/bin/env python3
"""Run the planner evaluation corpus and print a plan-level metrics report.

Usage:
    uv run python -m utils.planner.evaluation.run_eval [--split dev|holdout]
                                                       [--data-dir DIR] [--json]

Scores the deterministic drafter (for reproducibility) against the expected
plans, isolating the planner from any downstream phase.
"""

from __future__ import annotations

import argparse
import json as _json
import sys

from ..cards import load_source_cards
from .corpus import run_corpus
from .scorer import aggregate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate the planning agent's plan output.")
    parser.add_argument("--split", choices=["dev", "holdout"], default=None,
                        help="Restrict to one split (default: all cases)")
    parser.add_argument("--data-dir", default="data",
                        help="Directory holding source_cards/ (default: data)")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args(argv)

    cards = load_source_cards(args.data_dir)
    if not cards:
        print(f"No source cards under {args.data_dir}/source_cards — build them first.", file=sys.stderr)
        return 2

    results = run_corpus(cards, split=args.split)
    scores = [score for _case, _plan, score in results]
    agg = aggregate(scores)

    if args.json:
        print(_json.dumps({"aggregate": agg, "cases": [s.to_dict() for s in scores]}, indent=2))
        return 0

    print(f"\nPlanner evaluation — {agg['cases']} case(s)"
          + (f" [split={args.split}]" if args.split else ""))
    print("-" * 72)
    for score in scores:
        status = "PASS" if score.passed else "FAIL"
        print(
            f"  [{status}] {score.name:32s} "
            f"src_recall={score.source_recall:.2f} "
            f"ent_recall={score.entity_recall:.2f} "
            f"unnec={score.unnecessary_source_calls} "
            f"schema={'ok' if score.schema_adherent else 'BAD'}"
        )
        if not score.passed and score.gate_reasons:
            print(f"           gate: {score.gate_reasons[0]}")
    print("-" * 72)
    for key, value in agg.items():
        print(f"  {key}: {value}")
    print()
    return 0 if agg.get("pass_rate", 0) == 1.0 else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
