#!/usr/bin/env python3
"""Scaffold a new experiment folder. See `make new-experiment SLUG=<slug>`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.research_record.paths import REPO_ROOT  # noqa: E402
from utils.research_record.scaffold import ScaffoldError, scaffold  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slug", help="kebab-case slug, e.g. baseline-retrieval")
    args = parser.parse_args()

    try:
        target = scaffold(args.slug)
    except ScaffoldError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    rel = target.relative_to(REPO_ROOT)
    print(f"Created {rel}")
    print()
    print("Next:")
    print(f"  1. Fill {rel}/PROTOCOL.md  — BEFORE running anything.")
    print("  2. Run via the entrypoint recorded in manifest.yaml.")
    print(f"  3. Fill {rel}/RESULTS.md and regenerate figures.")
    print("  4. make validate-research && make index")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
