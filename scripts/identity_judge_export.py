#!/usr/bin/env python3
"""Export judging payloads so a cross-model judge can grade them.

    uv run python scripts/identity_judge_export.py --out docs/evaluation/identity-2026-08-21

Why export rather than judge in place: the local relay is the only judge the
pipeline knows how to call, and it is saturated. But this project already
established (C-009) that self-judged evaluation materially overstates quality
and that the primary evaluation must be cross-model — an independent Sonnet
panel scored the same pipeline 0.1054 below its own self-judgment. So a second,
independent judge is worth having on its own merits, not merely as a way around
a busy server.

**The prompt is the existing one, byte for byte.** ``build_messages`` from
``utils.evaluation.llm_judge.llm_judge`` composes it, and this module only
writes what that function returns. Only the *model* differs between the two
judgings, which is the single thing that makes them comparable — a
reimplemented rubric would confound the model change with a prompt change.

Answers are rebuilt by re-running the deterministic path, which carries no
language model and is byte-reproducible, so the export is exact.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from utils.config import load_env  # noqa: E402

load_env()

from scripts.identity_sweep import (  # noqa: E402
    ARMS,
    BASE_ENV,
    apply_env,
    clear_env,
    run_one,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True, help="a bank directory")
    parser.add_argument("--arms", default="generic,deterministic")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args(argv)

    from utils.evaluation.llm_judge.llm_judge import build_messages

    out = Path(args.out)
    bank = json.loads((out / "bank.json").read_text(encoding="utf-8"))
    questions = bank["questions"]
    order = list(questions)[: args.limit or None]

    export_dir = out / "judge_payloads"
    export_dir.mkdir(parents=True, exist_ok=True)

    manifest: list[dict[str, Any]] = []
    for arm in [a.strip() for a in args.arms.split(",") if a.strip()]:
        apply_env({**BASE_ENV, **ARMS[arm]})
        from utils.specialists.schema.build import get_registry

        get_registry.cache_clear()

        for index, qid in enumerate(order, 1):
            try:
                result = run_one(questions[qid]["question"])
            except Exception as exc:
                print(f"[{arm}] {qid}: rebuild failed — {type(exc).__name__}: {exc}")
                continue
            answer, evidence = result["_answer_obj"], result["_evidence_obj"]
            if answer is None or evidence is None:
                print(f"[{arm}] {qid}: nothing to judge")
                continue

            messages = build_messages(answer, evidence)
            report = answer.verification
            name = f"{arm}__{qid}.json"
            (export_dir / name).write_text(
                json.dumps(
                    {
                        "question_id": qid,
                        "arm": arm,
                        "kind": questions[qid]["kind"],
                        "system": messages[0]["content"],
                        "user": messages[1]["content"],
                        # Deterministic, verifier-derived, never the judge's to
                        # set — carried so the aggregate can reuse them exactly
                        # as the in-process judge does.
                        "unsupported_claim_rate": (
                            report.unsupported_claim_rate if report else 0.0
                        ),
                        "conflict_count": report.conflict_count if report else 0,
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            manifest.append({"file": name, "arm": arm, "question_id": qid,
                             "kind": questions[qid]["kind"]})
            print(f"[{arm}] exported {index}/{len(order)} {qid}")
        clear_env(ARMS[arm])

    (export_dir / "manifest.json").write_text(
        json.dumps({"count": len(manifest), "items": manifest}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"\nwrote {len(manifest)} payloads to {export_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
