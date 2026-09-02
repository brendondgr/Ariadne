#!/usr/bin/env python3
"""Validate and merge questions written by the Author agents.

The Author is not trusted, and this is where that is enforced. Every returned
question runs the same four checks the API-driven renderer applies — it must
name its anchor, must not name any other identifier, must not name the answer,
and must not contain schema vocabulary — plus one the agent path needs and the
API path did not: an agent has a filesystem, so it *could* have read the gold
instead of writing from the brief.

Nothing here can prove it didn't. What it can do is make the ways that would
show up fail loudly, and report the ones it cannot rule out:

* naming the answer is a hard rejection, which is the direct tell;
* schema vocabulary is a hard rejection, which is the tell for having read the
  templates or the census;
* `schema_overlap` is reported per question, so a batch that suddenly tracks the
  label vocabulary is visible even when no single question trips a rule.

That is weaker than an API call with no tools, and the weakness belongs in the
dataset card rather than in a footnote.

Usage:
    uv run python scripts/ingest_authored.py --authored docs/evaluation/composition/authored
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from utils.specialists.evalset import render as rd
from scripts.render_questions import DEFAULT_SPECS, load_specs

BRIEFS = Path("docs/evaluation/composition/briefs")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--specs", type=Path, default=DEFAULT_SPECS)
    parser.add_argument("--briefs", type=Path, default=BRIEFS)
    parser.add_argument("--authored", type=Path,
                        default=Path("docs/evaluation/composition/authored"))
    parser.add_argument("--model", default="claude-opus-5")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    index = json.loads((args.briefs / "index.json").read_text())
    specs = {s.id: s for s in load_specs(args.specs)}

    answers: dict[str, str] = {}
    duplicates: list[str] = []
    for path in sorted(args.authored.glob("*.json")):
        payload = json.loads(path.read_text())
        for entry in payload.get("questions", []):
            key = entry.get("id")
            if key in answers:
                duplicates.append(key)
            if key:
                answers[key] = (entry.get("question") or "").strip()

    results: list[dict[str, Any]] = []
    for key, meta in index.items():
        spec = specs[meta["spec_id"]]
        question = answers.get(key)
        if question is None:
            results.append({**meta, "id": key, "question": None, "ok": False,
                            "reason": "not returned"})
            continue
        reason = rd.rejection_reason(question, spec)
        results.append({
            **meta,
            "id": key,
            "tier": spec.tier,
            "question": question,
            "ok": reason is None,
            "reason": reason,
            "schema_overlap": rd.schema_overlap(question, spec),
        })

    kept = [r for r in results if r["ok"]]
    overlaps = sorted(r["schema_overlap"] for r in kept)
    reasons = Counter(
        str(r["reason"]).split(":")[0] for r in results if not r["ok"]
    )
    by_tier: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in results:
        by_tier[row.get("tier", "?")].append(row)

    report = {
        "author_model": args.model,
        "author_path": "subagent",
        "briefs": len(index),
        "returned": len(answers),
        "duplicates": duplicates,
        "kept": len(kept),
        "keep_rate": round(len(kept) / len(index), 4) if index else 0.0,
        "rejection_reasons": dict(reasons.most_common()),
        "by_tier": {
            tier: round(sum(1 for r in rows if r["ok"]) / len(rows), 4)
            for tier, rows in sorted(by_tier.items())
        },
        "by_register": {
            reg: round(
                statistics.fmean([r["schema_overlap"] for r in kept if r["register"] == reg]), 4
            )
            for reg in sorted({r["register"] for r in kept})
        },
        "schema_overlap": {
            "mean": round(statistics.fmean(overlaps), 4) if overlaps else None,
            "median": round(statistics.median(overlaps), 4) if overlaps else None,
            "p90": overlaps[int(0.9 * (len(overlaps) - 1))] if overlaps else None,
            "max": overlaps[-1] if overlaps else None,
        },
    }

    out = args.out or args.authored / "ingested.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"report": report, "questions": results}, indent=1) + "\n")

    print(f"ingested -> {out}")
    print(f"  {report['returned']}/{report['briefs']} returned; "
          f"kept {report['kept']} ({report['keep_rate']:.1%})")
    if duplicates:
        print(f"  DUPLICATE ids returned: {duplicates}")
    print(f"  keep rate by tier: {report['by_tier']}")
    print(f"  rejections: {report['rejection_reasons'] or 'none'}")
    ov = report["schema_overlap"]
    print(f"  schema overlap: median {ov['median']}, p90 {ov['p90']}, max {ov['max']}")
    print(f"  by register: {report['by_register']}")
    for row in results:
        if not row["ok"] and row["reason"] != "not returned":
            print(f"    REJECTED {row['spec_id']} [{row['register']}]: {row['reason']}")


if __name__ == "__main__":
    main()
