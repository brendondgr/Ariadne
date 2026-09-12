#!/usr/bin/env python3
"""Run the rest of the correctness-repair close-out without a human in the loop.

    uv run python scripts/closeout_run.py                # from wherever it got to
    uv run python scripts/closeout_run.py --only control-judge
    uv run python scripts/closeout_run.py --list

`docs/plans/2026-09-12-correctness-repair-closeout.md`, Steps 3 and 4. Each
stage is a subprocess and a line in `state.json`; a completed stage is skipped,
so a kill costs only the work in flight. That is the same shape
`scripts/dev_half_judged.py` used for the development half, and it is the reason
a nine-hour chain is survivable.

**Three start guards, all refusals rather than warnings.**

1. The tree must be clean. A figure has to be attributable to a commit.
2. `default-model` on `:9090` must serve `qwen38-27B-v2`. The alias has served
   three different models (`scripts/model_identity.py` exists because of that),
   and a control whose two sides ran against different weights measures nothing.
3. The fresh bank must be sealed before any fresh answer exists. `fresh_seal.py`
   proves the bank is unspent AND proves it can fail, and the seal is written
   into the record before the first arm runs, not after.

**Two human checkpoints, by design.** The author rejection rate above 25 % and
any kill-gate failure both stop the chain and report rather than proceed. They
are decisions about whether a number is worth having, and the chain does not get
to make them.
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

CONTROL = REPO / "docs/evaluation/experiments/paired-control-2026-09-12"
FRESH = REPO / "docs/evaluation/experiments/fresh-2026-09-12"
REGRESSION = REPO / "docs/evaluation/experiments/holdout-regression-2026-09-12"
FRESH_BANK = REPO / "docs/evaluation/composition/bank/bank-fresh-2026-09-12.json"
HOLDOUT_BANK = REPO / "docs/evaluation/composition/bank/bank-holdout.json"
STATE = REPO / "docs/evaluation/experiments/closeout-2026-09-12-state.json"
LOGS = REPO / "logs/closeout-2026-09-12"
ARMS = ("deterministic", "generic_composed", "generic")
PASSES = ((".rc1", 1), (".rc2", 2))
WORKERS = 32
MODEL = "default-model"
EXPECT = "qwen38-27B-v2"

ENV = {
    "ORCH_MAX_HOPS": "5",
    "SYNTHESIS_LLM_TIMEOUT_S": "600.0",
    "SPECIALIST_LLM_TIMEOUT_S": "4096",
}


def _run(name: str, cmd: list[str]) -> int:
    LOGS.mkdir(parents=True, exist_ok=True)
    began = time.time()
    print(f"[{name}] {' '.join(cmd[:6])} …", flush=True)
    with (LOGS / f"{name}.log").open("a") as handle:
        handle.write(f"\n=== {datetime.now().isoformat(timespec='seconds')} ===\n")
        handle.flush()
        code = subprocess.call(
            cmd, cwd=REPO, env={**os.environ, **ENV},
            stdout=handle, stderr=subprocess.STDOUT,
        )
    print(f"[{name}] exit {code} in {round(time.time() - began)}s", flush=True)
    return code


def _arm(root: Path, arm: str, bank: Path) -> list[str]:
    return [
        sys.executable, "-m", "utils.evaluation.experiment_untruncated",
        "--arm", arm, "--bank", str(bank), "--root", str(root),
        "--workers", str(WORKERS), "--llm-model", MODEL,
    ]


def _judge(root: Path, arm: str, suffix: str, position: int) -> list[str]:
    return [
        sys.executable, "-m", "utils.evaluation.judge_answers",
        "--root", str(root), "--arm", arm, "--workers", str(WORKERS),
        "--model", MODEL, "--suffix", suffix, "--position", str(position),
    ]


def _complete(root: Path, arm: str) -> bool:
    path = root / arm / "manifest.json"
    if not path.is_file():
        return False
    doc = json.loads(path.read_text())
    return bool(doc.get("count")) and doc.get("ok") == doc.get("count")


def stage_control_generate() -> int:
    return _run("control-generate",
                [sys.executable, "scripts/repair_control_run.py", "--stage", "generate"])


def stage_control_judge() -> int:
    return _run("control-judge",
                [sys.executable, "scripts/repair_control_run.py", "--stage", "judge"])


def stage_control_score() -> int:
    return _run("control-score",
                [sys.executable, "scripts/paired_control_score.py",
                 "--root", str(CONTROL)])


def stage_fresh_seal() -> int:
    """The seal, and the proof the seal can fail. Both, before anything runs."""
    code = _run("fresh-seal-selftest",
                [sys.executable, "scripts/fresh_seal.py", "--self-test"])
    if code:
        return code
    return _run("fresh-seal",
                [sys.executable, "scripts/fresh_seal.py", "--bank", str(FRESH_BANK),
                 "--out", str(REPO / "docs/research/experiments"
                              "/EXP-2026-09-018-correctness-repair/data/fresh_seal.json")])


def stage_fresh_generate() -> int:
    for arm in ARMS:
        if _complete(FRESH, arm):
            print(f"[fresh-generate] {arm} already complete", flush=True)
            continue
        code = _run(f"fresh-generate-{arm}", _arm(FRESH, arm, FRESH_BANK))
        if code:
            return code
        if not _complete(FRESH, arm):
            print(f"[fresh-generate] {arm} INCOMPLETE — stopping", flush=True)
            return 1
    return 0


def stage_fresh_judge() -> int:
    for suffix, position in PASSES:
        for arm in ARMS:
            code = _run(f"fresh-judge-{arm}{suffix}",
                        _judge(FRESH, arm, suffix, position))
            if code:
                return code
    return 0


def stage_regression_generate() -> int:
    for arm in ARMS:
        if _complete(REGRESSION, arm):
            print(f"[regression] {arm} already complete", flush=True)
            continue
        code = _run(f"regression-generate-{arm}", _arm(REGRESSION, arm, HOLDOUT_BANK))
        if code:
            return code
    return 0


def stage_regression_judge() -> int:
    for suffix, position in PASSES:
        for arm in ARMS:
            code = _run(f"regression-judge-{arm}{suffix}",
                        _judge(REGRESSION, arm, suffix, position))
            if code:
                return code
    return 0


VARIANTS = REPO / "docs/evaluation/variants-2026-08-29"
#: The T6 reference this tree is compared against — the most recent capture, so
#: the comparison measures the repairs rather than everything since August.
T6_REFERENCE = "reference_2026-09-08.json"
#: Single-user latency, at the budget the generic arm actually ships with and at
#: the old 120 s default, over the same 20 questions at ONE worker. `Q37` asks
#: for the shipped figure; the pair says what the budget itself costs.
LATENCY_BUDGETS = (("120", "120.0"), ("600", "600.0"))
LATENCY_QUESTIONS = 20


def stage_t6_rates() -> int:
    """Wrong-entity and catalogue-dump rates on the final tree.

    A Step 6 deliverable that was never produced. It is a different instrument
    from the judged bank — it asks whether an answer is about the entity that
    was asked for at all, which a correctness score can hide behind partial
    credit.
    """
    code = _run("t6-capture", [
        sys.executable, "scripts/variant_harness.py", "capture",
        "--out", str(VARIANTS), "--name", "reference_closeout-2026-09-12.json",
        "--workers", str(WORKERS),
    ])
    if code:
        return code
    return _run("t6-compare", [
        sys.executable, "scripts/variant_harness.py", "compare",
        "--out", str(VARIANTS), "--reference", T6_REFERENCE,
        "--name", "scored_closeout-2026-09-12.json", "--workers", str(WORKERS),
    ])


def stage_latency() -> int:
    """The shipped arm, one worker, both synthesis budgets."""
    for label, budget in LATENCY_BUDGETS:
        root = REPO / f"docs/evaluation/experiments/latency-2026-09-12/t{label}"
        if _complete(root, "generic"):
            print(f"[latency] t{label} already complete", flush=True)
            continue
        began = time.time()
        LOGS.mkdir(parents=True, exist_ok=True)
        cmd = [
            sys.executable, "-m", "utils.evaluation.experiment_untruncated",
            "--arm", "generic", "--bank",
            str(REPO / "docs/evaluation/composition/bank/bank-dev.json"),
            "--root", str(root), "--workers", "1",
            "--limit", str(LATENCY_QUESTIONS), "--llm-model", MODEL,
        ]
        with (LOGS / f"latency-t{label}.log").open("a") as handle:
            code = subprocess.call(
                cmd, cwd=REPO,
                env={**os.environ, **ENV, "SYNTHESIS_LLM_TIMEOUT_S": budget},
                stdout=handle, stderr=subprocess.STDOUT,
            )
        print(f"[latency] t{label} exit {code} in {round(time.time() - began)}s",
              flush=True)
        if code:
            return code
    return 0


#: Order matters and is the plan's order. The fresh set is sealed before it is
#: generated, and the holdout regression runs last because it is the only stage
#: whose result is not new evidence.
STAGES = (
    ("control-generate", stage_control_generate),
    ("control-judge", stage_control_judge),
    ("control-score", stage_control_score),
    ("fresh-seal", stage_fresh_seal),
    ("fresh-generate", stage_fresh_generate),
    ("fresh-judge", stage_fresh_judge),
    ("regression-generate", stage_regression_generate),
    ("regression-judge", stage_regression_judge),
    ("t6-rates", stage_t6_rates),
    ("latency", stage_latency),
)


def guards(skip_seal: bool) -> None:
    # CODE must be committed, so a figure is attributable to a commit. Run
    # output under `docs/evaluation/experiments` is exempt: the chain writes
    # there while it runs, and a guard that fails on its own output would stop
    # the chain the moment it started working.
    dirty = [
        line for line in subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=REPO, text=True,
        ).splitlines()
        if line[3:].strip() and not line[3:].strip().startswith(
            "docs/evaluation/experiments/"
        )
    ]
    if dirty:
        raise SystemExit(
            "working tree has uncommitted code; commit so every figure has a "
            "commit:\n  " + "\n  ".join(dirty)
        )

    from scripts.model_identity import resolve  # noqa: PLC0415

    identity = resolve("http://localhost:9090/v1", MODEL, 300.0)
    served = identity.get("served_model")
    if identity.get("error") or EXPECT not in str(served):
        raise SystemExit(
            f"{MODEL} serves {served!r}, expected {EXPECT} "
            f"({identity.get('error') or 'no error'}). The alias has served three "
            "different models; a control whose sides ran against different "
            "weights measures nothing."
        )
    print(f"[guard] {MODEL} serves {served}", flush=True)

    if not skip_seal and not FRESH_BANK.is_file():
        print(f"[guard] {FRESH_BANK.name} does not exist yet — the fresh stages "
              "will refuse; control stages can still run", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", action="append", default=[],
                    help="run just these stages, by name. Repeatable.")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--force", action="append", default=[],
                    help="re-run a stage already marked done")
    ap.add_argument("--skip-guards", action="store_true",
                    help="only for a resume where the guards were already met")
    args = ap.parse_args()

    if args.list:
        for name, _fn in STAGES:
            print(name)
        return 0

    if not args.skip_guards:
        guards(bool(args.only))

    state = json.loads(STATE.read_text()) if STATE.is_file() else {}
    state.setdefault("started", datetime.now().isoformat(timespec="seconds"))
    for name, fn in STAGES:
        if args.only and name not in args.only:
            continue
        if state.get(name, {}).get("ok") and name not in args.force:
            print(f"[{name}] done earlier, skipping", flush=True)
            continue
        began = time.time()
        code = fn()
        state[name] = {
            "ok": code == 0, "returncode": code,
            "elapsed_s": round(time.time() - began, 1),
            "finished": datetime.now().isoformat(timespec="seconds"),
        }
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(state, indent=2) + "\n")
        if code:
            print(f"[{name}] FAILED — chain stopped. Fix, then re-run; "
                  "completed stages are skipped.", flush=True)
            return code
    print("close-out chain complete", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
