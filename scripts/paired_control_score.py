#!/usr/bin/env python3
"""Score a paired control: the same questions, two commits, one sitting.

    uv run python scripts/paired_control_score.py --root <run root>
    uv run python scripts/paired_control_score.py --verify     # reproduce Step 6

`EXP-2026-09-018`. The Step 6 control produced `control-metrics.json` and the
code that produced it was never committed, so the experiment's headline pair —
0.7188 before, 0.7845 after — could be quoted but not re-derived. `--verify`
re-derives them from the committed judgments before this scorer is trusted on
anything new; a scorer whose first run is on fresh data has no way to be wrong
out loud.

**What makes it paired.** Every cell grades the same 284 development questions,
so the unit of analysis is the *question*, not the arm: the difference is taken
per question and its spread is the spread of those differences, not of the two
means. That is the whole reason the control exists — `Q46` records this grader
moving 0.0503 between sessions with near-zero spread inside each, and a paired
difference cancels exactly that kind of shift.

**Both grading positions, averaged.** Each answer is graded twice, in
counterbalanced order (`EXP-2026-08-022`), and a case's score is the mean of its
positions. Reading one position would confound the repair with the order the
cells happened to be graded in.

`separable` is `|difference| > 2 * standard_error`, the same rule the Step 6
metrics used. It is a coarse read and is reported as one: with n=284 and a
paired SD near 0.24 the standard error is about 0.014, so a difference under
roughly 0.03 is not separable from grading noise at this n.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

STEP6 = REPO / "docs/evaluation/experiments/repair-control-2026-09-11"
MECHANISMS = REPO / (
    "docs/research/experiments/EXP-2026-09-017-correctness-improvement-diagnostic"
    "/data/mechanisms.csv"
)
ARMS = ("deterministic", "generic_composed", "generic")
SIDES = ("reference", "repaired")
#: The pre-registered hypothesis slices. H1 is the chained/cross-catalogue half
#: the repairs targeted; H3 is the CAPEC gate slice.
H1_TIERS = ("D4", "D6")


def _scores(directory: Path) -> dict[str, float]:
    """Case id -> mean correctness across grading positions."""
    per_case: dict[str, list[float]] = {}
    for path in sorted(directory.glob("*.judgment*.json")):
        judgment = json.loads(path.read_text())
        case = judgment.get("case_id") or path.name.split(".judgment")[0]
        value = judgment.get("correctness")
        if value is not None:
            per_case.setdefault(str(case), []).append(float(value))
    return {case: statistics.fmean(v) for case, v in per_case.items()}


def _flag(directory: Path, field: str) -> int:
    """How many judgments raised ``field`` — the kill gate reads this."""
    total = 0
    for path in sorted(directory.glob("*.judgment*.json")):
        if json.loads(path.read_text()).get(field):
            total += 1
    return total


def _paired(before: dict[str, float], after: dict[str, float],
            ids: list[str] | None = None) -> dict | None:
    cases = sorted(set(before) & set(after)) if ids is None else [
        c for c in sorted(ids) if c in before and c in after
    ]
    if len(cases) < 2:
        return None
    diffs = [after[c] - before[c] for c in cases]
    sd = statistics.stdev(diffs)
    # The standard error of the PAIRED difference. The Step 6 metrics reported
    # one SE per arm, computed from the pooled per-answer SD rather than from
    # each slice's own spread; both are recorded so the older figures reproduce.
    se = sd / len(cases) ** 0.5
    difference = statistics.fmean(diffs)
    return {
        "n": len(cases),
        "before": round(statistics.fmean(before[c] for c in cases), 6),
        "after": round(statistics.fmean(after[c] for c in cases), 6),
        "paired_difference": round(difference, 6),
        "paired_sd": round(sd, 6),
        "standard_error": round(se, 6),
        "separable": abs(difference) > 2 * se,
    }


def _mechanism_slices() -> dict[str, list[str]]:
    import csv

    slices: dict[str, list[str]] = {}
    for row in csv.DictReader(MECHANISMS.open()):
        slices.setdefault(row["mechanism"], []).append(row["id"])
    return slices


def _tier(case: str) -> str:
    return case.split("-")[0]


def score(root: Path) -> dict:
    cells = {
        f"{side}/{arm}": _scores(root / side / arm / "answers")
        for side in SIDES for arm in ARMS
    }
    missing = [name for name, rows in cells.items() if not rows]
    if missing:
        raise SystemExit(f"no judgments in: {', '.join(missing)}")

    mechanisms = _mechanism_slices()
    report: dict = {"arms": {}, "kill_gate": {"per_cell": {}}}
    for arm in ARMS:
        before, after = cells[f"reference/{arm}"], cells[f"repaired/{arm}"]
        ids = sorted(set(before) & set(after))
        row: dict = {"overall": _paired(before, after)}
        if arm == "generic":
            row["H1_chain_D4_D6"] = _paired(
                before, after, [c for c in ids if _tier(c) in H1_TIERS]
            )
            row["H3_capec_slice"] = _paired(
                before, after, mechanisms.get("capec", [])
            )
            row["by_mechanism"] = {
                name: _paired(before, after, slice_ids)
                for name, slice_ids in mechanisms.items()
                if _paired(before, after, slice_ids)
            }
            row["by_tier"] = {
                tier: _paired(before, after, [c for c in ids if _tier(c) == tier])
                for tier in sorted({_tier(c) for c in ids})
            }
        report["arms"][arm] = row

    for name in cells:
        side, arm = name.split("/")
        report["kill_gate"]["per_cell"][name] = {
            "fabricated_mapping": _flag(root / side / arm / "answers",
                                        "fabricated_mapping"),
        }
    ref = sum(report["kill_gate"]["per_cell"][f"reference/{a}"]["fabricated_mapping"]
              for a in ARMS)
    rep = sum(report["kill_gate"]["per_cell"][f"repaired/{a}"]["fabricated_mapping"]
              for a in ARMS)
    report["kill_gate"].update({
        "fabricated_mapping_reference": ref,
        "fabricated_mapping_repaired": rep,
        # The gate the protocol pre-registered: the repair must not introduce
        # cross-catalogue mappings that are not in the graph.
        "passes": rep <= ref,
    })
    every = [v for rows in cells.values() for v in rows.values()]
    report["per_answer_sd"] = round(statistics.stdev(every), 4) if len(every) > 1 else 0.0
    return report


#: What `--verify` must reproduce, read off the committed Step 6 metrics.
VERIFY = [
    ("generic", "overall", "before", 0.71875),
    ("generic", "overall", "after", 0.784454),
    ("generic_composed", "overall", "before", 0.654665),
    ("generic_composed", "overall", "after", 0.753662),
    ("deterministic", "overall", "before", 0.501778),
    ("deterministic", "overall", "after", 0.573204),
]


def verify() -> int:
    """Re-derive Step 6's committed numbers. The scorer's own acceptance test."""
    report = score(STEP6)
    committed = json.loads((STEP6 / "control-metrics.json").read_text())
    bad = 0
    for arm, slice_name, field, expected in VERIFY:
        got = report["arms"][arm][slice_name][field]
        ok = abs(got - expected) < 5e-6
        bad += not ok
        print(f"  {'ok ' if ok else 'BAD'} {arm}/{slice_name}/{field}: "
              f"{got} (committed {expected})")
    for arm in ARMS:
        for slice_name in ("H1_chain_D4_D6", "H3_capec_slice"):
            want = (committed["arms"][arm].get(slice_name) or {})
            if not want:
                continue
            got = report["arms"][arm][slice_name]
            for field in ("n", "before", "after", "paired_difference"):
                ok = abs(got[field] - want[field]) < 5e-6
                bad += not ok
                print(f"  {'ok ' if ok else 'BAD'} {arm}/{slice_name}/{field}: "
                      f"{got[field]} (committed {want[field]})")
    print("REPRODUCED" if not bad else f"{bad} FIGURE(S) DO NOT REPRODUCE")
    return 1 if bad else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="paired-control run root")
    parser.add_argument("--verify", action="store_true",
                        help="reproduce the committed Step 6 figures and exit")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    if args.verify:
        return verify()
    if not args.root:
        parser.error("--root or --verify")
    report = score(Path(args.root))
    for arm in ARMS:
        row = report["arms"][arm]["overall"]
        print(f"{arm:18s} n={row['n']:3d}  {row['before']:.4f} -> {row['after']:.4f}"
              f"  diff {row['paired_difference']:+.4f} ± {row['standard_error']:.4f}"
              f"  {'separable' if row['separable'] else 'NOT separable'}")
    gate = report["kill_gate"]
    print(f"kill gate: fabricated_mapping {gate['fabricated_mapping_reference']} "
          f"-> {gate['fabricated_mapping_repaired']}  "
          f"{'PASSES' if gate['passes'] else 'FAILS'}")
    out = Path(args.out) if args.out else Path(args.root) / "control-metrics.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
