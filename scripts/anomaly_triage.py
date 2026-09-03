#!/usr/bin/env python3
"""Classify the three anomalies A-5 left unexplained. No model involved.

A-5 reported three numbers nobody can act on:

* **property reads score below single-hop traversals**, which the difficulty
  hypothesis did not predict;
* **containment shapes score 0.03–0.04** although the reconciliation proves the
  rows are loaded, so it is a retrieval gap and not a data gap;
* **abstention succeeds 60.7%** — on 24 of 61 unanswerable questions the system
  returned something.

Each becomes a named cause here, read out of the answer artifacts. Nothing is
inferred that the artifacts do not say: where the evidence cannot distinguish
two causes, the case is counted as `undetermined` rather than assigned.

    uv run python scripts/anomaly_triage.py
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

BANK = Path("docs/evaluation/composition/bank/bank.json")
ROOT = Path("docs/evaluation/experiments/expansion-2026-09-01")

CONTAINMENT = {
    "Category -[HAS_MEMBER]-> AttackPattern",
    "View -[HAS_MEMBER]-> AttackPattern",
    "View -[HAS_MEMBER]-> Category",
    "Matrix -[tactic_refs]-> Tactic",
}


#: Trace steps that record a row count, in the order we trust them. ``execute``
#: is the raw count the driver returned; ``assess`` and ``normalize`` re-record
#: it downstream and agree with it.
_ROW_COUNT_STEPS = ("execute", "assess", "normalize")


def row_count(result: dict[str, Any]) -> int:
    """Rows this result's query actually returned.

    The specialists record ``row_count`` inside ``traces[].detail``
    (`utils/specialists/base.py`), never on the result object itself. Until
    2026-09-03 this module read ``result["row_count"]``, which exists in no
    artifact ever written -- so the sum was always 0, ``classify`` returned
    ``query_built_returned_no_rows`` for every case that built a query, and the
    three branches below it were unreachable. That produced EXP-2026-09-002's
    "63 of 63 / 68 of 68" figures, which are the classifier's only reachable
    output rather than a finding, and are contradicted by the same artifacts:
    455 of 572 results carry records.

    Falls back to the materialised ``records`` list when no trace recorded a
    count, so a result that was never executed still classifies honestly.
    """
    by_step: dict[str, Any] = {}
    for trace in result.get("traces") or []:
        if not isinstance(trace, dict):
            continue
        detail = trace.get("detail")
        if isinstance(detail, dict) and "row_count" in detail:
            by_step.setdefault(trace.get("step"), detail["row_count"])
    for step in _ROW_COUNT_STEPS:
        if step in by_step:
            return int(by_step[step] or 0)
    if by_step:
        return int(next(iter(by_step.values())) or 0)
    records = result.get("records")
    return len(records) if isinstance(records, list) else 0


def classify(answer: dict[str, Any], entry: dict[str, Any]) -> str:
    """Why this question did not get its answer.

    Four causes the artifacts can actually distinguish, and one honest bucket
    for when they cannot.
    """
    flow = answer.get("logic_flow") or {}
    results = flow.get("results") or []
    volume = answer.get("evidence_volume") or {}
    records = volume.get("records") or 0
    related = volume.get("related") or 0

    if not results:
        return "no_query_built"
    rows = sum(row_count(r) for r in results if isinstance(r, dict))
    if rows == 0:
        return "query_built_returned_no_rows"
    if records == 0 and related == 0:
        return "rows_returned_but_no_evidence_extracted"
    coverage = (answer.get("deterministic_scores") or {}).get("coverage") or {}
    if coverage.get("coverage", 0) == 0:
        return "evidence_extracted_but_wrong_entities"
    return "partial_recall"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bank", type=Path, default=BANK)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--arm", default="deterministic")
    parser.add_argument("--out", type=Path,
                        default=Path("docs/evaluation/composition/bank/anomalies.json"))
    args = parser.parse_args()

    bank = {q["id"]: q for q in json.loads(args.bank.read_text())["questions"]}
    answers: dict[str, dict[str, Any]] = {}
    for path in sorted((args.root / args.arm / "answers").glob("*.json")):
        if ".judgment" in path.name:
            continue
        payload = json.loads(path.read_text())
        answers[payload["id"]] = payload

    property_reads: Counter = Counter()
    property_by_anchor: dict[str, list[float]] = defaultdict(list)
    containment: Counter = Counter()
    abstention: Counter = Counter()
    abstention_cases: list[dict[str, Any]] = []

    for case_id, entry in bank.items():
        answer = answers.get(case_id)
        if answer is None:
            continue
        coverage = (answer.get("deterministic_scores") or {}).get("coverage") or {}
        recall = coverage.get("coverage")
        volume = answer.get("evidence_volume") or {}
        shapes = entry["spec"]["shapes"]
        tier = entry["d_tier"]

        if tier == "D1":
            property_by_anchor[entry["spec"].get("anchor_label", "?")].append(recall or 0.0)
            if recall is not None and recall < 1.0:
                property_reads[classify(answer, entry)] += 1

        if any(s in CONTAINMENT for s in shapes) and recall is not None and recall < 1.0:
            containment[classify(answer, entry)] += 1

        if tier == "D0":
            returned = bool(volume.get("records") or volume.get("related"))
            if not returned:
                abstention["correctly_returned_nothing"] += 1
            else:
                cause = "returned_the_anchor_only" if (volume.get("records") or 0) <= 1 \
                    and not volume.get("related") else "returned_unrelated_neighbours"
                abstention[cause] += 1
                abstention_cases.append(
                    {
                        "id": case_id,
                        "predicate": entry["spec"]["steps"][0]["predicate"]
                        if entry["spec"]["steps"] else None,
                        "anchor_label": entry["spec"].get("anchor_label"),
                        "records": volume.get("records"),
                        "related": volume.get("related"),
                        "cause": cause,
                    }
                )

    result = {
        "arm": args.arm,
        "property_reads": {
            "failure_causes": dict(property_reads.most_common()),
            "recall_by_anchor_label": {
                label: round(sum(v) / len(v), 4)
                for label, v in sorted(property_by_anchor.items())
            },
        },
        "containment": {"failure_causes": dict(containment.most_common())},
        "abstention": {
            "outcomes": dict(abstention.most_common()),
            "failures": abstention_cases,
        },
    }
    args.out.write_text(json.dumps(result, indent=1) + "\n")

    print(f"anomaly triage -> {args.out}")
    print(f"\n  property reads, recall by the kind of thing asked about:")
    for label, value in sorted(result["property_reads"]["recall_by_anchor_label"].items(),
                               key=lambda kv: kv[1]):
        print(f"    {value:.2f}  {label}")
    print(f"  property read failures by cause: {result['property_reads']['failure_causes']}")
    print(f"\n  containment failures by cause: {result['containment']['failure_causes']}")
    print(f"\n  abstention outcomes: {result['abstention']['outcomes']}")


if __name__ == "__main__":
    main()
