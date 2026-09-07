#!/usr/bin/env python3
"""Recompute every judged mean on disk and diff it against the manifests.

**Why this exists.** On 2026-09-07 four recorded metrics in `EXP-2026-09-007`
were found to be wrong. They were not found by inspection or by review; they were
found by recomputing from the raw judgment sidecars. The cause was a manifest
filled from an intermediate summary file that declared its own incompleteness.
Nothing in the record would have caught that, because nothing recomputes.

This does. For every evaluation root that holds judgment sidecars it computes the
mean correctness per arm per grading pass, then asks whether each computed value
appears in some manifest and whether each manifest value is reproducible from
disk.

**It is an inventory, not a verdict.** A computed mean absent from every manifest
may be an intermediate nobody meant to publish. A manifest value absent from disk
may be a derived quantity, a difference, or a figure from a run whose artifacts
were never committed. Both are questions.

    uv run python scripts/recompute_audit.py
    uv run python scripts/recompute_audit.py --json out.json
"""

from __future__ import annotations

import argparse
import glob
import json
import statistics
from collections import defaultdict
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
EVAL = REPO / "docs/evaluation/experiments"
EXPERIMENTS = REPO / "docs/research/experiments"


def judged_means() -> dict[str, dict]:
    """mean correctness per (evaluation root, arm, judgment suffix)."""
    buckets: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    contaminated: list[str] = []
    for p in glob.glob(str(EVAL / "**" / "*.judgment*.json"), recursive=True):
        path = Path(p)
        name = path.name
        if ".judgment" not in name:
            continue
        suffix = name.split(".judgment", 1)[1].removesuffix(".json") or "(none)"
        # A suffix that itself contains ".judgment" means the judge consumed a
        # SIDECAR as if it were an answer -- e.g. ".run2.judgment.run3".
        #
        # These were ALREADY found and quarantined by an earlier session: they
        # sit under a directory named `_contaminated_run3`. This audit was
        # reading the quarantine bin, which is a defect in the audit and not a
        # new discovery. Counting them inflated one cell's spread to 0.0774
        # against a 0.0072 median across every other cell.
        if ".judgment" in suffix or "_contaminated" in str(path):
            contaminated.append(str(path.relative_to(REPO)))
            continue
        try:
            rel = path.relative_to(EVAL).parts
        except ValueError:
            continue
        root = rel[0]
        arm = next((a for a in rel if a in
                    ("deterministic", "generic", "llm_query", "merged",
                     "generic_composed", "gold_loop_llm", "llm")), "?")
        try:
            v = json.loads(path.read_text()).get("correctness")
        except Exception:
            continue
        if isinstance(v, (int, float)):
            buckets[(root, arm, suffix)].append(float(v))

    if contaminated:
        print(f"   {len(contaminated)} quarantined/doubly-judged sidecars "
              f"excluded (already handled by an earlier session):")
        for c in contaminated[:5]:
            print(f"     {c}")
        print()

    out = {}
    for (root, arm, suffix), vals in buckets.items():
        if len(vals) < 20:      # too few to be a reported figure
            continue
        out[f"{root}|{arm}|{suffix}"] = {
            "root": root, "arm": arm, "suffix": suffix,
            "n": len(vals), "mean": round(statistics.fmean(vals), 4),
        }
    return out


def manifest_index() -> dict[float, list[str]]:
    idx: dict[float, list[str]] = defaultdict(list)
    for mf in sorted(glob.glob(str(EXPERIMENTS / "EXP-*" / "manifest.yaml"))):
        exp = Path(mf).parent.name
        try:
            m = yaml.safe_load(open(mf)) or {}
        except Exception:
            continue
        for name, cell in ((m.get("metrics") or {}).get("values") or {}).items():
            if isinstance(cell, dict) and isinstance(cell.get("mean"), (int, float)):
                idx[round(float(cell["mean"]), 4)].append(f"{exp}:{name}")
    return idx


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    computed = judged_means()
    idx = manifest_index()

    matched, unmatched = [], []
    for key, row in sorted(computed.items()):
        hits = idx.get(row["mean"], [])
        (matched if hits else unmatched).append({**row, "manifest": hits[:3]})

    print(f"judged cells recomputed from disk : {len(computed)}")
    print(f"  appear in a manifest            : {len(matched)}")
    print(f"  appear in NO manifest           : {len(unmatched)}")
    print()
    print("-- computed on disk, recorded nowhere (inventory, not a verdict) --")
    print(f"{'root':38} {'arm':14} {'pass':10} {'n':>5} {'mean':>8}")
    for r in unmatched[:40]:
        print(f"{r['root'][:38]:38} {r['arm']:14} {r['suffix'][:10]:10} "
              f"{r['n']:>5} {r['mean']:>8}")

    if args.json:
        Path(args.json).write_text(json.dumps(
            {"matched": matched, "unmatched": unmatched}, indent=1) + "\n")
        print(f"\nwritten -> {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
