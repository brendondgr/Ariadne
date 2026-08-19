#!/usr/bin/env python3
"""Measure what was built on 2026-08-19, and say plainly whether it worked.

Four things were built and none of them had a number attached:

1. two fixes to how answers get written (the system was retrieving the right
   facts and then not stating them);
2. a generator for fresh, fairly-drawn question sets;
3. an arm where a language model writes the database query itself — the
   comparison `CLAIMS.md` C-012 needs and has never had; and
4. an isolated store for the merged-graph counterfactual (not exercised here).

This runs in four phases, ordered so the most important answer arrives first.

**Phase A — did the answer-writing fixes help?** Re-runs the default cascade over
the *old* question set and pairs it question-by-question against the answers
saved last night. Same questions, same grader, same night; only the code
differs. Pairing is what makes it a clean before/after — an unpaired pair of
means cannot separate a code change from grader drift.

**Phase B — how do the four arms compare?** All four over the *fresh* bank, which
no arm has ever seen and which was drawn to exclude every anchor the old set
used.

**Phase C — why did the LLM-query arm fail where it failed?** Its score conflates
two very different things: writing a bad query, and writing a good query whose
output the evidence reader cannot parse (the reader dispatches on the column
shapes the templates emit). Reported apart, because a single number that mixes
them would misrepresent the baseline in whichever direction the reader happens
to fall.

**Phase D — a plain-language report.**

Every phase writes its result the moment it has one, so an interrupted run
reports what it finished rather than losing it.
"""

from __future__ import annotations

import argparse
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
sys.path.insert(0, str(REPO))

OLD_BANK = REPO / "utils" / "specialists" / "tests" / "golden" / "holdout_questions.json"
NEW_BANK = REPO / "docs" / "evaluation" / "banks" / "bank-2026-08-19" / "bank.json"
EXPERIMENTS = REPO / "docs" / "evaluation" / "experiments"

#: Last night's answers for the old bank, written before the composer fixes.
PRE_FIX_ROOT = EXPERIMENTS / "outerjoin-holdout"

#: The four arms, in the order a reader wants them.
ARMS = [
    ("deterministic", "the default cascade (templates)"),
    ("generic", "no templates — schema-derived primitives only"),
    ("gold_loop_llm", "authored plan + LLM narrator"),
    ("llm_query", "a language model writes the query itself"),
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _run(cmd: list[str], env: dict[str, str] | None = None, timeout: int = 7200) -> str:
    merged = {**os.environ, **(env or {})}
    proc = subprocess.run(
        cmd, cwd=REPO, env=merged, capture_output=True, text=True, timeout=timeout
    )
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout)[-1500:]
        raise RuntimeError(f"{' '.join(cmd[:6])}… exited {proc.returncode}: {tail}")
    return (proc.stdout or "") + (proc.stderr or "")


class Measurement:
    def __init__(self, out: Path, workers: int) -> None:
        self.out = out
        self.workers = workers
        self.out.mkdir(parents=True, exist_ok=True)
        self.state: dict[str, Any] = {"started": now(), "phases": []}

    def _save(self) -> None:
        (self.out / "state.json").write_text(json.dumps(self.state, indent=2) + "\n")

    def phase(self, name: str, description: str, fn: Callable[[], Any]) -> Any:
        entry = {"name": name, "description": description, "started": now()}
        self.state["phases"].append(entry)
        self._save()
        print(f"\n=== {name}: {description}", flush=True)
        start = time.time()
        try:
            result = fn()
            entry.update(status="ok", result=result)
        except Exception as exc:  # noqa: BLE001 — a measurement records, never crashes
            entry.update(status="failed", error=f"{type(exc).__name__}: {exc}",
                         traceback=traceback.format_exc()[-2000:])
            print(f"!!! {name} FAILED: {exc}", flush=True)
            result = None
        entry["wall_s"] = round(time.time() - start, 1)
        entry["finished"] = now()
        self._save()
        return result

    # -- steps -------------------------------------------------------------

    def preflight(self) -> dict[str, Any]:
        checks: dict[str, Any] = {}
        # The Gremlin store does not survive a restart; reload before anything
        # that touches the live graph rather than discovering it mid-run.
        _run(["uv", "run", "main.py", "--dataset", "capec", "--graph", "gremlin"])
        checks["capec_reload"] = "ok"
        checks["capec_verify"] = "ok" if _run(
            ["uv", "run", "main.py", "--dataset", "capec", "--graph", "verify"]
        ) else "ok"
        checks["attack_verify"] = "ok" if _run(
            ["uv", "run", "main.py", "--dataset", "attack", "--graph", "verify"]
        ) else "ok"
        for bank in (OLD_BANK, NEW_BANK):
            if not bank.is_file():
                raise RuntimeError(f"missing bank: {bank}")
            checks[f"bank:{bank.parent.name}"] = len(
                json.loads(bank.read_text())["questions"]
            )
        if not list((PRE_FIX_ROOT / "deterministic" / "answers").glob("*.judgment.json")):
            raise RuntimeError(
                f"no pre-fix judgments under {PRE_FIX_ROOT} — phase A has nothing to pair against"
            )
        return checks

    def run_arm(self, arm: str, bank: Path, root: Path) -> dict[str, Any]:
        out = _run(
            ["uv", "run", "python", "-m", "utils.evaluation.experiment_untruncated",
             "--arm", arm, "--bank", str(bank), "--root", str(root),
             "--workers", "4"],
            # The loop is pinned to 1 hop in the local .env, which starves the
            # iterative arms; every recorded run of these arms used 5.
            env={"ORCH_MAX_HOPS": "5"},
        )
        return {"arm": arm, "bank": str(bank), "root": str(root), "tail": out[-400:]}

    def judge(self, root: Path, arm: str) -> dict[str, Any]:
        from utils.evaluation.judge_answers import JudgeConfig, run
        from scripts.overnight_sweep import roll_up

        result = run(root, arm, JudgeConfig(
            base_url=os.environ.get("EVAL_LLM_BASE_URL", "http://localhost:4000/v1"),
            model=os.environ.get("EVAL_LLM_MODEL", "skynet"),
            max_tokens=8192, timeout_s=600.0,
        ), workers=self.workers)
        result["roll"] = roll_up(root, arm)
        return result

    def paired_composer_delta(self, after_root: Path) -> dict[str, Any]:
        """Per-question before/after for the answer-writing fixes."""
        from utils.evaluation.stats import bootstrap_ci

        def load(directory: Path) -> dict[str, float]:
            out: dict[str, float] = {}
            for path in directory.glob("*.judgment.json"):
                if path.name.count(".judgment") != 1:
                    continue
                row = json.loads(path.read_text())
                out[row["case_id"]] = float(row["correctness"])
            return out

        before = load(PRE_FIX_ROOT / "deterministic" / "answers")
        after = load(after_root / "deterministic" / "answers")
        shared = sorted(set(before) & set(after))
        if len(shared) < 5:
            raise RuntimeError(f"only {len(shared)} paired cases")
        deltas = [after[c] - before[c] for c in shared]
        point, low, high = bootstrap_ci(deltas, lambda v: sum(v) / len(v))
        moved = sorted(
            ({"case": c, "before": before[c], "after": after[c],
              "delta": round(after[c] - before[c], 3)} for c in shared
             if abs(after[c] - before[c]) > 1e-9),
            key=lambda r: r["delta"],
        )
        return {
            "n": len(shared),
            "before_mean": round(sum(before[c] for c in shared) / len(shared), 4),
            "after_mean": round(sum(after[c] for c in shared) / len(shared), 4),
            "delta": round(point, 4),
            "ci95": [round(low, 4), round(high, 4)],
            "improved": sum(1 for d in deltas if d > 0),
            "regressed": sum(1 for d in deltas if d < 0),
            "unchanged": sum(1 for d in deltas if d == 0),
            "moved": moved,
        }

    def classify_llm_query_failures(self, root: Path) -> dict[str, Any]:
        """Split the LLM-query arm's failures by what actually went wrong.

        Four outcomes, and only two of them are the model's fault:

        * ``answered``            — a query ran and produced evidence
        * ``gate_rejected``       — every draft was refused before execution
        * ``execution_failed``    — the database refused it (bad syntax, wrong id type)
        * ``reader_could_not_parse`` — it ran and returned rows, and the evidence
          reader threw them away because the column shape was not one the
          templates emit. Not a query defect.
        """
        buckets: dict[str, list[str]] = {
            "answered": [], "gate_rejected": [], "execution_failed": [],
            "reader_could_not_parse": [], "no_result": [],
        }
        details: list[dict[str, Any]] = []
        for path in sorted((root / "llm_query" / "answers").glob("*.json")):
            if ".judgment" in path.name:
                continue
            art = json.loads(path.read_text())
            results = (art.get("logic_flow") or {}).get("results") or []
            if not results:
                buckets["no_result"].append(art["id"])
                continue
            worst = None
            for res in results:
                if res.get("ok"):
                    kind = "answered"
                else:
                    error = (res.get("error") or "").lower()
                    gates = [t for t in (res.get("traces") or []) if t.get("step") == "gate"]
                    if gates and not any(t.get("ok") for t in gates):
                        kind = "gate_rejected"
                    elif "primary_id" in error or "provenance" in error or "record" in error:
                        kind = "reader_could_not_parse"
                    else:
                        kind = "execution_failed"
                order = ["answered", "reader_could_not_parse", "execution_failed",
                         "gate_rejected", "no_result"]
                if worst is None or order.index(kind) > order.index(worst):
                    worst = kind
                if kind != "answered":
                    details.append({
                        "case": art["id"], "kind": kind,
                        "query": (res.get("query") or "")[:220],
                        "error": (res.get("error") or "")[:220],
                    })
            buckets[worst or "no_result"].append(art["id"])
        return {
            "counts": {k: len(v) for k, v in buckets.items()},
            "cases": buckets,
            "details": details[:40],
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure the 2026-08-19 changes.")
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--out", type=Path,
                        default=REPO / "docs" / "evaluation" / "measure-2026-08-19")
    parser.add_argument("--skip-llm-query", action="store_true")
    args = parser.parse_args(argv)

    m = Measurement(args.out, args.workers)
    fix_root = EXPERIMENTS / "composerfix-holdout"
    new_root = EXPERIMENTS / "bank20260819"

    m.phase("preflight", "graphs live, banks present, pre-fix judgments on disk", m.preflight)

    # -- Phase A: did the answer-writing fixes help? -------------------------
    m.phase("A1", "re-run the cascade on the OLD bank with the fixes in",
            lambda: m.run_arm("deterministic", OLD_BANK, fix_root))
    m.phase("A2", "grade it", lambda: m.judge(fix_root, "deterministic"))
    m.phase("A3", "pair it against last night, question by question",
            lambda: m.paired_composer_delta(fix_root))

    # -- Phase B: the four arms on the fresh bank ----------------------------
    for arm, blurb in ARMS:
        if arm == "llm_query" and args.skip_llm_query:
            continue
        m.phase(f"B-run-{arm}", f"run {arm} on the fresh bank — {blurb}",
                lambda a=arm: m.run_arm(a, NEW_BANK, new_root))
        m.phase(f"B-judge-{arm}", f"grade {arm}",
                lambda a=arm: m.judge(new_root, a))

    # -- Phase C: why the LLM-query arm failed where it did ------------------
    if not args.skip_llm_query:
        m.phase("C", "split the LLM-query failures by cause",
                lambda: m.classify_llm_query_failures(new_root))

    from scripts.measure_report import write_report
    path = m.phase("D", "write the report", lambda: str(write_report(args.out)))
    print(f"\nreport: {path}", flush=True)
    ran = [p for p in m.state["phases"] if p.get("status") == "ok"]
    print(f"phases: {len(m.state['phases'])} run, "
          f"{len(m.state['phases']) - len(ran)} failed", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
