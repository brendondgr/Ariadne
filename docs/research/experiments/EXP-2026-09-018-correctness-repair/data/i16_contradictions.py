#!/usr/bin/env python3
"""I-16's defining property, measured on every capture it is claimed for.

    uv run python .../data/i16_contradictions.py            # the committed cells
    uv run python .../data/i16_contradictions.py DIR [DIR…] # any answer directory

A contradiction is an absence claim the *same answer* refutes. It needs no
grader and no gold: the text denies a relation it elsewhere enumerates, so it is
false on its face. That is why this is the acceptance test for I-16 rather than
a move in the judged mean — the judged mean moved by well under the grader's own
between-session spread, and a contradiction count of zero is checkable.

The scanner itself lives in `scripts/mechanism_check.py` so the composer's
alias-folding and the check that reads it cannot drift apart; this file only
pins which captures the write-up's table quotes, and writes them to JSON.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO))

from scripts.mechanism_check import _answers, contradictions  # noqa: E402

#: The cells RESULTS quotes. The "before" column is generated in a worktree at
#: `c5cb2906` (the commit before the fix) against the same live graphs, so the
#: pair differs in exactly one thing: the composer.
BEFORE = "docs/evaluation/experiments/i16-baseline-c5cb2906"
AFTER = "docs/evaluation/experiments/i16-full-2026-09-12"
CELLS = {
    f"{when}/{bank}/{arm}": f"{root}/{bank}/{arm}/answers"
    for when, root in (("before", BEFORE), ("after", AFTER))
    for bank in ("dev", "holdout")
    for arm in ("generic_composed", "deterministic")
}


def scan(directory: Path) -> dict:
    answers = _answers(directory)
    found = [c for a in answers.values() for c in contradictions(a)]
    return {
        "answers": len(answers),
        "count": len(found),
        "by_shape": {
            shape: sum(1 for c in found if c["shape"] == shape)
            for shape in sorted({c["shape"] for c in found})
        },
        "claims": sorted({c["text"] for c in found}),
    }


def main(argv: list[str]) -> int:
    targets = (
        {d: d for d in argv} if argv else {k: str(REPO / v) for k, v in CELLS.items()}
    )
    report = {}
    for name, path in targets.items():
        directory = Path(path)
        if not directory.is_dir():
            print(f"{name:28s} MISSING {directory}")
            continue
        report[name] = scan(directory)
        row = report[name]
        print(
            f"{name:28s} n={row['answers']:4d}  contradictions={row['count']:2d}"
            f"  {row['by_shape'] or ''}"
        )
    if not argv:
        out = Path(__file__).with_suffix(".json")
        out.write_text(json.dumps(report, indent=2) + "\n")
        print(f"\nwrote {out.relative_to(REPO)}")
    if not argv:
        after = {k: v for k, v in report.items() if k.startswith("after/")}
        return 1 if any(r["count"] for r in after.values()) else 0
    return 1 if any(r["count"] for r in report.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
