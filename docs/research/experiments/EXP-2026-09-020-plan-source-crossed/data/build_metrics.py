"""Compose the 2x2 from the run artifacts. See RESULTS.md.

    uv run python docs/research/experiments/EXP-2026-09-020-plan-source-crossed/data/build_metrics.py
"""
from __future__ import annotations

import collections
import glob
import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
ROOT = REPO / "docs/evaluation/experiments/plan-source-2026-09-14"
CELLS = {
    "templates_authored": "deterministic",
    "primitives_authored": "generic_composed",
    "templates_planner": "deterministic_planned",
    "primitives_planner": "generic_planned",
}


def load(arm: str) -> dict[str, tuple[float, int, str]]:
    out = {}
    for path in glob.glob(f"{ROOT}/{arm}/answers/*.json"):
        if ".judgment" in path:
            continue
        d = json.loads(Path(path).read_text())
        cov = ((d.get("deterministic_scores") or {}).get("coverage") or {}).get("coverage")
        if cov is None:
            continue
        records = int((d.get("evidence_volume") or {}).get("records") or 0)
        out[d["id"]] = (float(cov), records, d.get("tier") or d["id"].split("-")[0])
    return out


def main() -> int:
    arms = {name: load(arm) for name, arm in CELLS.items()}
    ids = sorted(set.intersection(*[set(v) for v in arms.values()]))

    def paired(t: str, c: str) -> dict:
        diffs = [arms[t][i][0] - arms[c][i][0] for i in ids]
        mean = statistics.fmean(diffs)
        sd = statistics.stdev(diffs)
        se = sd / len(diffs) ** 0.5
        return {
            "treatment": CELLS[t], "control": CELLS[c],
            "difference": round(mean, 4), "sd": round(sd, 4),
            "standard_error": round(se, 4), "n": len(diffs),
            "separable": bool(abs(mean) > 2 * se),
            "control_retrieved_treatment_empty":
                sum(1 for i in ids if arms[c][i][1] > 0 and arms[t][i][1] == 0),
            "treatment_retrieved_control_empty":
                sum(1 for i in ids if arms[t][i][1] > 0 and arms[c][i][1] == 0),
        }

    tiers = collections.defaultdict(list)
    for i in ids:
        tiers[arms["templates_authored"][i][2]].append(i)

    engine_authored = paired("primitives_authored", "templates_authored")
    engine_planner = paired("primitives_planner", "templates_planner")

    out = {
        "note": "Built by build_metrics.py from the run artifacts. Do not hand-edit.",
        "metric": "deterministic gold coverage (deterministic_scores.coverage) — retrieval, not judged",
        "bank": "bank-dev.json, 284 questions",
        "n_paired": len(ids),
        "cells": {
            name: {
                "arm": arm,
                "mean": round(statistics.fmean([arms[name][i][0] for i in ids]), 4),
                "zero_record": sum(1 for i in ids if arms[name][i][1] == 0),
            }
            for name, arm in CELLS.items()
        },
        "engine_effect_primitives_minus_templates": {
            "at_authored_plan": engine_authored,
            "at_real_planner": engine_planner,
        },
        "plan_effect_planner_minus_authored": {
            "for_templates": paired("templates_planner", "templates_authored"),
            "for_primitives": paired("primitives_planner", "primitives_authored"),
        },
        "interaction": round(engine_planner["difference"] - engine_authored["difference"], 4),
        "engine_effect_at_real_planner_by_tier": {
            tier: {
                "n": len(group),
                "difference": round(statistics.fmean(
                    [arms["primitives_planner"][i][0] - arms["templates_planner"][i][0]
                     for i in group]), 4),
            }
            for tier, group in sorted(tiers.items())
        },
    }
    (HERE / "metrics.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out["cells"], indent=2))
    print("engine @ real planner:", out["engine_effect_primitives_minus_templates"]["at_real_planner"]["difference"],
          "separable:", out["engine_effect_primitives_minus_templates"]["at_real_planner"]["separable"])
    print("interaction:", out["interaction"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
