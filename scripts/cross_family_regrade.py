#!/usr/bin/env python3
"""Re-grade the August answers under a second model family.

Protocol: ``docs/research/experiments/EXP-2026-09-006-cross-family-august-regrade/PROTOCOL.md``.

Nothing here runs the pipeline. The 510 answers on disk are byte-identical to
the ones the August figures were computed over, so a difference between two
passes is attributable to the grader and to nothing else.

Two tracks run concurrently on two GPUs behind one relay:

* **gemma** (``default-model-2`` -> ``gemma4-31B-mtp``, 24 workers) is the second
  family and the thing that expires. Every gemma cell is bounded by ``--deadline``
  and a cell that cannot start before it is recorded ``not_run``.
* **qwen** (``default-model`` -> ``qwen38-27B-v2``, 16 workers) grades only the
  150 ``composerfix`` answers, which have never been graded by anything named.
  Without it, C-021's comparison would change grader family *and* grader
  identifiability at once. It does not expire.

Phases are a priority order, not a preference: an early cutoff must still close
C-021 and C-022.

Three disciplines are enforced rather than assumed:

* **Input count is asserted before every cell.** Twelve judgment suffixes
  already sit beside these answers and a glob that picks one up grades a
  judgment as if it were an answer (the 2026-09-01 contamination finding).
* **A partial cell is not a result.** Anything that raises is recorded with its
  error and its dependents still run; the roll-up refuses to average a cell
  whose judgment count does not match its answer count.
* **The served model is read from the endpoint, never from the alias**, which
  has stood for three different models (``D-028``).

    uv run python scripts/cross_family_regrade.py --dry-run
    uv run python scripts/cross_family_regrade.py --phase c021 c022
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from utils.config import load_env  # noqa: E402

load_env()

EXP = REPO / "docs/research/experiments/EXP-2026-09-006-cross-family-august-regrade"
RUNS = REPO / "docs/evaluation/experiments"
STATE = EXP / "data" / "regrade-state.json"
LOGS = REPO / "logs/cross-family-2026-09-05"

GEMMA_URL = "http://localhost:9090/v1"
GEMMA_MODEL = "default-model-2"
GEMMA_WORKERS = 24

QWEN_URL = "http://localhost:9090/v1"
QWEN_MODEL = "default-model"
QWEN_WORKERS = 16

#: Both graders at the same budget. EXP-2026-08-021 found 7-8% of the largest
#: answers fail to parse below this, and the failures land on the thorough
#: answers -- a cheaper second pass would confound grader with budget.
JUDGE_MAX_TOKENS = 32768
JUDGE_TIMEOUT_S = 900.0

#: (suffix, position). Position is swapped because the grading-order effect is
#: ~0.01 (EXP-2026-08-022) and in the original C-022 passes `merged` was graded
#: before `federated` every time.
GEMMA_PASSES = ((".g31", 1), (".g31p2", 2))
QWEN_PASSES = ((".q38b", 1), (".q38bp2", 2))

#: Priority order. C-021 first: its 150 answers carry exactly one judgment each,
#: written by a model nobody can name, and EXP-2026-08-021 did not touch them.
PHASES: dict[str, dict[str, list[tuple[str, str]]]] = {
    "c021": {
        "gemma": [("composerfix-dev", "deterministic"),
                  ("composerfix-holdout", "deterministic")],
        "qwen": [("composerfix-dev", "deterministic"),
                 ("composerfix-holdout", "deterministic")],
    },
    "c022": {
        "gemma": [("bank20260819", "generic_composed"), ("bank20260819", "merged"),
                  ("bank20260820", "generic_composed"), ("bank20260820", "merged")],
        "qwen": [],
    },
    "c012": {
        "gemma": [("bank20260819", "deterministic"), ("bank20260819", "llm_query"),
                  ("bank20260820", "deterministic"), ("bank20260820", "llm_query")],
        "qwen": [],
    },
    "rest": {
        "gemma": [("bank20260819", "generic"), ("bank20260819", "gold_loop_llm"),
                  ("bank20260820", "generic"), ("bank20260820", "gold_loop_llm")],
        "qwen": [],
    },
}

_lock = threading.Lock()


def load_state() -> dict[str, Any]:
    if STATE.is_file():
        return json.loads(STATE.read_text())
    return {"experiment": "EXP-2026-09-006", "started": None, "cells": {}}


def save(state: dict[str, Any]) -> None:
    with _lock:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(state, indent=1, default=str) + "\n")


def answer_paths(root: str, arm: str) -> list[Path]:
    """Answers only. ``.judgment`` sidecars live in the same directory."""
    adir = RUNS / root / arm / "answers"
    return sorted(p for p in adir.glob("*.json") if ".judgment" not in p.name)


def judgment_paths(root: str, arm: str, suffix: str) -> list[Path]:
    adir = RUNS / root / arm / "answers"
    want = f".judgment{suffix}.json"
    return sorted(p for p in adir.glob(f"*{want}") if p.name.endswith(want))


def probe(url: str, model: str) -> dict[str, Any]:
    """What is actually behind the alias, read off the response envelope."""
    import requests

    t0 = time.time()
    r = requests.post(
        f"{url.rstrip('/')}/chat/completions",
        json={"model": model, "messages": [{"role": "user", "content": "Reply with the single word: ready"}],
              "max_tokens": 512, "temperature": 0.0},
        timeout=180,
    )
    r.raise_for_status()
    body = r.json()
    msg = body["choices"][0]["message"]
    return {
        "alias": model,
        "served_model": body.get("model"),
        "wall_s": round(time.time() - t0, 2),
        "content_chars": len(msg.get("content") or ""),
        # Reasoning models put chain-of-thought here while `content` stays empty;
        # an empty `content` with a full `reasoning` means the budget was too
        # small, not that the model had nothing to say.
        "reasoning_chars": len(msg.get("reasoning") or msg.get("reasoning_content") or ""),
        "finish_reason": body["choices"][0].get("finish_reason"),
    }


def judge_cell(root: str, arm: str, *, url: str, model: str, workers: int,
               suffix: str, position: int) -> dict[str, Any]:
    from utils.evaluation.judge_answers import JudgeConfig, run as judge_run

    answers = answer_paths(root, arm)
    if not answers:
        raise RuntimeError(f"{root}/{arm}: no answers on disk")

    out = judge_run(
        RUNS / root, arm,
        JudgeConfig(base_url=url, model=model, max_tokens=JUDGE_MAX_TOKENS,
                    timeout_s=JUDGE_TIMEOUT_S, position=position),
        workers=workers, suffix=suffix,
    )
    written = judgment_paths(root, arm, suffix)
    # A cell that graded fewer cases than it was given is not a result. Record
    # the shortfall here so the roll-up never has to infer it.
    out = dict(out or {})
    out.update({
        "answers": len(answers),
        "judgments_written": len(written),
        "complete": len(written) == len(answers),
    })
    return out


def run_track(track: str, cells: list[tuple[str, str, str, int]], *, url: str,
              model: str, workers: int, state: dict[str, Any],
              deadline: datetime | None) -> None:
    for root, arm, suffix, position in cells:
        key = f"{track}:{root}:{arm}:{suffix}"
        rec = state["cells"].get(key, {})
        if rec.get("status") == "done":
            print(f"[{track}] {key}: already done", flush=True)
            continue
        if deadline is not None and datetime.now() >= deadline:
            state["cells"][key] = {"status": "not_run",
                                   "reason": f"past the {deadline:%H:%M} deadline"}
            save(state)
            print(f"[{track}] {key}: SKIPPED (past deadline)", flush=True)
            continue

        n = len(answer_paths(root, arm))
        print(f"[{track}] {key}: start ({n} answers)", flush=True)
        state["cells"][key] = {"status": "running", "started": datetime.now(),
                               "answers": n}
        save(state)
        t0 = time.time()
        try:
            detail = judge_cell(root, arm, url=url, model=model, workers=workers,
                                suffix=suffix, position=position)
            status = "done" if detail.get("complete") else "partial"
        except Exception as exc:                                  # noqa: BLE001
            detail = {"error": f"{type(exc).__name__}: {exc}"}
            status = "failed"
        state["cells"][key] = {"status": status, "elapsed_s": round(time.time() - t0, 1),
                               "finished": datetime.now(), "detail": detail}
        save(state)
        print(f"[{track}] {key}: {status} in {round(time.time() - t0, 1)}s "
              f"{json.dumps(detail)[:200]}", flush=True)


def plan_cells(phases: list[str]) -> dict[str, list[tuple[str, str, str, int]]]:
    out: dict[str, list[tuple[str, str, str, int]]] = {"gemma": [], "qwen": []}
    for phase in phases:
        spec = PHASES[phase]
        for root, arm in spec["gemma"]:
            for suffix, position in GEMMA_PASSES:
                out["gemma"].append((root, arm, suffix, position))
        for root, arm in spec["qwen"]:
            for suffix, position in QWEN_PASSES:
                out["qwen"].append((root, arm, suffix, position))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--phase", nargs="*", default=list(PHASES),
                    choices=list(PHASES), help="priority order; default all")
    ap.add_argument("--track", nargs="*", default=["gemma", "qwen"],
                    choices=["gemma", "qwen"],
                    help="run only these tracks; lets the qwen half start "
                         "while the gemma GPU is still coming up")
    ap.add_argument("--deadline", default="15:45",
                    help="HH:MM today; gemma cells do not start after this")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-probe", action="store_true")
    args = ap.parse_args(argv)

    hh, mm = (int(x) for x in args.deadline.split(":"))
    deadline = datetime.now().replace(hour=hh, minute=mm, second=0, microsecond=0)

    cells = plan_cells(args.phase)
    for track in list(cells):
        if track not in args.track:
            cells[track] = []
    total = 0
    print(f"phases: {', '.join(args.phase)}   gemma deadline {deadline:%H:%M}\n")
    for track, items in cells.items():
        n = sum(len(answer_paths(r, a)) for r, a, _, _ in items)
        total += n
        print(f"  {track:6} {len(items):2} cells, {n:4} judgments")
        for root, arm, suffix, position in items:
            print(f"      {root}/{arm}{suffix} pos={position} "
                  f"({len(answer_paths(root, arm))} answers)")
    print(f"\n  total {total} judgments")
    if args.dry_run:
        return 0

    LOGS.mkdir(parents=True, exist_ok=True)
    state = load_state()
    state["started"] = state.get("started") or str(datetime.now())

    if not args.skip_probe:
        for track, url, model in (("gemma", GEMMA_URL, GEMMA_MODEL),
                                  ("qwen", QWEN_URL, QWEN_MODEL)):
            if not cells[track]:
                continue
            info = probe(url, model)
            state.setdefault("probes", {})[track] = info
            print(f"\n[probe] {track}: {json.dumps(info)}", flush=True)
            if not info["content_chars"]:
                raise SystemExit(
                    f"{track} ({model}) returned empty content "
                    f"({info['reasoning_chars']} reasoning chars, "
                    f"finish_reason={info['finish_reason']}). Not grading with it.")
        save(state)

    print()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = []
        if cells["gemma"]:
            futures.append(pool.submit(run_track, "gemma", cells["gemma"],
                                       url=GEMMA_URL, model=GEMMA_MODEL,
                                       workers=GEMMA_WORKERS, state=state,
                                       deadline=deadline))
        if cells["qwen"]:
            futures.append(pool.submit(run_track, "qwen", cells["qwen"],
                                       url=QWEN_URL, model=QWEN_MODEL,
                                       workers=QWEN_WORKERS, state=state,
                                       deadline=None))
        for f in futures:
            f.result()

    done = sum(1 for c in state["cells"].values() if c.get("status") == "done")
    print(f"\n{done}/{len(state['cells'])} cells complete. State: {STATE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
