#!/usr/bin/env python3
"""Honest degradation to a partial plan (briefing §5.1/§5.3).

When the planning loop exhausts its iteration cap, the planner never loops
forever and never fabricates a plan to escape the gate: it keeps the
gate-valid subset of the last draft and names everything unresolved as
unsupported. This lives in its own module so both the ``PlanningAgent``
facade and the LangGraph planner subgraph node
(``utils.orchestration.agents.planner``) share the one implementation.
"""

from __future__ import annotations

from .cards import SourceCardView
from .discovery import LiveSourceView
from .gate import valid_subset
from .schema import Plan, UnsupportedPart


def degrade_to_partial(
    plan: Plan | None,
    request: str,
    live_view: LiveSourceView,
    reasons: list[str],
    trace: list[dict],
    *,
    cards: dict[str, SourceCardView],
    max_iterations: int,
) -> Plan:
    """Return the best honest partial plan from the last rejected draft."""
    if plan is None:  # defensive: cap was 0
        plan = Plan(request=request)
    kept_sq, kept_joins, dropped = valid_subset(plan, cards, live_view)
    degraded = Plan(
        request=request,
        sub_questions=kept_sq,
        joins=kept_joins,
        unsupported=list(plan.unsupported),
        assumptions=list(plan.assumptions),
        rationale=plan.rationale,
        partial=True,
        trace=trace,
    )
    for description, reason in dropped:
        degraded.unsupported.append(
            UnsupportedPart(description=description, reason=f"unresolved: {reason}")
        )
    if degraded.is_empty():
        degraded.unsupported.append(
            UnsupportedPart(
                description=request,
                reason=(
                    "planner could not produce a routable plan within "
                    f"{max_iterations} iterations: " + "; ".join(reasons)
                ),
            )
        )
    degraded.assumptions.append(
        f"degraded to partial plan after {max_iterations} iterations"
    )
    return degraded
