#!/usr/bin/env python3
"""Can the model write the query? Counted three ways, against a control.

The specialist seam is the one with a measured downside. On the 27B control the
model rewrote the query on 49 of 284 questions and at least one went backwards,
and `llm_query` scored 0.4039 on the holdout against `generic`'s 0.2507 higher.
So this does not ask whether the model *ran*; it asks what its queries retrieved
compared with the ones the shipped builders write.

Three counts and nothing else, per the plan:

* **Gate rejections naming `allowed_edge_patterns`** — a draft refused for
  proposing an edge the schema does not have.
* **Zero-record results** — the query ran and returned nothing.
* **Queries differing from the model-free arm's** — a model that changed nothing
  cannot have broken anything.

The denominator for the rejection rate is the number of **drafts submitted to
the gate**, one ``gate`` trace each, not the number of questions. A question
can carry several sub-questions and therefore several drafts, and dividing by
questions produced a "rejection rate" of 1.22 the first time this was run — a
rate above 1 being the arithmetic saying the denominator was wrong.

A draft that clears the gate has not succeeded. It can still fail at the
database, and on this evidence it usually does, so ``executed_but_errored`` is
counted separately and a draft only counts as working if it did neither.

Every count is reported beside the control's, never alone. A 100% zero-record
rate means something different when the control also retrieves nothing, and the
seam is only chargeable for the difference.

    uv run python scripts/specialist_seam_health.py --model <root/arm> --control <root/arm>
"""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
from typing import Any

#: Above this share of drafts refused, the plan declares the seam non-viable at
#: this model size and records that instead of widening to the full bank.
VIABLE_REJECTION_RATE = 0.25


def load(directory: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for path in sorted(directory.glob("*.json")):
        if ".judgment" in path.name or path.name == "manifest.json":
            continue
        artifact = json.loads(path.read_text())
        out[artifact["id"]] = artifact
    return out


def _traces(artifact: dict) -> list[dict]:
    return [
        trace
        for result in ((artifact.get("logic_flow") or {}).get("results") or [])
        for trace in (result.get("traces") or [])
    ]


def _reasons(artifact: dict) -> list[str]:
    return [str(r) for trace in _traces(artifact) for r in (trace.get("reasons") or [])]


def _queries(artifact: dict) -> list[str | None]:
    return [(t.get("detail") or {}).get("query") for t in _traces(artifact)]


def _records(artifact: dict) -> int:
    return int((artifact.get("evidence_volume") or {}).get("records") or 0)


def health(model: dict[str, dict], control: dict[str, dict]) -> dict[str, Any]:
    shared = sorted(set(model) & set(control))
    reasons: collections.Counter = collections.Counter()
    allowlist_rejections = 0
    empty_drafts = 0
    drafts = 0
    executed = 0
    executed_but_errored = 0
    zero_model: list[str] = []
    zero_control: list[str] = []
    differing_queries: list[str] = []
    retrieved_less: list[str] = []

    for case in shared:
        for trace in _traces(model[case]):
            step = trace.get("step")
            if step == "gate":
                drafts += 1
            elif step == "execute":
                executed += 1
                if trace.get("reasons"):
                    executed_but_errored += 1
        for reason in _reasons(model[case]):
            reasons[reason[:90]] += 1
            if "allowed_edge_patterns" in reason:
                allowlist_rejections += 1
            if reason.strip().lower() == "empty query":
                empty_drafts += 1
        if _records(model[case]) == 0:
            zero_model.append(case)
        if _records(control[case]) == 0:
            zero_control.append(case)
        if _queries(model[case]) != _queries(control[case]):
            differing_queries.append(case)
        if _records(model[case]) < _records(control[case]):
            retrieved_less.append(case)

    n = len(shared)
    rejected = allowlist_rejections + empty_drafts
    rejection_rate = round(rejected / drafts, 4) if drafts else 0.0
    working = drafts - rejected - executed_but_errored
    return {
        "cases": n,
        "drafts_submitted_to_the_gate": drafts,
        "queries_differing_from_control": len(differing_queries),
        "allowlist_rejections": allowlist_rejections,
        "empty_drafts": empty_drafts,
        "rejection_rate_over_drafts": rejection_rate,
        "executed": executed,
        "executed_but_errored": executed_but_errored,
        # A draft that cleared the gate and then failed at the database did not
        # work either. This is the number that matters.
        "drafts_that_worked": working,
        "viable_at_this_model_size": bool(n) and rejection_rate <= VIABLE_REJECTION_RATE,
        "zero_record_model": len(zero_model),
        "zero_record_control": len(zero_control),
        "retrieved_less_than_control": len(retrieved_less),
        "retrieved_less_case_ids": retrieved_less,
        "top_reasons": dict(reasons.most_common(10)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="the model-written arm's answers/")
    parser.add_argument("--control", required=True, help="the model-free arm's answers/")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    result = health(load(Path(args.model)), load(Path(args.control)))
    result["model_path"] = args.model
    result["control_path"] = args.control

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(result, indent=2) + "\n")
        print(f"written: {args.out}")
    print(f"cases                       {result['cases']}")
    print(f"drafts reaching the gate    {result['drafts_submitted_to_the_gate']}")
    print(f"queries differing           {result['queries_differing_from_control']}")
    print(f"empty drafts                {result['empty_drafts']}")
    print(f"allowlist rejections        {result['allowlist_rejections']}")
    print(f"rejection rate              {result['rejection_rate_over_drafts']} "
          f"(viable <= {VIABLE_REJECTION_RATE}: {result['viable_at_this_model_size']})")
    print(f"cleared gate, failed at db  {result['executed_but_errored']}/{result['executed']}")
    print(f"drafts that actually worked {result['drafts_that_worked']}"
          f"/{result['drafts_submitted_to_the_gate']}")
    print(f"zero-record  model {result['zero_record_model']}  control {result['zero_record_control']}")
    print(f"retrieved less than control {result['retrieved_less_than_control']}")
    return 0 if result["viable_at_this_model_size"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
