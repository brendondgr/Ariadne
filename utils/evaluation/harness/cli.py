#!/usr/bin/env python3
"""Command-line orchestrator for the decoupled golden-evaluation harness.

Each stage is independently runnable and hands off through persisted artifacts
under ``--out-dir`` (default ``docs/evaluation/golden``):

    run     golden set        -> answers.jsonl
    judge   answers.jsonl     -> judgments.jsonl
    report  judgments.jsonl   -> golden-eval.{md,json}
    all     run -> judge -> report in one process

Usage:
    uv run python -m utils.evaluation.harness.cli --stage run --set attack --limit 3
    uv run python -m utils.evaluation.harness.cli --stage judge --llm
    uv run python -m utils.evaluation.harness.cli --stage report
    uv run python -m utils.evaluation.harness.cli --stage all --set all --llm
"""

from __future__ import annotations

import argparse
import os
import sys

from utils.evaluation.harness.golden import ALL_SETS

DEFAULT_OUT_DIR = "docs/evaluation/golden"
ANSWERS_NAME = "answers.jsonl"
JUDGMENTS_NAME = "judgments.jsonl"
REPORT_MD_NAME = "golden-eval.md"
REPORT_JSON_NAME = "golden-eval.json"


def _paths(out_dir: str) -> dict[str, str]:
    return {
        "answers": os.path.join(out_dir, ANSWERS_NAME),
        "judgments": os.path.join(out_dir, JUDGMENTS_NAME),
        "report_md": os.path.join(out_dir, REPORT_MD_NAME),
        "report_json": os.path.join(out_dir, REPORT_JSON_NAME),
    }


def _resolve_sets(value: str) -> list[str]:
    if value == "all":
        return list(ALL_SETS)
    if value not in ALL_SETS:
        raise SystemExit(f"--set must be one of all|{'|'.join(ALL_SETS)}")
    return [value]


def do_run(args, paths: dict[str, str]) -> int:
    from utils.evaluation.harness.contracts import write_jsonl
    from utils.evaluation.harness.golden import load_entries
    from utils.evaluation.harness.run_stage import RunnerAgent, stack_reachable

    live = (not args.no_live) and stack_reachable()
    entries = load_entries(
        _resolve_sets(args.set),
        limit=args.limit,
        tiers=set(args.tier) if args.tier else None,
    )
    if args.agentic:
        mode = "agentic (real LLM pipeline: planner+specialists+synthesis)"
    elif args.llm_pipeline:
        mode = "gold path, LLM composer"
    else:
        mode = "gold path, deterministic"
    print(
        f"[run] {len(entries)} golden entries — live: "
        f"{'ON' if live else 'OFF (hermetic; nothing scored)'}, "
        f"pipeline: {mode}, concurrency={args.concurrency}",
        file=sys.stderr,
    )
    if not live:
        n = write_jsonl(paths["answers"], [])
    else:
        runner = RunnerAgent(
            agentic=args.agentic,
            use_llm_pipeline=args.llm_pipeline,
            concurrency=args.concurrency,
            data_dir=args.data_dir,
        )
        records = runner.run(entries)
        n = write_jsonl(paths["answers"], records)
        ran = sum(1 for r in records if r.error is None)
        print(f"[run] {ran}/{n} answered without error", file=sys.stderr)
    print(f"[run] wrote {n} answers to {paths['answers']}", file=sys.stderr)
    return 0


def do_judge(args, paths: dict[str, str]) -> int:
    from utils.evaluation.harness.judge_stage import JudgeAgent

    return JudgeAgent.from_args(args).run_files(
        paths["answers"], paths["judgments"]
    )


def do_report(args, paths: dict[str, str]) -> int:
    from utils.evaluation.harness.report_stage import ReporterAgent

    return ReporterAgent().run_files(
        paths["answers"],
        paths["judgments"],
        paths["report_md"],
        paths["report_json"],
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Decoupled golden-evaluation harness (run -> judge -> report)."
    )
    parser.add_argument(
        "--stage", choices=("run", "judge", "report", "all"), default="all"
    )
    parser.add_argument("--set", default="all", help="attack|capec|federated|all")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--limit", type=int, default=None, help="cap entries per set")
    parser.add_argument(
        "--tier", action="append", default=None, help="keep only this tier (repeatable)"
    )
    parser.add_argument("--data-dir", default=None)
    parser.add_argument(
        "--concurrency", type=int, default=16,
        help="max questions/answers processed in parallel (default 16)",
    )
    parser.add_argument(
        "--no-live", action="store_true", help="skip live running (hermetic)"
    )
    parser.add_argument(
        "--agentic", action="store_true",
        help="run each RAW question through the real LLM agentic pipeline "
             "(planner+specialists+synthesis via the local LLM), as the workbench does",
    )
    parser.add_argument(
        "--llm", dest="llm", action="store_true",
        help="use the local LLM to judge correctness (default: deterministic backstop)",
    )
    parser.add_argument(
        "--llm-pipeline", action="store_true",
        help="gold path only: enable the LLM composer while replaying pre-authored tasks",
    )
    parser.add_argument(
        "--judge-sample", type=int, default=None,
        help="max answers the LLM judge scores (rest use the deterministic backstop)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = _paths(args.out_dir)
    os.makedirs(args.out_dir, exist_ok=True)

    if args.stage in ("run", "all"):
        rc = do_run(args, paths)
        if rc != 0:
            return rc
    if args.stage in ("judge", "all"):
        rc = do_judge(args, paths)
        if rc != 0:
            return rc
    if args.stage in ("report", "all"):
        rc = do_report(args, paths)
        if rc != 0:
            return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
