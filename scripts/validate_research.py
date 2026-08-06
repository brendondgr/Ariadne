#!/usr/bin/env python3
"""Validate the research record. See `make validate-research`.

Exits non-zero on the first failing condition so CI and the pre-commit hook can
gate on it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.research_record.paths import REPO_ROOT, experiment_dirs  # noqa: E402
from utils.research_record.validate import validate_all  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="*",
        help="experiment directories to check (default: all)",
    )
    parser.add_argument(
        "--skip-index",
        action="store_true",
        help="skip the INDEX.md staleness check (used by the hook that regenerates it)",
    )
    args = parser.parse_args()

    targets = [Path(p).resolve() for p in args.paths] if args.paths else None
    findings = validate_all(targets, check_index_freshness=not args.skip_index)
    count = len(targets) if targets is not None else len(experiment_dirs())

    if not findings:
        print(f"research record OK — {count} experiment(s) validated")
        return 0

    print(f"research record INVALID — {len(findings)} finding(s):\n", file=sys.stderr)
    for finding in findings:
        print(f"  {finding}", file=sys.stderr)
    print(
        f"\nSee docs/research/AGENT_INSTRUCTIONS.md §7.3. Repo root: {REPO_ROOT}",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
