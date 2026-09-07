#!/usr/bin/env python3
"""Check that every number in the paper traces to an experiment manifest.

**This closes a record defect rather than adding a feature.** The repository has
claimed, in OUTLINE.md and in the draft's own appendix, that automated checks
enforce "every number cites an EXP- id, no orphan numbers". An independent
readiness audit on 2026-09-06 found that no such check exists: the structural
validator never opens the paper and never looks at a number. This is that check.

It is deliberately blunt. It extracts numeric literals from the LaTeX source and
asks whether each appears as a metric value in some ``manifest.yaml``. That
produces false alarms -- years, counts stated in prose, numbers quoted from other
people's papers -- so the output is a **review list, not a gate**. A number that
cannot be traced is a question to answer, not proof of an error.

    uv run python scripts/verify_paper_numbers.py
    uv run python scripts/verify_paper_numbers.py --json out.json
"""

from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
PAPER = REPO / "docs/research/paper/tmlr/ariadne-tmlr.tex"
EXPERIMENTS = REPO / "docs/research/experiments"

#: Numbers that are never experiment metrics. Keeping this list short and
#: explicit is better than a clever heuristic that silently excuses a real orphan.
IGNORE = {
    "2026", "2025", "2024", "2021", "2017", "1729", "0.05", "0.95", "2000",
    "9090", "4000", "84000", "16384", "67617", "84001", "32768", "512",
}

#: Prose regions where numbers are quoted from OTHER people's work and cannot
#: trace to our manifests. Matched as substrings of the surrounding line.
FOREIGN_CONTEXT = ("SPLIT-RAG", "Hit-point", "arXiv", "PhantomBench",
                   "Deceptive Grounding", "QUINT", "TeBaQA", "SEMANTiCS",
                   "WWW", "DOI", "TMLR", "OpenReview")

NUM = re.compile(r"(?<![\w.])(\d{1,3}(?:[,{]\d{3}\}?)+|\d+\.\d{2,4})(?![\w])")


def manifest_values() -> dict[str, set[str]]:
    """Every metric value in the record, mapped value -> {experiment ids}."""
    index: dict[str, set[str]] = {}
    for mf in sorted(glob.glob(str(EXPERIMENTS / "EXP-*" / "manifest.yaml"))):
        exp = Path(mf).parent.name
        try:
            m = yaml.safe_load(open(mf)) or {}
        except Exception:
            continue
        vals = ((m.get("metrics") or {}).get("values") or {})
        if not isinstance(vals, dict):
            continue
        for name, cell in vals.items():
            if not isinstance(cell, dict):
                continue
            for key in ("mean", "std", "n"):
                v = cell.get(key)
                if v is None:
                    continue
                for form in (f"{v}", f"{abs(v):.4f}", f"{abs(v):.3f}",
                             f"{abs(v):.2f}", f"{int(v)}" if float(v).is_integer() else ""):
                    if form:
                        index.setdefault(form.lstrip("0") or "0", set()).add(exp)
                        index.setdefault(form, set()).add(exp)
    return index


def normalise(tok: str) -> str:
    return tok.replace(",", "").replace("{", "").replace("}", "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    ap.add_argument("--paper", default=str(PAPER))
    args = ap.parse_args()

    paper = Path(args.paper)
    if not paper.exists():
        print(f"paper not found: {paper}")
        return 2

    index = manifest_values()
    traced, orphan, foreign = [], [], []

    for lineno, line in enumerate(paper.read_text().splitlines(), 1):
        if line.lstrip().startswith("%"):
            continue
        is_foreign = any(f in line for f in FOREIGN_CONTEXT)
        for tok in NUM.findall(line):
            raw = normalise(tok)
            if raw in IGNORE:
                continue
            hit = index.get(raw) or index.get(raw.lstrip("0"))
            if not hit and "." in raw:
                hit = index.get(f"{float(raw):.4f}")
            # A percentage in prose is the same measurement as a fraction in a
            # manifest. 22.71\% and 0.2271 are one number, and treating them as
            # two manufactures orphans that are only a formatting difference.
            if not hit and "%" in line:
                try:
                    hit = index.get(f"{float(raw) / 100:.4f}")
                except ValueError:
                    pass
            row = {"line": lineno, "value": raw,
                   "context": line.strip()[:110]}
            if hit:
                row["experiments"] = sorted(hit)[:3]
                traced.append(row)
            elif is_foreign:
                foreign.append(row)
            else:
                orphan.append(row)

    print(f"paper            : {paper.relative_to(REPO)}")
    print(f"manifest values  : {len(index)} distinct numeric forms")
    print(f"traced           : {len(traced)}")
    print(f"quoted from others: {len(foreign)}  (not expected to trace)")
    print(f"UNTRACED         : {len(orphan)}")
    if orphan:
        print("\n-- numbers with no manifest source (review, not a verdict) --")
        for r in orphan[:40]:
            print(f"  L{r['line']:<5} {r['value']:<12} {r['context']}")

    if args.json:
        Path(args.json).write_text(json.dumps(
            {"traced": traced, "untraced": orphan, "foreign": foreign}, indent=1) + "\n")
        print(f"\nwritten -> {args.json}")

    # Never a gate. An untraced number is a question, and the readiness audit
    # found that claiming enforcement we do not have is itself the defect.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
