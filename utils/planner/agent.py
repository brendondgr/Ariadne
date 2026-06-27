#!/usr/bin/env python3
"""The self-evaluating ReAct loop — the planner's single entry point.

``PlanningAgent.plan(request)`` ties the pieces together:

1. **Re-probe** the live-source view for this request (briefing §2.4).
2. **Draft** a plan with the configured drafter (briefing §3).
3. **Grade** it with the deterministic gate (briefing §4).
4. On failure, feed the gate's *specific* rejection reasons back into the next
   draft (briefing §5.2) and revise — up to a small ``max_iterations`` cap
   (briefing §5.1).
5. On exhaustion, **degrade** to the best honest partial plan: keep the
   gate-valid parts and name everything unresolved as unsupported — never an
   infinite loop, never a fabricated plan to escape the gate (briefing §5.1),
   never a degenerate plan emitted as success (briefing §5.3).

Every iteration is recorded in the plan's ``trace`` for inspectability.
"""

from __future__ import annotations

import logging

from .cards import SourceCardView, load_source_cards
from .config import PlannerConfig
from .discovery import LiveSourceProbe, LiveSourceView
from .drafter import PlanDrafter
from .drafter_factory import select_drafter
from .gate import evaluate, valid_subset
from .schema import Plan, UnsupportedPart

logger = logging.getLogger("ariadne.planner.agent")


class PlanningAgent:
    """Runs the bounded, self-evaluating planning loop."""

    def __init__(
        self,
        config: PlannerConfig | None = None,
        *,
        cards: dict[str, SourceCardView] | None = None,
        drafter: PlanDrafter | None = None,
        probe: LiveSourceProbe | None = None,
    ) -> None:
        self._config = config or PlannerConfig.from_env()
        self._cards = cards if cards is not None else load_source_cards(self._config.data_dir)
        self._drafter = drafter or select_drafter(self._config)
        self._probe = probe or LiveSourceProbe(self._config)

    @property
    def cards(self) -> dict[str, SourceCardView]:
        return self._cards

    def live_sources(self) -> LiveSourceView:
        """Return the current (cached-per-TTL) live-source view."""
        return self._probe.get_live_sources(self._cards)

    def plan(self, request: str) -> Plan:
        # Re-probe per request (short TTL cache amortises bursts).
        live_view = self._probe.get_live_sources(self._cards)
        feedback: list[str] | None = None
        trace: list[dict] = []
        last_plan: Plan | None = None

        for iteration in range(1, self._config.max_iterations + 1):
            plan = self._drafter.draft(request, self._cards, live_view, feedback)
            result = evaluate(plan, self._cards, live_view)
            drafter_used = getattr(self._drafter, "last_used", "") or type(self._drafter).__name__
            trace.append(
                {
                    "iteration": iteration,
                    "drafter": drafter_used,
                    "gate_ok": result.ok,
                    "reasons": list(result.reasons),
                    "sub_questions": len(plan.sub_questions),
                    "unsupported": len(plan.unsupported),
                }
            )
            last_plan = plan
            if result.ok:
                logger.info("plan converged on iteration %d (%s)", iteration, drafter_used)
                plan.trace = trace
                return plan
            logger.info(
                "iteration %d rejected (%d reason(s)); revising", iteration, len(result.reasons)
            )
            feedback = result.reasons

        # Exhausted the cap — degrade honestly rather than loop or fabricate.
        logger.info("max iterations reached; degrading to partial plan")
        return self._degrade(last_plan, request, live_view, feedback or [], trace)

    def _degrade(
        self,
        plan: Plan | None,
        request: str,
        live_view: LiveSourceView,
        reasons: list[str],
        trace: list[dict],
    ) -> Plan:
        if plan is None:  # defensive: cap was 0
            plan = Plan(request=request)
        kept_sq, kept_joins, dropped = valid_subset(plan, self._cards, live_view)
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
                        f"{self._config.max_iterations} iterations: " + "; ".join(reasons)
                    ),
                )
            )
        degraded.assumptions.append(
            f"degraded to partial plan after {self._config.max_iterations} iterations"
        )
        return degraded
