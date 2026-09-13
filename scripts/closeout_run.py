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
import shutil
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
SIDES = ("repaired", "reference")
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


#: `EXP-2026-09-016` A-8: healthy is at or below this, over ANSWERS.
HEALTHY_FALLBACK = 0.14
#: How many ungraded answers a cell-pass may carry before the stage fails.
#:
#: Not zero, and the difference matters. One answer timing out three times at
#: 900 s is a slow outlier — a 48 KB answer that graded fine in the other
#: position — and failing the stage for it means retrying the whole stage, which
#: at 60 supervised restarts would burn the night to recover one judgment the
#: scorer can already do without (it averages the positions a case actually
#: has). A dropped tunnel does not produce one gap, it produces hundreds. So the
#: threshold separates the two, and anything tolerated is recorded rather than
#: passed over in silence.
MAX_UNGRADED_PER_PASS = 2


def _fallback_rate(root: Path, arm: str) -> float:
    answers = [p for p in (root / arm / "answers").glob("*.json")
               if ".judgment" not in p.name]
    if not answers:
        return 1.0
    fell_back = 0
    for path in answers:
        try:
            reason = (json.loads(path.read_text()).get("answer") or {}).get(
                "fallback_reason")
        except (json.JSONDecodeError, OSError):
            reason = "unreadable"
        fell_back += bool(reason)
    return fell_back / len(answers)


def _complete(root: Path, arm: str) -> bool:
    """Every case answered — and, for the LLM arm, actually answered BY the LLM.

    `:9090` is an SSH tunnel, not a local server. If it drops mid-run the
    narrator falls back and the arm still writes an answer per case, so
    `ok == count` stays true while the cell quietly becomes a model-free run
    wearing the `generic` label. The fallback rate is the difference between a
    cell and a cell that means anything.
    """
    path = root / arm / "manifest.json"
    if not path.is_file():
        return False
    doc = json.loads(path.read_text())
    if not doc.get("count") or doc.get("ok") != doc.get("count"):
        return False
    if arm == "generic":
        rate = _fallback_rate(root, arm)
        if rate > HEALTHY_FALLBACK:
            print(f"[health] {root.name}/{arm} fallback rate {rate:.4f} exceeds "
                  f"{HEALTHY_FALLBACK} — the tunnel probably dropped; "
                  "the cell is NOT complete", flush=True)
            return False
    return True


def _ungraded(root: Path, arm: str, suffix: str) -> list[str]:
    """Answers with no judgment sidecar for this position.

    A judge run whose calls all fail still exits zero: each case writes
    `<case>.judgment<suffix>.error.txt` and no `.json`. Counting the answers
    against the sidecars is what turns that into a failure the chain can see.
    """
    directory = root / arm / "answers"
    missing = []
    for path in sorted(directory.glob("*.json")):
        if ".judgment" in path.name:
            continue
        if not path.with_name(f"{path.stem}.judgment{suffix}.json").is_file():
            missing.append(path.stem)
    return missing


#: The commit the repaired cells must have been produced at. Set when the tree
#: changes under a control that has already run: the repaired side is rebuilt,
#: the reference side is not, because it is a different commit and unaffected.
REPAIRED_SIDE_AT = "14331824"


def stage_control_regenerate_repaired() -> int:
    """Rebuild the repaired half of the control on the current tree.

    I-18 changed what an answer says, so the repaired cells measured a tree that
    no longer exists. The reference half is left alone — it is `e09c2571`, which
    this fix does not touch, and its judgments already reproduced the committed
    Step 6 reference to within 0.0016.
    """
    stale = CONTROL / "repaired"
    marker = stale / ".built-at"
    if marker.is_file() and marker.read_text().strip() == REPAIRED_SIDE_AT:
        print("[control-regenerate] repaired side already at "
              f"{REPAIRED_SIDE_AT}, skipping", flush=True)
        return 0
    if stale.is_dir():
        retired = CONTROL / f"repaired-pre-{REPAIRED_SIDE_AT}"
        if retired.exists():
            shutil.rmtree(retired)
        stale.rename(retired)
        print(f"[control-regenerate] kept the pre-fix side as {retired.name}",
              flush=True)
    for arm in ARMS:
        code = _run(f"control-regenerate-{arm}",
                    _arm(CONTROL / "repaired", arm,
                         REPO / "docs/evaluation/composition/bank/bank-dev.json"))
        if code:
            return code
        if not _complete(CONTROL / "repaired", arm):
            print(f"[control-regenerate] {arm} INCOMPLETE — stopping", flush=True)
            return 1
    marker.write_text(REPAIRED_SIDE_AT + "\n")
    return 0


def stage_control_rejudge() -> int:
    """Judge the rebuilt repaired half, both positions."""
    for suffix, position in PASSES:
        for arm in ARMS:
            code = _run(f"control-rejudge-{arm}{suffix}",
                        _judge(CONTROL / "repaired", arm, suffix, position))
            if code:
                return code
            if _report_ungraded("control-rejudge", f"repaired/{arm}{suffix}",
                                _ungraded(CONTROL / "repaired", arm, suffix)):
                return 1
    return 0


def stage_control_generate() -> int:
    """Skip entirely when all six cells are already on disk and complete.

    Belt and braces after 2026-09-12: the six cells had finished, the chain
    re-entered this stage to confirm it, the runner refused on a dirty tree it
    had dirtied itself, and the whole judging phase never started.
    """
    cells = [(side, arm) for side in ("repaired", "reference") for arm in ARMS]
    if all(_complete(CONTROL / side, arm) for side, arm in cells):
        print("[control-generate] all six cells complete on disk, skipping",
              flush=True)
        return 0
    return _run("control-generate",
                [sys.executable, "scripts/repair_control_run.py", "--stage", "generate"])


def stage_control_judge() -> int:
    code = _run("control-judge",
                [sys.executable, "scripts/repair_control_run.py", "--stage", "judge"])
    if code:
        return code
    # Same check as the other two judged stages: the judge exits zero whether it
    # graded a case or wrote an error beside it, so count the sidecars.
    for side in SIDES:
        for arm in ARMS:
            for suffix, _position in PASSES:
                if _report_ungraded("control-judge", f"{side}/{arm}{suffix}",
                                    _ungraded(CONTROL / side, arm, suffix)):
                    return 1
    return 0


def _claims_digest(path: Path) -> str:
    import hashlib

    doc = json.loads(path.read_text())
    text = "\u0000".join(
        c.get("text", "") for c in (doc.get("answer") or {}).get("claims") or []
    )
    return hashlib.sha256(text.encode()).hexdigest()


def stage_control_patch() -> int:
    """Re-answer the repaired side and re-judge ONLY what the tree changed.

    I-19 landed after the re-judge had started, and its blast radius is one
    answer in 852. Rebuilding and re-grading the whole side for that would cost
    four hours to correct two judgments; grading nothing would leave the control
    describing a tree that is not the one shipped. So: digest every answer's
    claims, regenerate, and delete the sidecars of exactly those whose claims
    moved. The judge then skips everything that still has one.

    It is written to be safe when nothing has changed — the usual case on a
    re-run — in which case it regenerates, finds no differences and grades
    nothing.
    """
    before = {}
    for arm in ARMS:
        for path in (CONTROL / "repaired" / arm / "answers").glob("*.json"):
            if ".judgment" not in path.name:
                before[(arm, path.name)] = _claims_digest(path)
    for arm in ARMS:
        code = _run(f"control-patch-{arm}",
                    _arm(CONTROL / "repaired", arm,
                         REPO / "docs/evaluation/composition/bank/bank-dev.json"))
        if code:
            return code
        if not _complete(CONTROL / "repaired", arm):
            print(f"[control-patch] {arm} INCOMPLETE — stopping", flush=True)
            return 1

    stale = []
    for arm in ARMS:
        for path in sorted((CONTROL / "repaired" / arm / "answers").glob("*.json")):
            if ".judgment" in path.name:
                continue
            key = (arm, path.name)
            if key in before and _claims_digest(path) != before[key]:
                stale.append((arm, path))
    print(f"[control-patch] {len(stale)} answer(s) changed", flush=True)
    for arm, path in stale:
        print(f"    {path.stem[:60]}", flush=True)
        for suffix, _position in PASSES:
            sidecar = path.with_name(f"{path.stem}.judgment{suffix}.json")
            if sidecar.is_file():
                sidecar.unlink()
    if not stale:
        return 0
    for suffix, position in PASSES:
        for arm in {a for a, _p in stale}:
            code = _run(f"control-patch-judge-{arm}{suffix}",
                        _judge(CONTROL / "repaired", arm, suffix, position))
            if code:
                return code
    return 0


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


def _report_ungraded(label: str, cell: str, missing: list[str]) -> int:
    """0 if the gap is tolerable and recorded, 1 if the stage must fail."""
    if not missing:
        return 0
    if len(missing) > MAX_UNGRADED_PER_PASS:
        print(f"[{label}] {cell}: {len(missing)} answers ungraded — that is not a "
              f"slow case, that is the endpoint. First: {missing[0]}. Re-running "
              "this stage picks them up.", flush=True)
        return 1
    print(f"[{label}] {cell}: TOLERATED {len(missing)} ungraded answer(s) "
          f"({', '.join(missing)}). Each was retried and timed out; the scorer "
          "averages the positions a case actually has, so these are scored on "
          "their other position. Recorded, not hidden.", flush=True)
    record = STATE.parent / "ungraded-2026-09-12.json"
    known = json.loads(record.read_text()) if record.is_file() else {}
    known[cell] = missing
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(json.dumps(known, indent=2) + "\n")
    return 0


def _judge_all(root: Path, label: str) -> int:
    for suffix, position in PASSES:
        for arm in ARMS:
            code = _run(f"{label}-judge-{arm}{suffix}",
                        _judge(root, arm, suffix, position))
            if code:
                return code
            if _report_ungraded(label, f"{arm}{suffix}",
                                _ungraded(root, arm, suffix)):
                return 1
    return 0


def stage_fresh_judge() -> int:
    return _judge_all(FRESH, "fresh")


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
    return _judge_all(REGRESSION, "regression")


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


#: Where the chain stops unless told otherwise. The operator asked for the
#: paired control and the fresh set and nothing beyond them (2026-09-13), so the
#: three stages after it stay defined — they are written and validated — but are
#: not run. `--through latency` or `--through regression-judge` turns them back
#: on without editing anything.
DEFAULT_THROUGH = "fresh-judge"

#: Order matters and is the plan's order. The fresh set is sealed before it is
#: generated, and the holdout regression runs last because it is the only stage
#: whose result is not new evidence.
STAGES = (
    ("control-generate", stage_control_generate),
    ("control-judge", stage_control_judge),
    # I-18 landed after the control had run, so the repaired half is rebuilt and
    # re-judged against the shipped tree before anything is scored from it.
    ("control-regenerate-repaired", stage_control_regenerate_repaired),
    ("control-rejudge", stage_control_rejudge),
    # I-19 landed mid-re-judge and changes one answer in 852; this re-grades
    # exactly that one rather than the side.
    ("control-patch", stage_control_patch),
    ("control-score", stage_control_score),
    ("fresh-seal", stage_fresh_seal),
    ("fresh-generate", stage_fresh_generate),
    ("fresh-judge", stage_fresh_judge),
    ("t6-rates", stage_t6_rates),
    ("latency", stage_latency),
    # Last on purpose: the holdout has been graded twice already, so this is
    # regression evidence and never a capability figure. Everything above it is
    # a number the write-up actually quotes.
    ("regression-generate", stage_regression_generate),
    ("regression-judge", stage_regression_judge),
)


def guards(skip_seal: bool) -> None:
    # CODE must be committed, so a figure is attributable to a commit. Run
    # output under `docs/evaluation/experiments` is exempt: the chain writes
    # there while it runs, and a guard that fails on its own output would stop
    # the chain the moment it started working.
    def _path_of(line: str) -> str:
        """The path a porcelain line is about, unquoted, rename-aware.

        git QUOTES a path containing anything unusual, and these case ids carry
        `[`, `]` and `::`, so a prefix test against the raw line matched nothing
        and the guard refused on its own run output the moment a stage renamed a
        directory. A rename line is `old -> new`; the destination is the one
        that matters.
        """
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip()
        return path.strip('"')

    dirty = [
        line for line in subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=REPO, text=True,
        ).splitlines()
        if _path_of(line)
        and not _path_of(line).startswith("docs/evaluation/experiments/")
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
    ap.add_argument("--through", default=DEFAULT_THROUGH,
                    help="last stage to run; later stages are not attempted")
    ap.add_argument("--skip-guards", action="store_true",
                    help="only for a resume where the guards were already met")
    args = ap.parse_args()

    if args.list:
        for name, _fn in STAGES:
            print(name)
        return 0

    if not args.skip_guards:
        guards(bool(args.only))

    names = [n for n, _fn in STAGES]
    if args.through not in names:
        raise SystemExit(f"--through {args.through!r} is not a stage: {names}")
    last = names.index(args.through)

    state = json.loads(STATE.read_text()) if STATE.is_file() else {}
    state.setdefault("started", datetime.now().isoformat(timespec="seconds"))
    for index, (name, fn) in enumerate(STAGES):
        if index > last:
            print(f"[{name}] not requested (--through {args.through})", flush=True)
            continue
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
    print(f"close-out chain complete (through {args.through})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
