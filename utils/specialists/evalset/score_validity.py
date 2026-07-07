#!/usr/bin/env python3
"""Query Validity (VA) — the grammar / valid-accuracy metric.

VA is the share of drafted queries that clear the pre-execution gate: syntax
parse, schema/label match, read-only enforcement, and LIMIT/depth caps. It runs
the specialist's own builder and validator through the same draft→gate retry
loop as ``base.py`` but stops before any DB call, so VA is fully hermetic and
byte-reproducible — no Neo4j/Gremlin required.

Two rates per specialist, per difficulty tier, each with a Wilson CI:

* **first-pass VA** — the drafted query cleared the gate on attempt 1.
* **post-retry VA** — it cleared within ``max_retries`` (feedback-repaired).

Schema-boundary questions (an entity the card doesn't model, e.g. Asset on
Enterprise ATT&CK) draft no query at all; they are reported separately, never
folded into the VA denominator. Because the query builder is deterministic —
it never free-generates text — VA is expected near the ceiling, and that is the
point: the deterministic builder sidesteps the generation-hallucination failure
mode that sinks free-form text-to-query systems.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from utils.evaluation.stats import wilson_interval
from utils.planner.cards import SourceCardView
from utils.specialists.config import SpecialistConfig
from utils.specialists.contracts import SpecialistTask
from utils.specialists.evalset.compile_banks import (
    ATTACK_BANK_PATH,
    CAPEC_BANK_PATH,
    load_bank,
)
from utils.specialists.resolve import resolve

SOURCE_CARDS = {
    "attack": "data/source_cards/attack.json",
    "capec": "data/source_cards/capec.json",
}
BANK_PATHS = {"attack": ATTACK_BANK_PATH, "capec": CAPEC_BANK_PATH}


@dataclass
class GateOutcome:
    """The hermetic gate result for one drafted task (no execution)."""

    boundary: bool
    first_pass_ok: bool
    final_ok: bool
    attempts: int
    template: str
    query: str
    reasons: list[str] = field(default_factory=list)


def gate_task(specialist: Any, task: SpecialistTask) -> GateOutcome:
    """Resolve → draft → validate (with retry) but never execute.

    Mirrors ``QuerySpecialist._loop`` up to the gate so VA measures exactly what
    the production gate would accept, without touching a database.
    """
    resolved = resolve(task, specialist.card)
    if resolved.unknown_entities:
        # Schema-boundary refusal: no query is drafted, so there is nothing to
        # validate. Not a VA success or failure — a separate category.
        return GateOutcome(
            boundary=True, first_pass_ok=False, final_ok=False,
            attempts=0, template="boundary", query="",
            reasons=[f"unknown entities: {list(resolved.unknown_entities)}"],
        )

    limits = {
        "max_traversal_depth": task.max_depth(),
        "max_result_rows": task.max_rows(),
        "query_timeout_ms": task.timeout_ms(),
    }
    feedback: list[str] | None = None
    first_pass_ok = False
    template = ""
    query = ""
    last_reasons: list[str] = []
    attempts = 0
    for attempt in range(1, specialist.max_retries + 2):
        attempts = attempt
        draft = specialist.builder.build(resolved, feedback)
        result = specialist.validator.validate(draft, specialist.card, limits)
        if attempt == 1:
            first_pass_ok = result.ok
            template = draft.template
            query = result.query
        if result.ok:
            return GateOutcome(
                boundary=False, first_pass_ok=first_pass_ok, final_ok=True,
                attempts=attempt, template=draft.template, query=result.query,
            )
        feedback = result.reasons
        last_reasons = list(result.reasons)
    return GateOutcome(
        boundary=False, first_pass_ok=first_pass_ok, final_ok=False,
        attempts=attempts, template=template, query=query, reasons=last_reasons,
    )


def build_specialists(config: SpecialistConfig | None = None) -> dict[str, Any]:
    """Build the Cypher and Gremlin specialists from the real source cards.

    Raises FileNotFoundError if the cards are not built — callers (tests) skip.
    """
    from utils.config import load_env
    from utils.specialists.cypher.specialist import build_cypher_specialist
    from utils.specialists.gremlin.specialist import build_gremlin_specialist

    load_env()  # populate NEO4J_*/GREMLIN_* like the golden fixtures do
    cfg = config or SpecialistConfig.from_env()
    out: dict[str, Any] = {}
    for source, path in SOURCE_CARDS.items():
        with open(path, encoding="utf-8") as f:
            card = SourceCardView.from_card_dict(json.load(f))
        builder = build_cypher_specialist if source == "attack" else build_gremlin_specialist
        out[source] = builder(card, cfg)
    return out


def _rate(successes: int, n: int) -> dict[str, Any]:
    point, low, high = wilson_interval(successes, n)
    return {"k": successes, "n": n, "rate": round(point, 4),
            "ci_low": round(low, 4), "ci_high": round(high, 4)}


def score_source(specialist: Any, questions: list[dict]) -> dict[str, Any]:
    """VA for one specialist, overall and per tier."""
    buckets: dict[str, dict[str, int]] = {}

    def _bucket(name: str) -> dict[str, int]:
        return buckets.setdefault(name, {"first": 0, "final": 0, "n": 0, "boundary": 0})

    for q in questions:
        outcome = gate_task(specialist, SpecialistTask.from_dict(q["task"]))
        tier = str(q.get("tier", "?"))
        for name in ("__all__", tier):
            b = _bucket(name)
            if outcome.boundary:
                b["boundary"] += 1
                continue
            b["n"] += 1
            b["first"] += int(outcome.first_pass_ok)
            b["final"] += int(outcome.final_ok)

    def _report(b: dict[str, int]) -> dict[str, Any]:
        return {
            "first_pass_va": _rate(b["first"], b["n"]),
            "post_retry_va": _rate(b["final"], b["n"]),
            "boundary": b["boundary"],
        }

    all_b = buckets.pop("__all__", {"first": 0, "final": 0, "n": 0, "boundary": 0})
    return {
        "overall": _report(all_b),
        "by_tier": {tier: _report(b) for tier, b in sorted(buckets.items())},
    }


def score_validity(config: SpecialistConfig | None = None) -> dict[str, Any]:
    """Full VA report across both specialists."""
    specialists = build_specialists(config)
    out: dict[str, Any] = {}
    for source, specialist in specialists.items():
        questions = load_bank(BANK_PATHS[source])["questions"]
        out[source] = score_source(specialist, questions)
    return out


def main() -> int:  # pragma: no cover - thin CLI wrapper
    report = score_validity()
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
