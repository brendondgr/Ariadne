#!/usr/bin/env python3
"""Regenerate docs/research/INDEX.md and docs/research/CURRENT.md. See `make index`.

With --check, writes nothing and exits non-zero if the committed index is stale.
That is the form CI uses.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.research_record.index import render_current, render_index, write_current, write_index  # noqa: E402
from utils.research_record.paths import CURRENT_PATH, INDEX_PATH, REPO_ROOT  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if INDEX.md is stale instead of rewriting it",
    )
    args = parser.parse_args()
    targets = ((INDEX_PATH, render_index, write_index), (CURRENT_PATH, render_current, write_current))

    if args.check:
        stale = False
        for path, render, _ in targets:
            rel = path.relative_to(REPO_ROOT)
            current = path.read_text() if path.is_file() else None
            if current == render():
                print(f"{rel} is current")
            else:
                print(f"{rel} is STALE — run `make index` and commit the result", file=sys.stderr)
                stale = True
        return 1 if stale else 0

    for path, _, write in targets:
        rel = path.relative_to(REPO_ROOT)
        print(f"{rel} regenerated" if write() else f"{rel} already current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
