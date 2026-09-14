"""Compose data/metrics.json from the per-step files and the judgment sidecars.

Condition 12 wants the manifest's numbers readable by machine from one file.
This builds that file by READING the others, so no manifest value is ever typed
by hand -- the failure mode EXP-2026-09-016 A-8 was made of.

    uv run python docs/research/experiments/EXP-2026-09-018-correctness-repair/data/build_metrics.py
"""
from __future__ import annotations

import glob
import json
import math
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
EVAL = REPO / "docs/evaluation/experiments"
ARMS = ("deterministic", "generic_composed", "generic")


def _per_question(root: Path, arm: str) -> dict[str, float]:
    """Mean correctness per question over whichever positions graded it.

    Averaging the positions before differencing is what makes the paired
    control paired: a question that graded once must not count as a question
    that graded twice.
    """
    acc: dict[str, list[float]] = {}
    for suffix in (".rc1", ".rc2"):
        for path in glob.glob(f"{root}/{arm}/answers/*.judgment{suffix}.json"):
            record = json.loads(Path(path).read_text())
            if record.get("correctness") is None:
                continue
            acc.setdefault(record["case_id"], []).append(float(record["correctness"]))
    return {case: statistics.fmean(values) for case, values in acc.items()}


def _cell(values: list[float]) -> dict[str, float | int]:
    return {
        "mean": round(statistics.fmean(values), 6),
        "std": round(statistics.pstdev(values), 6),
        "n": len(values),
        "standard_error": round(statistics.pstdev(values) / math.sqrt(len(values)), 6),
    }


def main() -> int:
    out: dict[str, object] = {
        "note": "Built by build_metrics.py from the sidecars and the per-step files. "
                "Do not hand-edit; re-run the script.",
    }

    # -- Step 6, the paired control: both positions averaged, then differenced.
    paired = {}
    control = EVAL / "paired-control-2026-09-12"
    for arm in ARMS:
        ref = _per_question(control / "reference", arm)
        rep = _per_question(control / "repaired", arm)
        common = sorted(set(ref) & set(rep))
        diffs = [rep[c] - ref[c] for c in common]
        paired[arm] = {
            "reference": _cell([ref[c] for c in common]),
            "repaired": _cell([rep[c] for c in common]),
            "gain": _cell(diffs),
        }
    out["paired_control"] = paired

    # -- Step 7 and Step 8 are already computed; carry them rather than recompute.
    for name, filename in (("fresh_set", "fresh_set.json"),
                           ("holdout_regression", "holdout_regression.json"),
                           ("latency", "latency.json"),
                           ("t6_rates", "t6_rates.json")):
        out[name] = json.loads((HERE / filename).read_text())

    # -- The flat headline names the manifest points at.
    fresh = out["fresh_set"]["arms"]
    reg = out["holdout_regression"]["arms"]
    lat = out["latency"]["arm_comparators_1worker"]
    out["headline"] = {
        "fresh_deterministic": fresh["deterministic"]["correctness"],
        "fresh_generic_composed": fresh["generic_composed"]["correctness"],
        "fresh_generic": fresh["generic"]["correctness"],
        "fresh_generic_composed_minus_deterministic": round(
            fresh["generic_composed"]["correctness"] - fresh["deterministic"]["correctness"], 6),
        "fresh_generic_minus_generic_composed": round(
            fresh["generic"]["correctness"] - fresh["generic_composed"]["correctness"], 6),
        "paired_gain_deterministic": paired["deterministic"]["gain"]["mean"],
        "paired_gain_generic_composed": paired["generic_composed"]["gain"]["mean"],
        "paired_gain_generic": paired["generic"]["gain"]["mean"],
        "regression_deterministic": reg["deterministic"]["correctness"],
        "regression_generic_composed": reg["generic_composed"]["correctness"],
        "regression_generic": reg["generic"]["correctness"],
        "seconds_per_answer_deterministic": lat["deterministic"]["seconds_per_answer"],
        "seconds_per_answer_generic_composed": lat["generic_composed"]["seconds_per_answer"],
        "seconds_per_answer_generic": lat["generic"]["seconds_per_answer"],
        "t6_wrong_entity": out["t6_rates"]["shipped_tree"]["wrong_entity"],
        "t6_catalogue_dump": out["t6_rates"]["shipped_tree"]["catalogue_dump"],
    }

    (HERE / "metrics.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out["headline"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
