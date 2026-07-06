#!/usr/bin/env python3
"""Weave the specialists into the planner workflow.

The planner emits a machine-readable ``Plan`` (sub-questions routed to sources,
declared joins, unsupported parts). This module dispatches each sub-question to
the specialist that serves its source, runs it, and collects the normalised
evidence into a single bundle keyed for the (future) synthesis agent.

The handoff is **evidence, not prose** (briefing §3): the federation gathers
each specialist's validated query, normalised records, grounded summary, and
provenance, and builds a ``join_index`` over the shared join key — but it does
**not** perform the cross-source join or compose a final answer. That is the
synthesis agent's job, kept deliberately out of scope here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from utils.planner.cards import SourceCardView, load_source_cards
from utils.planner.join_keys import get_join_key
from utils.planner.schema import Plan, SubQuestion

from . import build_specialist
from .config import SpecialistConfig
from .contracts import EvaluatorTrace, SpecialistResult, SpecialistTask


@dataclass
class FederatedEvidence:
    """All specialist evidence for one planned request, ready for synthesis."""

    request: str
    results: list[SpecialistResult] = field(default_factory=list)
    unsupported: list[dict[str, Any]] = field(default_factory=list)
    skipped: list[dict[str, Any]] = field(default_factory=list)
    partial: bool = False
    # Dependent-sequencing audit trail: one entry per consumer sub-question
    # that was seeded from (or skipped because of) a producer's join values.
    sequencing: list[dict[str, Any]] = field(default_factory=list)

    def by_source(self) -> dict[str, list[SpecialistResult]]:
        out: dict[str, list[SpecialistResult]] = {}
        for result in self.results:
            out.setdefault(result.task.source, []).append(result)
        return out

    def join_index(self) -> dict[str, list[dict[str, str]]]:
        """Map each join-key value to the (source, record) entries that carry it.

        This is the synthesis spine: a join value present under two different
        sources is a candidate cross-source correlation. The federation only
        *indexes* it; the synthesis agent decides what to do with it.
        """
        index: dict[str, list[dict[str, str]]] = {}
        for result in self.results:
            for record in result.records:
                for value in record.join_values:
                    index.setdefault(value, []).append(
                        {
                            "source": result.task.source,
                            "primary_id": record.primary_id,
                            "name": record.name,
                        }
                    )
        return index

    def cross_source_join_values(self) -> list[str]:
        """Join values reported by more than one distinct source."""
        out: list[str] = []
        for value, entries in self.join_index().items():
            if len({e["source"] for e in entries}) > 1:
                out.append(value)
        return sorted(out)

    def ok(self) -> bool:
        return bool(self.results) and all(r.ok for r in self.results) and not self.partial

    def to_dict(self) -> dict[str, Any]:
        return {
            "request": self.request,
            "results": [r.to_dict() for r in self.results],
            "unsupported": list(self.unsupported),
            "skipped": list(self.skipped),
            "partial": self.partial,
            "sequencing": list(self.sequencing),
            "join_index": self.join_index(),
            "cross_source_join_values": self.cross_source_join_values(),
        }


# -- dependent sequencing (join-derived ordering) ---------------------------
#
# The proposal's flagship flow is dependent: "retrieve mitigations FOR THOSE
# IDS" — the ATT&CK task consumes the T-IDs the CAPEC task produces. Ordering
# is derived from the declared join's canonical key, never invented: the
# endpoint that reaches the key via a mapping edge (``via_edge``) *produces*
# join values; the endpoint whose records natively carry the key *consumes*
# them as seed ids. With exactly two endpoints the dependency is acyclic by
# construction. Independent sub-questions keep the existing order unchanged.


def dependency_map(plan: Plan) -> dict[str, str]:
    """Map consumer sub-question id -> producer sub-question id, per declared join."""
    by_source: dict[str, SubQuestion] = {sq.source: sq for sq in plan.sub_questions}
    deps: dict[str, str] = {}
    for join in plan.joins:
        key = get_join_key(join.key)
        if key is None:
            continue
        producer_ds = consumer_ds = None
        for endpoint in key.endpoints:
            if endpoint.via_edge:
                producer_ds = endpoint.dataset
            else:
                consumer_ds = endpoint.dataset
        producer = by_source.get(producer_ds or "")
        consumer = by_source.get(consumer_ds or "")
        if producer is not None and consumer is not None and producer.id != consumer.id:
            deps[consumer.id] = producer.id
    return deps


def execution_order(plan: Plan) -> list[SubQuestion]:
    """Plan order with each join's producer hoisted before its consumer."""
    deps = dependency_map(plan)
    ordered: list[SubQuestion] = []
    placed: set[str] = set()
    by_id = {sq.id: sq for sq in plan.sub_questions}

    def place(sq: SubQuestion) -> None:
        if sq.id in placed:
            return
        producer_id = deps.get(sq.id)
        if producer_id and producer_id in by_id:
            place(by_id[producer_id])
        ordered.append(sq)
        placed.add(sq.id)

    for sq in plan.sub_questions:
        place(sq)
    return ordered


def harvest_seed_ids(
    producer: SpecialistResult, *, cap: int
) -> tuple[tuple[str, ...], bool]:
    """The producer's join values as consumer seeds, deterministic and bounded.

    Returns ``(seed_ids, truncated)``. Truncation is honest — it is recorded in
    the sequencing audit trail, never silent — and keeps the consumer's query
    inside its own ``max_result_rows`` bound.
    """
    values = sorted({v for r in producer.records for v in r.join_values})
    if cap and len(values) > cap:
        return tuple(values[:cap]), True
    return tuple(values), False


def dependency_skip_result(
    task: SpecialistTask, *, producer_id: str, reason: str
) -> SpecialistResult:
    """An honest empty for a consumer whose producer yielded no join values.

    Mirrors the schema-boundary refusal shape: ok, zero records, NO query
    executed, the dependency named in the trace — so synthesis renders an
    abstention rather than the consumer running a broad unseeded query.
    """
    return SpecialistResult(
        task=task,
        query="",
        records=[],
        summary=(
            f"Skipped: this sub-question depends on {producer_id} for its seed "
            f"identifiers, but {reason}."
        ),
        traces=[
            EvaluatorTrace(
                "dependency",
                ok=True,
                reasons=[f"producer {producer_id}: {reason}"],
                detail={"producer": producer_id},
            )
        ],
        ok=True,
        partial=False,
        error=None,
    )


def bundle_evidence(
    plan: Plan,
    results: list[SpecialistResult],
    skipped: list[dict[str, Any]],
    sequencing: list[dict[str, Any]] | None = None,
) -> FederatedEvidence:
    """Bundle specialist results for one plan — the *only* place the federated
    ``partial`` flag is computed. The router, the CLI, and the API all bundle
    through here so their degradation semantics cannot drift.
    """
    partial = (
        bool(plan.partial)
        or bool(plan.unsupported)
        or bool(skipped)
        or any((not r.ok) or r.partial for r in results)
    )
    return FederatedEvidence(
        request=plan.request,
        results=results,
        unsupported=[u.to_dict() for u in plan.unsupported],
        skipped=skipped,
        partial=partial,
        sequencing=list(sequencing or []),
    )


def status_and_exit(
    *,
    cards_present: bool,
    mode: str = "query",
    plan: Plan | None = None,
    evidence: FederatedEvidence | None = None,
) -> tuple[str, int]:
    """One status/exit-code rule for every pipeline entry point.

    Exit 2 only when no source cards exist; else 1 when the plan (plan mode) or
    the evidence bundle (query mode) is partial, 0 when clean.
    """
    if not cards_present:
        return "no_sources", 2
    if mode == "plan":
        assert plan is not None
        return ("partial", 1) if plan.partial else ("answered", 0)
    assert evidence is not None
    return ("partial", 1) if evidence.partial else ("answered", 0)


class SpecialistRouter:
    """Routes a planner ``Plan`` through the source-specific specialists."""

    def __init__(
        self,
        config: SpecialistConfig | None = None,
        *,
        cards: dict[str, SourceCardView] | None = None,
        specialists: dict[str, Any] | None = None,
    ) -> None:
        self._config = config or SpecialistConfig.from_env()
        self._cards = cards if cards is not None else load_source_cards(self._config.data_dir)
        # Optional pre-built specialists (injectable for testing); else built lazily.
        self._specialists: dict[str, Any] = dict(specialists or {})

    @property
    def cards(self) -> dict[str, SourceCardView]:
        return self._cards

    def _specialist_for(self, source: str) -> Any | None:
        if source in self._specialists:
            return self._specialists[source]
        card = self._cards.get(source)
        if card is None:
            return None
        try:
            specialist = build_specialist(source, card, self._config)
        except ValueError:
            return None
        self._specialists[source] = specialist
        return specialist

    def run_plan(self, plan: Plan) -> FederatedEvidence:
        """Dispatch every sub-question to its specialist and bundle the evidence.

        Sub-questions bound by a declared join run in dependency order: the
        producer first, its T-prefixed join values injected as the consumer's
        ``seed_ids`` (bounded by the consumer's own row limit). Independent
        sub-questions run exactly as before.
        """
        results: list[SpecialistResult] = []
        skipped: list[dict[str, Any]] = []
        sequencing: list[dict[str, Any]] = []
        deps = dependency_map(plan)
        by_id: dict[str, SpecialistResult] = {}

        for sq in execution_order(plan):
            specialist = self._specialist_for(sq.source)
            if specialist is None:
                skipped.append(
                    {
                        "sub_question": sq.id,
                        "source": sq.source,
                        "reason": f"no specialist available for source {sq.source!r}",
                    }
                )
                continue

            seed_ids: tuple[str, ...] = ()
            producer_id = deps.get(sq.id)
            if producer_id:
                producer = by_id.get(producer_id)
                task = SpecialistTask.from_sub_question(sq)
                if producer is None or not producer.ok:
                    reason = (
                        "it was not run" if producer is None
                        else f"it failed ({producer.error or 'no valid evidence'})"
                    )
                    result = dependency_skip_result(task, producer_id=producer_id, reason=reason)
                    results.append(result)
                    by_id[sq.id] = result
                    sequencing.append(
                        {"consumer": sq.id, "producer": producer_id,
                         "seed_count": 0, "truncated": False, "skipped": reason}
                    )
                    continue
                seed_ids, truncated = harvest_seed_ids(producer, cap=sq.limits.max_result_rows)
                if not seed_ids:
                    reason = "it returned no join values"
                    result = dependency_skip_result(task, producer_id=producer_id, reason=reason)
                    results.append(result)
                    by_id[sq.id] = result
                    sequencing.append(
                        {"consumer": sq.id, "producer": producer_id,
                         "seed_count": 0, "truncated": False, "skipped": reason}
                    )
                    continue
                sequencing.append(
                    {"consumer": sq.id, "producer": producer_id,
                     "seed_count": len(seed_ids), "truncated": truncated, "skipped": None}
                )

            task = SpecialistTask.from_sub_question(sq, seed_ids=seed_ids)
            result = specialist.run(task)
            results.append(result)
            by_id[sq.id] = result

        return bundle_evidence(plan, results, skipped, sequencing)


def run_plan(
    plan: Plan,
    config: SpecialistConfig | None = None,
    *,
    cards: dict[str, SourceCardView] | None = None,
) -> FederatedEvidence:
    """Convenience wrapper: route ``plan`` through a fresh ``SpecialistRouter``."""
    return SpecialistRouter(config, cards=cards).run_plan(plan)
