#!/usr/bin/env python3
"""Run one model test over a list of registry models (Era 2, Step 2).

    uv run python scripts/matrix_run.py --models gemma4-31b,qwen38-27b,gemma4-31b-remote \\
        --test toolcall-roundtrip --questions 2

Each model's identity is probed by token id before its first call and after its
last; a model that fails is refused, and a model that changed mid-run has its
rows marked. Rows go to ``logs/era2/matrix/<run_id>-<test>.jsonl`` and a summary
table is printed. Exit status is non-zero if any model was refused, unreachable
or changed identity.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from utils.llm.matrix import TESTS, run_matrix, write  # noqa: E402
from utils.llm.registry import load  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", required=True, help="comma-separated registry names")
    ap.add_argument("--test", default="toolcall-roundtrip", choices=sorted(TESTS))
    ap.add_argument("--questions", type=int, default=None, help="first N questions only")
    ap.add_argument("--registry", default=None, help="registry YAML (default utils/llm/models.yaml)")
    ap.add_argument("--out", default=str(REPO / "logs" / "era2" / "matrix"))
    args = ap.parse_args(argv)

    reg = load(args.registry)
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    result = run_matrix(models, args.test, n_questions=args.questions, registry=reg)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{result.run_id}-{args.test}.jsonl"
    write(result, path)

    summary = result.summary()
    keys = list(dict.fromkeys(k for row in summary for k in row))
    print("  ".join(keys))
    for row in summary:
        print("  ".join(json.dumps(row.get(k)) for k in keys))
    print(f"\n{len(result.rows)} rows -> {path.relative_to(REPO) if path.is_relative_to(REPO) else path}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
