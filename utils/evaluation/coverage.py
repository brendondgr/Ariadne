#!/usr/bin/env python3
"""How much of an answer set a judging pass actually covered.

A judged mean is quoted with an ``n`` and almost never with the number it is
*out of*, so ``n = 29`` reads as a complete set of 29 rather than as 30 answers
with one that could not be graded. That gap is not cosmetic.

EXP-2026-08-021 measured it: 6 of 1,794 gradings failed, and **every failure was
in the top 5% of answers by size** — median answer 10.3 KB, every failure
≥ 79 KB. The at-risk group is four case ids spanning two question types, so a
pass that drops them is not thinning the sample evenly, it is **removing the
hardest questions from the denominator**. The mean goes up and nothing in the
reported figure says why.

The same shape has now been found three separate ways in this project: an
earlier grading pass whose ``llm_query`` mean read 0.24 high because it dropped
its three worst answers (EXP-2026-08-021 ISSUES I-2); a fallback to a stronger
composer that made an arm look better the more often it failed
(EXP-2026-08-019, r = +0.62 between failure rate and measured quality); and this.
**A failure mode that improves the number it contaminates is the recurring
defect of this harness**, and the cheap defence is to report the denominator.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

__all__ = ["judgment_coverage", "coverage_note"]


def judgment_coverage(root: Path, arm: str, suffix: str = "") -> dict[str, Any]:
    """Answers present, judgments written, and cases that failed to grade.

    ``suffix`` selects a pass (``""`` is the base pass, ``".qwen38r2"`` a
    repeat). A doubly-suffixed name is a judgment of a judgment and is excluded,
    the same guard ``answer_files`` applies.
    """
    answers = root / arm / "answers"
    if not answers.is_dir():
        return {"n_answers": 0, "n_judged": 0, "n_errored": 0, "coverage": None, "complete": False}

    n_answers = sum(1 for p in answers.glob("*.json") if ".judgment" not in p.name)
    judged = [p for p in answers.glob(f"*.judgment{suffix}.json") if p.name.count(".judgment") == 1]
    errored = [p for p in answers.glob(f"*.judgment{suffix}.error.txt") if p.name.count(".judgment") == 1]

    n_judged, n_errored = len(judged), len(errored)
    return {
        "n_answers": n_answers,
        "n_judged": n_judged,
        "n_errored": n_errored,
        "ungraded_cases": sorted(p.name.split(".judgment")[0] for p in errored),
        "coverage": round(n_judged / n_answers, 4) if n_answers else None,
        "complete": n_answers > 0 and n_judged == n_answers,
    }


def coverage_note(cov: dict[str, Any]) -> str:
    """One line to print beside a mean. Empty when the pass is complete.

    Silent on the happy path on purpose: a note that fires every time is a note
    nobody reads.
    """
    if cov.get("complete") or not cov.get("n_answers"):
        return ""
    missing = cov["n_answers"] - cov["n_judged"]
    cases = ", ".join(cov.get("ungraded_cases") or []) or "cause not recorded"
    return (
        f"⚠️ {cov['n_judged']}/{cov['n_answers']} graded — {missing} missing ({cases}). "
        "Ungraded cases are not missing at random; they skew large. Do not read this mean "
        "as covering the whole set."
    )
