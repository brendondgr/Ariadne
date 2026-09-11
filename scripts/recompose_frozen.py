#!/usr/bin/env python3
"""Re-compose saved evidence with the repaired composer. One judge, two writers.

    uv run python scripts/recompose_frozen.py --out docs/evaluation/experiments/frozen-2026-09-11

`EXP-2026-09-018` Step 5. Every other step in that experiment changes what is
*retrieved*, so a judged difference could always be retrieval rather than
composition. This one holds the evidence fixed: it reads each saved
`EXP-2026-09-005` generic answer, rebuilds the `FederatedEvidence` from its own
`logic_flow.results` **verbatim**, and runs the current composer and verifier
over those identical records. The same rows, two composers.

Nothing is re-queried and no model is called here — the recomposition is
deterministic. The judging is a separate pass over the two answer sets.

**The drift control is the point of the design.** Answers whose claims did not
change are graded in both passes. Their paired difference must fall inside the
grader-repeatability SD of 0.0066 (`EXP-2026-09-012`), or the judge moved rather
than the system, and no comparison in the step is admissible.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from utils.config import load_env  # noqa: E402

load_env()

from utils.specialists.contracts import (  # noqa: E402
    EvaluatorTrace,
    EvidenceRecord,
    Provenance,
    SpecialistResult,
    SpecialistTask,
)
from utils.specialists.federation import FederatedEvidence  # noqa: E402
from utils.synthesis.composer import DeterministicComposer  # noqa: E402
from utils.synthesis.verifier import verify_answer  # noqa: E402

SOURCE = REPO / "docs/evaluation/experiments/post-repair-2026-09-03/generic/answers"


def _record(data: dict) -> EvidenceRecord:
    provenance = data.get("provenance") or None
    return EvidenceRecord(
        primary_id=data.get("primary_id", ""),
        id_scheme=data.get("id_scheme", ""),
        label=data.get("label", ""),
        name=data.get("name", ""),
        properties=dict(data.get("properties") or {}),
        related=list(data.get("related") or []),
        join_values=tuple(data.get("join_values") or ()),
        provenance=Provenance(**provenance) if provenance else None,
        facets=list(data.get("facets") or []),
    )


def _result(data: dict) -> SpecialistResult:
    """Rebuild one result from a saved answer's `logic_flow.results` entry.

    The saved shape is the *federated* one — `source`, `sub_question`, `records`
    — rather than a serialised `SpecialistResult`, so the task is reconstructed
    from the fields the answer actually carries. `entities` is read from the
    saved plan where it survives, because the composer's slot binding needs it.
    """
    task = SpecialistTask(
        sub_question_id=data.get("sub_question_id", "q1"),
        source=data.get("source", ""),
        text=data.get("sub_question", "") or data.get("text", ""),
        entities=tuple(data.get("entities") or ()),
        seed_ids=tuple(data.get("seed_ids") or ()),
        limits=dict(data.get("limits") or {}),
    )
    return SpecialistResult(
        task=task,
        query=data.get("query", ""),
        records=[_record(r) for r in (data.get("records") or [])],
        summary=data.get("summary", ""),
        traces=[
            EvaluatorTrace(
                step=t.get("step", ""),
                ok=bool(t.get("ok")),
                reasons=list(t.get("reasons") or []),
                detail=dict(t.get("detail") or {}),
            )
            for t in (data.get("traces") or [])
        ],
        ok=bool(data.get("ok")),
        partial=bool(data.get("partial")),
        error=data.get("error"),
    )


def evidence_from(answer: dict, task_entities: dict[str, tuple[str, ...]]) -> FederatedEvidence:
    flow = answer.get("logic_flow") or {}
    results = []
    for entry in flow.get("results") or []:
        entities = task_entities.get(entry.get("sub_question_id", "q1"), ())
        results.append(_result({**entry, "entities": entities}))
    return FederatedEvidence(
        request=answer.get("question", ""),
        results=results,
        unsupported=list(flow.get("unsupported") or []),
        skipped=list(flow.get("skipped") or []),
        partial=bool(flow.get("partial")),
    )


def _bank_entities(bank_path: Path) -> dict[str, dict[str, tuple[str, ...]]]:
    """`{case_id: {sub_question_id: entities}}` from the bank's own tasks."""
    out: dict[str, dict[str, tuple[str, ...]]] = {}
    for question in json.loads(bank_path.read_text())["questions"]:
        tasks = question.get("sub_questions") or (
            [question["task"]] if question.get("task") else []
        )
        out[question["id"]] = {
            str(t.get("id") or t.get("sub_question_id") or "q1"): tuple(
                t.get("entities") or ()
            )
            for t in tasks
        }
    return out


def requested_values_check(answer: dict, evidence: FederatedEvidence) -> tuple[int, int]:
    """(values present in the evidence, values also present in the claims).

    Deterministic, no judge. This is the construction property Step 4 claims and
    it is checked here on the frozen evidence, where retrieval cannot account for
    a difference.
    """
    from utils.planner.cards import load_source_cards
    from utils.planner.canonical import requested_slots
    from utils.specialists.schema import get_registry

    cards = load_source_cards()
    registry = get_registry()
    text = " ".join(c.get("text", "") for c in (answer["answer"].get("claims") or []))
    have = rendered = 0
    for result in evidence.results:
        card = cards.get(result.task.source)
        if card is None:
            continue
        slots = requested_slots(result.task.text, result.task.entities, card, registry)
        if not slots.property:
            continue
        for record in result.records:
            value = (record.properties or {}).get(slots.property)
            if value is None:
                continue
            items = value if isinstance(value, (list, tuple)) else [value]
            items = [str(i).strip() for i in items if str(i).strip()][:12]
            if not items:
                continue
            have += 1
            if all(i in text for i in items):
                rendered += 1
    return have, rendered


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    parser.add_argument("--bank", default="docs/evaluation/composition/bank/bank-dev.json")
    args = parser.parse_args()

    entities = _bank_entities(REPO / args.bank)
    out_dir = REPO / args.out / "generic_recomposed" / "answers"
    out_dir.mkdir(parents=True, exist_ok=True)

    composer = DeterministicComposer()
    changed = unchanged = 0
    have_total = rendered_before = rendered_after = 0
    for path in sorted(SOURCE.glob("*.json")):
        if ".judgment" in path.name:
            continue
        original = json.loads(path.read_text())
        evidence = evidence_from(original, entities.get(original["id"], {}))

        before_have, before_rendered = requested_values_check(original, evidence)
        have_total += before_have
        rendered_before += before_rendered

        answer = composer.compose(evidence)
        verify_answer(answer, evidence)
        rebuilt = dict(original)
        rebuilt["answer"] = answer.to_dict()
        rebuilt["recomposed_from"] = str(path.relative_to(REPO))

        _, after_rendered = requested_values_check(rebuilt, evidence)
        rendered_after += after_rendered

        before_claims = [c.get("text") for c in (original["answer"].get("claims") or [])]
        after_claims = [c.get("text") for c in (rebuilt["answer"].get("claims") or [])]
        rebuilt["claims_changed"] = before_claims != after_claims
        changed += rebuilt["claims_changed"]
        unchanged += not rebuilt["claims_changed"]

        (out_dir / path.name).write_text(json.dumps(rebuilt, indent=1) + "\n")

    summary = {
        "source": str(SOURCE.relative_to(REPO)),
        "out": str(out_dir.relative_to(REPO)),
        "answers": changed + unchanged,
        "claims_changed": changed,
        "claims_unchanged_drift_control": unchanged,
        "requested_values_in_evidence": have_total,
        "rendered_before": rendered_before,
        "rendered_after": rendered_after,
    }
    (REPO / args.out / "recompose-summary.json").write_text(
        json.dumps(summary, indent=2) + "\n"
    )
    for key, value in summary.items():
        print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
