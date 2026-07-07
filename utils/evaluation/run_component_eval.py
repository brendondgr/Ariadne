#!/usr/bin/env python3
"""Run every component scorer and write the component-evaluation report.

Usage:
    uv run python -m utils.evaluation.run_component_eval [--out-dir docs/evaluation]
                                                         [--no-live]

Planner + query-validity + safety are hermetic and always run; execution
accuracy and latency are live and are skipped (with an honest note in the
report) when the graph stack is unreachable or --no-live is passed.
"""

from __future__ import annotations

import argparse
import sys

from utils.evaluation.component_report import (
    build_json,
    collect_planner,
    collect_specialists,
    write_report,
)

MD_NAME = "component-evaluation.md"
JSON_NAME = "component-evaluation.json"


def _stack_reachable() -> bool:
    try:
        from utils.specialists.tests.test_cypher_specialist import _neo4j_reachable
        from utils.specialists.tests.test_gremlin_specialist import _gremlin_reachable
        return bool(_neo4j_reachable() and _gremlin_reachable())
    except Exception:  # pragma: no cover - defensive: never let probing crash the run
        return False


def _meta(live: bool) -> dict[str, str]:
    from utils.specialists.evalset.gold_bank import load_gold_bank

    meta = load_gold_bank()["meta"]
    note = "full report (live EX + latency)" if live else "hermetic-only (EX + latency skipped)"
    return {
        "attack_version": meta.get("attack_version", "?"),
        "capec_version": meta.get("capec_version", "?"),
        "generated_note": note,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the component-level evaluation.")
    parser.add_argument("--out-dir", default="docs/evaluation")
    parser.add_argument("--no-live", action="store_true", help="skip live EX + latency")
    args = parser.parse_args(argv)

    live = (not args.no_live) and _stack_reachable()
    print(f"Component evaluation — live scorers: {'ON' if live else 'OFF (hermetic only)'}",
          file=sys.stderr)

    planner = collect_planner()
    specialists = collect_specialists(live=live)
    data = build_json(planner, specialists, _meta(live))

    md_path = f"{args.out_dir}/{MD_NAME}"
    json_path = f"{args.out_dir}/{JSON_NAME}"
    write_report(data, md_path, json_path)
    print(f"wrote {md_path} and {json_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
