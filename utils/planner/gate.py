#!/usr/bin/env python3
"""The deterministic self-evaluation gate.

This is the planner's core safety mechanism: the LLM proposes a plan, this gate
disposes. It is **fully deterministic** — set-membership checks against the live
source view and the source cards, never a model "does this look right?" prompt
(briefing §4.2). It checks structural validity, not stylistic preference, so
ambiguous-but-valid plans pass (briefing §4.3); and it asserts non-degeneracy so
a plan that silently drops the request cannot ship as success (briefing §5.3).

Any failure returns specific reasons, which the loop feeds back into the next
draft (briefing §5.2). The model never grades its own homework.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .cards import SourceCardView
from .discovery import LiveSourceView
from .join_keys import resolve_join_key
from .schema import Plan, SubQuestion


@dataclass(frozen=True)
class GateResult:
    """The verdict and, on failure, the specific reasons to revise."""

    ok: bool
    reasons: list[str] = field(default_factory=list)

    def reason_text(self) -> str:
        return "; ".join(self.reasons)


def _check_sub_question(
    sq: SubQuestion,
    cards: dict[str, SourceCardView],
    live_view: LiveSourceView,
) -> list[str]:
    reasons: list[str] = []
    label = f"sub-question {sq.id or '?'}"

    # (a) named source must be a known, live source.
    card = cards.get(sq.source)
    if card is None:
        reasons.append(f"{label}: unknown source {sq.source!r} (not a registered card)")
        return reasons  # nothing else is checkable without a card
    if not live_view.is_live(sq.source):
        live = live_view.get(sq.source)
        why = f" ({live.reason})" if live else ""
        reasons.append(f"{label}: source {sq.source!r} is not live{why}")

    # (b) every entity must exist in that source's card (introspected fields).
    if not sq.entities:
        reasons.append(f"{label}: names no graph entity to query")
    else:
        unknown = card.unknown_entities(sq.entities)
        if unknown:
            reasons.append(
                f"{label}: entities not in {sq.source} card: {sorted(unknown)}"
            )

    # (c) per-sub-question limits must be present and within the card's bounds.
    limits = sq.limits
    if not limits.is_present():
        reasons.append(
            f"{label}: missing required traversal limits "
            f"(got {limits.to_dict()})"
        )
    else:
        bounds = card.limits()
        if limits.max_traversal_depth > bounds["max_traversal_depth"]:
            reasons.append(
                f"{label}: max_traversal_depth {limits.max_traversal_depth} "
                f"exceeds card bound {bounds['max_traversal_depth']}"
            )
        if limits.max_result_rows > bounds["max_result_rows"]:
            reasons.append(
                f"{label}: max_result_rows {limits.max_result_rows} "
                f"exceeds card bound {bounds['max_result_rows']}"
            )
        if limits.query_timeout_ms > bounds["query_timeout_ms"]:
            reasons.append(
                f"{label}: query_timeout_ms {limits.query_timeout_ms} "
                f"exceeds card bound {bounds['query_timeout_ms']}"
            )

    return reasons


def _check_join(
    join,
    cards: dict[str, SourceCardView],
    live_view: LiveSourceView,
) -> list[str]:
    reasons: list[str] = []
    label = f"join {join.key!r}"

    # The join must reference exactly two distinct, known, live sources.
    sources = list(dict.fromkeys(join.sources))  # de-dup, keep order
    if len(sources) != 2:
        reasons.append(f"{label}: must join exactly two distinct sources, got {join.sources}")
        return reasons
    for source in sources:
        if source not in cards:
            reasons.append(f"{label}: unknown source {source!r}")
        elif not live_view.is_live(source):
            reasons.append(f"{label}: source {source!r} is not live")
    if reasons:
        return reasons

    # The key must be declared AND structurally bindable across both cards.
    resolved = resolve_join_key(cards[sources[0]], cards[sources[1]])
    if resolved is None:
        reasons.append(
            f"{label}: no declared canonical join key binds {sources[0]} and {sources[1]}"
        )
    elif resolved.name != join.key:
        reasons.append(
            f"{label}: key {join.key!r} is not the canonical bridge "
            f"(expected {resolved.name!r})"
        )
    return reasons


def evaluate(
    plan: Plan,
    cards: dict[str, SourceCardView],
    live_view: LiveSourceView,
) -> GateResult:
    """Deterministically accept or reject a drafted plan before it ships."""
    reasons: list[str] = []

    # Per-sub-question structural checks.
    seen_ids: set[str] = set()
    for sq in plan.sub_questions:
        if sq.id in seen_ids:
            reasons.append(f"duplicate sub-question id {sq.id!r}")
        seen_ids.add(sq.id)
        reasons.extend(_check_sub_question(sq, cards, live_view))

    # Cross-source join checks.
    for join in plan.joins:
        reasons.extend(_check_join(join, cards, live_view))

    # Non-degeneracy: a plan that references almost nothing and is not honestly
    # marked partial/unsupported has silently dropped the request.
    if plan.is_empty():
        reasons.append(
            "degenerate plan: no sub-questions and no unsupported parts "
            "(the request was silently dropped)"
        )

    return GateResult(ok=not reasons, reasons=reasons)


def valid_subset(
    plan: Plan,
    cards: dict[str, SourceCardView],
    live_view: LiveSourceView,
) -> tuple[list[SubQuestion], list, list[tuple[str, str]]]:
    """Partition a plan into the gate-valid items and the dropped ones.

    Used by the loop to degrade honestly on non-convergence: keep the parts that
    pass the gate, and surface every dropped sub-question/join as an explicit
    unsupported part with its reason. Returns (kept_sub_questions, kept_joins,
    dropped) where ``dropped`` is a list of (description, reason).
    """
    kept_sq: list[SubQuestion] = []
    dropped: list[tuple[str, str]] = []
    seen: set[str] = set()
    for sq in plan.sub_questions:
        reasons = _check_sub_question(sq, cards, live_view)
        if sq.id in seen:
            reasons = reasons + [f"duplicate sub-question id {sq.id!r}"]
        seen.add(sq.id)
        if reasons:
            dropped.append((f"sub-question {sq.id} -> {sq.source}: {sq.text}", "; ".join(reasons)))
        else:
            kept_sq.append(sq)

    kept_sources = {sq.source for sq in kept_sq}
    kept_joins = []
    for join in plan.joins:
        reasons = _check_join(join, cards, live_view)
        if not reasons and not set(join.sources).issubset(kept_sources):
            reasons = ["one or both joined sub-questions were dropped"]
        if reasons:
            dropped.append((f"join {join.key!r} on {join.sources}", "; ".join(reasons)))
        else:
            kept_joins.append(join)

    return kept_sq, kept_joins, dropped
