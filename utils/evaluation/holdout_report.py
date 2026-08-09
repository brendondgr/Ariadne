#!/usr/bin/env python3
"""Roll the blind-holdout judgments into `docs/evaluation/holdout-v1/results.json`.

Every number in the write-up is produced here, from the per-case judgment files,
and never transcribed from prose. That rule exists because several figures in
this repository were previously spliced from a superseded run and read as
current; recomputing is the only way to keep that from happening again.

Two things this module refuses to do:

* **Average the two federated strata.** "Correctness" means answer correctness in
  the answerable partition and abstention behaviour in the abstention-expected
  one. A system that scores well on the first and hallucinates mappings on the
  second has a much worse result than the blend would suggest.
* **Report a bare point estimate.** At n=30 the Wilson interval is wide, and
  quoting the point alone overclaims. `correctness` is a mean of continuous
  judge scores, so it carries a bootstrap CI; the CORRECT-verdict *rate* is a
  genuine binomial and carries the Wilson interval plan 02 §10 asks for.

Run with::

    uv run python -m utils.evaluation.holdout_report
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from utils.evaluation.stats import bootstrap_ci, wilson_interval

REPO_ROOT = Path(__file__).resolve().parents[2]
BANK_PATH = REPO_ROOT / "utils" / "specialists" / "tests" / "golden" / "holdout_questions.json"
DEFAULT_ROOT = REPO_ROOT / "docs" / "evaluation" / "experiments" / "holdout-v1"
RESULTS_PATH = REPO_ROOT / "docs" / "evaluation" / "holdout-v1" / "results.json"

#: arm letter -> (holdout run directory, development-set run directory)
ARMS: dict[str, tuple[str, str]] = {
    "A": ("deterministic", "untruncated-fixed/deterministic"),
    "F": ("gold_loop_llm", "untruncated-goldloop/gold_loop_llm"),
}

#: H-SW-01 asks what techniques a *sub-technique* implements — the §5 `software`
#: category is phrased for a Software anchor while the stratum's population is
#: techniques. The question was kept verbatim rather than edited, because editing
#: it would have converted a blind question into a co-authored one. Every figure
#: is therefore reported twice: over all 30, and excluding this one.
MALFORMED = "H-SW-01"


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def load_judgments(root: Path, arm_dir: str) -> list[dict[str, Any]]:
    answers = root / arm_dir / "answers"
    out = []
    for path in sorted(answers.glob("*.judgment.json")):
        out.append(json.loads(path.read_text()))
    return out


def _roll(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"n": 0}
    correctness = [float(r["correctness"]) for r in rows]
    point, low, high = bootstrap_ci(correctness, _mean)
    correct = sum(1 for r in rows if r["verdict"] == "CORRECT")
    w_point, w_low, w_high = wilson_interval(correct, len(rows))
    return {
        "n": len(rows),
        "correctness": {
            "mean": round(point, 4),
            "ci95_low": round(low, 4),
            "ci95_high": round(high, 4),
            "method": "percentile bootstrap, 2000 resamples, seed 1729",
        },
        "correct_rate": {
            "correct": correct,
            "point": round(w_point, 4),
            "wilson95_low": round(w_low, 4),
            "wilson95_high": round(w_high, 4),
        },
        "faithfulness": round(_mean([float(r["faithfulness"]) for r in rows]), 4),
        "groundedness": round(_mean([float(r["groundedness"]) for r in rows]), 4),
        "completeness": round(_mean([float(r["completeness"]) for r in rows]), 4),
        "verdicts": {
            "CORRECT": correct,
            "PARTIAL": sum(1 for r in rows if r["verdict"] == "PARTIAL"),
            "INCORRECT": sum(1 for r in rows if r["verdict"] == "INCORRECT"),
        },
        "hallucinations": sum(len(r.get("hallucinations") or []) for r in rows),
        "answers_with_hallucination": sum(1 for r in rows if r.get("hallucinations")),
    }


def _abstention_roll(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """The abstention stratum is scored on behaviour, not on answer content."""
    base = _roll(rows)
    if not rows:
        return base
    return {
        **base,
        "abstained": sum(1 for r in rows if r.get("abstained")),
        "abstention_carries_query": sum(1 for r in rows if r.get("abstention_carries_query")),
        "fabricated_mapping": sum(1 for r in rows if r.get("fabricated_mapping")),
    }


def build(root: Path = DEFAULT_ROOT) -> dict[str, Any]:
    bank = json.loads(BANK_PATH.read_text())
    meta_by_id = {e["id"]: e["holdout_meta"] for e in bank["questions"]}
    stratum_by_id = {
        e["id"]: ("federated" if "sub_questions" in e else e["task"]["source"])
        for e in bank["questions"]
    }

    report: dict[str, Any] = {
        "experiment": "EXP-2026-08-001",
        "bank": "utils/specialists/tests/golden/holdout_questions.json",
        "n_questions": len(bank["questions"]),
        "seed": bank["meta"]["seed"],
        "author_model": bank["meta"]["author_model"],
        "frozen_at": "freeze/holdout-v1 (974e85a494f020e218e8b73f193543c11ea0d292)",
        "judge": "one independent Sonnet 5 agent per case per arm",
        "malformed_question": {
            "id": MALFORMED,
            "reason": (
                "asks what techniques a SubTechnique implements — the §5 `software` "
                "category is phrased for a Software anchor while the stratum's "
                "population is techniques"
            ),
            "handling": "kept verbatim; every figure is also reported excluding it",
        },
        "arms": {},
    }

    for letter, (arm_dir, dev_dir) in ARMS.items():
        rows = load_judgments(root, arm_dir)
        if not rows:
            continue
        for row in rows:
            cid = row["case_id"]
            row["category"] = meta_by_id[cid]["category"]
            row["stratum"] = stratum_by_id[cid]
            row["partition"] = meta_by_id[cid].get("federated_partition")

        answerable = [r for r in rows if r["partition"] != "abstention-expected"]
        abstention = [r for r in rows if r["partition"] == "abstention-expected"]
        by_category: dict[str, Any] = {}
        for row in rows:
            by_category.setdefault(row["category"], []).append(row)
        by_stratum: dict[str, Any] = {}
        for row in rows:
            by_stratum.setdefault(row["stratum"], []).append(row)

        dev = [
            json.loads(p.read_text())
            for p in sorted(
                (REPO_ROOT / "docs" / "evaluation" / "experiments" / dev_dir / "answers").glob(
                    "*.judgment.json"
                )
            )
        ]

        report["arms"][letter] = {
            "arm_code": arm_dir,
            "holdout": {
                "all": _roll(rows),
                "excluding_malformed": _roll([r for r in rows if r["case_id"] != MALFORMED]),
                "answerable": _roll(answerable),
                "abstention_expected": _abstention_roll(abstention),
                "by_stratum": {k: _roll(v) for k, v in sorted(by_stratum.items())},
                "by_category": {k: _roll(v) for k, v in sorted(by_category.items())},
            },
            "development": {
                "source": f"docs/evaluation/experiments/{dev_dir}",
                **_roll(dev),
            },
            "cases": sorted(
                (
                    {
                        "id": r["case_id"],
                        "category": r["category"],
                        "stratum": r["stratum"],
                        "partition": r["partition"],
                        "verdict": r["verdict"],
                        "correctness": r["correctness"],
                        "completeness": r["completeness"],
                        "faithfulness": r["faithfulness"],
                        "groundedness": r["groundedness"],
                        "gold_expected": r["gold_expected"],
                        "gold_present": r["gold_present"],
                        "hallucinations": r.get("hallucinations") or [],
                        "rationale": r["rationale"],
                    }
                    for r in rows
                ),
                key=lambda c: c["id"],
            ),
        }

    for letter, arm in report["arms"].items():
        holdout = arm["holdout"]["all"]["correctness"]["mean"]
        dev = arm["development"]["correctness"]["mean"]
        arm["blind_minus_dev"] = round(holdout - dev, 4)

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--out", type=Path, default=RESULTS_PATH)
    args = parser.parse_args()

    report = build(args.root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {args.out}")
    for letter, arm in report["arms"].items():
        h = arm["holdout"]["all"]
        print(
            f"  Arm {letter} ({arm['arm_code']}): blind {h['correctness']['mean']} "
            f"[{h['correctness']['ci95_low']}, {h['correctness']['ci95_high']}] "
            f"vs dev {arm['development']['correctness']['mean']} "
            f"→ {arm['blind_minus_dev']:+}"
        )


if __name__ == "__main__":
    main()
