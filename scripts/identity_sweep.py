#!/usr/bin/env python3
"""EXP-2026-08-011 — run both arms against the identity schema and score them.

    uv run python scripts/identity_sweep.py --out docs/evaluation/identity-2026-08-21

**No language model is in the loop.** Planning is the deterministic drafter,
query construction is deterministic by construction, synthesis is the
deterministic composer, and the primary metric is computed by set comparison
against gold derived from the generator blueprint. The result is therefore
byte-reproducible and does not wait on the shared inference server -- which is
the whole reason the experiment was sequenced with this step before judging.

Two arms, the same pair EXP-2026-08-009 compared so the reading is calibrated
against a known instrument:

``deterministic``  the 25-template if-cascade
``generic``        schema-derived describe/expand primitives, templates off
                   (``SPECIALIST_GENERIC_ONLY``)

The gap between them is the measurement. C-010 counts the dataset-specific
surface by parsing source for template identifiers; this runs that surface
against a schema it was not written for and reports what the difference is
worth in retrieval.

Every question's result is written the moment it exists, so an interrupted run
reports what it finished, and ``--resume`` picks up from the state file.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from utils.config import load_env  # noqa: E402

load_env()

IDENTITY_DATA_DIR = "data-identity"
IDENTITY_NEO4J_URI = "bolt://localhost:5459"

# Every LLM seam off, explicitly, on both arms. Stated as data rather than
# assumed from .env, because .env is the operator's and this must not depend on
# what it happens to say today.
BASE_ENV: dict[str, str] = {
    "ARIADNE_DATA_DIR": IDENTITY_DATA_DIR,
    "NEO4J_URI": IDENTITY_NEO4J_URI,
    "PLANNER_LLM_ENABLED": "false",
    "SPECIALIST_LLM_ENABLED": "false",
    "SYNTHESIS_LLM_ENABLED": "false",
    "CONVERSATION_LLM_ENABLED": "false",
    "ORCH_MAX_HOPS": "5",
    "ORCH_CHASE_FACETS": "true",
    "ORCH_MAX_FACET_EXPANSIONS": "4",
}

ARMS: dict[str, dict[str, str]] = {
    "deterministic": {},
    "generic": {"SPECIALIST_GENERIC_ONLY": "true"},
}


def apply_env(overlay: dict[str, str]) -> None:
    for key, value in overlay.items():
        os.environ[key] = value


def clear_env(overlay: dict[str, str]) -> None:
    for key in overlay:
        os.environ.pop(key, None)


def _record_ids(evidence: Any) -> set[str]:
    """Every identifier an evidence record exposes, however it is shaped.

    Deliberately permissive. The scorer's job is to ask whether the gold node
    was retrieved, not whether the harness put it in the column the scorer
    happened to expect -- a strict reading would score the evidence reader's
    column conventions rather than retrieval, which is the confound Q18 already
    records against C-012.
    """
    found: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(value, str) and key in {
                    "id",
                    "record_id",
                    "primary_id",
                    "node_id",
                    "name",
                    "group_id",
                    "group_name",
                    "technique_id",
                    "technique_name",
                }:
                    found.add(value)
                else:
                    walk(value)
        elif isinstance(node, (list, tuple)):
            for item in node:
                walk(item)

    walk(evidence)
    return found


def run_one(question: str) -> dict[str, Any]:
    """Run one question through the real pipeline and capture what it retrieved."""
    from utils.orchestration.main import PipelineRun, iter_pipeline

    run = PipelineRun(question=question, mode="query")
    plan_sources: list[str] = []
    evidence_payload: Any = None
    answer_text = ""
    abstained = False
    queries: list[str] = []

    for event, payload in iter_pipeline(
        question, mode="query", use_llm=False, data_dir=IDENTITY_DATA_DIR, run=run
    ):
        if event == "plan":
            plan = payload.get("plan")
            if plan is not None:
                plan_sources = sorted(plan.target_sources())
        elif event == "evidence":
            evidence_payload = payload.get("evidence")
        elif event == "answer":
            if payload.get("evidence") is not None:
                evidence_payload = payload["evidence"]
            answer = payload.get("synthesized")
            answer_text = getattr(answer, "narrative", "") or str(answer or "")
            abstained = bool(getattr(answer, "abstained", False))

    blob = json.loads(json.dumps(evidence_payload, default=str)) if evidence_payload else {}
    for match in json.dumps(blob).split('"query": "')[1:]:
        queries.append(match.split('"')[0])

    return {
        "plan_sources": plan_sources,
        "retrieved_ids": sorted(_record_ids(blob)),
        "queries": queries[:6],
        "answer": answer_text[:4000],
        "abstained": abstained,
    }


def score(entry: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """Gold-in-evidence retrieval for one question.

    For ``unanswerable`` the correct behaviour is an abstention, so the score is
    1.0 when the arm declined or returned nothing beyond the anchor, and 0.0
    when it produced neighbours it could not have had.
    """
    retrieved = set(result["retrieved_ids"])
    gold_ids = set(entry["expected_ids"])
    gold_names = set(entry["expected_names"])

    if entry["kind"] == "unanswerable":
        leaked = bool(retrieved - {entry["anchor_id"], entry["anchor_name"]})
        return {
            "retrieval": 0.0 if leaked else 1.0,
            "hit": 0 if leaked else 1,
            "of": 1,
            "abstained": result["abstained"],
        }

    # A gold node counts as retrieved if either its opaque id or its name is
    # present. Both are legitimate: the id is what the graph joins on, the name
    # is what an analyst reads, and different templates surface different ones.
    hits = 0
    for node_id, name in zip(sorted(gold_ids), sorted(gold_names)) if len(
        gold_ids
    ) == len(gold_names) else [(i, "") for i in sorted(gold_ids)]:
        if node_id in retrieved or (name and name in retrieved):
            hits += 1
    if not gold_ids:
        return {"retrieval": 1.0, "hit": 0, "of": 0, "abstained": result["abstained"]}
    return {
        "retrieval": hits / len(gold_ids),
        "hit": hits,
        "of": len(gold_ids),
        "abstained": result["abstained"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default="docs/evaluation/identity-2026-08-21")
    parser.add_argument("--arms", default="generic,deterministic")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)

    out = Path(args.out)
    bank = json.loads((out / "bank.json").read_text(encoding="utf-8"))
    questions = bank["questions"]
    state_path = out / "sweep_state.json"
    state: dict[str, Any] = (
        json.loads(state_path.read_text(encoding="utf-8"))
        if args.resume and state_path.is_file()
        else {"results": {}}
    )

    order = list(questions)
    if args.limit:
        order = order[: args.limit]

    for arm in args.arms.split(","):
        arm = arm.strip()
        if not arm:
            continue
        overlay = {**BASE_ENV, **ARMS[arm]}
        apply_env(overlay)
        # The registry caches per data dir; an arm switch must not reuse the
        # previous arm's build.
        from utils.specialists.schema.build import get_registry

        get_registry.cache_clear()

        for index, qid in enumerate(order, 1):
            key = f"{arm}::{qid}"
            if key in state["results"]:
                continue
            entry = questions[qid]
            started = time.time()
            try:
                result = run_one(entry["question"])
                error = None
            except Exception as exc:  # a failure is a datum, not a stop
                result = {
                    "plan_sources": [],
                    "retrieved_ids": [],
                    "queries": [],
                    "answer": "",
                    "abstained": False,
                }
                error = f"{type(exc).__name__}: {exc}"
            scored = score(entry, result)
            state["results"][key] = {
                "arm": arm,
                "question_id": qid,
                "kind": entry["kind"],
                "homogeneous": entry["homogeneous"],
                "uses_inferred": entry["uses_inferred"],
                "direction": entry["direction"],
                "edge": entry["edge"],
                "anchor_label": entry["anchor_label"],
                "neighbour_label": entry["neighbour_label"],
                "question": entry["question"],
                "expected_count": entry["expected_count"],
                "elapsed_s": round(time.time() - started, 2),
                "error": error,
                **result,
                **scored,
            }
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
            print(
                f"[{arm}] {index}/{len(order)} {qid:22s} {entry['kind']:13s} "
                f"{scored['hit']}/{scored['of']}  {scored['retrieval']:.2f}"
                + (f"  ERROR {error}" if error else "")
            )
        clear_env(ARMS[arm])

    print(f"\nwrote {state_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
