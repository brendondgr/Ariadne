#!/usr/bin/env python3
"""EXP-2026-08-009 — does federating beat merging? (C-015)

The project's pitch is that keeping ATT&CK and CAPEC in separate engines, each
queried in its own language, is worth the complexity. That has never been
contrasted with the obvious alternative, because the alternative did not exist.
It does now: one Neo4j holding both catalogues, answered by one Cypher
specialist running the schema-driven primitives.

**The comparison this measures.** `merged` against `generic` — Arm H, the
federated arm that also runs schema-driven primitives and no templates. Same
query capability, same authored plans, same questions, same grader. The number
of stores is the only difference, which is what makes a difference between them
attributable to the architecture. `deterministic` is graded alongside as a
secondary reading, because it is the arm the paper leads with.

**Why the federated arms are re-judged rather than re-run.** Their answers are
already on disk. Re-running `generic` would introduce run-to-run variance — it
has a language model in the loop, and the narrator arm was measured at 0.0283
against itself — while removing only grader variance, which is 0.0050. Judging
the saved files with this session's grader removes the grader from the
comparison without adding anything.

Every phase writes its result the moment it has one, so an interrupted run
reports what it finished. `--resume` picks up from the state file.

    uv run python scripts/merged_sweep.py --out docs/evaluation/merged-2026-08-21
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.measure_arms import EXPERIMENTS, Measurement, _run, now  # noqa: E402
from utils.config import load_env  # noqa: E402

load_env()

BANKS = {
    "bank20260819": REPO / "docs" / "evaluation" / "banks" / "bank-2026-08-19" / "bank.json",
    "bank20260820": REPO / "docs" / "evaluation" / "banks" / "bank-2026-08-20" / "bank.json",
}

#: The arm under test, and the two it is read against. `generic` is the primary
#: comparison — same primitives, two stores instead of one. `deterministic` is
#: the arm the paper leads with, read as a secondary.
MERGED_ARM = "merged"
FEDERATED_ARMS = ("generic", "deterministic")

#: One grader, one session, every cell. A suffixed pass so the committed
#: judgments are never overwritten — and `roll_up` counts `.judgment` exactly
#: once, so a suffixed file cannot be mistaken for a plain one.
JUDGE_SUFFIX = ".c015"
JUDGE_MODEL = os.environ.get("MERGED_JUDGE_MODEL", "skynet")
JUDGE_MAX_TOKENS = int(os.environ.get("MERGED_JUDGE_MAX_TOKENS", "8192"))

MERGED_DATA_DIR = "data-merged"
MERGED_URI = f"bolt://localhost:{os.environ.get('NEO4J_MERGED_BOLT_PORT', '5458')}"


def _judge_config():
    from utils.evaluation.judge_answers import JudgeConfig

    return JudgeConfig(
        base_url=os.environ.get("EVAL_LLM_BASE_URL", "http://localhost:4000/v1"),
        model=JUDGE_MODEL,
        max_tokens=JUDGE_MAX_TOKENS,
        timeout_s=900.0,
    )


class MergedSweep(Measurement):
    def __init__(self, out: Path, workers: int, resume: bool = False) -> None:
        super().__init__(out, workers)
        self._prior: dict[str, Any] = {}
        state_path = out / "state.json"
        if resume and state_path.is_file():
            prior = json.loads(state_path.read_text())
            self._prior = {p["name"]: p for p in prior["phases"] if p.get("status") == "ok"}
            self.state["phases"] = list(prior["phases"])
            self.state["resumed_from"] = prior.get("started")

    def phase(self, name: str, description: str, fn):
        done = self._prior.get(name)
        if done is not None:
            print(f"=== {name}: reusing the result already on disk", flush=True)
            return done.get("result")
        self.state["phases"] = [p for p in self.state["phases"] if p.get("name") != name]
        return super().phase(name, description, fn)

    # -- P0 -----------------------------------------------------------------

    def preflight(self) -> dict[str, Any]:
        """Both graphs live and whole, both banks present, both arms' answers on disk.

        The merged store's separation checks run here rather than at the end,
        because every figure this sweep produces is meaningless if the store is
        half-loaded or is quietly mixing the two catalogues — and a half-loaded
        store answers questions perfectly happily.
        """
        from scripts.merged_separation import run as separation

        checks: dict[str, Any] = {}
        # CAPEC's Gremlin fixture never survives a container restart. Reload
        # before anything touches it rather than discovering it mid-run.
        _run(["uv", "run", "main.py", "--dataset", "capec", "--graph", "gremlin"])
        checks["capec_reload"] = "ok"

        sep = separation()
        checks["separation"] = sep
        if not sep["passed"]:
            failed = [c["check"] for c in sep["checks"] if not c["ok"]]
            raise RuntimeError(f"merged store failed separation checks: {failed}")

        for name, bank in BANKS.items():
            if not bank.is_file():
                raise RuntimeError(f"missing bank: {bank}")
            for arm in FEDERATED_ARMS:
                answers = EXPERIMENTS / name / arm / "answers"
                n = len(list(answers.glob("*.json"))) if answers.is_dir() else 0
                if n == 0:
                    raise RuntimeError(f"no committed answers for {name}/{arm}")
                checks[f"{name}/{arm}"] = n
        return checks

    # -- M1/M2: run the merged arm ------------------------------------------

    def run_merged(self, bank_name: str) -> dict[str, Any]:
        bank = BANKS[bank_name]
        root = EXPERIMENTS / bank_name
        env = {
            "ARIADNE_DATA_DIR": MERGED_DATA_DIR,
            "NEO4J_URI": MERGED_URI,
            "ORCH_MAX_HOPS": "5",
        }
        out = _run(
            ["uv", "run", "python", "-m", "utils.evaluation.experiment_untruncated",
             "--arm", MERGED_ARM, "--bank", str(bank), "--root", str(root),
             "--workers", str(self.workers)],
            env=env, timeout=3600,
        )
        answers = root / MERGED_ARM / "answers"
        return {
            "bank": bank_name,
            "answers": len(list(answers.glob("*.json"))),
            "tail": out.strip().splitlines()[-1] if out.strip() else "",
        }

    # -- M3/M4/M5/M6: one grader over every cell ----------------------------

    def judge(self, bank_name: str, arm: str) -> dict[str, Any]:
        """Grade one arm on one bank, into a suffixed sidecar.

        `force=True` because the point is *this* grader's read of every cell.
        Without it a cell that already carries a `.c015` judgment from an
        interrupted attempt would be skipped and silently mix two passes.
        """
        from scripts.overnight_sweep import roll_up
        from utils.evaluation.judge_answers import run as judge_run

        root = EXPERIMENTS / bank_name
        result = judge_run(
            root, arm, _judge_config(), workers=self.workers,
            suffix=JUDGE_SUFFIX, force=True,
        )
        result["roll"] = roll_up(root, arm, suffix=JUDGE_SUFFIX)
        result["bank"] = bank_name
        result["arm"] = arm
        return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)

    out = Path(args.out)
    sweep = MergedSweep(out, args.workers, resume=args.resume)
    print(f"=== EXP-2026-08-009 started {now()} — out {out}", flush=True)

    sweep.phase("P0", "graphs live, merged store whole and separable, banks on disk",
                sweep.preflight)

    for i, bank in enumerate(BANKS, start=1):
        sweep.phase(f"M{i}-run", f"run the merged arm on {bank}",
                    lambda b=bank: sweep.run_merged(b))
        sweep.phase(f"M{i}-judge", f"grade the merged arm on {bank}",
                    lambda b=bank: sweep.judge(b, MERGED_ARM))

    n = len(BANKS)
    for j, arm in enumerate(FEDERATED_ARMS):
        for i, bank in enumerate(BANKS, start=1):
            sweep.phase(
                f"M{n + j + 1}-judge-{arm}-{i}",
                f"re-grade the committed {arm} answers on {bank} with this session's grader",
                lambda b=bank, a=arm: sweep.judge(b, a),
            )

    def report() -> dict[str, Any]:
        from scripts.merged_report import write_report

        return {"report": str(write_report(out))}

    sweep.phase("M9", "write the plain-language report", report)

    failed = [p["name"] for p in sweep.state["phases"] if p.get("status") != "ok"]
    print(f"\n=== finished {now()}; "
          f"{len(sweep.state['phases'])} phases, {len(failed)} failed {failed}", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
