#!/usr/bin/env python3
"""Per-tier table of harness arms on both banks, from the scored files only.

Reads ``scored_<arm>.json`` produced by ``scripts/variant_harness.py compare``
and writes ``tables/arms.md`` plus the ``arms`` key of ``data/metrics.json``.
Every number in RESULTS.md comes from here; nothing is typed in.

    uv run python .../data/arm_table.py --arm baseline --arm distinct [--arm anchor_first]
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
REPO = EXP.parents[3]
sys.path.insert(0, str(REPO))

BANKS = {
    "exposed": REPO / "docs/evaluation/variants-2026-09-15",
    "sealed": REPO / "docs/evaluation/variants-holdout-2026-09",
}
#: The exposed bank's baseline for this experiment is EXP-2026-09-021's shipped
#: arm (D-034 + D-035, `--rewrite model_noid_anchored`), recorded there as
#: scored_noid_anchored.json; every other arm here is a file named after it.
FILES = {("exposed", "baseline"): "scored_noid_anchored.json"}
METRICS = ("records_exact", "records_recall", "recall_no_dump", "abstained", "wrong_entity", "catalogue_dump")
TIERS = ("T1", "T2", "T3", "T4", "T5", "T6")


def tier_means(rows: list[dict]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for tier in TIERS:
        sub = [r for r in rows if r.get("tier") == tier and "records_exact" in r]
        if not sub:
            continue
        out[tier] = {"n": len(sub)}
        for m in METRICS:
            if m == "recall_no_dump":
                # the harness's `r|nodump`: recall over the rows that are not
                # catalogue dumps (a dump "contains" its gold and earns nothing)
                vals = [float(r.get("records_recall") or 0.0) for r in sub if not r.get("catalogue_dump")]
                out[tier][m] = round(sum(vals) / len(vals), 4) if vals else 0.0
                continue
            vals = [float(bool(r.get(m))) if isinstance(r.get(m), bool) else float(r.get(m) or 0.0) for r in sub]
            out[tier][m] = round(sum(vals) / len(sub), 4)
        rungs = collections.Counter((r.get("rewrite") or {}).get("rung") if isinstance(r.get("rewrite"), dict) else r.get("rung") for r in sub)
        out[tier]["rungs"] = dict(sorted((str(k), v) for k, v in rungs.items()))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--arm", action="append", required=True)
    args = ap.parse_args()

    arms: dict[str, dict[str, dict]] = {}
    lines = ["| bank | arm | tier | n | records_exact | records_recall | recall (no dump) | abstained | wrong_entity | catalogue_dump | skipped_unresolved_anchor |",
             "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for bank, bank_dir in BANKS.items():
        for arm in args.arm:
            path = bank_dir / FILES.get((bank, arm), f"scored_{arm}.json")
            if not path.exists():
                continue
            means = tier_means(json.loads(path.read_text()))
            arms.setdefault(bank, {})[arm] = means
            for tier, m in means.items():
                lines.append(
                    f"| {bank} | {arm} | {tier} | {m['n']} | {m['records_exact']:.4f} | {m['records_recall']:.4f} | "
                    f"{m['recall_no_dump']:.4f} | {m['abstained']:.4f} | {m['wrong_entity']:.4f} | {m['catalogue_dump']:.4f} | "
                    f"{m['rungs'].get('skipped_unresolved_anchor', 0)} |"
                )
    (EXP / "tables").mkdir(exist_ok=True)
    (EXP / "tables/arms.md").write_text("\n".join(lines) + "\n")
    metrics_path = EXP / "data/metrics.json"
    metrics = json.loads(metrics_path.read_text()) if metrics_path.exists() else {}
    metrics["arms"] = arms
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
