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
from dataclasses import replace
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from utils.config import load_env  # noqa: E402

load_env()

IDENTITY_DATA_DIR = "data/identity"
IDENTITY_NEO4J_URI = "bolt://localhost:5459"

# The tri-source condition: the SAME bank and the SAME gold, run against a card
# directory holding ATT&CK, CAPEC and the identity graph at once instead of the
# identity graph alone. Nothing about the questions or the expected answers
# changes, so the difference between the two runs is the cost of having three
# live sources rather than one -- which is measurable without supplying any
# knowledge, and is the honest floor beneath any cross-source correlation.
TRI_DATA_DIR = "data-tri"
TRI_ENV: dict[str, str] = {
    "ARIADNE_ENDPOINT_ATTACK": "bolt://localhost:5456",
    "ARIADNE_ENDPOINT_CAPEC": "ws://localhost:6455/gremlin",
    "ARIADNE_ENDPOINT_IDENTITY": IDENTITY_NEO4J_URI,
}

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


def run_one(question: str, data_dir: str | None = None) -> dict[str, Any]:
    """Run one question through the real pipeline and capture what it retrieved."""
    from utils.orchestration.main import PipelineRun, iter_pipeline

    data_dir = data_dir or os.environ.get("ARIADNE_DATA_DIR") or IDENTITY_DATA_DIR

    run = PipelineRun(question=question, mode="query")
    plan_sources: list[str] = []
    evidence_payload: Any = None
    answer_text = ""
    answer_obj: Any = None
    abstained = False
    queries: list[str] = []

    for event, payload in iter_pipeline(
        question, mode="query", use_llm=False, data_dir=data_dir, run=run
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
            answer_obj = answer
            answer_text = getattr(answer, "narrative", "") or str(answer or "")
            abstained = bool(getattr(answer, "abstained", False))

    # `to_dict()`, not `json.dumps(..., default=str)`. The evidence bundle is a
    # dataclass tree, and `default=str` silently flattens each node to its repr
    # -- which yields a JSON *string* where the structure should be, so every
    # nested query and record id disappears. That produced an empty query list
    # and an apparent "0/27 questions routed correctly" that was an artifact of
    # this function, not a measurement.
    blob: dict[str, Any] = {}
    if evidence_payload is not None:
        to_dict = getattr(evidence_payload, "to_dict", None)
        blob = to_dict() if callable(to_dict) else json.loads(
            json.dumps(evidence_payload, default=str)
        )

    def collect_queries(node: Any) -> None:
        if isinstance(node, dict):
            value = node.get("query")
            if isinstance(value, str) and value:
                queries.append(value)
            for item in node.values():
                collect_queries(item)
        elif isinstance(node, (list, tuple)):
            for item in node:
                collect_queries(item)

    collect_queries(blob)

    return {
        "plan_sources": plan_sources,
        "retrieved_ids": sorted(_record_ids(blob)),
        "queries": queries[:6],
        "answer": answer_text[:4000],
        "abstained": abstained,
        # The live objects, for the judge stage. Not serialised into the state
        # file -- they are rebuilt by re-running, which is free of a language
        # model and byte-reproducible on this path.
        "_answer_obj": answer_obj,
        "_evidence_obj": evidence_payload,
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



class _RetryingJudge:
    """The LLM judge with bounded retries, falling back only once exhausted.

    The shared judge raises ``JudgeUnavailable`` on any failure and the hybrid
    wrapper drops straight to the deterministic proxy. On an idle relay that is
    fine; on a contended one it silently converts a correctness measurement into
    a proxy measurement, which is how the first development-bank pass ended up
    with 0 of 27 answers actually judged (ISSUES I-7).

    Retrying here rather than inside ``utils/evaluation/llm_judge`` is
    deliberate: that module is the instrument several recorded experiments were
    measured with, and changing its failure behaviour would change what their
    numbers mean.
    """

    name = "llm"

    def __init__(self, inner: Any, proxy: Any, attempts: int, backoff_s: float) -> None:
        self._inner = inner
        self._proxy = proxy
        self._attempts = attempts
        self._backoff = backoff_s
        self.retried = 0
        self.exhausted: list[str] = []

    def judge(self, question_id: str, answer: Any, evidence: Any) -> Any:
        last: Exception | None = None
        for attempt in range(1, self._attempts + 1):
            try:
                verdict = self._inner.judge(question_id, answer, evidence)
                if attempt > 1:
                    self.retried += 1
                return verdict
            except Exception as exc:  # JudgeUnavailable and transport errors
                last = exc
                if attempt < self._attempts:
                    time.sleep(self._backoff * attempt)
        self.exhausted.append(question_id)
        print(f"    judge exhausted {self._attempts} attempts on {question_id}: {last}")
        return self._proxy.judge(question_id, answer, evidence)


def judge(
    out: Path,
    arms: list[str],
    limit: int = 0,
    attempts: int = 4,
    backoff: float = 20.0,
    workers: int | None = None,
) -> int:
    """Grade the persisted answers for correctness, not just retrieval.

    The answers are rebuilt by re-running the pipeline rather than read back
    from the state file. That is not wasteful: this path has no language model
    in it and is byte-reproducible, so the rebuild is exact, and the judge needs
    the structured answer and evidence objects rather than the prose the state
    file keeps.

    Judgments go to ``judgments.json`` -- a distinct filename, not a suffixed
    sidecar beside the bank, because a suffixed variant sitting next to its
    input has been re-consumed by a later pass in this repository before.
    """
    from utils.evaluation.llm_judge.config import EvalConfig
    from utils.evaluation.llm_judge.deterministic_judge import DeterministicJudge
    from utils.evaluation.llm_judge.factory import judge_run
    from utils.evaluation.llm_judge.llm_judge import OpenAICompatibleJudge

    bank = json.loads((out / "bank.json").read_text(encoding="utf-8"))
    questions = bank["questions"]
    order = list(questions)[: limit or None]

    config = EvalConfig.from_env()
    # Every answer must reach the LLM judge, not the first `sample_size` of
    # them -- a partial pass would silently mix two graders in one mean.
    needed = len(order) * len(arms)
    if config.sample_size < needed:
        config = replace(config, sample_size=needed)
    if workers:
        # Fewer concurrent posts on a contended relay. Eight simultaneous
        # requests against a saturated server is what produced the timeouts;
        # throughput is bounded by the server either way, so lowering this
        # costs wall time and buys coverage.
        config = replace(config, judge_workers=workers)
    print(
        f"judge: llm_enabled={config.llm_enabled} model={config.llm_model} "
        f"max_tokens={config.llm_max_tokens} workers={config.judge_workers} "
        f"sample_size={config.sample_size}"
    )
    if not config.llm_enabled:
        print("  WARNING: EVAL_LLM_ENABLED is not set — this would grade with the "
              "deterministic proxy only, which is not a correctness measurement.")

    payload: dict[str, Any] = {"meta": {"arms": arms, "n_questions": len(order)},
                               "verdicts": {}}
    path = out / "judgments.json"

    for arm in arms:
        overlay = {**BASE_ENV, **ARMS[arm]}
        apply_env(overlay)
        from utils.specialists.schema.build import get_registry

        get_registry.cache_clear()

        items: list[tuple[str, Any, Any]] = []
        for index, qid in enumerate(order, 1):
            try:
                result = run_one(questions[qid]["question"])
            except Exception as exc:
                print(f"[{arm}] {qid}: rebuild failed — {type(exc).__name__}: {exc}")
                continue
            answer_obj, evidence_obj = result["_answer_obj"], result["_evidence_obj"]
            if answer_obj is None or evidence_obj is None:
                print(f"[{arm}] {qid}: no answer object to judge")
                continue
            items.append((qid, answer_obj, evidence_obj))
            print(f"[{arm}] rebuilt {index}/{len(order)} {qid}")

        print(f"[{arm}] judging {len(items)} answers …")
        retrying = _RetryingJudge(
            OpenAICompatibleJudge(config), DeterministicJudge(), attempts, backoff
        )
        report = judge_run(items, config, judge=retrying)
        if retrying.retried or retrying.exhausted:
            print(
                f"[{arm}] retries that succeeded: {retrying.retried}; "
                f"exhausted (fell to proxy): {len(retrying.exhausted)}"
            )
        summary = report.to_dict()
        payload["verdicts"][arm] = summary
        print(
            f"[{arm}] source={summary['source']} "
            f"llm_covered={summary['llm_covered']}/{summary['answers_scored']} "
            f"faithfulness={summary['mean_faithfulness']} "
            f"groundedness={summary['mean_groundedness']} "
            f"sufficiency={summary['mean_evidence_sufficiency']} "
            f"unsupported={summary['mean_unsupported_claim_rate']}"
        )
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"[{arm}] wrote {path}")
        clear_env(ARMS[arm])

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default="docs/evaluation/identity-2026-08-21")
    parser.add_argument("--arms", default="generic,deterministic")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--stage", choices=["run", "judge"], default="run")
    parser.add_argument("--judge-attempts", type=int, default=4)
    parser.add_argument("--judge-backoff", type=float, default=20.0)
    parser.add_argument("--judge-workers", type=int, default=0)
    parser.add_argument(
        "--tri", action="store_true",
        help="run against data-tri (ATT&CK + CAPEC + identity live at once) "
             "instead of the identity graph alone; same bank, same gold",
    )
    args = parser.parse_args(argv)

    if args.tri:
        # Mutating the module's BASE_ENV rather than threading a parameter: every
        # arm overlay is applied on top of it, and the condition must reach all
        # of them identically or the comparison is not one thing changed.
        BASE_ENV["ARIADNE_DATA_DIR"] = TRI_DATA_DIR
        BASE_ENV.update(TRI_ENV)
        print(f"[tri] three sources live; data_dir={TRI_DATA_DIR}")

    out = Path(args.out)
    if args.stage == "judge":
        return judge(
            out,
            [a.strip() for a in args.arms.split(",") if a.strip()],
            args.limit,
            attempts=args.judge_attempts,
            backoff=args.judge_backoff,
            workers=args.judge_workers,
        )
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
            result = {k: v for k, v in result.items() if not k.startswith("_")}
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
