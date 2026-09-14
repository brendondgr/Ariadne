#!/usr/bin/env python3
"""What does it cost to let the planner run? `generic_planned` vs `generic_composed`.

Every headline figure this programme has published replays an authored
decomposition. `generic` and `generic_composed` are both driven by gold-replay
runners that hand the pipeline its plan, so 0.92 is the ceiling for retrieval
and composition *given a correct plan*. This scores the same 284 development
questions with exactly one thing changed — where the plan comes from.

Paired per question, because the unit of analysis is the question and not the
arm: the two arms answer the same bank, so the difference is taken per case and
its spread is the spread of those differences.

The metric is deterministic gold coverage (`deterministic_scores.coverage`), not
a graded score. That is deliberate for this step: both arms are model-free and
byte-reproducible, so a difference here cannot be grading noise or run variance,
and it costs seconds rather than the nine hours a judged pass costs. The plan
gates judging on this number exceeding 0.02.

    uv run python scripts/planner_cost_score.py --root <run root> --out <file>
"""

from __future__ import annotations

import argparse
import collections
import glob
import json
import statistics
from pathlib import Path
from typing import Any

DEFAULT_CONTROL_ARM = "generic_composed"
DEFAULT_TREATMENT_ARM = "generic_planned"


def load_arm(root: Path, arm: str) -> dict[str, dict]:
    """Case id -> artifact, for one arm's answers directory.

    Only `*.json` that are not judgment sidecars: a sidecar sitting beside its
    input is re-consumed unless every suffixed variant is excluded, which is how
    `EXP-2026-09-016` double-counted a grading pass.
    """
    out: dict[str, dict] = {}
    for path in sorted(glob.glob(str(root / arm / "answers" / "*.json"))):
        if ".judgment" in Path(path).name:
            continue
        artifact = json.loads(Path(path).read_text())
        out[artifact["id"]] = artifact
    return out


def coverage(artifact: dict) -> float | None:
    """Gold coverage for one answer, or None when the entry carries no gold."""
    block = (artifact.get("deterministic_scores") or {}).get("coverage") or {}
    return block.get("coverage")


def records(artifact: dict) -> int:
    return int((artifact.get("evidence_volume") or {}).get("records") or 0)


def summarize(control: dict[str, dict], treatment: dict[str, dict],
              control_arm: str = DEFAULT_CONTROL_ARM,
              treatment_arm: str = DEFAULT_TREATMENT_ARM) -> dict[str, Any]:
    """The paired difference, overall and per tier, plus the retrieval failures."""
    ids = sorted(set(control) & set(treatment))
    diffs: list[float] = []
    per_tier: dict[str, list[float]] = collections.defaultdict(list)
    control_values: list[float] = []
    treatment_values: list[float] = []
    lost: list[str] = []      # control retrieved, treatment retrieved nothing
    gained: list[str] = []    # the reverse, which is not assumed to be empty
    both_empty = 0

    for case in ids:
        a, b = coverage(control[case]), coverage(treatment[case])
        if a is not None and b is not None:
            diffs.append(b - a)
            per_tier[case.split("-")[0]].append(b - a)
            control_values.append(a)
            treatment_values.append(b)
        rc, rt = records(control[case]), records(treatment[case])
        if rc > 0 and rt == 0:
            lost.append(case)
        elif rt > 0 and rc == 0:
            gained.append(case)
        elif rc == 0 and rt == 0:
            both_empty += 1

    n = len(diffs)
    mean = statistics.fmean(diffs) if n else 0.0
    sd = statistics.stdev(diffs) if n > 1 else 0.0
    se = sd / (n ** 0.5) if n else 0.0
    return {
        "n_paired": n,
        "metric": "deterministic gold coverage (deterministic_scores.coverage)",
        "control": {"arm": control_arm, "mean": round(statistics.fmean(control_values), 4) if n else None},
        "treatment": {"arm": treatment_arm, "mean": round(statistics.fmean(treatment_values), 4) if n else None},
        "paired_difference": {
            "mean": round(mean, 4),
            "sd": round(sd, 4),
            "standard_error": round(se, 4),
            # The same coarse rule the Step 6 metrics used, reported as coarse.
            "separable": bool(abs(mean) > 2 * se),
        },
        "per_tier": {
            tier: {"n": len(v), "mean_difference": round(statistics.fmean(v), 4)}
            for tier, v in sorted(per_tier.items())
        },
        "retrieval": {
            "treatment_empty_where_control_retrieved": len(lost),
            "control_empty_where_treatment_retrieved": len(gained),
            "both_empty": both_empty,
            "lost_case_ids": lost,
            "gained_case_ids": gained,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="run root holding both arms' answers/")
    parser.add_argument("--out", default=None)
    parser.add_argument("--control", default=DEFAULT_CONTROL_ARM,
                        help=f"control arm directory (default {DEFAULT_CONTROL_ARM})")
    parser.add_argument("--treatment", default=DEFAULT_TREATMENT_ARM,
                        help=f"treatment arm directory (default {DEFAULT_TREATMENT_ARM})")
    args = parser.parse_args()

    root = Path(args.root)
    control_arm, treatment_arm = args.control, args.treatment
    control = load_arm(root, control_arm)
    treatment = load_arm(root, treatment_arm)
    if not control or not treatment:
        raise SystemExit(f"missing an arm under {root}: "
                         f"{control_arm}={len(control)} {treatment_arm}={len(treatment)}")

    result = summarize(control, treatment, control_arm, treatment_arm)
    result["source_root"] = str(root)
    result["counts"] = {control_arm: len(control), treatment_arm: len(treatment)}

    text = json.dumps(result, indent=2) + "\n"
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text)
        print(f"written: {args.out}")
    diff = result["paired_difference"]
    print(f"{control_arm} {result['control']['mean']}  ->  "
          f"{treatment_arm} {result['treatment']['mean']}")
    print(f"paired difference {diff['mean']:+} (se {diff['standard_error']}), "
          f"separable={diff['separable']}, n={result['n_paired']}")
    print(f"treatment retrieved nothing where control retrieved: "
          f"{result['retrieval']['treatment_empty_where_control_retrieved']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
