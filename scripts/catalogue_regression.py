#!/usr/bin/env python3
"""Score two harness captures against the golden banks' own gold answers.

    uv run python scripts/catalogue_regression.py \
        --before docs/evaluation/variants-2026-08-29/reference.json \
        --after  docs/evaluation/variants-2026-08-29/reference_arm4.json

**Every builder, normalizer or router change requires this.** A change that
moves a catalogue answer is a regression until it is shown to be an improvement,
and "shown" means scored against gold parsed from the raw source files — not
against the previous capture, which is only the system's own prior opinion.

Two captures are compared, but **neither is the reference for correctness**:
both are scored independently against `ex_gold.expected` and
`assertions.must_include_related`, which come from the pinned STIX and CAPEC
bundles rather than from any run. The comparison then reports how many answers
moved and in which direction. A question with no recorded gold is counted as
changed and reported separately, never silently credited.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from utils.config import load_env  # noqa: E402

load_env()

from utils.specialists.evalset.compile_banks import (  # noqa: E402
    ATTACK_BANK_PATH,
    CAPEC_BANK_PATH,
    FEDERATED_BANK_PATH,
    load_bank,
)
from utils.synthesis.grounding import normalize_id  # noqa: E402


def gold_by_case() -> dict[str, set[str]]:
    """Gold identifiers per question, from the banks' snapshot-computed fields."""
    out: dict[str, set[str]] = {}
    for path in (ATTACK_BANK_PATH, CAPEC_BANK_PATH, FEDERATED_BANK_PATH):
        entries = load_bank(Path(path))
        questions = entries["questions"] if isinstance(entries, dict) else entries
        for q in questions:
            ids: set[str] = set()
            for block in (q.get("ex_gold") or {}, q.get("assertions") or {}):
                for key in ("expected", "must_include_related", "must_include_ids"):
                    for value in (block.get(key) or []):
                        ids.add(normalize_id(str(value)))
            out[q.get("id", "")] = {i for i in ids if i}
    return out


def _recall(ids: list[str], gold: set[str]) -> float | None:
    return len(set(ids) & gold) / len(gold) if gold else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    gold = gold_by_case()
    before = {r["case_id"]: r for r in json.loads(Path(args.before).read_text())}
    after = {r["case_id"]: r for r in json.loads(Path(args.after).read_text())}

    changed = [k for k in before
               if before[k].get("entity_ids") != after.get(k, {}).get("entity_ids")]
    better = worse = same = ungraded = 0
    rows: list[tuple[str, float, float]] = []
    for k in sorted(changed):
        g = gold.get(k) or set()
        if not g:
            ungraded += 1
            continue
        a, b = _recall(before[k]["entity_ids"], g), _recall(after[k]["entity_ids"], g)
        rows.append((k, a, b))
        better += b > a
        worse += b < a
        same += b == a

    scorable = [k for k in before if gold.get(k)]
    ra = sum(_recall(before[k]["entity_ids"], gold[k]) for k in scorable) / len(scorable)
    rb = sum(_recall(after[k]["entity_ids"], gold[k]) for k in scorable) / len(scorable)

    if not args.quiet and rows:
        print(f"{'case':14s} {'before':>8s} {'after':>8s}  verdict")
        print("-" * 46)
        for k, a, b in rows:
            v = "BETTER" if b > a else ("WORSE" if b < a else "same")
            print(f"{k:14s} {a:>8.4f} {b:>8.4f}  {v}")

    print(f"\n  changed {len(changed)} of {len(before)}"
          f"  |  better {better}  worse {worse}  same {same}"
          f"  |  {ungraded} changed with no recorded gold")
    print(f"  gold recall over {len(scorable)} scorable questions: "
          f"{ra:.4f} -> {rb:.4f}  ({rb - ra:+.4f})")
    if worse:
        print(f"\n  ** {worse} question(s) got WORSE — this is a regression "
              f"until explained. **")
    return 1 if worse else 0


if __name__ == "__main__":
    raise SystemExit(main())
