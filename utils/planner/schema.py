#!/usr/bin/env python3
"""The machine-readable plan the planner emits.

The plan is the planner's only output: target sources, sub-questions (each with
the entities it touches and the traversal limits the downstream phase needs),
declared cross-source joins, explicitly unsupported parts, the source-selection
rationale, and any assumptions made. It is pure data — serialisable to/from
JSON — so the self-eval gate (deterministic code) can grade it and downstream
phases (out of scope here) can consume it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .intent import IntentClassification


@dataclass(frozen=True)
class Limits:
    """Per-sub-question safety bounds drawn from the source card (§3.5)."""

    max_traversal_depth: int = 0
    max_result_rows: int = 0
    query_timeout_ms: int = 0

    def is_present(self) -> bool:
        """All three bounds must be positive to count as 'present'."""
        return (
            self.max_traversal_depth > 0
            and self.max_result_rows > 0
            and self.query_timeout_ms > 0
        )

    def to_dict(self) -> dict[str, int]:
        return {
            "max_traversal_depth": self.max_traversal_depth,
            "max_result_rows": self.max_result_rows,
            "query_timeout_ms": self.query_timeout_ms,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "Limits":
        data = data or {}
        return cls(
            max_traversal_depth=int(data.get("max_traversal_depth", 0) or 0),
            max_result_rows=int(data.get("max_result_rows", 0) or 0),
            query_timeout_ms=int(data.get("query_timeout_ms", 0) or 0),
        )


@dataclass(frozen=True)
class SubQuestion:
    """One scoped task routed to exactly one live source.

    ``hop`` records which iterative-retrieval hop introduced the sub-question:
    ``0`` for the initial plan, ``1+`` for re-planned expansions. It is a pure
    tag (execution order derives only from declared joins), and — to keep the
    single-pass plan JSON byte-identical to the pre-loop baselines — it is
    omitted from ``to_dict`` when ``0``.
    """

    id: str
    source: str
    text: str
    entities: list[str]
    limits: Limits
    join_key: str | None = None
    rationale: str = ""
    hop: int = 0

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "source": self.source,
            "text": self.text,
            "entities": list(self.entities),
            "limits": self.limits.to_dict(),
            "join_key": self.join_key,
            "rationale": self.rationale,
        }
        if self.hop:
            out["hop"] = self.hop
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SubQuestion":
        return cls(
            id=str(data.get("id", "")),
            source=str(data.get("source", "")),
            text=str(data.get("text", "")),
            entities=[str(e) for e in data.get("entities", [])],
            limits=Limits.from_dict(data.get("limits")),
            join_key=data.get("join_key"),
            rationale=str(data.get("rationale", "")),
            hop=int(data.get("hop", 0) or 0),
        )


@dataclass(frozen=True)
class JoinDeclaration:
    """A declared cross-source join on a canonical key."""

    key: str
    sources: list[str]
    on: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"key": self.key, "sources": list(self.sources), "on": self.on}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JoinDeclaration":
        return cls(
            key=str(data.get("key", "")),
            sources=[str(s) for s in data.get("sources", [])],
            on=str(data.get("on", "")),
        )


@dataclass(frozen=True)
class UnsupportedPart:
    """A part of the request the planner cannot answer, named explicitly."""

    description: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"description": self.description, "reason": self.reason}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UnsupportedPart":
        return cls(
            description=str(data.get("description", "")),
            reason=str(data.get("reason", "")),
        )


@dataclass
class Plan:
    """The full machine-readable plan emitted by the planner."""

    request: str
    sub_questions: list[SubQuestion] = field(default_factory=list)
    joins: list[JoinDeclaration] = field(default_factory=list)
    unsupported: list[UnsupportedPart] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    rationale: str = ""
    partial: bool = False
    trace: list[dict[str, Any]] = field(default_factory=list)
    # The analyst intent the planner classified for this request (planner step
    # one). ``None`` until the classify node runs; omitted from ``to_dict`` when
    # absent so pre-intent plan JSON stays byte-identical to the baselines.
    intent: IntentClassification | None = None

    def target_sources(self) -> set[str]:
        return {sq.source for sq in self.sub_questions}

    def is_empty(self) -> bool:
        return not self.sub_questions and not self.unsupported

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "request": self.request,
            "sub_questions": [sq.to_dict() for sq in self.sub_questions],
            "joins": [j.to_dict() for j in self.joins],
            "unsupported": [u.to_dict() for u in self.unsupported],
            "assumptions": list(self.assumptions),
            "rationale": self.rationale,
            "partial": self.partial,
            "trace": list(self.trace),
        }
        if self.intent is not None:
            out["intent"] = self.intent.to_dict()
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Plan":
        return cls(
            request=str(data.get("request", "")),
            sub_questions=[SubQuestion.from_dict(d) for d in data.get("sub_questions", [])],
            joins=[JoinDeclaration.from_dict(d) for d in data.get("joins", [])],
            unsupported=[UnsupportedPart.from_dict(d) for d in data.get("unsupported", [])],
            assumptions=[str(a) for a in data.get("assumptions", [])],
            rationale=str(data.get("rationale", "")),
            partial=bool(data.get("partial", False)),
            trace=list(data.get("trace", [])),
            intent=IntentClassification.from_dict(data.get("intent")),
        )


# -- re-plan merge / de-duplication -----------------------------------------
#
# The iterative-retrieval loop re-plans by drafting an *expansion* and grafting
# only its genuinely-new sub-questions onto the plan run so far. De-duplication
# is keyed on the semantic identity of a sub-question — its source, the set of
# entities it touches, and its normalized text — never its ``id`` (ids are
# per-plan and re-assigned). This keeps the loop from re-asking an answered
# sub-question or ever shrinking below what it has already gathered.


def _normalize_text(text: str) -> str:
    """Case-fold and collapse whitespace so trivially-different text matches."""
    return " ".join(text.lower().split())


def subquestion_key(sq: SubQuestion) -> tuple[str, tuple[str, ...], str]:
    """The dedupe identity of a sub-question: (source, sorted entities, text)."""
    return (
        sq.source,
        tuple(sorted(e.lower() for e in sq.entities)),
        _normalize_text(sq.text),
    )


def merge_plans(base: Plan, addition: Plan, *, hop: int) -> Plan:
    """Return ``base`` with ``addition``'s *new* sub-questions/joins appended.

    Base sub-questions keep their ids untouched (the specialist loop's
    ``by_id`` accumulator and the running ``cursor`` key on them). Each
    appended sub-question is de-duplicated against everything already in the
    plan, given a fresh unique id continuing the ``q#`` sequence, and tagged
    with ``hop``. Joins are unioned by ``(key, frozenset(sources))``. The base
    ``request``/``unsupported``/``assumptions``/``rationale`` are preserved;
    ``partial`` stays set if either plan was partial.
    """
    merged = Plan(
        request=base.request,
        sub_questions=list(base.sub_questions),
        joins=list(base.joins),
        unsupported=list(base.unsupported),
        assumptions=list(base.assumptions),
        rationale=base.rationale,
        partial=base.partial,
        trace=list(base.trace),
        intent=base.intent,  # the classified intent survives re-plan grafting
    )

    seen_sq = {subquestion_key(sq) for sq in merged.sub_questions}
    used_ids = {sq.id for sq in merged.sub_questions}
    next_n = len(merged.sub_questions)

    def _fresh_id() -> str:
        nonlocal next_n
        while True:
            next_n += 1
            candidate = f"q{next_n}"
            if candidate not in used_ids:
                used_ids.add(candidate)
                return candidate

    appended = 0
    for sq in addition.sub_questions:
        key = subquestion_key(sq)
        if key in seen_sq:
            continue
        seen_sq.add(key)
        merged.sub_questions.append(
            SubQuestion(
                id=_fresh_id(),
                source=sq.source,
                text=sq.text,
                entities=list(sq.entities),
                limits=sq.limits,
                join_key=sq.join_key,
                rationale=sq.rationale,
                hop=hop,
            )
        )
        appended += 1

    seen_join = {(j.key, frozenset(j.sources)) for j in merged.joins}
    for join in addition.joins:
        sig = (join.key, frozenset(join.sources))
        if sig in seen_join:
            continue
        seen_join.add(sig)
        merged.joins.append(join)

    if appended and addition.partial:
        merged.partial = True
    return merged
