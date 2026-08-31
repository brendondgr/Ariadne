#!/usr/bin/env python3
"""Fit the ranked-matcher's accept thresholds — on the tuning half only.

    uv run python scripts/threshold_sweep.py --out docs/evaluation/variants-2026-08-29

**Safety before coverage, and that ordering is the finding it encodes.** Arm 1
raised the score on the golden catalogue while making real questions worse, and
Arm 3 gained 3 answers for 11 wrong ones. So a configuration is ranked by, in
order: wrong-entity rate, catalogue-dump rate, negative-control abstention — and
only among configurations that beat the no-name-search baseline on all three is
`records_exact` allowed to decide.

**The frozen half is never touched here.** `--split tune` filters it out before
a single question runs, so the reporting half is unreachable rather than merely
unused. One configuration is chosen, and it is scored against the frozen half
exactly once, afterwards.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

SCORES = (4.0, 8.0, 12.0)
MARGINS = (1.25, 1.6, 2.2)


def run(out: str, score: float, margin: float, split: str, name: str) -> dict:
    env = {
        **os.environ,
        "ARIADNE_LEXICON": "1", "ARIADNE_EXACTNAME": "1", "ARIADNE_NAMESEARCH": "1",
        "ARIADNE_NS_MIN_SCORE": str(score), "ARIADNE_NS_MIN_MARGIN": str(margin),
    }
    subprocess.run(
        [sys.executable, "scripts/variant_harness.py", "compare", "--out", out,
         "--variants", "variants_with_control.json", "--name", name,
         "--workers", "8", "--split", split],
        cwd=REPO, env=env, capture_output=True, text=True, timeout=3600,
    )
    rows = json.loads((REPO / out / name).read_text())
    scored = [r for r in rows if "records_exact" in r and r.get("tier") != "T0"]
    n = len(scored) or 1
    t6 = [r for r in scored if r.get("tier") == "T6"]
    return {
        "min_score": score, "min_margin": margin, "n": n,
        "wrong_entity": round(sum(r["wrong_entity"] for r in scored) / n, 4),
        "catalogue_dump": round(sum(bool(r.get("catalogue_dump")) for r in scored) / n, 4),
        "t6_abstained": round(sum(r["abstained"] for r in t6) / len(t6), 4) if t6 else None,
        "records_exact": round(sum(r["records_exact"] for r in scored) / n, 4),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True)
    ap.add_argument("--split", default="tune", choices=("tune", "report"))
    args = ap.parse_args()

    results = [{"label": "baseline (no ranked matching)",
                **run(args.out, 1e9, 1e9, args.split, "sweep_baseline.json")}]
    for s in SCORES:
        for m in MARGINS:
            label = f"score>={s:g} margin>={m:g}"
            print(f"== {label}")
            results.append({"label": label,
                            **run(args.out, s, m, args.split,
                                  f"sweep_{s:g}_{m:g}.json".replace(".", "p"))})

    base = results[0]
    print(f"\n{'configuration':34s} {'WRONG':>7s} {'DUMP':>7s} {'T6abs':>7s} {'exact':>7s}  safe?")
    print("-" * 78)
    safe: list[dict] = []
    for r in results:
        ok = (r["wrong_entity"] <= base["wrong_entity"]
              and r["catalogue_dump"] <= base["catalogue_dump"]
              and (r["t6_abstained"] or 0) >= (base["t6_abstained"] or 0))
        if ok and r is not base:
            safe.append(r)
        t6 = f"{r['t6_abstained']:.4f}" if r["t6_abstained"] is not None else "—"
        print(f"{r['label']:34s} {r['wrong_entity']:>7.4f} {r['catalogue_dump']:>7.4f} "
              f"{t6:>7s} {r['records_exact']:>7.4f}  {'yes' if ok else 'NO'}")

    (REPO / args.out / "threshold_sweep.json").write_text(
        json.dumps({"split": args.split, "results": results}, indent=2) + "\n")

    if not safe:
        print("\n  NO configuration beats the no-ranked-matching baseline on all three "
              "safety metrics. Ranked matching stays OFF; that is the result.")
        return 0
    best = max(safe, key=lambda r: (r["records_exact"], -r["wrong_entity"]))
    print(f"\n  chosen on the TUNING half: {best['label']}")
    print("  Score it against the frozen half exactly once, then stop.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
