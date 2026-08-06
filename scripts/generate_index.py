#!/usr/bin/env python3
"""Regenerate docs/research/INDEX.md. See `make index`.

With --check, writes nothing and exits non-zero if the committed index is stale.
That is the form CI uses.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.research_record.index import render_index, write_index  # noqa: E402
from utils.research_record.paths import INDEX_PATH, REPO_ROOT  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if INDEX.md is stale instead of rewriting it",
    )
    args = parser.parse_args()
    rel = INDEX_PATH.relative_to(REPO_ROOT)

    if args.check:
        current = INDEX_PATH.read_text() if INDEX_PATH.is_file() else None
        if current == render_index():
            print(f"{rel} is current")
            return 0
        print(f"{rel} is STALE — run `make index` and commit the result", file=sys.stderr)
        return 1

    if write_index():
        print(f"{rel} regenerated")
    else:
        print(f"{rel} already current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
