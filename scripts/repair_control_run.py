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
which is `Q56` — and the reference commit predates that preflight, its
`--llm-model` still defaulting to the dead `skynet` alias, so the model is
passed explicitly on both sides and the fallback rate is asserted after every
arm.

**Hardened 2026-09-12** for the close-out's Step 3, in four ways the Step 6 run
did without:

* the reference commit is checked out into a **worktree**, not over the top of
  the working tree. A `git checkout` mid-run leaves the repository unusable for
  hours and loses everything if the process dies between the two checkouts.
  Note `data/versions.json` is tracked, so `data/` itself must not be replaced
  by a symlink — the *subdirectories* are linked, or the schema registry
  discovers no datasets and the run reports "no specialist for source 'attack'"
  on most cases while still exiting zero;
* every arm asserts `ok == count` from its own manifest. The failure above is
  silent otherwise: 33 of 288 answers written, exit code 0;
* cells resume. A completed cell is skipped on restart, so a kill costs only
  the in-flight requests;
* `--stage dry` runs eight questions through **both** sides first and refuses
  the full chain unless the reference side resolves its data, serves the right
  model and falls back on nothing.
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

#: Overridable so a later control does not overwrite an earlier one's record.
RUN = os.environ.get("PAIRED_CONTROL_RUN", "paired-control-2026-09-12")
ROOT = REPO / "docs/evaluation/experiments" / RUN
LOGS = REPO / "logs" / RUN
STATE = ROOT / "state.json"
#: Where the reference commit is checked out. Outside the repository, so a
#: failed run cannot leave the working tree on a detached head.
WORKTREE = Path(
    os.environ.get("PAIRED_CONTROL_WORKTREE", f"/tmp/ariadne-reference-{RUN}")
)
#: Two per hard tier, one per easy tier: the dry run's slice.
DRY_TIERS = {"D0": 1, "D1": 1, "D2": 1, "D3": 1, "D4": 2, "D5": 1, "D6": 2}
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


def _completeness(root: Path, arm: str) -> dict:
    """``ok`` against ``count`` from the arm's own manifest.

    The reference side failed 255 of 288 cases once, with "no specialist for
    source 'attack'", and reported it as a one-line "wrote 33/288" before
    exiting zero. A number derived from that run would have looked like a
    catastrophic regression at the reference commit. Read the manifest.
    """
    path = root / arm / "manifest.json"
    if not path.is_file():
        return {"ok": 0, "count": 0, "complete": False, "reason": "no manifest"}
    doc = json.loads(path.read_text())
    ok, count = int(doc.get("ok", 0)), int(doc.get("count", 0))
    errors: dict[str, int] = {}
    for case in doc.get("cases", []):
        if not case.get("ok"):
            key = str(case.get("error") or "unknown")[:80]
            errors[key] = errors.get(key, 0) + 1
    return {"ok": ok, "count": count, "complete": count > 0 and ok == count,
            "errors": dict(sorted(errors.items(), key=lambda kv: -kv[1])[:3])}


def _run_arm(arm: str, root: Path, workers: int, limit: int | None = None,
             cwd: Path | None = None, only: str | None = None) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, "-m", "utils.evaluation.experiment_untruncated",
        "--arm", arm, "--bank", str(BANK), "--root", str(root),
        "--workers", str(workers), "--llm-model", JUDGE_MODEL,
    ]
    if limit:
        cmd += ["--limit", str(limit)]
    if only:
        cmd += ["--only", only]
    tag = f"{root.name}-{arm}"
    began = time.time()
    with (LOGS / f"{tag}.log").open("w") as handle:
        code = subprocess.call(
            cmd, cwd=str(cwd or REPO), env={**os.environ, **ENV},
            stdout=handle, stderr=subprocess.STDOUT,
        )
    return {
        "arm": arm, "root": str(root.relative_to(REPO)), "returncode": code,
        "elapsed_s": round(time.time() - began, 1),
        "health": _fallback_rate(root, arm),
        "completeness": _completeness(root, arm),
        "finished": datetime.now().isoformat(timespec="seconds"),
    }


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO, text=True).strip()


def _ensure_worktree() -> Path:
    """The reference commit, checked out beside the repo rather than over it.

    `data/` is NOT replaced by a symlink: `data/versions.json` is tracked, so a
    link would either be refused or land inside the checked-out directory. Its
    subdirectories are linked individually, which is the difference between a
    reference run and 255 silent failures.
    """
    if not (WORKTREE / ".git").exists():
        WORKTREE.parent.mkdir(parents=True, exist_ok=True)
        subprocess.check_call(
            ["git", "worktree", "add", "--detach", str(WORKTREE), REFERENCE_COMMIT],
            cwd=REPO,
        )
    for child in sorted((REPO / "data").iterdir()):
        if child.name == "versions.json":
            continue  # tracked; the checkout's own copy is correct
        link = WORKTREE / "data" / child.name
        if link.is_symlink():
            link.unlink()
        elif link.exists():
            continue
        link.symlink_to(child)
    env = WORKTREE / ".env"
    if env.is_symlink():
        env.unlink()
    if not env.exists():
        env.symlink_to(REPO / ".env")
    graphs = WORKTREE / "data" / "graphs"
    if not (graphs / "attack" / "canonical" / "nodes.jsonl").is_file():
        raise SystemExit(
            f"reference worktree cannot see the canonical artifacts under {graphs}; "
            "the schema registry would discover no datasets and every case would "
            "fail with \"no specialist for source 'attack'\""
        )
    return WORKTREE


def _dry_ids() -> list[str]:
    """Two questions per hard tier, one per easy tier, deterministically."""
    bank = json.loads(BANK.read_text())
    entries = bank if isinstance(bank, list) else bank.get("questions") or bank.get("cases")
    picked: list[str] = []
    for tier, want in DRY_TIERS.items():
        ids = sorted(e["id"] for e in entries if str(e["id"]).startswith(f"{tier}-"))
        picked.extend(ids[:want])
    return picked


def dry(state: dict) -> None:
    """Eight questions through both sides before five hours are committed to it.

    Generation only. What it is really testing is the reference side: that the
    worktree resolves `data/` and `.env`, that the endpoint serves the model it
    is told to use, and that nothing falls back. A reference number produced by
    a broken checkout looks exactly like a catastrophic pre-repair score.
    """
    only = ",".join(_dry_ids())
    print(f"-- dry run, {len(only.split(','))} questions --\n   {only}", flush=True)
    root = ROOT / "_dry"
    worktree = _ensure_worktree()
    rows = {}
    for side, cwd in (("repaired", REPO), ("reference", worktree)):
        for arm in ARMS:
            row = _run_arm(arm, root / side, WORKERS, cwd=cwd, only=only)
            rows[f"{side}/{arm}"] = row
            print(f"  {side}/{arm}: {row['completeness']} {row['health']}", flush=True)
    state["dry"] = rows
    STATE.write_text(json.dumps(state, indent=2) + "\n")

    bad = [name for name, row in rows.items() if not row["completeness"]["complete"]]
    if bad:
        raise SystemExit(
            f"dry run incomplete on {bad} — do NOT start the full chain.\n"
            + json.dumps({k: rows[k]["completeness"] for k in bad}, indent=2)
        )
    hot = [name for name, row in rows.items()
           if name.endswith("/generic") and row["health"]["fallbacks"]]
    if hot:
        raise SystemExit(f"dry run fell back on {hot}: {json.dumps(rows, indent=2)}")
    print("dry run clean: both sides resolve their data and nothing fell back")


def generate(state: dict) -> None:
    """Both commits, one sitting. The reference is checked out, never quoted."""
    if _git("status", "--porcelain", "--untracked-files=no"):
        raise SystemExit(
            "working tree has uncommitted tracked changes; commit first so the "
            "cell this run measures is identified by a commit."
        )
    head = _git("rev-parse", "HEAD")
    state["head"] = head
    state["reference_commit"] = _git("rev-parse", REFERENCE_COMMIT)
    worktree = _ensure_worktree()
    state["reference_worktree"] = str(worktree)

    for side, cwd in (("repaired", REPO), ("reference", worktree)):
        for arm in ARMS:
            cell = f"{side}/{arm}"
            done = (state.get("cells") or {}).get(cell)
            if done and done.get("completeness", {}).get("complete"):
                print(f"  {cell}: already complete, skipping", flush=True)
                continue
            row = _run_arm(arm, ROOT / side, WORKERS, cwd=cwd)
            state.setdefault("cells", {})[cell] = row
            STATE.write_text(json.dumps(state, indent=2) + "\n")
            print(f"  {cell}: {row['completeness']} {row['health']}", flush=True)

    incomplete = [cell for cell, row in state["cells"].items()
                  if not row["completeness"]["complete"]]
    if incomplete:
        raise SystemExit(
            f"INCOMPLETE cells: {incomplete}. Every case must be answered on both "
            "sides or the pair is not a pair. Do not judge these."
        )
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
    parser.add_argument("--stage", choices=("dry", "generate", "judge"), required=True)
    args = parser.parse_args()

    ROOT.mkdir(parents=True, exist_ok=True)
    state = json.loads(STATE.read_text()) if STATE.is_file() else {}
    state["started"] = state.get("started") or datetime.now().isoformat(timespec="seconds")

    if args.stage == "dry":
        dry(state)
    elif args.stage == "generate":
        generate(state)
    else:
        judge(state)
    STATE.write_text(json.dumps(state, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
