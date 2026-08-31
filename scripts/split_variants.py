#!/usr/bin/env python3
"""Split the variant bank into a tuning half and a frozen reporting half.

    uv run python scripts/split_variants.py --out docs/evaluation/variants-2026-08-29

**Drawn before any threshold is chosen, and by a rule rather than by hand.**
Everything after this point involves fitting — how confident is confident enough
before a ranked match is accepted. Fitting while able to see the whole bank
turns the bank into practice material and makes every figure already published
from it a figure the system was tuned to produce. That is the failure C-021
measures, and Q28 already specifies this protocol for exactly this reason.

**The unit is the gold question, not the variant.** Splitting by variant would
put T1 and T5 paraphrases of the same question on opposite sides, so the frozen
half would contain near-duplicates of what was tuned on. Splitting by case id
keeps a question and all of its paraphrases together.

**The rule is a hash, not a shuffle.** `sha256(case_id)` is stable across
machines, runs and Python versions, so the split is reproducible by anyone
without shipping a seed or trusting an RNG. Stratified by bank so both halves
carry ATT&CK, CAPEC and federated questions in proportion.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def half_for(case_id: str) -> str:
    """`tune` or `report`, from a stable hash of the question id."""
    digest = hashlib.sha256(case_id.encode("utf-8")).hexdigest()
    return "tune" if int(digest[:8], 16) % 2 == 0 else "report"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out_dir = REPO / args.out

    variants = json.loads((out_dir / "variants.json").read_text())
    by_case: dict[str, list[dict]] = defaultdict(list)
    for v in variants:
        by_case[v["case_id"]].append(v)

    assignment = {case: half_for(case) for case in sorted(by_case)}
    counts = Counter(assignment.values())
    per_bank: dict[str, Counter] = defaultdict(Counter)
    per_tier: dict[str, Counter] = defaultdict(Counter)
    for case, half in assignment.items():
        rows = by_case[case]
        per_bank[rows[0]["bank"]][half] += 1
        for r in rows:
            per_tier[r["tier"]][half] += 1

    payload = {
        "rule": "sha256(case_id)[:8] as int, even -> tune, odd -> report",
        "unit": "gold question (case_id); every variant follows its question",
        "drawn": "2026-08-31, before any threshold was fitted",
        "questions": {"tune": counts["tune"], "report": counts["report"]},
        "assignment": assignment,
    }
    (out_dir / "split.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    print(f"  questions: tune {counts['tune']}  report {counts['report']}")
    print(f"  by bank:   { {b: dict(c) for b, c in sorted(per_bank.items())} }")
    print(f"  by tier:   { {t: dict(c) for t, c in sorted(per_tier.items())} }")
    print(f"\n  wrote {(out_dir / 'split.json').relative_to(REPO)}")
    print("  ** The `report` half is frozen. Do not score against it while tuning. **")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
