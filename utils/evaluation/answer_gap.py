#!/usr/bin/env python3
"""Classify the loss that survives *complete* retrieval.

``retrieval_coverage`` answers "did the gold reach the evidence". On the blind
holdout the answer is yes for 22 of 30 questions that still lost judged score —
45% of the arm's total deficit. No amount of better query construction touches
that, so it needs its own instrument.

This walks the cases where retrieval was **complete** and names why the answer
lost anyway. The ladder is ordered and the first rule that fires wins:

``wrongful_abstention``  the answer declined while gold ids were expected *and*
                         present in the evidence — the worst class, because the
                         system had the answer and refused it.
``unfaithful``           a claim the evidence does not support.
``ungrounded``           a claim carrying no citation.
``under_enumeration``    the evidence held the gold and the answer stated only
                         some of it. The dominant class, and the actionable one:
                         it is a composition bug, not a knowledge problem.
``property_gap``         the gold demands attribute *values* and the answer
                         names the node without them.
``judge_nuance``         scored below 1.0 with none of the above — presentation,
                         ordering, or judge disagreement.

Only ``judge_nuance`` is not a defect. Everything above it is fixable in the
composer, and the counts say which fix is worth most.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from utils.evaluation.failure_terminus import (
    _answer_states_value,
    _evidence_has_value,
    gold_property_values,
)
from utils.evaluation.retrieval_coverage import score_arm


def classify(artifact: dict, judgment: dict) -> str:
    """Name the reason an answer lost score despite complete retrieval.

    Classes are chosen by the **magnitude** of each observable deficit, not by a
    fixed precedence. A fixed ladder scatters one defect across several classes:
    H-PRE-01 states 1 of 4 gold ids *and* carries a 0.1 faithfulness deduction,
    and ranking "unfaithful" above "under_enumeration" would file it under a
    0.1 symptom rather than the 0.75 failure. Ranking by size files each case
    under the thing most worth fixing.

    ``wrongful_abstention`` keeps hard precedence because it is categorical
    rather than a magnitude — the system had the answer and declined to give it.
    """
    expected = int(judgment.get("gold_expected") or 0)
    present = int(judgment.get("gold_present") or 0)

    if judgment.get("abstained") and expected > 0:
        return "wrongful_abstention"

    deficits: list[tuple[float, str]] = []
    if expected:
        deficits.append((1.0 - present / expected, "under_enumeration"))
    faith = 1.0 - (judgment.get("faithfulness") if judgment.get("faithfulness") is not None else 1.0)
    if judgment.get("hallucinations"):
        faith = max(faith, 1.0 / max(expected, 1))
    deficits.append((faith, "unfaithful"))
    ground = 1.0 - (judgment.get("groundedness") if judgment.get("groundedness") is not None else 1.0)
    deficits.append((ground, "ungrounded"))

    props = gold_property_values(artifact)
    unstated = [
        (a, k, v)
        for a, k, v in props
        if _evidence_has_value(artifact, a, k, v) and not _answer_states_value(artifact, v)
    ]
    if props:
        deficits.append((len(unstated) / len(props), "property_gap"))

    # Ties break toward the earlier entry, which is the order above: enumeration,
    # then faithfulness, then grounding, then properties.
    best, reason = max(deficits, key=lambda d: d[0])
    return reason if best > 0 else "judge_nuance"


def analyse(
    artifact_root: Path, arm: str, judgment_root: Path, judgment_arm: str
) -> dict[str, Any]:
    """Classify every complete-retrieval case that scored below 1.0.

    ``artifact_root`` supplies retrieval; ``judgment_root`` supplies the grades.
    They are separate because an arm may be scored against another arm's
    judgments only when the artifacts are the same run — the caller is
    responsible for that, and the ``paired`` count in the result makes a
    mismatch visible.
    """
    coverage = score_arm(artifact_root, arm)
    answers = judgment_root / judgment_arm / "answers"

    rows: list[dict[str, Any]] = []
    for jpath in sorted(answers.glob("*.judgment.json")):
        cid = jpath.name[: -len(".judgment.json")]
        apath = answers / f"{cid}.json"
        if cid not in coverage or not apath.exists():
            continue
        judgment = json.loads(jpath.read_text())
        artifact = json.loads(apath.read_text())
        correctness = judgment.get("correctness")
        if correctness is None:
            continue
        rows.append(
            {
                "id": cid,
                "retrieval_complete": coverage[cid]["covered"],
                "correctness": correctness,
                "loss": 1.0 - correctness,
                "gold_expected": judgment.get("gold_expected"),
                "gold_present": judgment.get("gold_present"),
                "reason": classify(artifact, judgment)
                if coverage[cid]["covered"]
                else "retrieval_incomplete",
            }
        )

    n = len(rows) or 1
    complete = [r for r in rows if r["retrieval_complete"]]
    by_reason: dict[str, dict[str, Any]] = {}
    for reason, count in Counter(r["reason"] for r in complete).most_common():
        loss = sum(r["loss"] for r in complete if r["reason"] == reason)
        by_reason[reason] = {
            "questions": count,
            "loss_share_of_total": loss / n,
            "ids": [r["id"] for r in complete if r["reason"] == reason],
        }
    return {
        "n": len(rows),
        "retrieval_complete": len(complete),
        "total_loss": sum(r["loss"] for r in rows) / n,
        "loss_with_complete_retrieval": sum(r["loss"] for r in complete) / n,
        "by_reason": by_reason,
        "cases": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="artifacts to score retrieval on")
    parser.add_argument("--arm", default="generic")
    parser.add_argument("--judgment-root", required=True)
    parser.add_argument("--judgment-arm", required=True)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    report = analyse(
        Path(args.root), args.arm, Path(args.judgment_root), args.judgment_arm
    )
    print(json.dumps({k: v for k, v in report.items() if k != "cases"}, indent=2))
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
