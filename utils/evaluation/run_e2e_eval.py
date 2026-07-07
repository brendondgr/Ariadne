#!/usr/bin/env python3
"""Run the end-to-end evaluation and write the e2e report.

Usage:
    uv run python -m utils.evaluation.run_e2e_eval [--out-dir docs/evaluation]
        [--no-live] [--judge] [--judge-sample N] [--limit N] [--no-single]

The four e2e metrics and the unsupported-claim rate are deterministic. The LLM
judge is opt-in (``--judge`` or ``EVAL_LLM_ENABLED``); without it the
deterministic proxy fills the qualitative dimensions and the report is
byte-reproducible. Live scoring needs both backends up; ``--no-live`` (or an
unreachable stack) produces an honest hermetic report that scores nothing.
"""

from __future__ import annotations

import argparse
import dataclasses
import sys

from utils.evaluation.e2e_report import build_json, collect_e2e, write_report
from utils.evaluation.llm_judge import EvalConfig

MD_NAME = "e2e-evaluation.md"
JSON_NAME = "e2e-evaluation.json"


def _stack_reachable() -> bool:
    try:
        from utils.specialists.tests.test_cypher_specialist import _neo4j_reachable
        from utils.specialists.tests.test_gremlin_specialist import _gremlin_reachable

        return bool(_neo4j_reachable() and _gremlin_reachable())
    except Exception:  # pragma: no cover - defensive: never let probing crash the run
        return False


def _meta(live: bool, judge_source_hint: str) -> dict[str, str]:
    from utils.specialists.evalset.gold_bank import load_gold_bank

    meta = load_gold_bank()["meta"]
    note = (
        f"full report (live), judge={judge_source_hint}"
        if live
        else "hermetic-only (nothing scored)"
    )
    return {
        "attack_version": meta.get("attack_version", "?"),
        "capec_version": meta.get("capec_version", "?"),
        "generated_note": note,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the end-to-end evaluation.")
    parser.add_argument("--out-dir", default="docs/evaluation")
    parser.add_argument("--no-live", action="store_true", help="skip live scoring")
    parser.add_argument("--judge", action="store_true", help="enable the LLM judge")
    parser.add_argument("--judge-sample", type=int, default=None,
                        help="max answers the LLM judge scores (default from env)")
    parser.add_argument("--limit", type=int, default=None,
                        help="cap entries per bank (smoke runs)")
    parser.add_argument("--no-single", action="store_true",
                        help="score only the federated bank")
    args = parser.parse_args(argv)

    live = (not args.no_live) and _stack_reachable()

    judge_config = EvalConfig.from_env()
    if args.judge:
        judge_config = dataclasses.replace(judge_config, llm_enabled=True)
    if args.judge_sample is not None:
        judge_config = dataclasses.replace(judge_config, sample_size=args.judge_sample)

    print(
        f"End-to-end evaluation — live: {'ON' if live else 'OFF (hermetic)'}, "
        f"LLM judge: {'ON' if judge_config.llm_enabled else 'OFF (proxy)'}",
        file=sys.stderr,
    )

    e2e = collect_e2e(
        live=live,
        judge_config=judge_config,
        limit=args.limit,
        include_single=not args.no_single,
    )
    judge_hint = "llm" if judge_config.llm_enabled else "proxy"
    data = build_json(e2e, _meta(live, judge_hint))

    md_path = f"{args.out_dir}/{MD_NAME}"
    json_path = f"{args.out_dir}/{JSON_NAME}"
    write_report(data, md_path, json_path)
    print(f"wrote {md_path} and {json_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
