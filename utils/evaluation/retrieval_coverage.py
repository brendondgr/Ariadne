#!/usr/bin/env python3
"""Score *retrieval* from the artifacts alone — no judge, no model in the loop.

``failure_terminus`` needs a judgment file per question because it localises a
*graded* failure. That makes it the wrong tool for measuring a retrieval change:
judging 120 questions costs a panel of independent agents, and the question
"did the gold answer reach the evidence" does not need one. It is a set
membership test against the committed artifact.

So this computes, per arm and per question:

``gold_required``      ids the gold assertions demand (single + federated)
``in_evidence``        how many of them the executed queries actually returned
``in_answer``          how many the analyst finally sees
``covered``            whether the evidence contained the whole gold set
``skipped_consumers``  dependent sub-questions that never ran for want of seeds

The headline is ``gold_in_evidence`` — mean per-question fraction of gold that
reached the evidence. It is deterministic, so two runs of the same code over the
same graph produce the same number, and it moves only when retrieval changes.

Deliberately **not** named ``answer_coverage``: that metric already exists in
``score_e2e.py`` and means something else — the fraction of gold the *answer*
enumerates, over entries with enumerable gold only. The two are not comparable
and must never be quoted against each other. ``gold_in_evidence_scorable``
applies the same "skip entries with no enumerable gold" rule as that metric, so
there is one number here that is at least measured over the same population.

Paired against a reference arm it also reports **regressions**: questions whose
gold-in-evidence count fell. A change that raises the mean while losing ground
somewhere is a trade, not a fix, and this is what makes that visible.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from utils.evaluation.failure_terminus import answer_ids, evidence_ids, gold_ids


def _skipped_consumers(artifact: dict) -> int:
    """Dependent sub-questions that never executed because a producer gave no seeds."""
    count = 0
    for result in (artifact.get("logic_flow") or {}).get("results") or []:
        for trace in result.get("traces") or []:
            if trace.get("step") != "dependency":
                continue
            reasons = " ".join(trace.get("reasons") or []).lower()
            if "no join values" in reasons or "not run" in reasons:
                count += 1
    return count


def _templates(artifact: dict) -> list[str]:
    out: list[str] = []
    for result in (artifact.get("logic_flow") or {}).get("results") or []:
        for trace in result.get("traces") or []:
            if trace.get("step") == "gate":
                template = (trace.get("detail") or {}).get("template")
                if template:
                    out.append(str(template))
    return out


def score_case(artifact: dict) -> dict[str, Any]:
    gold = gold_ids(artifact)
    evidence = evidence_ids(artifact)
    answer = answer_ids(artifact)
    records = sum(
        len(r.get("records") or [])
        for r in (artifact.get("logic_flow") or {}).get("results") or []
    )
    return {
        "id": artifact.get("id"),
        "category": artifact.get("category"),
        "gold_required": len(gold),
        "in_evidence": len(gold & evidence),
        "in_answer": len(gold & answer),
        "missing": sorted(gold - evidence),
        # A question with no id assertions (a negative or a bounded scan) is
        # vacuously covered; counting it as 0.0 would punish the arm for a
        # question shape that asserts nothing about ids.
        "coverage": 1.0 if not gold else len(gold & evidence) / len(gold),
        "covered": not (gold - evidence),
        "skipped_consumers": _skipped_consumers(artifact),
        "records": records,
        "templates": sorted(set(_templates(artifact))),
    }


def score_arm(root: Path, arm: str) -> dict[str, dict[str, Any]]:
    answers = root / arm / "answers"
    out: dict[str, dict[str, Any]] = {}
    for path in sorted(answers.glob("*.json")):
        if path.name.endswith(".judgment.json"):
            continue
        try:
            artifact = json.loads(path.read_text())
        except ValueError:
            continue
        row = score_case(artifact)
        out[row["id"] or path.stem] = row
    return out


def _mean_scorable(cases: dict[str, dict[str, Any]]) -> float:
    """Same population as ``score_e2e.score_answer_coverage``: enumerable gold only."""
    scorable = [c for c in cases.values() if c["gold_required"]]
    if not scorable:
        return 0.0
    return sum(c["coverage"] for c in scorable) / len(scorable)


def summarize(cases: dict[str, dict[str, Any]]) -> dict[str, Any]:
    n = len(cases) or 1
    return {
        "n": len(cases),
        "gold_in_evidence": sum(c["coverage"] for c in cases.values()) / n,
        "gold_in_evidence_scorable": _mean_scorable(cases),
        "fully_covered": sum(1 for c in cases.values() if c["covered"]),
        "gold_ids_missing": sum(len(c["missing"]) for c in cases.values()),
        "skipped_consumers": sum(c["skipped_consumers"] for c in cases.values()),
        "records": sum(c["records"] for c in cases.values()),
    }


def compare(
    treatment: dict[str, dict[str, Any]], reference: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Paired per-question comparison. Regressions are reported, never averaged away."""
    shared = sorted(set(treatment) & set(reference))
    gained, lost = [], []
    for cid in shared:
        delta = treatment[cid]["in_evidence"] - reference[cid]["in_evidence"]
        if delta > 0:
            gained.append({"id": cid, "delta": delta})
        elif delta < 0:
            lost.append(
                {
                    "id": cid,
                    "delta": delta,
                    "missing": treatment[cid]["missing"][:8],
                    "templates": treatment[cid]["templates"],
                }
            )
    return {
        "paired": len(shared),
        "improved": len(gained),
        "regressed": len(lost),
        "gold_ids_recovered": sum(g["delta"] for g in gained),
        "gold_ids_lost": -sum(x["delta"] for x in lost),
        "regressions": lost,
        "improvements": sorted(gained, key=lambda g: -g["delta"]),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--arm", default="generic")
    parser.add_argument("--reference-root", default=None)
    parser.add_argument("--reference-arm", default="generic")
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    cases = score_arm(Path(args.root), args.arm)
    report: dict[str, Any] = {"summary": summarize(cases), "cases": cases}
    print(json.dumps(report["summary"], indent=2))

    if args.reference_root:
        reference = score_arm(Path(args.reference_root), args.reference_arm)
        report["reference_summary"] = summarize(reference)
        report["comparison"] = compare(cases, reference)
        print("\n-- vs reference --")
        print(json.dumps(report["reference_summary"], indent=2))
        print(json.dumps(
            {k: v for k, v in report["comparison"].items()
             if k not in ("regressions", "improvements")},
            indent=2,
        ))
        if report["comparison"]["regressions"]:
            print("\nREGRESSIONS:")
            for row in report["comparison"]["regressions"]:
                print(f"  {row['id']}: {row['delta']} missing={row['missing']}")

    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
