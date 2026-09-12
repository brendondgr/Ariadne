#!/usr/bin/env python3
"""Judge the frozen-evidence pair in one session, counterbalanced.

    uv run python scripts/frozen_judge.py

`EXP-2026-09-018` Step 5. Two answer sets over the SAME evidence — the saved
`EXP-2026-09-005` composition and the repaired one — graded by one judge in one
sitting, each in both grading positions.

**Both sets are re-graded here, including the one that already has judgments.**
Reusing `EXP-2026-09-005`'s saved scores would be cheaper and wrong: they were
taken in a different session, and `Q46` records a 0.0503 move between sessions
with near-zero spread inside each. A comparison spanning that is not a paired
comparison.

Fresh suffixes (`.fz1`, `.fz2`) rather than the existing `.judgment*`, because a
sidecar written beside its input is re-consumed by the next reader unless every
suffixed variant is excluded — the contamination `EXP-2026-09-016` had to
unpick.

Position-major, and a position is all-or-nothing across both sets: grading one
set twice and the other once would compare two conditions on different
instruments, one carrying the ~0.01 order correction and the other not.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from utils.config import load_env  # noqa: E402

load_env()

ROOT = REPO / "docs/evaluation/experiments/frozen-2026-09-11"
ARMS = ("generic_original", "generic_recomposed")
PASSES = ((".fz1", 1), (".fz2", 2))

JUDGE_URL = "http://localhost:9090/v1"
JUDGE_MODEL = "default-model"
JUDGE_EXPECT = "qwen"
JUDGE_MAX_TOKENS = 32768
JUDGE_TIMEOUT_S = 900.0
WORKERS = 16


def _probe() -> str:
    """The weights the alias actually serves.

    `default-model` is a relay alias and this project's aliases have resolved to
    three different models over its life (`D-028`, `Q12`), so the name is
    recorded from the response envelope, never assumed.
    """
    import urllib.request

    request = urllib.request.Request(
        f"{JUDGE_URL}/chat/completions",
        data=json.dumps(
            {
                "model": JUDGE_MODEL,
                "max_tokens": 32,
                "temperature": 0.0,
                "messages": [{"role": "user", "content": "ready"}],
            }
        ).encode(),
        headers={"Content-Type": "application/json"},
    )
    served = json.loads(urllib.request.urlopen(request, timeout=300).read())["model"]
    if JUDGE_EXPECT not in str(served).lower():
        raise SystemExit(
            f"{JUDGE_MODEL} serves {served}, not {JUDGE_EXPECT} — refusing to write "
            f"judgments under a name that would misattribute them"
        )
    return str(served)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--positions", nargs="*", type=int, default=None)
    parser.add_argument(
        "--arms", nargs="*", default=None, choices=list(ARMS),
        help="re-grade only these sets. Used when one side's claims changed and "
             "the other's did not: the drift control is what then says whether "
             "the judge moved between the two sittings.")
    args = parser.parse_args()

    from utils.evaluation.grading_order import counterbalanced
    from utils.evaluation.judge_answers import JudgeConfig, run as judge_run

    served = _probe()
    print(f"[judge] {JUDGE_MODEL} serves {served} at {WORKERS} workers", flush=True)

    state = {"served_model": served, "workers": WORKERS, "cells": {}}
    state_path = ROOT / "judge-state.json"
    started = time.time()

    for suffix, position in PASSES:
        if args.positions and position not in args.positions:
            continue
        order = counterbalanced(list(ARMS), position - 1)
        if args.arms:
            order = [a for a in order if a in args.arms]
        print(f"[position {position}] order: {order}", flush=True)
        for arm in order:
            answers = sum(
                1
                for p in (ROOT / arm / "answers").glob("*.json")
                if ".judgment" not in p.name
            )
            cell = f"{arm}@{position}"
            began = time.time()
            result = judge_run(
                ROOT,
                arm,
                JudgeConfig(
                    base_url=JUDGE_URL,
                    model=JUDGE_MODEL,
                    max_tokens=JUDGE_MAX_TOKENS,
                    timeout_s=JUDGE_TIMEOUT_S,
                    position=position,
                ),
                workers=WORKERS,
                suffix=suffix,
            )
            elapsed = round(time.time() - began, 1)
            state["cells"][cell] = {
                "answers": answers,
                "suffix": suffix,
                "position": position,
                "elapsed_s": elapsed,
                "result": result,
            }
            state_path.write_text(json.dumps(state, indent=2) + "\n")
            print(f"  {cell}: {answers} answers in {elapsed}s", flush=True)

    state["total_s"] = round(time.time() - started, 1)
    state_path.write_text(json.dumps(state, indent=2) + "\n")
    print(f"[judge] done in {state['total_s']}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
