#!/usr/bin/env python3
"""Score the frozen-evidence pair: drift control first, then the hypotheses.

    uv run python scripts/frozen_score.py

`EXP-2026-09-018` Step 5. Reads the four graded cells written by
`scripts/frozen_judge.py` and reports, in this order:

1. **The grader-drift control.** Answers whose claims did not change are graded
   in both sets. Their paired difference must fall inside the
   grader-repeatability SD of 0.0066 (`EXP-2026-09-012`). If it does not, the
   judge moved rather than the system and nothing below is admissible — so it is
   printed first and the exit status is non-zero.
2. **The changed answers**, which is where `H4` and `H5` are read.
3. **The tier slices** `D1` and `D5`, the two the step exists to settle.

Every mean is over both grading positions, so the ~0.01 order effect
(`EXP-2026-08-022`) cancels rather than being carried by one side.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

ROOT = REPO / "docs/evaluation/experiments/frozen-2026-09-11"
ARMS = ("generic_original", "generic_recomposed")
SUFFIXES = (".fz1", ".fz2")
#: `EXP-2026-09-012`: the median paired SD of one grader re-grading one answer.
GRADER_SD = 0.0066


def _scores(arm: str) -> dict[str, float]:
    """Case -> correctness, averaged over the two counterbalanced positions.

    A case graded in only one position is dropped rather than averaged over one,
    because a one-position mean carries the order effect the second position
    exists to cancel. The count is reported so a partial run is visible.
    """
    per_case: dict[str, list[float]] = {}
    for suffix in SUFFIXES:
        for path in (ROOT / arm / "answers").glob(f"*.judgment{suffix}.json"):
            judgment = json.loads(path.read_text())
            value = judgment.get("correctness")
            if value is None:
                continue
            per_case.setdefault(judgment["case_id"], []).append(float(value))
    return {
        case: sum(values) / len(values)
        for case, values in per_case.items()
        if len(values) == len(SUFFIXES)
    }


def _flags(arm: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for suffix in SUFFIXES:
        for path in (ROOT / arm / "answers").glob(f"*.judgment{suffix}.json"):
            judgment = json.loads(path.read_text())
            row = out.setdefault(judgment["case_id"], {"fabricated": 0, "halluc": 0})
            row["fabricated"] += bool(judgment.get("fabricated_mapping"))
            row["halluc"] += len(judgment.get("hallucinations") or [])
    return out


def _paired(a: dict[str, float], b: dict[str, float], cases: list[str]):
    diffs = [b[c] - a[c] for c in cases if c in a and c in b]
    if not diffs:
        return 0.0, 0.0, 0
    sd = statistics.pstdev(diffs) if len(diffs) > 1 else 0.0
    return sum(diffs) / len(diffs), sd, len(diffs)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bank", default="docs/evaluation/composition/bank/bank-dev.json")
    args = parser.parse_args()

    bank = {
        q["id"]: q for q in json.loads((REPO / args.bank).read_text())["questions"]
    }
    recomposed_dir = ROOT / "generic_recomposed" / "answers"
    changed = {
        json.loads(p.read_text())["id"]
        for p in recomposed_dir.glob("*.json")
        if ".judgment" not in p.name and json.loads(p.read_text())["claims_changed"]
    }

    before, after = _scores(ARMS[0]), _scores(ARMS[1])
    both = sorted(set(before) & set(after))
    unchanged_cases = [c for c in both if c not in changed]
    changed_cases = [c for c in both if c in changed]

    drift, drift_sd, drift_n = _paired(before, after, unchanged_cases)
    # A control with no cases is not a control that passed. `holdout_seal.py`'s
    # predecessor reported exactly this: an assertion whose loop never ran,
    # reporting a true conclusion it had not tested. The count is part of the
    # verdict.
    admissible = drift_n > 0 and abs(drift) <= GRADER_SD

    report = {
        "judged_cases_both_positions": {arm: len(_scores(arm)) for arm in ARMS},
        "paired_cases": len(both),
        "drift_control": {
            "n": drift_n,
            "paired_mean_difference": round(drift, 6),
            "paired_sd": round(drift_sd, 6),
            "grader_repeatability_sd": GRADER_SD,
            "admissible": admissible,
            "empty_control": drift_n == 0,
        },
    }

    print("== grader-drift control (claims unchanged) ==")
    print(f"  n={drift_n}  paired difference={drift:+.6f}  sd={drift_sd:.6f}")
    print(f"  admissible (n > 0 and |diff| <= {GRADER_SD}): {admissible}")
    if drift_n == 0:
        print("  NOT a pass: the control is empty, so nothing was tested")

    mean_before = statistics.mean(before[c] for c in both) if both else 0.0
    mean_after = statistics.mean(after[c] for c in both) if both else 0.0
    overall, overall_sd, overall_n = _paired(before, after, both)
    changed_mean, changed_sd, changed_n = _paired(before, after, changed_cases)
    report["overall"] = {
        "n": overall_n,
        "before": round(mean_before, 6),
        "after": round(mean_after, 6),
        "paired_difference": round(overall, 6),
        "paired_sd": round(overall_sd, 6),
    }
    report["changed_answers"] = {
        "n": changed_n,
        "before": round(statistics.mean(before[c] for c in changed_cases), 6)
        if changed_cases
        else None,
        "after": round(statistics.mean(after[c] for c in changed_cases), 6)
        if changed_cases
        else None,
        "paired_difference": round(changed_mean, 6),
        "paired_sd": round(changed_sd, 6),
    }

    print("\n== all paired answers ==")
    print(f"  n={overall_n}  {mean_before:.4f} -> {mean_after:.4f}  ({overall:+.4f})")
    print("\n== answers whose claims changed ==")
    if changed_cases:
        print(
            f"  n={changed_n}  "
            f"{statistics.mean(before[c] for c in changed_cases):.4f} -> "
            f"{statistics.mean(after[c] for c in changed_cases):.4f}  ({changed_mean:+.4f})"
        )

    print("\n== by tier ==")
    tiers: dict[str, dict] = {}
    for tier in sorted({bank[c]["d_tier"] for c in both if c in bank}):
        cases = [c for c in both if bank.get(c, {}).get("d_tier") == tier]
        moved = [c for c in cases if c in changed]
        diff, sd, n = _paired(before, after, cases)
        tiers[tier] = {
            "n": n,
            "changed": len(moved),
            "before": round(statistics.mean(before[c] for c in cases), 6),
            "after": round(statistics.mean(after[c] for c in cases), 6),
            "paired_difference": round(diff, 6),
            "paired_sd": round(sd, 6),
        }
        print(
            f"  {tier}: n={n:3d} changed={len(moved):3d}  "
            f"{tiers[tier]['before']:.4f} -> {tiers[tier]['after']:.4f}  ({diff:+.4f})"
        )
    report["by_tier"] = tiers

    before_flags, after_flags = _flags(ARMS[0]), _flags(ARMS[1])
    report["kill_gate"] = {
        "fabricated_mapping_before": sum(f["fabricated"] for f in before_flags.values()),
        "fabricated_mapping_after": sum(f["fabricated"] for f in after_flags.values()),
        "hallucination_flags_before": sum(f["halluc"] for f in before_flags.values()),
        "hallucination_flags_after": sum(f["halluc"] for f in after_flags.values()),
    }
    print("\n== kill gate ==")
    for key, value in report["kill_gate"].items():
        print(f"  {key}: {value}")

    (ROOT / "frozen-metrics.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"\nwrote {(ROOT / 'frozen-metrics.json').relative_to(REPO)}")
    return 0 if admissible else 1


if __name__ == "__main__":
    raise SystemExit(main())
