#!/usr/bin/env python3
"""The concurrent paired control: repaired and reference arms in one session.

    uv run python scripts/repair_control_run.py --stage generate
    uv run python scripts/repair_control_run.py --stage judge

`EXP-2026-09-018` Step 6. Four cells over the development half — `generic`,
`generic_composed` and `deterministic` at the repaired commit, and the same
three at the pre-repair commit — generated **in one sitting on the same live
graphs**, then judged in one sitting, each answer in both grading positions.

**Why a concurrent control and not the published baseline.** `Q46` records a
metric moving 0.0503 between sessions while both sessions reported near-zero
spread inside themselves. A repaired arm compared against a figure from another
day is compared against that move as much as against the repair. The reference
commit is therefore re-run here rather than quoted.

**The reference commit runs against the CURRENT data.** Step 4b repaired two
data-layer defects (`Q54`, `Q55`), so a control at the old data would fold a
data change into a code comparison. `data/reference/reference-datafix.json` is
the model-free version of the same decision.

Only `:9090` with `default-model` (operator directive, 2026-09-11). The arm
runner preflights it and refuses to start if the endpoint does not serve it,
which is `Q56`.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from utils.config import load_env  # noqa: E402

load_env()

ROOT = REPO / "docs/evaluation/experiments/repair-control-2026-09-11"
LOGS = REPO / "logs/repair-control-2026-09-11"
STATE = ROOT / "state.json"
BANK = REPO / "docs/evaluation/composition/bank/bank-dev.json"

#: The commit the repairs are measured against: Step 0, before any repair.
REFERENCE_COMMIT = "e09c2571"
ARMS = ("deterministic", "generic_composed", "generic")
WORKERS = 24
JUDGE_URL = "http://localhost:9090/v1"
JUDGE_MODEL = "default-model"
JUDGE_EXPECT = "qwen"
JUDGE_WORKERS = 16
JUDGE_MAX_TOKENS = 32768
PASSES = ((".rc1", 1), (".rc2", 2))

#: `EXP-2026-09-016` A-8: a generic run whose narrator fell back on more than
#: this share of its ANSWERS is discarded rather than reported.
HEALTHY_FALLBACK_RATE = 0.14

ENV = {
    "ORCH_MAX_HOPS": "5",
    # The narrator's failures were read time-outs at the 120 s default
    # (`EXP-2026-09-010`). This is the budget every generic figure in this
    # experiment is produced at, and the latency sample reports both.
    "SYNTHESIS_LLM_TIMEOUT_S": "600.0",
    "SPECIALIST_LLM_TIMEOUT_S": "4096",
}


def _fallback_rate(root: Path, arm: str) -> dict:
    """Fallbacks over ANSWERS, never over files.

    The 2026-09-10 audit divided by the file count of a directory that also
    holds judgment sidecars and reported 0.04 where the truth was 0.43
    (`EXP-2026-09-016` A-8). The denominator is the finding.
    """
    directory = root / arm / "answers"
    answers = [p for p in directory.glob("*.json") if ".judgment" not in p.name]
    reasons: dict[str, int] = {}
    for path in answers:
        try:
            reason = (json.loads(path.read_text()).get("answer") or {}).get(
                "fallback_reason"
            )
        except Exception:  # noqa: BLE001
            reason = "<unparseable artifact>"
        if reason:
            key = str(reason).split("(")[0].strip()
            reasons[key] = reasons.get(key, 0) + 1
    count = sum(reasons.values())
    return {
        "answers": len(answers),
        "fallbacks": count,
        "rate": round(count / max(len(answers), 1), 4),
        "reasons": reasons,
        "healthy": len(answers) > 0
        and count / max(len(answers), 1) <= HEALTHY_FALLBACK_RATE,
    }


def _run_arm(arm: str, root: Path, workers: int, limit: int | None = None) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, "-m", "utils.evaluation.experiment_untruncated",
        "--arm", arm, "--bank", str(BANK), "--root", str(root),
        "--workers", str(workers), "--llm-model", JUDGE_MODEL,
    ]
    if limit:
        cmd += ["--limit", str(limit)]
    tag = f"{root.name}-{arm}"
    began = time.time()
    with (LOGS / f"{tag}.log").open("w") as handle:
        code = subprocess.call(
            cmd, cwd=REPO, env={**os.environ, **ENV},
            stdout=handle, stderr=subprocess.STDOUT,
        )
    return {
        "arm": arm, "root": str(root.relative_to(REPO)), "returncode": code,
        "elapsed_s": round(time.time() - began, 1),
        "health": _fallback_rate(root, arm),
        "finished": datetime.now().isoformat(timespec="seconds"),
    }


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO, text=True).strip()


def generate(state: dict) -> None:
    """Both commits, one sitting. The reference is checked out, never quoted."""
    if _git("status", "--porcelain", "--untracked-files=no"):
        raise SystemExit(
            "working tree has uncommitted tracked changes; the reference "
            "checkout would lose them. Commit first."
        )
    head = _git("rev-parse", "HEAD")
    state["head"] = head
    state["reference_commit"] = _git("rev-parse", REFERENCE_COMMIT)

    for arm in ARMS:
        state.setdefault("cells", {})[f"repaired/{arm}"] = _run_arm(
            arm, ROOT / "repaired", WORKERS
        )
        STATE.write_text(json.dumps(state, indent=2) + "\n")
        print(f"  repaired/{arm}: {state['cells'][f'repaired/{arm}']['health']}", flush=True)

    print(f"-- checking out reference {REFERENCE_COMMIT} --", flush=True)
    subprocess.check_call(["git", "checkout", "-q", REFERENCE_COMMIT], cwd=REPO)
    try:
        for arm in ARMS:
            state["cells"][f"reference/{arm}"] = _run_arm(
                arm, ROOT / "reference", WORKERS
            )
            STATE.write_text(json.dumps(state, indent=2) + "\n")
            print(
                f"  reference/{arm}: {state['cells'][f'reference/{arm}']['health']}",
                flush=True,
            )
    finally:
        subprocess.check_call(["git", "checkout", "-q", head], cwd=REPO)
        print(f"-- back at {head[:8]} --", flush=True)

    unhealthy = [
        cell for cell, row in state["cells"].items()
        if cell.endswith("/generic") and not row["health"]["healthy"]
    ]
    if unhealthy:
        print(f"UNHEALTHY (fallback rate above {HEALTHY_FALLBACK_RATE}): {unhealthy}")
        print("Discard and re-run these cells; do not report them.")


def judge(state: dict) -> None:
    from utils.evaluation.grading_order import counterbalanced
    from utils.evaluation.judge_answers import JudgeConfig, run as judge_run

    import urllib.request
    probe = urllib.request.Request(
        f"{JUDGE_URL}/chat/completions",
        data=json.dumps({"model": JUDGE_MODEL, "max_tokens": 32,
                         "temperature": 0.0,
                         "messages": [{"role": "user", "content": "ready"}]}).encode(),
        headers={"Content-Type": "application/json"})
    served = json.loads(urllib.request.urlopen(probe, timeout=300).read())["model"]
    if JUDGE_EXPECT not in str(served).lower():
        raise SystemExit(f"{JUDGE_MODEL} serves {served}, not {JUDGE_EXPECT}")
    state["judge_served_model"] = served
    print(f"[judge] {JUDGE_MODEL} serves {served}", flush=True)

    cells = [(side, arm) for side in ("repaired", "reference") for arm in ARMS]
    for suffix, position in PASSES:
        order = counterbalanced([f"{s}/{a}" for s, a in cells], position - 1)
        print(f"[position {position}] {order}", flush=True)
        for cell in order:
            side, arm = cell.split("/")
            began = time.time()
            result = judge_run(
                ROOT / side, arm,
                JudgeConfig(base_url=JUDGE_URL, model=JUDGE_MODEL,
                            max_tokens=JUDGE_MAX_TOKENS, timeout_s=900.0,
                            position=position),
                workers=JUDGE_WORKERS, suffix=suffix,
            )
            state.setdefault("judged", {})[f"{cell}@{position}"] = {
                "elapsed_s": round(time.time() - began, 1), "result": result,
            }
            STATE.write_text(json.dumps(state, indent=2) + "\n")
            print(f"  {cell}@{position} in {state['judged'][f'{cell}@{position}']['elapsed_s']}s",
                  flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("generate", "judge"), required=True)
    args = parser.parse_args()

    ROOT.mkdir(parents=True, exist_ok=True)
    state = json.loads(STATE.read_text()) if STATE.is_file() else {}
    state["started"] = state.get("started") or datetime.now().isoformat(timespec="seconds")

    if args.stage == "generate":
        generate(state)
    else:
        judge(state)
    STATE.write_text(json.dumps(state, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
