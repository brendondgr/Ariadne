#!/usr/bin/env python3
"""Wait for gemma, then run the remaining gemma work in order, verifying as it goes.

Replaces a shell chain that treated **process exit as success**. When the
operator restarted the endpoint mid-run, `armgap` died, the chain read that as
"finished", and drove 288 holdout cases into a dead server -- 168 sidecars of
`HTTP 502` and not one judgment. No data was lost, because a failed judgment
writes `.error.txt` and never `.json`, but nothing was gained either and a
booting server was hammered for several minutes.

So each stage here does three things the shell chain did not:

* **Re-check the endpoint before starting**, requiring two consecutive real
  completions with non-empty content, never a health flag and never an alias.
* **Verify the stage's own output landed**, by counting judgments on disk, not
  by trusting a return code.
* **Refuse to advance** on a stage that produced nothing, rather than passing
  the failure downstream where it looks like a different problem.

    uv run python scripts/gemma_chain.py --until 15:30
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from utils.config import load_env  # noqa: E402

load_env()

from scripts.cross_family_regrade import GEMMA_MODEL, GEMMA_URL, probe  # noqa: E402

LOGS = REPO / "logs/cross-family-2026-09-05"
SPLIT = REPO / "docs/evaluation/experiments/llm-query-split-2026-09-05/llm_query/answers"
HOLD = REPO / "docs/evaluation/experiments/holdout-spend-2026-09-05"


def count(d: Path, suffix: str) -> int:
    want = f".judgment{suffix}.json"
    return sum(1 for p in d.glob(f"*{want}") if p.name.endswith(want)) if d.is_dir() else 0


def wait_ready(deadline: datetime, interval: float = 30.0) -> bool:
    """Two consecutive real completions. A health flag is not evidence."""
    good = 0
    while datetime.now() < deadline:
        try:
            info = probe(GEMMA_URL, GEMMA_MODEL)
        except Exception as exc:                                  # noqa: BLE001
            info = {"error": f"{type(exc).__name__}: {exc}"}
        served = str(info.get("served_model") or "")
        ok = bool(info.get("content_chars")) and "gemma" in served.lower()
        good = good + 1 if ok else 0
        print(f"{datetime.now():%H:%M:%S} ready={good} {json.dumps(info)[:200]}", flush=True)
        if good >= 2:
            return True
        time.sleep(interval)
    return False


def run(name: str, cmd: list[str], log: Path) -> int:
    print(f"\n=== {name} — {datetime.now():%H:%M:%S} ===", flush=True)
    with log.open("a") as fh:
        return subprocess.run(cmd, cwd=REPO, stdout=fh, stderr=subprocess.STDOUT,
                              stdin=subprocess.DEVNULL, check=False).returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--until", default="15:30")
    args = ap.parse_args()
    hh, mm = (int(x) for x in args.until.split(":"))
    deadline = datetime.now().replace(hour=hh, minute=mm, second=0, microsecond=0)
    LOGS.mkdir(parents=True, exist_ok=True)

    if not wait_ready(deadline):
        print("gemma never became ready before the deadline; nothing run", flush=True)
        return 1

    # 1. armgap — resumes; completed cells cost nothing.
    before = count(SPLIT, ".gemma") + count(SPLIT, ".gemma2")
    run("armgap", ["uv", "run", "python", "scripts/cross_family_regrade.py",
                   "--track", "gemma", "--phase", "armgap",
                   "--deadline", args.until, "--skip-probe"],
        LOGS / "armgap.log")
    after = count(SPLIT, ".gemma") + count(SPLIT, ".gemma2")
    print(f"armgap judgments {before} -> {after} (of 568)", flush=True)
    if after <= before:
        print("armgap produced nothing — refusing to advance to the holdout", flush=True)
        return 2

    # 2. The one missing position-1 judgment from the August set.
    if datetime.now() < deadline and wait_ready(deadline, interval=10.0):
        run("c021 retry", ["uv", "run", "python", "scripts/cross_family_regrade.py",
                           "--track", "gemma", "--phase", "c021",
                           "--deadline", args.until, "--skip-probe"],
            LOGS / "gemma-retry.log")

    # 3. The holdout, position-major, so a cut-off leaves both arms usable.
    if datetime.now() >= deadline or not wait_ready(deadline, interval=10.0):
        print("no gemma time left for the holdout", flush=True)
        return 3
    before = sum(count(HOLD / a / "answers", s)
                 for a in ("deterministic", "generic") for s in (".gem", ".gemp2"))
    run("holdout judging", ["uv", "run", "python", "scripts/holdout_judge.py",
                            "--grader", "gemma", "--arm", "deterministic", "generic",
                            "--deadline", args.until],
        LOGS / "holdout-gemma.log")
    after = sum(count(HOLD / a / "answers", s)
                for a in ("deterministic", "generic") for s in (".gem", ".gemp2"))
    print(f"holdout judgments {before} -> {after} (of 1152)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
