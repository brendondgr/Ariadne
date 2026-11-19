#!/usr/bin/env python3
"""Input / output contracts shared by both query specialists.

These are pure, JSON-serialisable dataclasses — the boundary the planner writes
to (``SpecialistTask``) and the synthesis agent reads from (``SpecialistResult``
carrying ``EvidenceRecord``s with ``Provenance``). Locking these once, before
either engine is built, is what lets the two specialists "emit it identically"
so synthesis can join on the shared schema (briefing §5).

Nothing here is language-specific: a Cypher row and a Gremlin traversal result
both normalise into the *same* ``EvidenceRecord`` shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .signals import TaskSignals

# The three traversal/result bounds every task carries, drawn from the card.
_LIMIT_KEYS = ("max_traversal_depth", "max_result_rows", "query_timeout_ms")


@dataclass(frozen=True)
class SpecialistTask:
    """One filtered task routed to exactly one specialist (planner → specialist).

    This is a planner ``SubQuestion`` re-expressed for the specialist: the
    sub-question text, the graph entities it touches, the safety limits the
    planner already bounded, the optional cross-source join key, and any concrete
    identifiers (``seed_ids``) the resolver pulled out of the text.

    ``signals`` is everything the specialists may know about the wording
    (Era 2 Step 8, the text boundary). It is derived from ``text`` once, here,
    when the task is made, unless the caller supplies it; the builders and the
    resolver read only ``signals`` and never ``text``.
    """

    sub_question_id: str
    source: str
    text: str
    entities: tuple[str, ...] = ()
    limits: dict[str, int] = field(default_factory=dict)
    join_key: str | None = None
    seed_ids: tuple[str, ...] = ()
    rationale: str = ""
    signals: "TaskSignals | None" = None

    def __post_init__(self) -> None:
        if self.signals is None:
            from .signals import derive_signals

            object.__setattr__(self, "signals", derive_signals(self.text))

    # -- limit accessors (default to conservative non-zero values) ----------

    def max_rows(self) -> int:
        return int(self.limits.get("max_result_rows") or 1000)

    def max_depth(self) -> int:
        return int(self.limits.get("max_traversal_depth") or 3)

    def timeout_ms(self) -> int:
        return int(self.limits.get("query_timeout_ms") or 5000)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sub_question_id": self.sub_question_id,
            "source": self.source,
            "text": self.text,
            "entities": list(self.entities),
            "limits": {k: int(self.limits.get(k, 0)) for k in _LIMIT_KEYS},
            "join_key": self.join_key,
            "seed_ids": list(self.seed_ids),
            "rationale": self.rationale,
            "signals": self.signals.to_dict() if self.signals is not None else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SpecialistTask":
        return cls(
            sub_question_id=str(data.get("sub_question_id", "")),
            source=str(data.get("source", "")),
            text=str(data.get("text", "")),
            entities=tuple(str(e) for e in data.get("entities", [])),
            limits={k: int((data.get("limits") or {}).get(k, 0) or 0) for k in _LIMIT_KEYS},
            join_key=data.get("join_key"),
            seed_ids=tuple(str(s) for s in data.get("seed_ids", [])),
            rationale=str(data.get("rationale", "")),
            signals=_signals_from(data.get("signals")),
        )

    @classmethod
    def from_sub_question(cls, sq: Any, *, seed_ids: tuple[str, ...] = ()) -> "SpecialistTask":
        """Adapt a planner ``SubQuestion`` (duck-typed) into a specialist task.

        Accepts anything exposing ``id``, ``source``, ``text``, ``entities``,
        ``limits.to_dict()`` and ``join_key`` — i.e. ``utils.planner.schema.
        SubQuestion`` — without importing the planner package here.
        """
        limits = sq.limits.to_dict() if hasattr(sq.limits, "to_dict") else dict(sq.limits or {})
        signals = getattr(sq, "signals", None)
        # A typed step (EXP-2026-11-015) carries its own signals: the step and
        # the id families of its anchors, never anything read from words. Its
        # anchors seed the task unless a producer already seeded it.
        step = getattr(sq, "step", None)
        if step is not None:
            from .signals import TypedStep, step_signals

            typed = step if isinstance(step, TypedStep) else TypedStep.from_dict(step)
            signals = step_signals(typed)
            if not seed_ids:
                seed_ids = typed.anchor_ids
        return cls(
            sub_question_id=str(getattr(sq, "id", "")),
            source=str(getattr(sq, "source", "")),
            text=str(getattr(sq, "text", "")),
            entities=tuple(str(e) for e in getattr(sq, "entities", []) or []),
            limits={k: int(limits.get(k, 0) or 0) for k in _LIMIT_KEYS},
            join_key=getattr(sq, "join_key", None),
            seed_ids=tuple(seed_ids),
            rationale=str(getattr(sq, "rationale", "")),
            signals=signals,
        )


def _signals_from(data: Any) -> "TaskSignals | None":
    """A serialised ``signals`` block, or ``None`` (derived from the text) when absent."""
    if not isinstance(data, dict):
        return None
    from .signals import TaskSignals

    return TaskSignals.from_dict(data)


@dataclass(frozen=True)
class Provenance:
    """The audit trail behind a single evidence record (briefing §5.2)."""

    source: str          # human-readable dataset name, e.g. "MITRE ATT&CK Enterprise"
    dataset: str         # registry dataset key, e.g. "attack"
    backend: str         # "neo4j" | "gremlin"
    query: str           # the exact validated query that produced the record
    record_id: str       # the backend node/edge id
    timestamp: str       # ISO-8601 capture time

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "dataset": self.dataset,
            "backend": self.backend,
            "query": self.query,
            "record_id": self.record_id,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class EvidenceRecord:
    """One normalised record in the shared evidence schema.

    ``primary_id`` is the join-relevant identifier (an ATT&CK ``T``-number or a
    ``CAPEC-N``) when one exists; ``related`` carries adjacent records (e.g. the
    mitigations of a technique) as lightweight ``{id, name, ...}`` dicts so
    synthesis can align without re-querying.
    """

    primary_id: str
    id_scheme: str
    label: str
    name: str
    properties: dict[str, Any] = field(default_factory=dict)
    related: list[dict[str, Any]] = field(default_factory=list)
    join_values: tuple[str, ...] = ()
    provenance: Provenance | None = None
    # The bounded facet block from ``describe``: a count of adjacent nodes grouped
    # by ``(relationship, direction, neighbour label)``. Each entry is a
    # ``{"rel", "direction", "label", "count"}`` dict. Empty for template records
    # and for records that carry individual neighbours in ``related`` instead.
    facets: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "primary_id": self.primary_id,
            "id_scheme": self.id_scheme,
            "label": self.label,
            "name": self.name,
            "properties": dict(self.properties),
            "related": list(self.related),
            "join_values": list(self.join_values),
            "provenance": self.provenance.to_dict() if self.provenance else None,
            "facets": list(self.facets),
        }


@dataclass(frozen=True)
class EvaluatorTrace:
    """One checkpoint in the specialist loop, recorded for inspectability."""

    step: str                       # "intake" | "gate" | "execute" | "assess" | "normalize"
    ok: bool
    reasons: list[str] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "ok": self.ok,
            "reasons": list(self.reasons),
            "detail": dict(self.detail),
        }


@dataclass
class SpecialistResult:
    """What a specialist hands the synthesis agent (specialist → synthesis)."""

    task: SpecialistTask
    query: str = ""
    records: list[EvidenceRecord] = field(default_factory=list)
    summary: str = ""
    traces: list[EvaluatorTrace] = field(default_factory=list)
    ok: bool = False
    partial: bool = False
    error: str | None = None

    def join_values(self) -> list[str]:
        """Every distinct join-key value across the records (synthesis spine)."""
        seen: dict[str, None] = {}
        for rec in self.records:
            for value in rec.join_values:
                seen.setdefault(value, None)
        return list(seen)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task.to_dict(),
            "query": self.query,
            "records": [r.to_dict() for r in self.records],
            "record_count": len(self.records),
            "summary": self.summary,
            "traces": [t.to_dict() for t in self.traces],
            "ok": self.ok,
            "partial": self.partial,
            "error": self.error,
            "join_values": self.join_values(),
        }
