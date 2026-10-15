#!/usr/bin/env python3
"""EXP-2026-08-015 — the first confidence interval the templates-vs-generic gap has ever had.

    uv run python scripts/variance_sweep.py --population catalogue --out docs/evaluation/variance-2026-08-23

**Why resampling the bank and not re-running the arm.** Q2 has asked since July
what the variance on any of these numbers is, and every manifest still carries
`n_runs: 1` with a null `statistical_test`. The obvious reading — run each arm
ten times — measures **nothing here**: both arms are LLM-free end to end, so ten
runs produce ten byte-identical numbers. Pipeline variance on this path is zero
by construction, and that is a property to state rather than a quantity to
estimate.

The variance that exists is in **which questions you happened to ask.** Every
blind figure in the study rests on a single draw of thirty anchors. So this draws
ten anchor-disjoint banks and runs both arms over each: the spread across banks
is bank-draw variance, uncontaminated by anything else, and the paired difference
per bank is the quantity C-023 turns on.

**Retrieval only, deliberately.** `gold_in_evidence` is a set-membership test
against the committed artifact — no judge, no model, deterministic. Buying
judged correctness on ten banks is a separate decision the operator has deferred;
nothing here forecloses it, since the artifacts these runs write are exactly what
a judge pass consumes.

Two populations, reported side by side and never pooled:

``catalogue``  ATT&CK + CAPEC, where the templates-vs-generic comparison is the
               paper claim and where every recorded arm figure lives.
``identity``   the ReliaQuest customer schema, where the arm gap is an order of
               magnitude larger (+0.59) and has never carried an interval — the
               most exposed number in the record.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from utils.config import load_env  # noqa: E402

load_env()

from utils.evaluation.retrieval_coverage import score_arm, summarize  # noqa: E402

ARMS = ("deterministic", "generic")

#: Pinned so a re-run reproduces the interval exactly. 1729 matches the
#: precedent set by EXP-2026-08-007's repair-delta bootstrap.
BOOTSTRAP_SEED = 1729
BOOTSTRAP_RESAMPLES = 2000

POPULATIONS: dict[str, dict[str, Any]] = {
    "catalogue": {
        "banks_glob": "docs/evaluation/variance-2026-08-23/banks/bank*/bank.json",
        "env": {"ORCH_MAX_HOPS": "5"},
    },
    "identity": {
        "banks_glob": "docs/evaluation/variance-2026-08-23/identity/bank*/bank.json",
        # The identity stack is a separate data dir AND a separate Neo4j. Both
        # halves matter: `endpoint_for(backend)` resolves one address per
        # *backend*, so two Neo4j-backed sources in one process share it unless
        # the per-source override is set. EXP-2026-08-013 lost a whole run to
        # that — `identity` silently probed ATT&CK's store and reported ATT&CK's
        # node count as its own.
        "env": {
            "ORCH_MAX_HOPS": "5",
            "ARIADNE_DATA_DIR": "data/identity",
            "NEO4J_URI": "bolt://localhost:5459",
            "ARIADNE_ENDPOINT_IDENTITY": "bolt://localhost:5459",
        },
    },
}


def _run(cmd: list[str], env: dict[str, str] | None = None) -> str:
    import os

    merged = {**os.environ, **(env or {})}
    proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, env=merged)
    if proc.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd[:6])}… exited {proc.returncode}: "
                           f"{(proc.stdout + proc.stderr)[-800:]}")
    return proc.stdout


def run_identity_bank(bank_dir: Path, env: dict[str, str]) -> dict[str, float]:
    """Run both arms over one identity bank and return per-arm mean score.

    The identity population needs a different runner and a different scorer, and
    that is a property of the data rather than a convenience: identity questions
    carry `expected_ids` against a foreign schema with no ATT&CK-style public
    identifier, so `retrieval_coverage` — which reads `gold` assertions off a
    catalogue bank — has nothing to read. `identity_sweep` was built for exactly
    this and already scores set membership against the tenant's own gold.

    The two populations are therefore never pooled, which the protocol requires
    for a second reason as well: different schemas, different gold, different
    question shapes.
    """
    state_path = bank_dir / "sweep_state.json"
    if not state_path.is_file():
        _run(
            ["uv", "run", "python", "scripts/identity_sweep.py",
             "--out", str(bank_dir), "--arms", ",".join(ARMS)],
            env=env,
        )
    state = json.loads(state_path.read_text())
    per_arm: dict[str, list[float]] = {arm: [] for arm in ARMS}
    for key, row in (state.get("results") or {}).items():
        arm = row.get("arm") or key.split("::")[0]
        # `retrieval` is identity_sweep's per-question gold-recall fraction
        # (`hit`/`of`). It is NOT called `score` — reading a missing key as 0.0
        # produced a full sweep of clean zeros on the first attempt, which is
        # exactly the shape of a real "templates retrieve nothing" result and
        # would have been believable. Absent values raise rather than default.
        if arm not in per_arm:
            continue
        if "retrieval" not in row:
            raise KeyError(
                f"{key}: no 'retrieval' field — identity_sweep's schema changed, "
                "and defaulting would fabricate a zero"
            )
        if row["retrieval"] is not None:
            per_arm[arm].append(float(row["retrieval"]))
    return {
        arm: (round(statistics.fmean(v), 4) if v else 0.0) for arm, v in per_arm.items()
    } | {f"{arm}_n": len(v) for arm, v in per_arm.items()}


def run_bank(bank: Path, root: Path, env: dict[str, str], workers: int) -> None:
    for arm in ARMS:
        if (root / arm / "answers").is_dir():
            continue  # resumable: a completed arm is not re-run
        _run(
            [
                "uv", "run", "python", "-m", "utils.evaluation.experiment_untruncated",
                "--arm", arm, "--bank", str(bank), "--root", str(root),
                "--workers", str(workers),
            ],
            env=env,
        )


def paired_bootstrap(diffs: list[float]) -> dict[str, Any]:
    """Percentile bootstrap over the per-bank paired differences."""
    if len(diffs) < 2:
        return {"mean": diffs[0] if diffs else None, "ci95": None, "n": len(diffs)}
    rng = random.Random(BOOTSTRAP_SEED)
    means = []
    for _ in range(BOOTSTRAP_RESAMPLES):
        sample = [diffs[rng.randrange(len(diffs))] for _ in diffs]
        means.append(statistics.fmean(sample))
    means.sort()
    lo = means[int(0.025 * len(means))]
    hi = means[int(0.975 * len(means)) - 1]
    return {
        "mean": round(statistics.fmean(diffs), 4),
        "sd": round(statistics.stdev(diffs), 4),
        "ci95": [round(lo, 4), round(hi, 4)],
        "n": len(diffs),
        "resamples": BOOTSTRAP_RESAMPLES,
        "seed": BOOTSTRAP_SEED,
    }


def sweep(population: str, out_dir: Path, workers: int, skip_runs: bool) -> dict[str, Any]:
    spec = POPULATIONS[population]
    banks = sorted(REPO.glob(spec["banks_glob"]))
    if not banks:
        raise SystemExit(f"no banks matched {spec['banks_glob']}")

    per_bank: list[dict[str, Any]] = []
    for bank in banks:
        label = bank.parent.name if bank.name == "bank.json" else bank.stem
        root = out_dir / "runs" / label
        if not skip_runs and population != "identity":
            print(f"  [{population}] {label}: running both arms")
            run_bank(bank, root, spec["env"], workers)
        elif not skip_runs:
            print(f"  [{population}] {label}: running both arms")

        row: dict[str, Any] = {"bank": label, "path": str(bank.relative_to(REPO))}
        if population == "identity":
            scores = run_identity_bank(bank.parent, spec["env"])
            row.update(scores)
            det, gen = scores["deterministic"], scores["generic"]
            row["deterministic"] = {"gold_in_evidence": det, "n": scores["deterministic_n"]}
            row["generic"] = {"gold_in_evidence": gen, "n": scores["generic_n"]}
        else:
            for arm in ARMS:
                cases = score_arm(root, arm)
                row[arm] = summarize(cases)
            det = row["deterministic"]["gold_in_evidence"]
            gen = row["generic"]["gold_in_evidence"]
        row["diff_templates_minus_generic"] = round(det - gen, 4)
        per_bank.append(row)
        print(f"  [{population}] {label}: templates {det:.4f}  generic {gen:.4f}  "
              f"diff {det - gen:+.4f}")

    det_scores = [b["deterministic"]["gold_in_evidence"] for b in per_bank]
    gen_scores = [b["generic"]["gold_in_evidence"] for b in per_bank]
    diffs = [b["diff_templates_minus_generic"] for b in per_bank]

    def spread(xs: list[float]) -> dict[str, Any]:
        return {
            "mean": round(statistics.fmean(xs), 4),
            "sd": round(statistics.stdev(xs), 4) if len(xs) > 1 else 0.0,
            "min": round(min(xs), 4),
            "max": round(max(xs), 4),
            "n": len(xs),
        }

    return {
        "population": population,
        "banks": per_bank,
        "deterministic": spread(det_scores),
        "generic": spread(gen_scores),
        "paired_difference": paired_bootstrap(diffs),
        "note": (
            "Retrieval only (gold_in_evidence). Both arms are LLM-free, so "
            "pipeline variance is zero by construction and all spread here is "
            "bank-draw variance."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--population", choices=sorted(POPULATIONS), required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--skip-runs", action="store_true",
                        help="score existing run directories without re-running")
    args = parser.parse_args()

    out_dir = REPO / args.out / args.population
    out_dir.mkdir(parents=True, exist_ok=True)
    result = sweep(args.population, out_dir, args.workers, args.skip_runs)
    (out_dir / "metrics.json").write_text(json.dumps(result, indent=2) + "\n")

    d, g, p = result["deterministic"], result["generic"], result["paired_difference"]
    print(f"\n== {args.population}: {d['n']} anchor-disjoint banks, retrieval only")
    print(f"  templates  mean {d['mean']:.4f}  sd {d['sd']:.4f}  [{d['min']:.4f}, {d['max']:.4f}]")
    print(f"  generic    mean {g['mean']:.4f}  sd {g['sd']:.4f}  [{g['min']:.4f}, {g['max']:.4f}]")
    ci = p.get("ci95")
    print(f"  templates - generic: {p['mean']:+.4f}"
          + (f"  95% CI [{ci[0]:+.4f}, {ci[1]:+.4f}]" if ci else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
