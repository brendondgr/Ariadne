#!/usr/bin/env python3
"""Run the expansion-bank experiment chain unattended, then write the report.

Started before bed, read over coffee. Phases are ordered **by value, not by
dependency**, so an interruption at 3am leaves the questions that matter most
answered rather than the first ones. Each phase writes its artifacts before the
next begins and records its outcome in `overnight-state.json`, so a restart
costs one phase and nothing before it.

What this does not do: it does not change a line of the system under test, it
does not push, it does not touch the sealed holdout half, and it does not invent
a number — every figure in the report is read from a file this run produced.

    uv run python scripts/expansion_overnight.py --workers 16
    uv run python scripts/expansion_overnight.py --dry-run
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

REPO = Path(__file__).resolve().parents[1]
BANK_DIR = REPO / "docs/evaluation/composition/bank"
BANK = BANK_DIR / "bank.json"
DEV_BANK = BANK_DIR / "bank-dev.json"
#: The grader-free score already ran over the whole bank here.
ROOT = REPO / "docs/evaluation/experiments/expansion-2026-09-01"

#: The judged comparison gets its own root, with **all three arms run over the
#: same dev half**. Judging the existing root would compare `deterministic` on
#: 572 questions against the other arms on 284 — a different population per arm,
#: which is not a comparison.
JUDGED_ROOT = REPO / "docs/evaluation/experiments/expansion-judged-2026-09-01"
STATE = BANK_DIR / "overnight-state.json"
LOGS = REPO / "logs/overnight"

#: `deterministic` already ran; the other two make the bank a comparison rather
#: than a measurement. `merged` is out of scope — it needs its own data
#: directory and store, which cannot be set up safely unsupervised.
ARMS = ("deterministic", "generic", "llm_query")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _run(cmd: list[str], env: dict[str, str] | None = None, log: Path | None = None) -> str:
    merged = {**os.environ, **(env or {})}
    result = subprocess.run(cmd, cwd=REPO, env=merged, capture_output=True, text=True)
    output = (result.stdout or "") + (result.stderr or "")
    if log:
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(output)
    if result.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd[:6])}… exited {result.returncode}: {output[-1500:]}")
    return output


class Sweep:
    """Phase runner. Records every outcome; never lets one failure end the night."""

    def __init__(self, workers: int, dry_run: bool) -> None:
        self.workers = workers
        self.dry_run = dry_run
        self.state: dict[str, Any] = {"started": now(), "phases": []}
        if STATE.is_file():
            try:
                prior = json.loads(STATE.read_text())
                self.state["phases"] = [p for p in prior.get("phases", []) if p.get("status") == "ok"]
                self.state["resumed_from"] = prior.get("started")
            except json.JSONDecodeError:
                pass

    def _save(self) -> None:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(self.state, indent=1) + "\n")

    def done(self, name: str) -> bool:
        return any(p["name"] == name and p["status"] == "ok" for p in self.state["phases"])

    def phase(self, name: str, fn: Callable[[], Any]) -> Any:
        if self.done(name):
            print(f"[skip] {name} (already ok in a previous run)", flush=True)
            return None
        if self.dry_run:
            print(f"[plan] {name}")
            return None
        entry = {"name": name, "started": now(), "status": "running"}
        self.state["phases"].append(entry)
        self._save()
        print(f"\n=== {name} — {now()}", flush=True)
        start = time.time()
        try:
            result = fn()
            entry.update(status="ok", result=result)
        except Exception as exc:  # noqa: BLE001 — a sweep records, it never crashes
            entry.update(status="failed", error=f"{type(exc).__name__}: {exc}",
                         traceback=traceback.format_exc()[-2000:])
            print(f"!!! {name} FAILED: {exc}", flush=True)
            result = None
        entry["wall_s"] = round(time.time() - start, 1)
        entry["finished"] = now()
        self._save()
        return result

    # -- phases ------------------------------------------------------------

    def preflight(self) -> dict[str, Any]:
        """Verify the ground before standing on it.

        Every overnight failure this project has recorded started here: an empty
        store, a stale build, or a grader alias serving a different model than
        the log claimed. Also writes the dev-half bank, so no later phase can
        touch the sealed holdout by accident.
        """
        checks: dict[str, Any] = {}
        _run(["uv", "run", "main.py", "--graph", "gremlin", "--dataset", "capec"],
             log=LOGS / "preflight-load.log")
        for dataset in ("attack", "capec"):
            _run(["uv", "run", "main.py", "--graph", "fixture-qa", "--dataset", dataset],
                 log=LOGS / f"preflight-qa-{dataset}.log")
            checks[f"fixture_qa_{dataset}"] = "pass"

        identity = _run(["uv", "run", "python", "scripts/model_identity.py"],
                        log=LOGS / "preflight-model.log")
        checks["grader_identity"] = next(
            (line.strip() for line in identity.splitlines() if "skynet" in line), "unknown"
        )

        bank = json.loads(BANK.read_text())
        checks["bank_sha256"] = hashlib.sha256(BANK.read_bytes()).hexdigest()
        dev = [q for q in bank["questions"] if q["split"] == "dev"]
        holdout = [q for q in bank["questions"] if q["split"] != "dev"]
        DEV_BANK.write_text(
            json.dumps({**bank, "questions": dev}, indent=1, ensure_ascii=False) + "\n"
        )
        checks["dev_questions"] = len(dev)
        checks["holdout_questions_sealed"] = len(holdout)
        if not dev:
            raise RuntimeError("dev half is empty — refusing to start")
        return checks

    def run_arm(self, arm: str) -> dict[str, Any]:
        out = _run(
            ["uv", "run", "python", "-m", "utils.evaluation.experiment_untruncated",
             "--arm", arm, "--bank", str(DEV_BANK), "--root", str(JUDGED_ROOT),
             "--workers", "4"],
            # The local .env pins ORCH_MAX_HOPS=1, which starves the iterative
            # arms; every recorded run of these used 5.
            env={"ORCH_MAX_HOPS": "5"},
            log=LOGS / f"arm-{arm}.log",
        )
        return {"arm": arm, "tail": out[-300:]}

    def judge(self, arm: str, suffix: str, position: int) -> dict[str, Any]:
        from utils.evaluation.judge_answers import JudgeConfig, run

        summary = run(
            JUDGED_ROOT, arm,
            JudgeConfig(
                base_url=os.environ.get("EVAL_LLM_BASE_URL", "http://localhost:4000/v1"),
                model=os.environ.get("EVAL_LLM_MODEL", "skynet"),
                # EXP-2026-08-021: ~7-8% of the largest answers fail to grade at
                # smaller budgets, and the failures land on the thorough answers.
                max_tokens=32768,
                timeout_s=900.0,
                position=position,
            ),
            workers=self.workers,
            suffix=suffix,
        )
        return {"arm": arm, "suffix": suffix, "position": position, "summary": summary}

    def rollup(self) -> dict[str, Any]:
        """Average each arm's judged correctness, with its denominator.

        Both passes are averaged per case first, so an arm that lost a judgment
        in one pass is not silently scored on fewer questions than the others.
        """
        import statistics
        from collections import defaultdict

        per_arm: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
        for arm in ARMS:
            answers = JUDGED_ROOT / arm / "answers"
            for path in sorted(answers.glob("*.judgment*.json")) if answers.is_dir() else []:
                try:
                    payload = json.loads(path.read_text())
                except json.JSONDecodeError:
                    continue
                if payload.get("correctness") is not None:
                    per_arm[arm][payload.get("case_id", path.name)].append(payload["correctness"])

        result: dict[str, Any] = {}
        summary: dict[str, float | None] = {}
        for arm in ARMS:
            cases = per_arm.get(arm, {})
            means = [statistics.fmean(v) for v in cases.values() if v]
            summary[arm] = round(statistics.fmean(means), 4) if means else None
            result[arm] = {
                "cases_judged": len(means),
                "judgments": sum(len(v) for v in cases.values()),
                "mean_correctness": summary[arm],
            }
        (BANK_DIR / "judged.json").write_text(json.dumps(summary, indent=1) + "\n")
        (BANK_DIR / "judged-detail.json").write_text(json.dumps(result, indent=1) + "\n")
        return result

    def analysis(self, script: str, *args: str) -> dict[str, Any]:
        out = _run(["uv", "run", "python", f"scripts/{script}", *args],
                   log=LOGS / f"{Path(script).stem}.log")
        return {"script": script, "tail": out[-1200:]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-judge", action="store_true",
                        help="analysis and report only, for a fast rehearsal")
    args = parser.parse_args(argv)

    sweep = Sweep(args.workers, args.dry_run)
    LOGS.mkdir(parents=True, exist_ok=True)

    sweep.phase("preflight", sweep.preflight)

    # All three over the dev half, into the judged root, so every arm answers
    # exactly the same questions.
    for arm in ARMS:
        sweep.phase(f"run:{arm}", lambda a=arm: sweep.run_arm(a))

    # Score and the two analyses run BEFORE judging: they need no model, they
    # take minutes, and they answer the questions the night is really for. If
    # grading overruns, these are already on disk.
    sweep.phase("score", lambda: sweep.analysis("score_bank.py"))
    sweep.phase("direction", lambda: sweep.analysis("direction_contrast.py"))
    sweep.phase("anomalies", lambda: sweep.analysis("anomaly_triage.py"))
    sweep.phase("report:early", lambda: sweep.analysis("morning_report.py"))

    if not args.skip_judge:
        # Two passes with the arm order reversed between them, so the ~0.01
        # position effect (EXP-2026-08-022) can be subtracted rather than
        # loaded onto whichever arm happens to go last.
        from utils.evaluation.grading_order import counterbalanced, position_of

        for block, suffix in enumerate((".p1", ".p2")):
            for arm in counterbalanced(ARMS, block):
                sweep.phase(
                    f"judge:{arm}{suffix}",
                    lambda a=arm, s=suffix, b=block: sweep.judge(a, s, position_of(a, ARMS, b)),
                )

    sweep.phase("rollup", sweep.rollup)
    sweep.phase("report:final", lambda: sweep.analysis("morning_report.py"))

    sweep.state["finished"] = now()
    sweep._save()

    ok = sum(1 for p in sweep.state["phases"] if p["status"] == "ok")
    total = len(sweep.state["phases"])
    print(f"\n=== sweep finished {now()}: {ok}/{total} phases ok")
    for phase in sweep.state["phases"]:
        mark = "ok  " if phase["status"] == "ok" else "FAIL"
        print(f"  [{mark}] {phase['name']}  {phase.get('wall_s', 0)}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
