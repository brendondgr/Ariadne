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
from utils.planner.schema import Plan

from . import build_specialist
from .config import SpecialistConfig
from .contracts import SpecialistResult, SpecialistTask


@dataclass
class FederatedEvidence:
    """All specialist evidence for one planned request, ready for synthesis."""

    request: str
    results: list[SpecialistResult] = field(default_factory=list)
    unsupported: list[dict[str, Any]] = field(default_factory=list)
    skipped: list[dict[str, Any]] = field(default_factory=list)
    partial: bool = False

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
            "join_index": self.join_index(),
            "cross_source_join_values": self.cross_source_join_values(),
        }


def bundle_evidence(
    plan: Plan,
    results: list[SpecialistResult],
    skipped: list[dict[str, Any]],
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
        """Dispatch every sub-question to its specialist and bundle the evidence."""
        results: list[SpecialistResult] = []
        skipped: list[dict[str, Any]] = []

        for sq in plan.sub_questions:
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
            task = SpecialistTask.from_sub_question(sq)
            results.append(specialist.run(task))

        return bundle_evidence(plan, results, skipped)


def run_plan(
    plan: Plan,
    config: SpecialistConfig | None = None,
    *,
    cards: dict[str, SourceCardView] | None = None,
) -> FederatedEvidence:
    """Convenience wrapper: route ``plan`` through a fresh ``SpecialistRouter``."""
    return SpecialistRouter(config, cards=cards).run_plan(plan)
