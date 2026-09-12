#!/usr/bin/env python3
"""The full judged development half at the current commit, unattended.

    uv run python scripts/dev_half_judged.py

`EXP-2026-09-018`. The slice judged in `data/judged_hard_slice.json` measured
two tiers and projected the other five; this measures all seven, so the ship
gate stops resting on a projection.

Arms in cost order, each judged in BOTH grading positions before the next
begins, so the arm that matters lands first and a later failure cannot cost the
earlier answer:

  generic           the LLM arm — the figure the gate is about
  generic_composed  the same primitives with no model
  deterministic     the template arm, regression control

The comparison is against `repair-control-2026-09-11/repaired`, which was
generated and judged in one sitting at `46652efc` on these same live graphs.

Only `:9090` with `default-model` (operator directive, 2026-09-11); the arm
runner preflights it and refuses to start otherwise.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from utils.config import load_env  # noqa: E402

load_env()

ROOT = REPO / "docs/evaluation/experiments/dev-half-2026-09-12"
BANK = REPO / "docs/evaluation/composition/bank/bank-dev.json"
STATE = ROOT / "state.json"
ARMS = ("generic", "generic_composed", "deterministic")
GEN_WORKERS = 32
#: Raised from 16 on operator request, mid-run (2026-09-12). Safe to change
#: between runs and safe to change DURING one: the judge skips any answer that
#: already carries a judgment for the pass it is on, so a restart re-enters the
#: interrupted step and grades only what is missing. Concurrency does not enter
#: a judgment — each answer is graded on its own — so a pass split across two
#: settings is still one pass.
JUDGE_WORKERS = 32
JUDGE_MODEL = "default-model"
JUDGE_MAX_TOKENS = 32768
PASSES = ((".rc1", 1), (".rc2", 2))

ENV = {
    "SYNTHESIS_LLM_TIMEOUT_S": "600.0",
    "SPECIALIST_LLM_TIMEOUT_S": "4096",
    "ORCH_MAX_HOPS": "5",
}


def _state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"started": datetime.now(timezone.utc).isoformat(), "done": []}


def _save(state: dict) -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2) + "\n")


def _run(cmd: list[str], step: str, state: dict) -> None:
    """Run one step, recording it so a restart resumes rather than repeats."""
    if step in state["done"]:
        print(f"[skip] {step}", flush=True)
        return
    import os

    print(f"[run ] {step}", flush=True)
    t0 = time.monotonic()
    subprocess.check_call(cmd, cwd=REPO, env={**os.environ, **ENV})
    state["done"].append(step)
    state[step] = round(time.monotonic() - t0, 1)
    _save(state)
    print(f"[done] {step} in {state[step]}s", flush=True)


def main() -> int:
    state = _state()
    _save(state)
    for arm in ARMS:
        _run(
            [sys.executable, "-m", "utils.evaluation.experiment_untruncated",
             "--arm", arm, "--bank", str(BANK), "--root", str(ROOT),
             "--workers", str(GEN_WORKERS), "--llm-model", JUDGE_MODEL],
            f"generate:{arm}", state,
        )
        for suffix, position in PASSES:
            _run(
                [sys.executable, "-m", "utils.evaluation.judge_answers",
                 "--root", str(ROOT), "--arm", arm,
                 "--workers", str(JUDGE_WORKERS), "--model", JUDGE_MODEL,
                 "--max-tokens", str(JUDGE_MAX_TOKENS),
                 "--suffix", suffix, "--position", str(position)],
                f"judge:{arm}{suffix}", state,
            )
        print(f"=== {arm} complete ===", flush=True)
    state["finished"] = datetime.now(timezone.utc).isoformat()
    _save(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
