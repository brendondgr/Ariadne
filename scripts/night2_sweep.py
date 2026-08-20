#!/usr/bin/env python3
"""The second unattended night: harden yesterday's numbers, then stop.

Yesterday produced an arm table from **one** 30-question bank, graded **once**,
by a grader that shares a server with the system it is grading. Every one of
those is a caveat printed in the report's own §5. This night attacks the
caveats rather than adding features — nothing here changes a line of the system
under test, and nothing here needs a design judgment made while nobody is
watching.

  N1  draw a SECOND fresh bank, disjoint from every anchor used before
  N2  all four arms on it            — does the arm ordering survive a new draw?
  N3  the LLM-query arm at a 4x token budget  — two of its three gate refusals
                                        were empty replies, not bad queries
  N4  repeat runs of two arms        — how much does a version vary with itself?
  N5  re-grade bank 1 with a DIFFERENT model  — is the grader's ranking its own?
  N6  load the merged store          — mechanical; leaves C-015 one arm away
  N7  the morning report

Order is by value, so an interrupted night still answers the questions that
matter most. Phases write to disk the moment they have a result.

Usage:
    uv run python scripts/night2_sweep.py --workers 12
    uv run python scripts/night2_sweep.py --dry-run
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.measure_arms import ARMS, EXPERIMENTS, Measurement, _run, now  # noqa: E402
from utils.config import load_env  # noqa: E402

# Every entry point in this repo loads `.env` explicitly (see `main.py`), and
# this one did not. Subprocesses were unaffected — they load it themselves — but
# the sweep's own Neo4j calls fell back to the image-default password and read
# as "the container never came up". `override=False`, so a real env var still
# wins and the merged-store URI override in N6 still works.
load_env()

BANK1 = REPO / "docs" / "evaluation" / "banks" / "bank-2026-08-19" / "bank.json"
BANK2_DIR = REPO / "docs" / "evaluation" / "banks" / "bank-2026-08-20"
BANK2 = BANK2_DIR / "bank.json"
BANK2_SEED = 20260820

#: Yesterday's four-arm run over bank 1. N5 re-grades these answers; it does not
#: re-run them, because a cross-model grade is only interpretable if the answers
#: being graded are byte-identical to the ones the first grader saw.
BANK1_ROOT = EXPERIMENTS / "bank20260819"

#: The grader for N5. `local` is gemma-4-26B-it, a different family from the
#: `skynet` upstream that graded everything so far, and it is the only genuinely
#: independent model this relay serves. It is single-stream — llama.cpp answers
#: one request at a time — so this phase runs at one worker no matter what
#: --workers says. Eight of them saturate it into a timeout; that is measured,
#: not assumed.
CROSS_JUDGE_MODEL = os.environ.get("NIGHT2_CROSS_JUDGE", "local")

MERGED_URI = f"bolt://localhost:{os.environ.get('NEO4J_MERGED_BOLT_PORT', '5458')}"


class Night2(Measurement):
    def __init__(self, out: Path, workers: int, resume: bool = False) -> None:
        super().__init__(out, workers)
        #: Phases this night already completed. The sweep's promise is that an
        #: interrupted run costs the phase it died in and nothing before it —
        #: which was only half true, because there was no way to pick it back up.
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
        # Drop a previous *failed* attempt so the record shows one entry per
        # phase rather than a failure and a success sitting side by side.
        self.state["phases"] = [p for p in self.state["phases"] if p.get("name") != name]
        return super().phase(name, description, fn)

    # -- N1: a second bank -------------------------------------------------

    def make_bank2(self) -> dict[str, Any]:
        """Draw and author bank 2, excluding every anchor any bank has used.

        This is the first time the generator has been asked for a *second* bank,
        which is the only way to find out whether the exclusion registry works
        in anger. A fresh seed alone does not give disjointness: over 59 reseeds
        against the v1 draw, 30 shared at least one anchor.
        """
        if BANK2.is_file():
            return {"reused": True, "questions": len(json.loads(BANK2.read_text())["questions"])}
        out = _run(
            ["uv", "run", "python", "-m", "utils.specialists.evalset.make_bank",
             "--seed", str(BANK2_SEED), "--scale", "1", "--out", str(BANK2),
             "--workers", "1"],
            # ~8s per question measured against `local`, so 30 questions is
            # minutes. A generous ceiling here would let a hung author eat the
            # night; an hour is ten times the measured cost.
            timeout=3600,
        )
        bank = json.loads(BANK2.read_text())
        anchors = {(q.get("holdout_meta") or {}).get("anchor") for q in bank["questions"]}
        prior = _prior_anchors()
        return {
            "questions": len(bank["questions"]),
            "overlap_with_prior_banks": sorted(a for a in anchors if a in prior),
            "tail": out[-600:],
        }

    # -- N3: the LLM-query arm, properly funded -----------------------------

    def llm_query_funded(self, root: Path) -> dict[str, Any]:
        """Re-run the query-writing arm with four times the token budget.

        Its recorded score carries a confound: of three cases where the safety
        gate refused every draft, **two were empty replies** — the model spent
        its whole budget reasoning and emitted nothing. That is a budget defect
        in the harness, not a query the gate caught, and leaving it in the
        headline would overstate the templates' margin.
        """
        return self.run_arm_env(
            "llm_query", BANK1, root,
            {"SPECIALIST_LLM_MAX_TOKENS": "16384", "ORCH_MAX_HOPS": "5"},
        )

    def run_arm_env(self, arm: str, bank: Path, root: Path, env: dict[str, str]) -> dict[str, Any]:
        out = _run(
            ["uv", "run", "python", "-m", "utils.evaluation.experiment_untruncated",
             "--arm", arm, "--bank", str(bank), "--root", str(root), "--workers", "4"],
            env=env, timeout=14400,
        )
        return {"arm": arm, "root": str(root), "env": env, "tail": out[-400:]}

    # -- N4: how much does an arm vary with itself? -------------------------

    def repeat_run(self, arm: str, index: int) -> dict[str, Any]:
        root = EXPERIMENTS / f"repeat-{arm}-r{index}"
        self.run_arm_env(arm, BANK1, root, {"ORCH_MAX_HOPS": "5"})
        return {"root": str(root), "digests": _answer_digests(root, arm)}

    def repeat_summary(self, arm: str, roots: list[Path]) -> dict[str, Any]:
        """Same code, same questions, run again: does the answer change?

        For the templated cascade the honest expectation is *byte-identical*, and
        a digest comparison settles that without spending a single grader call.
        Where the digests differ the arm has a language model in its answer path,
        and only then is a graded spread worth buying.
        """
        base = _answer_digests(BANK1_ROOT, arm)
        rows = []
        for root in roots:
            other = _answer_digests(root, arm)
            shared = sorted(set(base) & set(other))
            rows.append({
                "root": root.name,
                "n": len(shared),
                "identical": sum(1 for c in shared if base[c] == other[c]),
                "differing": sorted(c for c in shared if base[c] != other[c]),
            })
        return {"arm": arm, "baseline": BANK1_ROOT.name, "repeats": rows}

    # -- N5: a grader that is not ours --------------------------------------

    def cross_judge(self, arm: str) -> dict[str, Any]:
        """Grade bank 1's answers again with a different model, and compare.

        The point is not a second opinion on the absolute score — it is whether
        the *ordering of the arms* is a property of the system or a property of
        the grader. A grader that ranks the arms differently would invalidate
        the comparison table, and nothing so far could have detected that.
        """
        from utils.evaluation.judge_answers import JudgeConfig, run
        from scripts.overnight_sweep import roll_up

        result = run(
            BANK1_ROOT, arm,
            JudgeConfig(
                base_url=os.environ.get("EVAL_LLM_BASE_URL", "http://localhost:4000/v1"),
                model=CROSS_JUDGE_MODEL, max_tokens=8192, timeout_s=900.0,
            ),
            workers=1, suffix=".cross",
        )
        result["roll"] = roll_up(BANK1_ROOT, arm, suffix=".cross")
        result["agreement"] = _agreement(BANK1_ROOT, arm)
        return result

    # -- N6: the merged store ------------------------------------------------

    def merged_load(self) -> dict[str, Any]:
        """Put both catalogues in one Neo4j — the counterfactual's data half.

        Deliberately stops at the data. C-015 needs something that *answers*
        against this store, and the existing templates are source-specific, so
        the arm is a code change with judgment in it. Loading is mechanical and
        it is the slow part, so it happens tonight and the arm happens awake.
        """
        # `--env-file` is not optional here. Compose resolves variables against
        # the compose file's own directory, so a bare invocation reads
        # `docker/.env` — which deliberately carries only version pins — and the
        # container comes up on the image default `neo4j/password` while every
        # client in this repo authenticates with the root `.env` password. The
        # repo's own `docker_manager.py` layers the root file on top for exactly
        # this reason; calling compose directly has to do the same.
        _run(["docker", "compose", "--env-file", str(REPO / ".env"),
              "-f", "docker/docker-compose.yml",
              "--profile", "merged", "up", "-d", "neo4j-merged"], timeout=600)
        env = {"NEO4J_URI": MERGED_URI, "ARIADNE_ALLOW_MERGED_GRAPH": "1"}
        deadline = time.time() + 300
        while time.time() < deadline:
            try:
                _counts(MERGED_URI)
                break
            except Exception:  # noqa: BLE001 — the container is simply not up yet
                time.sleep(5)
        else:
            raise RuntimeError(f"{MERGED_URI} never became reachable")
        # The failure that would ruin everything is a load landing in the MAIN
        # store instead of this one: CAPEC in the ATT&CK graph turns `Mitigation`
        # into both catalogues' mitigations and silently invalidates every figure
        # already recorded. `load_env(override=False)` means a real env var wins,
        # so the override is sound — but "sound by reading" is not "checked", and
        # this runs unattended. Count the main store before and after.
        main_uri = os.environ.get("NEO4J_URI", "bolt://localhost:5456")
        if main_uri == MERGED_URI:
            raise RuntimeError(f"merged uri equals the main uri ({main_uri}) — refusing to load")
        main_before = _counts(main_uri)

        loaded = {}
        for dataset in ("attack", "capec"):
            _run(["uv", "run", "main.py", "--dataset", dataset, "--graph", "neo4j"],
                 env=env, timeout=7200)
            loaded[dataset] = _counts(MERGED_URI)
            main_after = _counts(main_uri)
            if main_after != main_before:
                raise RuntimeError(
                    f"the {dataset} load reached the MAIN store: {main_before} -> {main_after}. "
                    "Every recorded ATT&CK figure is now suspect; restore before running anything."
                )
        return {"uri": MERGED_URI, "after_each_load": loaded,
                "main_store_untouched": main_before,
                "separation": _separation(MERGED_URI)}


# -- helpers ------------------------------------------------------------------


def _prior_anchors() -> set[str]:
    from utils.specialists.evalset.make_bank import load_registry, used_anchors
    registry = load_registry()
    banks = registry.get("banks", {})
    return {a for name, entry in banks.items() if name != BANK2_DIR.name
            for a in entry.get("anchors", [])}


def _answer_digests(root: Path, arm: str) -> dict[str, str]:
    """Hash the answer text of every case, ignoring timestamps and durations."""
    out: dict[str, str] = {}
    directory = root / arm / "answers"
    if not directory.is_dir():
        return out
    for path in sorted(directory.glob("*.json")):
        if ".judgment" in path.name:
            continue
        art = json.loads(path.read_text())
        payload = json.dumps(art.get("answer") or art.get("final_answer") or "", sort_keys=True)
        out[art.get("id", path.stem)] = hashlib.sha256(payload.encode()).hexdigest()[:16]
    return out


def _agreement(root: Path, arm: str) -> dict[str, Any]:
    """Per-question comparison of the two graders on identical answers."""
    directory = root / arm / "answers"
    pairs = []
    for path in sorted(directory.glob("*.judgment.json")):
        case = path.name[: -len(".judgment.json")]
        other = directory / f"{case}.judgment.cross.json"
        if not other.is_file():
            continue
        a = json.loads(path.read_text())
        b = json.loads(other.read_text())
        pairs.append((case, float(a["correctness"]), float(b["correctness"])))
    if not pairs:
        return {"n": 0}
    home = [p[1] for p in pairs]
    away = [p[2] for p in pairs]
    n = len(pairs)
    mean_h, mean_a = sum(home) / n, sum(away) / n
    cov = sum((h - mean_h) * (a - mean_a) for h, a in zip(home, away))
    var_h = sum((h - mean_h) ** 2 for h in home)
    var_a = sum((a - mean_a) ** 2 for a in away)
    r = cov / ((var_h * var_a) ** 0.5) if var_h > 0 and var_a > 0 else None
    return {
        "n": n,
        "home_mean": round(mean_h, 4),
        "cross_mean": round(mean_a, 4),
        "offset": round(mean_h - mean_a, 4),
        "pearson_r": round(r, 4) if r is not None else None,
        "biggest_disagreements": sorted(
            ({"case": c, "home": h, "cross": a, "gap": round(h - a, 3)} for c, h, a in pairs),
            key=lambda row: -abs(row["gap"]),
        )[:8],
    }


def _driver(uri: str):
    from neo4j import GraphDatabase
    return GraphDatabase.driver(
        uri,
        auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ.get("NEO4J_PASSWORD", "password")),
    )


def _counts(uri: str) -> dict[str, int]:
    with _driver(uri) as driver, driver.session() as session:
        return {
            "nodes": session.run("MATCH (n) RETURN count(n) AS c").single()["c"],
            "relationships": session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"],
        }


def _separation(uri: str) -> dict[str, Any]:
    """`Mitigation` is the one label both catalogues use — prove it separates.

    An unscoped `MATCH (m:Mitigation)` against the merged store returns both
    catalogues' mitigations, which is exactly the silent contamination the
    second container exists to prevent. The marker labels have to do the work.
    """
    queries = {
        "attack_objects": "MATCH (n:AttackObject) RETURN count(n) AS c",
        "capec_objects": "MATCH (n:CapecObject) RETURN count(n) AS c",
        "mitigations_total": "MATCH (n:Mitigation) RETURN count(n) AS c",
        "mitigations_attack": "MATCH (n:Mitigation:AttackObject) RETURN count(n) AS c",
        "mitigations_capec": "MATCH (n:Mitigation:CapecObject) RETURN count(n) AS c",
        "unmarked": "MATCH (n) WHERE NOT n:AttackObject AND NOT n:CapecObject RETURN count(n) AS c",
    }
    with _driver(uri) as driver, driver.session() as session:
        return {name: session.run(q).single()["c"] for name, q in queries.items()}


# -- the night ----------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Second unattended night.")
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--out", type=Path,
                        default=REPO / "docs" / "evaluation" / "night2-2026-08-20")
    parser.add_argument("--skip-merged", action="store_true")
    parser.add_argument("--resume", action="store_true",
                        help="reuse phases this out-dir already completed")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if args.dry_run:
        for line in __doc__.splitlines():
            if line.strip().startswith(("N1", "N2", "N3", "N4", "N5", "N6", "N7")):
                print(line.strip())
        return 0

    m = Night2(args.out, args.workers, resume=args.resume)
    bank2_root = EXPERIMENTS / "bank20260820"
    funded_root = EXPERIMENTS / "llmquery-funded"

    m.phase("preflight", "graphs live, bank 1 and its judgments on disk", m.preflight)

    # -- N1/N2: does the arm ordering survive a second draw? -----------------
    m.phase("N1", "draw and author a second bank, disjoint from all prior anchors",
            m.make_bank2)
    if BANK2.is_file():
        for arm, blurb in ARMS:
            m.phase(f"N2-run-{arm}", f"run {arm} on bank 2 — {blurb}",
                    lambda a=arm: m.run_arm_env(a, BANK2, bank2_root, {"ORCH_MAX_HOPS": "5"}))
            m.phase(f"N2-judge-{arm}", f"grade {arm} on bank 2",
                    lambda a=arm: m.judge(bank2_root, a))
        m.phase("N2-split", "split the bank-2 LLM-query failures by cause",
                lambda: m.classify_llm_query_failures(bank2_root))

    # -- N3: remove the token-budget confound from C-012 ---------------------
    m.phase("N3-run", "re-run the query-writing arm at 4x the token budget",
            lambda: m.llm_query_funded(funded_root))
    m.phase("N3-judge", "grade it", lambda: m.judge(funded_root, "llm_query"))
    m.phase("N3-split", "split its failures by cause",
            lambda: m.classify_llm_query_failures(funded_root))

    # -- N4: self-variance ---------------------------------------------------
    repeats: dict[str, list[Path]] = {}
    for arm in ("deterministic", "gold_loop_llm"):
        roots = []
        for index in (2, 3):
            got = m.phase(f"N4-{arm}-r{index}", f"repeat run {index} of {arm} on bank 1",
                          lambda a=arm, i=index: m.repeat_run(a, i))
            if got:
                roots.append(Path(got["root"]))
        repeats[arm] = roots
        m.phase(f"N4-summary-{arm}", f"does {arm} answer identically when re-run?",
                lambda a=arm, r=roots: m.repeat_summary(a, r))

    # -- N5: a grader that is not ours ---------------------------------------
    for arm, _ in ARMS:
        m.phase(f"N5-cross-{arm}", f"re-grade {arm} on bank 1 with {CROSS_JUDGE_MODEL}",
                lambda a=arm: m.cross_judge(a))

    # -- N6: the merged store ------------------------------------------------
    if not args.skip_merged:
        m.phase("N6", "load ATT&CK and CAPEC into the merged store and prove separation",
                m.merged_load)

    from scripts.night2_report import write_report
    path = m.phase("N7", "write the morning report", lambda: str(write_report(args.out)))
    print(f"\nreport: {path}", flush=True)
    failed = [p["name"] for p in m.state["phases"] if p.get("status") != "ok"]
    print(f"phases: {len(m.state['phases'])} run, {len(failed)} failed {failed}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
