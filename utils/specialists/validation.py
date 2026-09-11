#!/usr/bin/env python3
"""Shared validator base — the pre-run gate scaffold (briefing §4).

The pre-run gate is the cheap static checkpoint that keeps a bad query off the
database (§3 step 4): syntax/structure, schema conformance, read-only safety,
and cap injection — all deterministic, no LLM. The orchestration lives here in
the shared column; only the language-specific parser and the traversal/depth
rules swap in (subclasses in ``cypher/`` and ``gremlin/``).
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class QueryDraft:
    """A drafted query before the gate has run."""

    query: str
    params: dict[str, Any] = field(default_factory=dict)
    template: str = ""
    expected_nonempty: bool = False
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationResult:
    """The gate verdict and, on success, the cap-injected query to execute."""

    ok: bool
    query: str
    params: dict[str, Any] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    injected: list[str] = field(default_factory=list)
    #: Observations that do NOT change the verdict. A warning exists so a gate
    #: rejection can say *why the card disagrees with the data* without the data
    #: ever becoming a permission — see `schema_warnings`.
    warnings: list[str] = field(default_factory=list)

    def reason_text(self) -> str:
        return "; ".join(self.reasons)


def word_present(query: str, word: str) -> bool:
    """Case-insensitive whole-token search; collapses internal whitespace.

    Works for single keywords (``CREATE``) and multi-word clauses
    (``DETACH DELETE``). Terms with non-word characters fall back to a literal,
    case-insensitive substring search.
    """
    term = word.strip()
    if not term:
        return False
    if re.fullmatch(r"[A-Za-z]+(?:\s+[A-Za-z]+)*", term):
        pattern = r"\b" + r"\s+".join(re.escape(part) for part in term.split()) + r"\b"
        return re.search(pattern, query, re.IGNORECASE) is not None
    return term.lower() in query.lower()


class BaseValidator(ABC):
    """Deterministic pre-run gate, parameterised by the source card.

    Subclasses supply the four language-specific pieces; ``validate`` runs them
    in the briefing's order and only injects caps once a query is otherwise
    clean, so nothing hits the DB until it passes.
    """

    #: "cypher" | "gremlin" — for trace labelling.
    kind: str = "base"

    def validate(
        self, draft: QueryDraft, card: Any, limits: dict[str, int]
    ) -> ValidationResult:
        query = (draft.query or "").strip()
        reasons: list[str] = []
        if not query:
            return ValidationResult(False, query, draft.params, ["empty query"], [])

        reasons.extend(self.structural_reasons(query))
        reasons.extend(self.violates_read_only(query, card))
        reasons.extend(self.schema_reasons(query, card))
        reasons.extend(self.binding_reasons(draft, card))
        reasons.extend(self.cap_reasons(query, card, limits))
        warnings = self.schema_warnings(query, card)

        if reasons:
            return ValidationResult(False, query, draft.params, reasons, [], warnings)

        capped_query, injected = self.inject_caps(query, limits, card)
        return ValidationResult(
            True, capped_query, draft.params, [], injected, warnings
        )

    # -- language-specific swap points -------------------------------------

    @abstractmethod
    def structural_reasons(self, query: str) -> list[str]:
        """Syntax/shape checks (single statement, expected start/return, …)."""

    @abstractmethod
    def violates_read_only(self, query: str, card: Any) -> list[str]:
        """Reject any write clause/step declared in the card's safety block."""

    @abstractmethod
    def schema_reasons(self, query: str, card: Any) -> list[str]:
        """Every label/edge (and direction) referenced must exist in the card."""

    def schema_warnings(self, query: str, card: Any) -> list[str]:
        """Observations about the schema that must NOT change the verdict.

        The card is the permission source and stays the permission source. This
        hook exists for the one case where that rule is expensive: when the card
        lags the data, the gate rejects a real edge and the rejection reads as
        though the edge does not exist. Q45 is exactly that — five CAPEC edges the
        snapshot carries were absent from the card's allowlist, so 34 development
        questions were refused before they ran, and nothing in the trace said the
        edge was real.

        A warning makes that visible without making the data a permission. The
        alternative — falling back to the registry when the card has no pattern —
        would move policy from a reviewed file to whatever happens to be loaded,
        and a gate whose permissions come from the thing it is guarding is not a
        gate. Default: no warnings.
        """
        return []

    @abstractmethod
    def inject_caps(
        self, query: str, limits: dict[str, int], card: Any
    ) -> tuple[str, list[str]]:
        """Inject/clamp the row/depth limit; return (query, injected-notes)."""

    # Optional hook (default: no extra cap rejections). Override to *reject* a
    # query whose hard caps cannot be satisfied by simple injection — e.g. a
    # traversal already deeper than ``max_traversal_depth`` (briefing §4). Unlike
    # ``inject_caps`` (which runs only on an otherwise-clean query), this runs in
    # the reason-collecting phase so an unfixable over-cap query is kept off the DB.
    def cap_reasons(
        self, query: str, card: Any, limits: dict[str, int]
    ) -> list[str]:
        return []

    # Language-agnostic, so it lives in the shared column rather than in a swap
    # point: a query that filters a property against values that property can
    # never hold matches nothing, and an empty result from an impossible query
    # is indistinguishable from an honest "there are none". Timid by design —
    # see ``utils/specialists/binding.py``; anything unlearned passes.
    def binding_reasons(self, draft: QueryDraft, card: Any) -> list[str]:
        from utils.specialists.binding import binding_reasons as _reasons

        dataset = getattr(card, "dataset", "") or ""
        return _reasons(draft, dataset)
