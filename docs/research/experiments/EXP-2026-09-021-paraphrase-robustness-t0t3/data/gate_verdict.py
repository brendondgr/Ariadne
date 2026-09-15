#!/usr/bin/env python3
"""Score the identifier-gated rewrite arm against the pre-registered ship rule.

    uv run python docs/research/experiments/EXP-2026-09-021-.../data/gate_verdict.py

The rule was written in the plan before Step 4 ran and is quoted in
`PROTOCOL.md`. It is applied here clause by clause, from the metrics files, so
the verdict cannot drift from the numbers and cannot be softened after the fact.
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]

# Pre-registered in docs/plans/2026-09-15-paraphrase-robustness-t0-t3.md Step 4,
# before any arm in Steps 4-5 was run. Values are not editable after the fact.
T3_MIN_GAIN = 0.10
TIER_TOLERANCE = -0.02
MAX_WRONG_ENTITY = 0.0950
MAX_CATALOGUE_DUMP = 0.0915
IN_SCOPE = ("T1", "T2", "T3")


def _tiers(name: str) -> dict:
    return json.loads((HERE / name).read_text())["tiers"]


def _v(tiers: dict, tier: str, metric: str) -> float:
    cell = tiers[tier][metric]
    return float(cell["mean"] if isinstance(cell, dict) else cell)


def main() -> int:
    base, arm = _tiers("metrics_baseline.json"), _tiers("metrics_noid.json")
    clauses = []

    gain = _v(arm, "T3", "records_exact") - _v(base, "T3", "records_exact")
    clauses.append({
        "clause": "T3 records_exact >= baseline + 0.10",
        "value": round(gain, 4), "threshold": T3_MIN_GAIN, "passes": gain >= T3_MIN_GAIN,
    })
    for tier in ("T1", "T2"):
        d = _v(arm, tier, "records_exact") - _v(base, tier, "records_exact")
        clauses.append({
            "clause": f"{tier} records_exact not below baseline - 0.02",
            "value": round(d, 4), "threshold": TIER_TOLERANCE, "passes": d >= TIER_TOLERANCE,
        })
    for tier in IN_SCOPE:
        for metric, cap in (("wrong_entity", MAX_WRONG_ENTITY),
                            ("catalogue_dump", MAX_CATALOGUE_DUMP)):
            v = _v(arm, tier, metric)
            clauses.append({
                "clause": f"{tier} {metric} <= {cap}",
                "value": round(v, 4), "threshold": cap, "passes": v <= cap,
                "baseline": round(_v(base, tier, metric), 4),
            })

    # The operator's rule, adopted 2026-09-15 AFTER the pre-registered cap was
    # seen to fail (D-034). Reported ALONGSIDE the original verdict, never in
    # place of it: the pre-registered result stands as recorded.
    operator_clauses = []
    for c in clauses:
        if c["clause"].endswith(f"catalogue_dump <= {MAX_CATALOGUE_DUMP}"):
            tier = c["clause"].split()[0]
            passes = c["value"] <= c["baseline"]
            operator_clauses.append({
                "clause": f"{tier} catalogue_dump not worse than the shipped baseline",
                "value": c["value"], "threshold": c["baseline"], "passes": passes,
            })
        else:
            operator_clauses.append(c)

    payload = {
        "rule_source": "docs/plans/2026-09-15-paraphrase-robustness-t0-t3.md Step 4, "
                       "pre-registered before Step 4 ran",
        "arm": "model_noid (rewrite gated on: the question cites no identifier)",
        "clauses": clauses,
        "clauses_passed": sum(1 for c in clauses if c["passes"]),
        "clauses_total": len(clauses),
        "verdict": "PASS" if all(c["passes"] for c in clauses) else "FAIL",
        "operator_rule": {
            "source": "D-034, adopted 2026-09-15 after the pre-registered cap failed",
            "difference": "catalogue_dump is judged against the shipped baseline "
                          "rather than the 0.0915 whole-bank reference",
            "clauses": operator_clauses,
            "verdict": "PASS" if all(c["passes"] for c in operator_clauses) else "FAIL",
        },
    }
    (HERE / "metrics_gate_verdict.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )
    for c in clauses:
        mark = "PASS" if c["passes"] else "FAIL"
        extra = f"  (baseline {c['baseline']})" if "baseline" in c else ""
        print(f"  [{mark}] {c['clause']:<42} = {c['value']}{extra}")
    print(f"\n  PRE-REGISTERED VERDICT: {payload['verdict']} "
          f"({payload['clauses_passed']}/{payload['clauses_total']} clauses)")
    op = payload["operator_rule"]
    print(f"\n  Under D-034, only the dump clauses change:")
    original = {c["clause"] for c in clauses}
    for c in op["clauses"]:
        if c["clause"] in original:
            continue
        print(f"  [{'PASS' if c['passes'] else 'FAIL'}] {c['clause']} "
              f"= {c['value']} (baseline {c['threshold']})")
    print(f"  OPERATOR-RULE VERDICT (D-034): {op['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
