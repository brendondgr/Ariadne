#!/usr/bin/env python3
"""Tables and metrics for EXP-2026-09-029 from the judge bridge's summary and judgments only."""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
REPO = EXP.parents[3]
ROOT = REPO / "docs/evaluation/experiments/variants-judged-2026-09-15/sealed-form_execute"
ANSWERS = ROOT / "form_execute" / "answers"


def main() -> int:
    summary = json.loads((ROOT / "summary.json").read_text())
    lines = ["| tier | n judged | faithfulness | groundedness | completeness | abstained | fabricated mapping | with hallucinations |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for tier, m in sorted(summary.items()):
        f = lambda k: ("—" if m.get(k) is None else f"{m[k]:.4f}")  # noqa: E731
        lines.append(f"| {tier} | {m['n']} | {f('faithfulness')} | {f('groundedness')} | {f('completeness')} | {f('abstained')} | {m['fabricated_mapping']} | {m['with_hallucinations']} |")
    # the two readings the protocol named
    t6_answered = []
    fabricated = []
    errors = sorted(p.name for p in ANSWERS.glob("*.error.txt"))
    for path in sorted(ANSWERS.glob("*.judgment*.json")):
        j = json.loads(path.read_text())
        tier = path.stem.split("__")[1]
        if tier == "T6" and not j.get("abstained") and (j.get("faithfulness") or 0) >= 0.5:
            t6_answered.append(path.stem.split(".")[0])
        if j.get("fabricated_mapping"):
            fabricated.append(path.stem.split(".")[0])
    (EXP / "tables").mkdir(exist_ok=True)
    (EXP / "tables/judged.md").write_text("\n".join(lines) + "\n")
    metrics = {"summary": summary, "t6_answered_not_abstained": t6_answered, "fabricated_mapping_cases": fabricated,
               "judge_errors": errors, "n_answers": len([p for p in ANSWERS.glob("*.json") if ".judgment" not in p.name])}
    (EXP / "data/metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    print("\n".join(lines)); print("T6 answered (not abstained, faithful>=0.5):", t6_answered); print("fabricated:", fabricated); print("errors:", len(errors))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
