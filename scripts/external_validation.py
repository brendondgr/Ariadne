#!/usr/bin/env python3
"""EXP-2026-08-010 — does Ariadne survive questions it did not co-author?

Every correctness figure this project has published came from a bank Ariadne
co-authored. This runs the same arms, unchanged, over two published benchmarks
whose gold is set-valued ATT&CK identifiers, so the score needs no language
model at all.

Three things make the numbers readable:

**The oracle.** Both benchmarks predate ATT&CK 19.0, so a missed gold id is
either Ariadne's failure or the benchmark's staleness. The oracle reads the
canonical files directly and bounds what any retriever could return; Ariadne is
read against it rather than against 1.0.

**Two plan conditions.** Every published arm replays a plan its bank hands it.
Plan-given reproduces that. Plan-free hands over the question text and nothing
else, which is what a user actually gets and what no figure has ever measured.

**One subset for the slow arms.** The narrator and planner arms have a
single-stream local model in the loop, so they run a fixed 60-item subset --
and the fast arm is scored on that same 60 as well as on everything, so the
comparison is like-for-like rather than a comparison of sample sizes.

    uv run python scripts/external_validation.py sweep --out docs/evaluation/external-2026-08-21
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from utils.evaluation.external import fetch, items as items_mod, oracle  # noqa: E402
from utils.evaluation.external.families import FAMILIES  # noqa: E402
from utils.evaluation.external.graph import load_attack  # noqa: E402
from utils.evaluation.external.score import Score, extract_ids, pool  # noqa: E402

#: Fixed before the run. Changing either changes which questions were asked.
PER_FAMILY = 10
SAMPLE_SEED = 20260821
#: How many items the model-in-the-loop arms cover. Chosen for wall clock: the
#: local model answers one request at a time, so 182 items in the narrator arm
#: is hours. The subset is drawn deterministically and shared by both slow arms.
LLM_SUBSET = 60

PHASES = [
    ("oracle", "plan-given", "oracle", None),
    ("deterministic", "plan-given", "ariadne", None),
    ("generic", "plan-given", "ariadne", LLM_SUBSET),
    ("llm", "plan-free", "ariadne", LLM_SUBSET),
]


# -- items -------------------------------------------------------------------


def build_items() -> list[items_mod.Item]:
    """Every usable item from both benchmarks, in a stable order.

    Unusable means the anchor or some gold identifier is absent from the loaded
    ATT&CK 19.0 -- overwhelmingly Mobile entries, which this deployment does not
    hold. They are excluded from scoring and counted in the coverage block, never
    dropped in silence (D-021).
    """
    index = load_attack()
    everything = items_mod.cti_ate_items(
        fetch.read_cti_ate(fetch.fetch(fetch.CTI_ATE)), index)
    everything += items_mod.attackqa_items(
        fetch.read_attackqa(fetch.fetch(fetch.ATTACKQA)),
        per_family=PER_FAMILY, seed=SAMPLE_SEED, index=index)
    usable = [i for i in everything if i.anchor_present and i.gold_present]
    usable.sort(key=lambda i: i.item_id)
    return usable


def llm_subset(all_items: list[items_mod.Item]) -> list[items_mod.Item]:
    """A fixed, benchmark-balanced draw for the arms with a model in the loop.

    Interleaved by benchmark rather than sliced off the front: the item ids sort
    so that every cti-ate item precedes every AttackQA one, and a head slice
    would hand the slow arms a single benchmark and a single question shape.
    """
    import random

    rng = random.Random(SAMPLE_SEED)
    by_benchmark: dict[str, list] = {}
    for item in all_items:
        by_benchmark.setdefault(item.benchmark, []).append(item)
    for group in by_benchmark.values():
        rng.shuffle(group)
    out: list[items_mod.Item] = []
    order = sorted(by_benchmark)
    while len(out) < LLM_SUBSET and any(by_benchmark[b] for b in order):
        for benchmark in order:
            if by_benchmark[benchmark] and len(out) < LLM_SUBSET:
                out.append(by_benchmark[benchmark].pop())
    out.sort(key=lambda i: i.item_id)
    return out


# -- running one arm ---------------------------------------------------------


def answer_text(answer: Any) -> str:
    """What a person reads, which is what gets scored.

    Claim ``entity_ids`` are deliberately excluded. They are retrieval output,
    not the answer, and counting them would credit an arm for finding something
    it never said -- exactly the composer gap this project already knows about.
    They are recorded separately so the difference stays visible.
    """
    parts = [getattr(answer, "headline", "") or "", getattr(answer, "narrative", "") or ""]
    parts += [c.text or "" for c in (getattr(answer, "claims", None) or [])]
    return "\n".join(parts)


def retrieved_ids(answer: Any) -> set[str]:
    """Identifiers the claims carry structurally, said aloud or not."""
    found: set[str] = set()
    for claim in getattr(answer, "claims", None) or []:
        found.update(claim.entity_ids or ())
    return found


def run_child(arm: str, condition: str, out: Path, workers: int, limit: int | None) -> dict:
    """Run one arm over the external items in this process.

    A subprocess per arm, because the arm's posture is an environment overlay and
    the specialist pools are thread-local: two arms in one interpreter would read
    each other's flags.
    """
    from utils.config import load_env
    from utils.evaluation.experiment_untruncated import (
        RUNNERS, _MergedPool, _RouterPool, apply_env, untruncated_env,
    )

    # The ceiling is a file read, not an arm. Routing it through here would send
    # it down the retrieval path it exists to bound, and it has no entry in
    # RUNNERS -- so the failure would be 182 caught KeyErrors written as empty
    # answers, which score as a total collapse rather than as a mistake.
    if arm == "oracle":
        raise SystemExit("oracle is not an arm — call run_oracle()")

    load_env()
    apply_env(untruncated_env(arm=arm, llm_model="skynet", llm_max_tokens=16384))
    os.environ["ORCH_MAX_HOPS"] = "5"

    everything = build_items()
    work = llm_subset(everything) if limit else everything

    if arm in ("llm", "llm_loop", "gold_loop_llm", "generic"):
        run_pool = None
    elif arm == "merged":
        run_pool = _MergedPool()
    else:
        run_pool = _RouterPool(llm_enabled=False, llm_query_builder=False)

    answers = out / f"{arm}--{condition}"
    answers.mkdir(parents=True, exist_ok=True)
    plan_given = condition == "plan-given"

    def one(item: items_mod.Item) -> dict:
        started = time.time()
        entry = item.entry(plan_given=plan_given)
        evidence, answer, extra = RUNNERS[arm](entry, "attack", run_pool)
        return {
            "id": item.item_id, "benchmark": item.benchmark, "family": item.family,
            "anchor": item.anchor, "question": item.question,
            "gold": sorted(item.gold), "arm": arm, "condition": condition,
            "answer_text": answer_text(answer),
            "retrieved_ids": sorted(retrieved_ids(answer)),
            "composer": getattr(answer, "composer", None),
            "run_meta": {**extra, "wall_s": round(time.time() - started, 3)},
            "evidence_records": sum(len(r.records) for r in evidence.results),
        }

    started = time.time()
    ok = failed = 0
    print(f"[{arm}/{condition}] {len(work)} items, {workers} workers…", flush=True)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(one, i): i for i in work}
        for done, future in enumerate(as_completed(futures), start=1):
            item = futures[future]
            try:
                record = future.result()
            except Exception as exc:  # noqa: BLE001 — one bad item must not sink the arm
                failed += 1
                record = {"id": item.item_id, "benchmark": item.benchmark,
                          "family": item.family, "anchor": item.anchor,
                          "question": item.question, "gold": sorted(item.gold),
                          "arm": arm, "condition": condition, "answer_text": "",
                          "retrieved_ids": [],
                          "error": f"{type(exc).__name__}: {exc}"}
                print(f"  ! {item.item_id}: {record['error']}", flush=True)
            else:
                ok += 1
            (answers / f"{record['id']}.json").write_text(
                json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
            if done % 20 == 0 or done == len(work):
                print(f"  [{arm}/{condition}] {done}/{len(work)}", flush=True)

    summary = {"arm": arm, "condition": condition, "items": len(work),
               "ok": ok, "failed": failed,
               "wall_s": round(time.time() - started, 1)}
    (out / f"{arm}--{condition}.summary.json").write_text(
        json.dumps(summary, indent=2) + "\n")
    return summary


def run_oracle(out: Path) -> dict:
    """The ceiling. No subprocess, no pool, no model -- it is a file read."""
    index = load_attack()
    answers = out / "oracle--plan-given"
    answers.mkdir(parents=True, exist_ok=True)
    everything = build_items()
    for item in everything:
        (answers / f"{item.item_id}.json").write_text(json.dumps({
            "id": item.item_id, "benchmark": item.benchmark, "family": item.family,
            "anchor": item.anchor, "question": item.question,
            "gold": sorted(item.gold), "arm": "oracle", "condition": "plan-given",
            "answer_text": oracle.as_text(item, index),
            "retrieved_ids": sorted(oracle.answer(item, index)),
            "run_meta": {"planner": "none", "synthesis": "direct graph read"},
        }, indent=2, ensure_ascii=False), encoding="utf-8")
    summary = {"arm": "oracle", "condition": "plan-given",
               "items": len(everything), "ok": len(everything), "failed": 0,
               "wall_s": 0.0}
    (out / "oracle--plan-given.summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


# -- scoring -----------------------------------------------------------------


def score_cell(out: Path, arm: str, condition: str,
               restrict: set[str] | None = None) -> dict[str, Any]:
    """Score one arm's answers. No model is consulted anywhere in here."""
    index = load_attack()
    folder = out / f"{arm}--{condition}"
    if not folder.is_dir():
        return {"n": 0}

    lookup = {i.item_id: i for i in build_items()}
    scores: list[Score] = []
    loose_scores: list[Score] = []
    retrieval_scores: list[Score] = []
    per_item: list[dict] = []
    by_benchmark: dict[str, list[Score]] = {}
    by_family: dict[str, list[Score]] = {}
    errors = 0

    for path in sorted(folder.glob("*.json")):
        record = json.loads(path.read_text())
        item = lookup.get(record["id"])
        if item is None or (restrict is not None and item.item_id not in restrict):
            continue
        if record.get("error"):
            errors += 1
        targets = FAMILIES[item.family].target_labels
        # Both sides go through one extractor and one label filter, so neither
        # is helped by phrasing. The filter is what stops the anchor -- echoed
        # by nearly every answer -- from scoring as its own gold.
        said = {i for i in extract_ids(record.get("answer_text", ""))
                if index.label_of.get(i) in targets}
        held = {i for i in record.get("retrieved_ids", [])
                if index.label_of.get(i) in targets}
        gold = items_mod.apply_granularity(item, set(item.gold))
        said = items_mod.apply_granularity(item, said)
        held = items_mod.apply_granularity(item, held)

        # What the answer names once the anchor is removed, WITHOUT the
        # type filter. The filtered figure is the fair recall comparison --
        # both sides get it -- but it is generous about precision to an arm
        # that dumps every neighbour and lets the filter tidy up. This is what
        # a reader actually sees.
        loose = items_mod.apply_granularity(
            item, {i for i in extract_ids(record.get("answer_text", ""))
                   if i != item.anchor})

        score = Score(frozenset(gold), frozenset(said))
        scores.append(score)
        loose_scores.append(Score(frozenset(gold), frozenset(loose)))
        retrieval_scores.append(Score(frozenset(gold), frozenset(held)))
        by_benchmark.setdefault(item.benchmark, []).append(score)
        by_family.setdefault(item.family, []).append(score)
        per_item.append({"id": item.item_id, "benchmark": item.benchmark,
                         "family": item.family, **score.as_dict()})

    return {
        "arm": arm, "condition": condition, "errors": errors,
        "answered": pool(scores),
        "answered_unfiltered": pool(loose_scores),
        "retrieved": pool(retrieval_scores),
        "by_benchmark": {b: pool(s) for b, s in sorted(by_benchmark.items())},
        "by_family": {f: pool(s) for f, s in sorted(by_family.items())},
        "per_item": per_item,
    }


def score_all(out: Path) -> dict[str, Any]:
    everything = build_items()
    subset = {i.item_id for i in llm_subset(everything)}
    cells: dict[str, Any] = {}
    for arm, condition, _kind, limit in PHASES:
        key = f"{arm}--{condition}"
        cells[key] = score_cell(out, arm, condition,
                                restrict=subset if limit else None)
        # The same arm read on the slow arms' 60 items, so a comparison between
        # them is a comparison of arms rather than of sample sizes.
        if limit is None:
            cells[f"{key}--subset60"] = score_cell(out, arm, condition, restrict=subset)

    everything_all = items_mod.cti_ate_items(
        fetch.read_cti_ate(fetch.fetch(fetch.CTI_ATE)), load_attack())
    return {
        "cells": cells,
        "coverage": {
            "cti_ate": items_mod.coverage(everything_all),
            "usable_items": len(everything),
            "llm_subset": len(subset),
            "per_family": PER_FAMILY, "sample_seed": SAMPLE_SEED,
        },
    }


# -- orchestration -----------------------------------------------------------


def sweep(out: Path, workers: int, llm_workers: int) -> int:
    out.mkdir(parents=True, exist_ok=True)
    state: dict[str, Any] = {"started": time.strftime("%Y-%m-%dT%H:%M:%S"), "phases": []}

    def record(name: str, result: dict, wall: float, error: str | None = None) -> None:
        state["phases"].append({"name": name, "result": result,
                                "wall_s": round(wall, 1),
                                "status": "ok" if error is None else error})
        (out / "state.json").write_text(json.dumps(state, indent=2) + "\n")

    print("=== P0 preflight", flush=True)
    started = time.time()
    everything = build_items()
    preflight = {
        "usable_items": len(everything),
        "cti_ate": sum(1 for i in everything if i.benchmark == "cti-ate"),
        "attackqa": sum(1 for i in everything if i.benchmark == "attackqa"),
        "families": len({i.family for i in everything}),
        "cti_ate_digest": fetch.digest(fetch.CACHE / fetch.CTI_ATE.filename),
        "attackqa_digest": fetch.digest(fetch.CACHE / fetch.ATTACKQA.filename),
    }
    print(json.dumps(preflight, indent=2), flush=True)
    record("P0", preflight, time.time() - started)

    for arm, condition, kind, limit in PHASES:
        name = f"{arm}--{condition}"
        print(f"=== {name}", flush=True)
        started = time.time()
        if kind == "oracle":
            record(name, run_oracle(out), time.time() - started)
            continue
        cmd = [sys.executable, str(Path(__file__)), "run", "--arm", arm,
               "--condition", condition, "--out", str(out),
               "--workers", str(llm_workers if limit else workers)]
        if limit:
            cmd += ["--limit", str(limit)]
        proc = subprocess.run(cmd, cwd=str(REPO), env={**os.environ, "ORCH_MAX_HOPS": "5"})
        summary_path = out / f"{name}.summary.json"
        summary = json.loads(summary_path.read_text()) if summary_path.is_file() else {}
        record(name, summary, time.time() - started,
               None if proc.returncode == 0 else f"exit {proc.returncode}")

    print("=== scoring", flush=True)
    started = time.time()
    metrics = score_all(out)
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    record("score", {k: v.get("answered", {}) for k, v in metrics["cells"].items()},
           time.time() - started)

    from scripts.external_report import write_report

    print(write_report(out), flush=True)
    failed = [p["name"] for p in state["phases"] if p["status"] != "ok"]
    print(f"=== finished; {len(state['phases'])} phases, {len(failed)} failed {failed}",
          flush=True)
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    s = sub.add_parser("sweep", help="the whole experiment")
    s.add_argument("--out", required=True)
    s.add_argument("--workers", type=int, default=4)
    s.add_argument("--llm-workers", type=int, default=2)

    r = sub.add_parser("run", help="one arm (used by sweep as a subprocess)")
    r.add_argument("--arm", required=True)
    r.add_argument("--condition", required=True, choices=("plan-given", "plan-free"))
    r.add_argument("--out", required=True)
    r.add_argument("--workers", type=int, default=4)
    r.add_argument("--limit", type=int, default=None)

    c = sub.add_parser("score", help="re-score what is already on disk")
    c.add_argument("--out", required=True)

    args = parser.parse_args(argv)
    if args.command == "sweep":
        return sweep(Path(args.out), args.workers, args.llm_workers)
    if args.command == "run":
        run_child(args.arm, args.condition, Path(args.out), args.workers, args.limit)
        return 0
    metrics = score_all(Path(args.out))
    (Path(args.out) / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    print(json.dumps({k: v.get("answered") for k, v in metrics["cells"].items()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
