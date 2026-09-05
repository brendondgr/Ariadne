#!/usr/bin/env python3
"""Judge the holdout arms under both grader families, counterbalanced.

Protocol: ``docs/research/experiments/EXP-2026-09-007-holdout-spend/PROTOCOL.md``.

Same instrument as the dev measurement it will be compared against: same
budget, same two grading positions, same two families. Anything cheaper here
would make the holdout figure incomparable to ``EXP-2026-09-005``, which is the
only thing it is for.

Arms are graded in the order given, so a grader that expires part-way leaves
whole arms finished rather than every arm half-finished. An arm whose judgment
count does not match its answer count is reported, not averaged.

    uv run python scripts/holdout_judge.py --grader gemma --arm deterministic generic
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from utils.config import load_env  # noqa: E402

load_env()

ROOT = REPO / "docs/evaluation/experiments/holdout-spend-2026-09-05"
EXP = REPO / "docs/research/experiments/EXP-2026-09-007-holdout-spend"
LOGS = REPO / "logs/holdout-2026-09-05"

JUDGE_MAX_TOKENS = 32768
JUDGE_TIMEOUT_S = 900.0

GRADERS: dict[str, dict[str, Any]] = {
    "gemma": {"url": "http://localhost:9090/v1", "model": "default-model-2",
              # Operator: the restarted gemma4-31B-mtp serves 16 concurrency,
              # not the 24 the earlier instance did.
              "workers": 16, "passes": ((".gem", 1), (".gemp2", 2))},
    "qwen": {"url": "http://localhost:9090/v1", "model": "default-model",
             "workers": 16, "passes": ((".qw", 1), (".qwp2", 2))},
}


def answer_count(arm: str) -> int:
    adir = ROOT / arm / "answers"
    if not adir.is_dir():
        return 0
    return sum(1 for p in adir.glob("*.json") if ".judgment" not in p.name)


def judged_count(arm: str, suffix: str) -> int:
    adir = ROOT / arm / "answers"
    want = f".judgment{suffix}.json"
    return sum(1 for p in adir.glob(f"*{want}") if p.name.endswith(want))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--grader", nargs="+", default=["qwen", "gemma"],
                    choices=list(GRADERS))
    ap.add_argument("--arm", nargs="+",
                    default=["deterministic", "generic", "llm_query"])
    ap.add_argument("--deadline", default=None, help="HH:MM; no cell starts after")
    args = ap.parse_args()

    deadline = None
    if args.deadline:
        hh, mm = (int(x) for x in args.deadline.split(":"))
        deadline = datetime.now().replace(hour=hh, minute=mm, second=0, microsecond=0)

    from utils.evaluation.judge_answers import JudgeConfig, run as judge_run

    # Measured on this endpoint at 16 workers (armgap, 204 judgments in 1667s).
    # Used only to decide whether a WHOLE position fits; never to skip work that
    # would have fitted.
    rate_s = 8.5
    observed: list[float] = []

    LOGS.mkdir(parents=True, exist_ok=True)
    state_path = EXP / "data" / f"judge-state-{'-'.join(sorted(args.grader))}.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state = json.loads(state_path.read_text()) if state_path.is_file() else {"cells": {}}

    for grader in args.grader:
        spec = GRADERS[grader]
        # POSITION-MAJOR, deliberately. Arm-major would spend the whole budget
        # giving one arm both grading positions before the second arm has any,
        # so a deadline hit would leave one arm graded and one arm absent --
        # which is not a comparison at all. This way a cut-off leaves every arm
        # with position 1 and the ~0.01 order effect uncorrected, which is a
        # usable result with a stated limitation.
        for suffix, position in spec["passes"]:
            # A position is all-or-nothing across arms. Grading position 2 for
            # one arm and not the other leaves exactly the two arms being
            # compared on different instruments, with one carrying the ~0.01
            # order correction and the other not. Better to have both arms at
            # position 1 and say the order effect is uncorrected than to have a
            # silent asymmetry inside the comparison.
            # ...but ONLY for positions after the first. Position 1 IS the
            # measurement; every later position is the order correction on top
            # of it. Declining to measure at all in order to protect the
            # symmetry of a correction gets the priority exactly backwards, and
            # at 9.3 s/judgment under relay contention that is a live risk, not
            # a hypothetical. Position 1 always attempts, and per-cell deadline
            # checks record whatever could not start.
            if deadline and position > 1:
                todo = sum(answer_count(a) for a in args.arm
                           if judged_count(a, suffix) < answer_count(a))
                need = todo * (sum(observed) / len(observed) if observed else rate_s)
                left = (deadline - datetime.now()).total_seconds()
                if todo and need > left:
                    for a in args.arm:
                        state["cells"][f"{grader}:{a}{suffix}"] = {
                            "status": "not_run",
                            "reason": (f"position {position} needs ~{need/60:.0f} min for "
                                       f"{todo} judgments, {left/60:.0f} min left before "
                                       f"{deadline:%H:%M}; skipped for ALL arms so the "
                                       "comparison stays symmetric"),
                        }
                    state_path.write_text(json.dumps(state, indent=1, default=str) + "\n")
                    print(f"[{grader}] position {position}: SKIPPED for all arms — "
                          f"needs ~{need/60:.0f} min, {left/60:.0f} min left", flush=True)
                    continue
            for arm in args.arm:
                n = answer_count(arm)
                if n == 0:
                    print(f"[{grader}] {arm}: no answers on disk, skipping", flush=True)
                    continue
                key = f"{grader}:{arm}{suffix}"
                if state["cells"].get(key, {}).get("status") == "done":
                    print(f"[{grader}] {key}: already done", flush=True)
                    continue
                if deadline and datetime.now() >= deadline:
                    state["cells"][key] = {"status": "not_run",
                                           "reason": f"past {deadline:%H:%M}"}
                    state_path.write_text(json.dumps(state, indent=1, default=str) + "\n")
                    print(f"[{grader}] {key}: SKIPPED (past deadline)", flush=True)
                    continue
                print(f"[{grader}] {key}: start ({n} answers) {datetime.now():%H:%M:%S}",
                      flush=True)
                t0 = time.time()
                try:
                    out = judge_run(ROOT, arm,
                                    JudgeConfig(base_url=spec["url"], model=spec["model"],
                                                max_tokens=JUDGE_MAX_TOKENS,
                                                timeout_s=JUDGE_TIMEOUT_S,
                                                position=position),
                                    workers=spec["workers"], suffix=suffix)
                    wrote = judged_count(arm, suffix)
                    status = "done" if wrote == n else "partial"
                    detail = {**(out or {}), "answers": n, "judgments_written": wrote}
                except Exception as exc:                              # noqa: BLE001
                    detail = {"error": f"{type(exc).__name__}: {exc}"}
                    status = "failed"
                elapsed = time.time() - t0
                if status == "done" and n:
                    observed.append(elapsed / n)
                state["cells"][key] = {"status": status,
                                       "elapsed_s": round(elapsed, 1),
                                       "detail": detail}
                state_path.write_text(json.dumps(state, indent=1, default=str) + "\n")
                print(f"[{grader}] {key}: {status} in {round(time.time() - t0, 1)}s",
                      flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
