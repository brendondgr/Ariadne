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

The loop itself runs as a LangGraph subgraph
(``utils.orchestration.agents.planner``): draft → gate → conditional edge back
to draft with feedback, or on to finalize/degrade. This class is the stable
facade — it owns the collaborators (cards, drafter, probe) and the public
contract; the graph owns the control flow.
"""

from __future__ import annotations

import logging

from .cards import SourceCardView, load_source_cards
from .config import PlannerConfig
from .degrade import degrade_to_partial
from .discovery import LiveSourceProbe, LiveSourceView
from .drafter import PlanDrafter
from .drafter_factory import select_drafter
from .schema import Plan

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
        self._graph = None  # compiled lazily; collaborators are fixed at init

    @property
    def cards(self) -> dict[str, SourceCardView]:
        return self._cards

    def live_sources(self) -> LiveSourceView:
        """Return the current (cached-per-TTL) live-source view."""
        return self._probe.get_live_sources(self._cards)

    def _compiled(self):
        if self._graph is None:
            # Imported here: utils.orchestration imports planner modules, so a
            # top-level import would be circular.
            from utils.orchestration.agents.planner.graph import build_planning_graph
            from utils.orchestration.config import OrchestrationConfig

            self._graph = (
                build_planning_graph(self._drafter, self._cards, self._config.max_iterations),
                OrchestrationConfig.from_env(),
            )
        return self._graph

    def plan(self, request: str) -> Plan:
        # Re-probe per request (short TTL cache amortises bursts).
        live_view = self._probe.get_live_sources(self._cards)
        if self._config.max_iterations <= 0:  # defensive: no drafts allowed
            return self._degrade(None, request, live_view, [], [])
        graph, orch = self._compiled()
        out = graph.invoke(
            {"request": request, "live_view": live_view, "iteration": 0, "feedback": None},
            config={"recursion_limit": orch.recursion_limit},
        )
        return out["plan"]

    def _degrade(
        self,
        plan: Plan | None,
        request: str,
        live_view: LiveSourceView,
        reasons: list[str],
        trace: list[dict],
    ) -> Plan:
        """Kept for compatibility; the graph's degrade node uses the same helper."""
        return degrade_to_partial(
            plan, request, live_view, reasons, trace,
            cards=self._cards, max_iterations=self._config.max_iterations,
        )
