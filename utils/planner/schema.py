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
    """One scoped task routed to exactly one live source."""

    id: str
    source: str
    text: str
    entities: list[str]
    limits: Limits
    join_key: str | None = None
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source,
            "text": self.text,
            "entities": list(self.entities),
            "limits": self.limits.to_dict(),
            "join_key": self.join_key,
            "rationale": self.rationale,
        }

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

    def target_sources(self) -> set[str]:
        return {sq.source for sq in self.sub_questions}

    def is_empty(self) -> bool:
        return not self.sub_questions and not self.unsupported

    def to_dict(self) -> dict[str, Any]:
        return {
            "request": self.request,
            "sub_questions": [sq.to_dict() for sq in self.sub_questions],
            "joins": [j.to_dict() for j in self.joins],
            "unsupported": [u.to_dict() for u in self.unsupported],
            "assumptions": list(self.assumptions),
            "rationale": self.rationale,
            "partial": self.partial,
            "trace": list(self.trace),
        }

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
        )
