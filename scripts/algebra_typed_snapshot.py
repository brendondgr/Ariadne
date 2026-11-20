#!/usr/bin/env python3
"""Phase D check: today's typed steps compile to the same query text after the move.

``snapshot`` compiles every distinct recorded typed step with the current
builders, and writes the drafts (template, query, parameters, meta) to a JSONL
file. ``compare`` compiles them again on the current tree and reports every
difference. Take the snapshot at the commit before Phase D's move, then compare
after it. The bar is zero differences, and the snapshot is never updated to
match.

Steps come from ``algebra_convert_check.recorded_steps`` (EXP-2026-11-018's
outputs). A step with no anchor ids is compiled with its recorded seed ids when
the record has them, else with one fixed placeholder id per graph. Seeds change
only the parameters, never the query's shape.

    uv run python scripts/algebra_typed_snapshot.py snapshot OUT.jsonl
    uv run python scripts/algebra_typed_snapshot.py compare  OUT.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
LIMITS = {"max_traversal_depth": 3, "max_result_rows": 1000, "query_timeout_ms": 5000}
PLACEHOLDER = {"attack": ("T1047",), "capec": ("CAPEC-66",)}


def distinct_steps() -> list[dict]:
    from scripts.algebra_convert_check import RUN, recorded_steps

    seen, out = set(), []
    for s in recorded_steps(RUN):
        seeds = tuple(s["step"].get("anchor_ids") or ()) or PLACEHOLDER.get(s["source"], ())
        key = json.dumps([s["source"], s["step"], seeds], sort_keys=True)
        if key not in seen:
            seen.add(key)
            out.append({"key": key, "source": s["source"], "step": s["step"], "seeds": list(seeds)})
    return out


def compile_all(steps: list[dict]) -> list[dict]:
    from utils.config import load_env
    from utils.planner.cards import load_source_cards
    from utils.specialists.contracts import SpecialistTask
    from utils.specialists.cypher.builder import CypherQueryBuilder
    from utils.specialists.gremlin.builder import GremlinQueryBuilder
    from utils.specialists.resolve import resolve
    from utils.specialists.signals import TypedStep, step_signals

    load_env()
    cards = load_source_cards(REPO / "data")
    out = []
    for s in steps:
        step = TypedStep.from_dict(s["step"])
        card = cards[s["source"]]
        task = SpecialistTask(sub_question_id="q1", source=s["source"], text="", entities=tuple(step.entities()),
                              limits=dict(LIMITS), seed_ids=tuple(s["seeds"]), signals=step_signals(step))
        builder = GremlinQueryBuilder() if card.runtime_backend == "gremlin" else CypherQueryBuilder()
        try:
            d = builder.build(resolve(task, card), None)
            row = {"template": d.template, "query": d.query, "params": d.params, "meta": d.meta}
        except Exception as exc:  # noqa: BLE001 - an error is part of the snapshot
            row = {"error": f"{type(exc).__name__}: {exc}"}
        out.append({"key": s["key"], **json.loads(json.dumps(row, sort_keys=True, default=str))})
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["snapshot", "compare"])
    ap.add_argument("path")
    a = ap.parse_args(argv)
    rows = compile_all(distinct_steps())
    path = Path(a.path)
    if a.cmd == "snapshot":
        path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
        print(f"{len(rows)} drafts written to {path}")
        return 0
    want = {json.loads(line)["key"]: json.loads(line) for line in path.read_text().splitlines() if line.strip()}
    got = {r["key"]: r for r in rows}
    missing = sorted(set(want) - set(got))
    diff = [k for k in want if k in got and want[k] != got[k]]
    print(json.dumps({"snapshot": len(want), "compiled": len(got), "missing": len(missing), "different": len(diff)}))
    for k in diff[:5]:
        print("DIFF", k[:160])
        for f in ("template", "query", "params", "meta", "error"):
            if want[k].get(f) != got[k].get(f):
                print(f"  {f}:\n    want {str(want[k].get(f))[:400]}\n    got  {str(got[k].get(f))[:400]}")
    return 0 if not (missing or diff) else 1


if __name__ == "__main__":
    raise SystemExit(main())
