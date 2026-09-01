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

from utils.evaluation.grading_order import counterbalanced, position_of  # noqa: E402
sys.path.insert(0, str(REPO))

from scripts.measure_arms import EXPERIMENTS, Measurement, _run, now  # noqa: E402
from utils.config import load_env  # noqa: E402

load_env()

BANKS = {
    "bank20260819": REPO / "docs" / "evaluation" / "banks" / "bank-2026-08-19" / "bank.json",
    "bank20260820": REPO / "docs" / "evaluation" / "banks" / "bank-2026-08-20" / "bank.json",
}

#: The arm under test, and the three it is read against.
#:
#: `generic_composed` is THE comparison: schema-derived primitives and
#: deterministic composition, exactly as `merged` runs them, over two stores
#: instead of one. Both sides are byte-reproducible, so a difference between
#: them cannot be run variance.
#:
#: `generic` was the intended comparison until the first pass showed it turns on
#: the LLM narrator and the facet loop as well as disabling the templates —
#: reading `merged` against it varies two things at once. It is kept because it
#: is the recorded Arm H and the study's strongest arm, but it is a secondary.
#: `deterministic` is the arm the paper leads with, also a secondary.
MERGED_ARM = "merged"
CONTROL_ARM = "generic_composed"
FEDERATED_ARMS = (CONTROL_ARM, "generic", "deterministic")

#: Arms whose answers this sweep produces rather than re-judges. The two
#: recorded arms are re-judged from disk; the control has never been run.
ARMS_TO_RUN = (MERGED_ARM, CONTROL_ARM)

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
        from utils.evaluation.judge_answers import answer_files

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
                if arm in ARMS_TO_RUN:
                    continue   # produced by this sweep, not read from disk
                # Count through the judge's own selector, not a bare glob: the
                # answers directory also holds `.judgment*.json` sidecars, and a
                # glob counts 30 answers as 90. Harmless as a presence check and
                # misleading as a recorded number, which is worse.
                n = len(answer_files(EXPERIMENTS / name, arm))
                if n == 0:
                    raise RuntimeError(f"no committed answers for {name}/{arm}")
                checks[f"{name}/{arm}"] = n
        return checks

    # -- M1/M2: run the merged arm ------------------------------------------

    def run_one(self, arm: str, bank_name: str) -> dict[str, Any]:
        """Run one arm on one bank. The arm's own env overlay does the rest."""
        bank = BANKS[bank_name]
        root = EXPERIMENTS / bank_name
        out = _run(
            ["uv", "run", "python", "-m", "utils.evaluation.experiment_untruncated",
             "--arm", arm, "--bank", str(bank), "--root", str(root),
             "--workers", str(self.workers)],
            env={"ORCH_MAX_HOPS": "5"}, timeout=3600,
        )
        from utils.evaluation.judge_answers import answer_files

        return {
            "arm": arm,
            "bank": bank_name,
            # Through the judge's selector for the same reason as in preflight:
            # once this bank has been graded the directory holds sidecars too.
            "answers": len(answer_files(root, arm)),
            "tail": out.strip().splitlines()[-1] if out.strip() else "",
        }

    # -- M3/M4/M5/M6: one grader over every cell ----------------------------

    def judge(self, bank_name: str, arm: str, position: int | None = None) -> dict[str, Any]:
        """Grade one arm on one bank, into a suffixed sidecar.

        `force=True` because the point is *this* grader's read of every cell.
        Without it a cell that already carries a `.c015` judgment from an
        interrupted attempt would be skipped and silently mix two passes.
        """
        from scripts.overnight_sweep import roll_up
        from utils.evaluation.judge_answers import run as judge_run

        root = EXPERIMENTS / bank_name
        config = _judge_config()
        config.position = position
        result = judge_run(
            root, arm, config, workers=self.workers,
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

    # Every cell graded in one session by one grader, so the grader cancels out
    # of every comparison rather than being a term in it.
    step = 0
    for arm in ARMS_TO_RUN:
        for bank in BANKS:
            step += 1
            sweep.phase(f"M{step}-run-{arm}-{bank[-4:]}",
                        f"run {arm} on {bank}",
                        lambda a=arm, b=bank: sweep.run_one(a, b))
    # Counterbalanced, per bank. `merged` used to be graded first on every bank,
    # and `generic_composed` -- the federated control, i.e. the other half of
    # C-022's comparison -- always second. EXP-2026-08-022 measured what that
    # costs: the condition graded second scores about 0.01 lower whichever it is,
    # against a reported merged-minus-federated difference of 0.033 and 0.000.
    # The bias was loading entirely onto federation.
    judge_arms = (MERGED_ARM, *FEDERATED_ARMS)
    for bank_index, bank in enumerate(BANKS):
        for arm in counterbalanced(judge_arms, bank_index):
            step += 1
            verb = "grade" if arm in ARMS_TO_RUN else "re-grade the committed"
            position = position_of(arm, judge_arms, bank_index)
            sweep.phase(f"M{step}-judge-{arm}-{bank[-4:]}",
                        f"{verb} {arm} answers on {bank} (position {position})",
                        lambda a=arm, b=bank, p=position: sweep.judge(b, a, position=p))

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
