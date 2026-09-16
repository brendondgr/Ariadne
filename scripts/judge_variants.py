#!/usr/bin/env python3
"""Judge the answers a harness arm gave on a variant bank, with the recorded judge.

Plan `docs/plans/2026-09-15-open-question-correctness.md`, Step 10. The
variant harness scores answers by record identity — exact, recall, wrong
entity, dump — and none of those can grade a *widened* answer or a disclosed
resolution fairly. This bridges one arm's scored rows into the answer shape
`utils/evaluation/judge_answers.py` grades (question, gold expectations, the
claims and abstentions the composer wrote) and runs that judge, so the same
rubric that graded every recorded arm grades these.

    uv run python scripts/judge_variants.py --bank sealed --arm form_execute --tiers T3,T4,T5,T6
    uv run python scripts/judge_variants.py --bank sealed --arm form_execute --aggregate-only

Answer files and judgments land under
``docs/evaluation/experiments/variants-judged-2026-09-15/<bank>-<arm>/``; the
aggregate is printed and written beside them as ``summary.json``.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from utils.config import load_env  # noqa: E402

load_env()

from utils.evaluation.judge_answers import JudgeConfig, run  # noqa: E402

BANKS = {
    "exposed": (REPO / "docs/evaluation/variants-2026-09-15", REPO / "docs/evaluation/variants-2026-09-15/reference.json"),
    "sealed": (REPO / "docs/evaluation/variants-holdout-2026-09", REPO / "docs/evaluation/variants-holdout-2026-09/reference.json"),
}
OUT = REPO / "docs/evaluation/experiments/variants-judged-2026-09-15"


def write_answers(bank: str, arm: str, tiers: set[str]) -> Path:
    bank_dir, ref_path = BANKS[bank]
    gold = {r["case_id"]: r for r in json.loads(ref_path.read_text())}
    rows = json.loads((bank_dir / f"scored_{arm}.json").read_text())
    root = OUT / f"{bank}-{arm}"
    (root / arm / "answers").mkdir(parents=True, exist_ok=True)
    n = 0
    for i, r in enumerate(rows):
        if r.get("tier") not in tiers:
            continue
        g = gold.get(r["case_id"]) or {}
        case = f"{r['case_id']}__{r['tier']}__{i:03d}"
        doc = {
            "id": case, "tier": r["tier"], "case_id": r["case_id"],
            "question": r["question"],
            "gold": {"assertions": {"must_include_ids": sorted(g.get("entity_ids") or []),
                                    "note": "the ids the gold question's own answer carried; a T6 question is an invented anchor and expects nothing"}},
            "answer": {"headline": "", "claims": [{"text": c} for c in (r.get("claims") or [])],
                       "abstentions": [{"statement": a} for a in (r.get("abstentions") or [])],
                       "composer": "deterministic"},
            "evidence_volume": r.get("record_count"),
            "logic_flow": {"rewrite": r.get("rewrite"), "canonical_question": r.get("canonical_question")},
        }
        (root / arm / "answers" / f"{case}.json").write_text(json.dumps(doc, indent=1) + "\n")
        n += 1
    print(f"wrote {n} answer files under {root.relative_to(REPO)}/{arm}/answers")
    return root


def aggregate(root: Path, arm: str) -> dict:
    per: dict[str, list[dict]] = collections.defaultdict(list)
    for path in sorted((root / arm / "answers").glob("*.judgment*.json")):
        j = json.loads(path.read_text())
        tier = path.stem.split("__")[1]
        per[tier].append(j)
    out = {}
    for tier, js in sorted(per.items()):
        def mean(key):
            vals = [float(j.get(key)) for j in js if isinstance(j.get(key), (int, float))]
            return round(sum(vals) / len(vals), 4) if vals else None
        out[tier] = {
            "n": len(js),
            "faithfulness": mean("faithfulness"),
            "groundedness": mean("groundedness"),
            "completeness": mean("completeness"),
            "abstained": round(sum(bool(j.get("abstained")) for j in js) / len(js), 4),
            "fabricated_mapping": sum(bool(j.get("fabricated_mapping")) for j in js),
            "with_hallucinations": sum(bool(j.get("hallucinations")) for j in js),
        }
    (root / "summary.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bank", choices=tuple(BANKS), required=True)
    ap.add_argument("--arm", required=True)
    ap.add_argument("--tiers", default="T3,T4,T5,T6")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--aggregate-only", action="store_true")
    args = ap.parse_args()
    root = OUT / f"{args.bank}-{args.arm}"
    if not args.aggregate_only:
        root = write_answers(args.bank, args.arm, set(args.tiers.split(",")))
        run(root, args.arm, JudgeConfig(), workers=args.workers)
    aggregate(root, args.arm)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
