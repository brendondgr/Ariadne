#!/usr/bin/env python3
"""Run the judged-arm experiment chain unattended, then write a morning report.

Started before bed, read over coffee. Each phase is independent and its results
are written to disk the moment they exist, so a server restart at 3am costs you
that phase and nothing before it. The report states exactly what ran and what
did not — a partial sweep presented as a complete one is the only outcome worse
than no sweep at all.

**What this does not do.** It does not change a line of the system under test,
it does not push, and it does not invent a number: every figure in the report is
computed from judgment files on disk. The composer fix is deliberately absent —
that is a code change with design judgment in it and it is not something to do
while nobody is watching.

Order is by value, not by dependency, so an interrupted night still leaves the
questions that matter most answered:

  E0  calibrate the local judge against the committed Sonnet judgments
  E1  the repaired cascade, judged blind          — did retrieval reach answers?
  E3  Arm H, judged blind                         — templates vs schema-driven,
                                                    at equal retrieval
  E2  two more judge passes over E1's answers     — is any delta above noise?
  E4  answer_gap on both arms                     — where the loss actually is
  E5  the same pair on the 120-question catalogue — tighter n
  E7  Arm F generation 2                          — closes EXP-2026-08-006

Usage:
    uv run python scripts/overnight_sweep.py --workers 12
    uv run python scripts/overnight_sweep.py --dry-run     # print the plan only
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import traceback
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Callable

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

EXPERIMENTS = REPO / "docs" / "evaluation" / "experiments"

# (label, run root, arm dir) for every answer set this sweep grades.
CASCADE_BLIND = ("cascade-blind", EXPERIMENTS / "outerjoin-holdout", "deterministic")
CASCADE_DEV = ("cascade-dev", EXPERIMENTS / "outerjoin-dev", "deterministic")
GENERIC_BLIND = ("generic-blind", EXPERIMENTS / "holdout-v1-generic-outer", "generic")
GENERIC_DEV = ("generic-dev", EXPERIMENTS / "untruncated-generic-outer", "generic")
ARM_F_BLIND = ("armf-blind", EXPERIMENTS / "gen2-armf-holdout", "gold_loop_llm")
ARM_F_DEV = ("armf-dev", EXPERIMENTS / "gen2-armf-dev", "gold_loop_llm")
REFERENCE_BLIND = ("reference-blind", EXPERIMENTS / "holdout-v1", "deterministic")

HOLDOUT_BANK = "utils/specialists/tests/golden/holdout_questions.json"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Sweep:
    def __init__(self, out_dir: Path, workers: int, skip_armf: bool) -> None:
        self.out_dir = out_dir
        self.workers = workers
        self.skip_armf = skip_armf
        self.state: dict[str, Any] = {
            "started": now(),
            "workers": workers,
            "commit": _git("rev-parse", "HEAD"),
            "phases": [],
        }
        out_dir.mkdir(parents=True, exist_ok=True)

    # -- plumbing ----------------------------------------------------------

    def _save(self) -> None:
        (self.out_dir / "state.json").write_text(json.dumps(self.state, indent=2) + "\n")

    def phase(self, name: str, description: str, fn: Callable[[], Any]) -> Any:
        entry = {"name": name, "description": description, "started": now()}
        self.state["phases"].append(entry)
        self._save()
        print(f"\n=== {name}: {description}", flush=True)
        start = time.time()
        try:
            result = fn()
            entry.update(status="ok", result=result)
        except Exception as exc:  # noqa: BLE001 — an unattended run records, never crashes
            entry.update(
                status="failed",
                error=f"{type(exc).__name__}: {exc}",
                traceback=traceback.format_exc()[-2000:],
            )
            print(f"!!! {name} FAILED: {exc}", flush=True)
            result = None
        entry["wall_s"] = round(time.time() - start, 1)
        entry["finished"] = now()
        self._save()
        return result

    # -- steps -------------------------------------------------------------

    def preflight(self) -> dict[str, Any]:
        from utils.specialists.schema import get_registry

        checks: dict[str, Any] = {}
        with urllib.request.urlopen("http://localhost:4000/v1/models", timeout=30) as r:
            models = [m["id"] for m in json.load(r)["data"]]
        checks["llm_models"] = models
        if "skynet" not in models:
            raise RuntimeError("skynet not served — refusing to start")
        checks["neo4j_verify"] = _run(
            ["uv", "run", "main.py", "--dataset", "attack", "--graph", "verify"]
        )
        checks["gremlin_verify"] = _run(
            ["uv", "run", "main.py", "--dataset", "capec", "--graph", "verify"]
        )
        checks["git_clean"] = _git("status", "--porcelain") == ""
        for label, root, arm in (
            CASCADE_BLIND, CASCADE_DEV, GENERIC_BLIND, GENERIC_DEV, REFERENCE_BLIND
        ):
            answers = root / arm / "answers"
            n = len([p for p in answers.glob("*.json") if not p.name.endswith(".judgment.json")]) \
                if answers.is_dir() else 0
            checks[f"answers:{label}"] = n
            if n == 0:
                raise RuntimeError(f"{label}: no answers at {answers} — nothing to judge")
        return checks

    def judge(self, target: tuple[str, Path, str], suffix: str = "") -> dict[str, Any]:
        label, root, arm = target
        from utils.evaluation.judge_answers import JudgeConfig, run

        summary = run(root, arm, JudgeConfig(), workers=self.workers, suffix=suffix)
        summary["label"] = label
        summary["roll"] = roll_up(root, arm, suffix)
        return summary

    def calibrate(self) -> dict[str, Any]:
        from utils.evaluation.judge_answers import JudgeConfig, calibrate

        label, root, arm = REFERENCE_BLIND
        result = calibrate(root, arm, JudgeConfig(), self.workers)
        result["label"] = label
        (self.out_dir / "calibration.json").write_text(json.dumps(result, indent=2) + "\n")
        return {k: v for k, v in result.items() if k != "cases"}

    def answer_gap(self, target: tuple[str, Path, str]) -> dict[str, Any]:
        label, root, arm = target
        out = self.out_dir / f"answer-gap-{label}.json"
        _run([
            "uv", "run", "python", "-m", "utils.evaluation.answer_gap",
            "--root", str(root), "--arm", arm,
            "--judgment-root", str(root), "--judgment-arm", arm,
        ], out_file=out)
        try:
            return json.loads(out.read_text())
        except Exception:
            return {"note": "answer_gap wrote no JSON; see the text output", "path": str(out)}

    def run_arm_f(self, target: tuple[str, Path, str], bank: str | None) -> dict[str, Any]:
        label, root, arm = target
        cmd = [
            "uv", "run", "python", "-m", "utils.evaluation.experiment_untruncated",
            "--arm", "gold_loop_llm", "--root", str(root), "--workers", "4",
        ]
        if bank:
            cmd += ["--bank", bank]
        output = _run(cmd, env={"ORCH_MAX_HOPS": "5"})
        return {"label": label, "tail": output[-400:]}


# -- roll-ups ----------------------------------------------------------------


def roll_up(root: Path, arm: str, suffix: str = "") -> dict[str, Any]:
    """Mean correctness with a bootstrap interval, from judgment files on disk."""
    from utils.evaluation.stats import bootstrap_ci, wilson_interval

    answers = root / arm / "answers"
    rows = [
        json.loads(p.read_text())
        for p in sorted(answers.glob(f"*.judgment{suffix}.json"))
        # belt-and-braces: a doubly-suffixed name is a judgment of a judgment
        if p.name.count(".judgment") == 1
    ]
    from utils.evaluation.coverage import judgment_coverage

    cov = judgment_coverage(root, arm, suffix)
    if not rows:
        return {"n": 0, "coverage": cov}
    correctness = [float(r["correctness"]) for r in rows]
    point, low, high = bootstrap_ci(correctness, lambda v: mean(v))
    correct = sum(1 for r in rows if r["verdict"] == "CORRECT")
    w_point, w_low, w_high = wilson_interval(correct, len(rows))
    abstained = [r for r in rows if r.get("abstained")]
    return {
        "n": len(rows),
        # What n is out of. A judged mean quoted without its denominator hides a
        # loss that is not random -- see utils/evaluation/coverage.py.
        "coverage": cov,
        "correctness": {"mean": round(point, 4), "ci95": [round(low, 4), round(high, 4)]},
        "correct_rate": {
            "correct": correct,
            "point": round(w_point, 4),
            "wilson95": [round(w_low, 4), round(w_high, 4)],
        },
        "verdicts": {
            v: sum(1 for r in rows if r["verdict"] == v)
            for v in ("CORRECT", "PARTIAL", "INCORRECT")
        },
        "faithfulness": round(mean(float(r["faithfulness"]) for r in rows), 4),
        "groundedness": round(mean(float(r["groundedness"]) for r in rows), 4),
        "completeness": round(mean(float(r["completeness"]) for r in rows), 4),
        "hallucinations": sum(len(r.get("hallucinations") or []) for r in rows),
        "answers_with_hallucination": sum(1 for r in rows if r.get("hallucinations")),
        "abstained": len(abstained),
        "abstention_carries_query": sum(
            1 for r in abstained if r.get("abstention_carries_query")
        ),
        "fabricated_mapping": sum(1 for r in rows if r.get("fabricated_mapping")),
    }


def _run(cmd: list[str], env: dict[str, str] | None = None, out_file: Path | None = None) -> str:
    import os

    merged = {**os.environ, **(env or {})}
    proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, env=merged)
    output = proc.stdout + proc.stderr
    if out_file:
        out_file.write_text(proc.stdout)
    if proc.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd[:6])}… exited {proc.returncode}: {output[-600:]}")
    return output


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True
    ).stdout.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--out", default=None)
    parser.add_argument("--skip-arm-f", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_dir = Path(args.out) if args.out else REPO / "docs" / "evaluation" / f"overnight-{stamp}"

    if args.dry_run:
        print(__doc__)
        print(f"would write to {out_dir}, {args.workers} workers")
        return 0

    sweep = Sweep(out_dir, args.workers, args.skip_arm_f)
    sweep.phase("preflight", "graphs live, model served, answers present", sweep.preflight)
    sweep.phase("E0", "calibrate the local judge against the committed Sonnet judgments",
                sweep.calibrate)
    sweep.phase("E1", "judge the repaired cascade on the blind holdout",
                lambda: sweep.judge(CASCADE_BLIND))
    sweep.phase("E3", "judge Arm H on the blind holdout",
                lambda: sweep.judge(GENERIC_BLIND))
    sweep.phase("E2a", "second judge pass over the cascade's blind answers",
                lambda: sweep.judge(CASCADE_BLIND, suffix=".run2"))
    sweep.phase("E2b", "third judge pass over the cascade's blind answers",
                lambda: sweep.judge(CASCADE_BLIND, suffix=".run3"))
    sweep.phase("E4a", "answer_gap on the cascade", lambda: sweep.answer_gap(CASCADE_BLIND))
    sweep.phase("E4b", "answer_gap on Arm H", lambda: sweep.answer_gap(GENERIC_BLIND))
    sweep.phase("E5a", "judge the cascade on the 120-question catalogue",
                lambda: sweep.judge(CASCADE_DEV))
    sweep.phase("E5b", "judge Arm H on the 120-question catalogue",
                lambda: sweep.judge(GENERIC_DEV))
    if not args.skip_arm_f:
        sweep.phase("E7a", "run Arm F generation 2 on the blind holdout",
                    lambda: sweep.run_arm_f(ARM_F_BLIND, HOLDOUT_BANK))
        sweep.phase("E7b", "judge Arm F on the blind holdout",
                    lambda: sweep.judge(ARM_F_BLIND))
        sweep.phase("E7c", "run Arm F generation 2 on the catalogue",
                    lambda: sweep.run_arm_f(ARM_F_DEV, None))
        sweep.phase("E7d", "judge Arm F on the catalogue",
                    lambda: sweep.judge(ARM_F_DEV))

    sweep.state["finished"] = now()
    sweep._save()

    from scripts.overnight_report import write_report

    report = write_report(out_dir)
    print(f"\nreport: {report}")
    failed = [p for p in sweep.state["phases"] if p["status"] != "ok"]
    print(f"phases: {len(sweep.state['phases'])} run, {len(failed)} failed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
