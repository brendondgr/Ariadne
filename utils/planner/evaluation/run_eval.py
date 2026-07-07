#!/usr/bin/env python3
"""Run the planner evaluation corpus and print a plan-level metrics report.

Usage:
    uv run python -m utils.planner.evaluation.run_eval [--split dev|holdout]
        [--data-dir DIR] [--drafter deterministic|llm|hybrid] [--json]

By default scores the deterministic drafter (byte-reproducible). ``--drafter
llm``/``hybrid`` scores the LLM path best-effort: if the OpenAI-compatible
endpoint is unreachable the hybrid drafter falls back to deterministic, which is
reported in the ``drafter`` field rather than failing the run.
"""

from __future__ import annotations

import argparse
import dataclasses
import json as _json
import sys

from ..cards import load_source_cards
from ..config import PlannerConfig
from ..drafter import DeterministicDrafter, PlanDrafter
from ..drafter_factory import select_drafter
from .corpus import run_corpus
from .scorer import CaseScore, aggregate


def _build_drafter(kind: str, data_dir: str) -> PlanDrafter:
    """Deterministic by default; llm/hybrid go through the config-driven factory."""
    if kind == "deterministic":
        return DeterministicDrafter()
    config = dataclasses.replace(
        PlannerConfig.from_env(), data_dir=data_dir, llm_enabled=True
    )
    return select_drafter(config)


def _split_report(scores: list[CaseScore], split: str) -> dict:
    subset = [s for s in scores if s.split == split]
    return aggregate(subset) if subset else {"cases": 0}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate the planning agent's plan output.")
    parser.add_argument("--split", choices=["dev", "holdout"], default=None,
                        help="Restrict to one split (default: all cases)")
    parser.add_argument("--data-dir", default="data",
                        help="Directory holding source_cards/ (default: data)")
    parser.add_argument("--drafter", choices=["deterministic", "llm", "hybrid"],
                        default="deterministic",
                        help="Which drafter to score (default: deterministic)")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args(argv)

    cards = load_source_cards(args.data_dir)
    if not cards:
        print(f"No source cards under {args.data_dir}/source_cards — build them first.", file=sys.stderr)
        return 2

    drafter = _build_drafter(args.drafter, args.data_dir)
    results = run_corpus(cards, split=args.split, drafter=drafter)
    scores = [score for _case, _plan, score in results]
    drafter_used = next(
        (plan.trace[-1]["drafter"] for _c, plan, _s in results if plan.trace),
        type(drafter).__name__,
    )
    agg = aggregate(scores)

    if args.json:
        payload = {
            "drafter_requested": args.drafter,
            "drafter_used": drafter_used,
            "aggregate": agg,
            "dev": _split_report(scores, "dev"),
            "holdout": _split_report(scores, "holdout"),
            "cases": [s.to_dict() for s in scores],
        }
        print(_json.dumps(payload, indent=2))
        return 0 if agg.get("pass_rate", 0) == 1.0 else 1

    print(f"\nPlanner evaluation — {agg['cases']} case(s)"
          + (f" [split={args.split}]" if args.split else "")
          + f" [drafter={args.drafter} -> {drafter_used}]")
    print("-" * 84)
    for score in scores:
        status = "PASS" if score.passed else "FAIL"
        print(
            f"  [{status}] {score.name:32s} [{score.split:7s}] "
            f"src_rec={score.source_recall:.2f} "
            f"sub_q={score.sub_question_quality:.2f} "
            f"(cnt={'y' if score.count_correct else 'n'}"
            f"/rte={'y' if score.routing_correct else 'n'}"
            f"/dep={'y' if score.dependency_correct else 'n'}) "
            f"unnec={score.unnecessary_source_calls} "
            f"schema={'ok' if score.schema_adherent else 'BAD'}"
        )
        if not score.passed and score.gate_reasons:
            print(f"           gate: {score.gate_reasons[0]}")
    print("-" * 84)
    for key, value in agg.items():
        print(f"  {key}: {value}")
    if args.split is None:
        for split in ("dev", "holdout"):
            sub = _split_report(scores, split)
            print(f"  [{split}] cases={sub.get('cases')} "
                  f"pass_rate={sub.get('pass_rate')} "
                  f"sub_question_quality={sub.get('mean_sub_question_quality')}")
    print()
    return 0 if agg.get("pass_rate", 0) == 1.0 else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
