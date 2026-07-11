#!/usr/bin/env python3
"""Planner subgraph nodes: draft, gate, finalize, degrade.

Each node wraps the exact domain logic ``PlanningAgent.plan`` used to inline —
the configured ``PlanDrafter``, the deterministic gate (``utils.planner.gate.
evaluate``), and honest degradation (``utils.planner.degrade``). Nodes are
built by a factory closure so the drafter/cards/iteration-cap live outside the
graph state (they are collaborators, not data).
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from utils.orchestration.state import PlanningState
from utils.planner.cards import SourceCardView
from utils.planner.degrade import degrade_to_partial
from utils.planner.drafter import PlanDrafter
from utils.planner.gate import evaluate
from utils.planner.intent import IntentClassifier

logger = logging.getLogger("ariadne.planner.agent")

NodeFn = Callable[[PlanningState], dict[str, Any]]


def build_nodes(
    drafter: PlanDrafter,
    cards: dict[str, SourceCardView],
    max_iterations: int,
    classifier: IntentClassifier,
) -> dict[str, NodeFn]:
    """Return the planner subgraph's node functions, closed over collaborators."""

    def classify(state: PlanningState) -> dict[str, Any]:
        # Planner step one: name the analyst intent before any drafting. The
        # label biases the draft; the gate remains the authority on what ships.
        intent = classifier.classify(state["request"], cards)
        logger.info(
            "intent classified: %s (%.2f, %s)",
            intent.label, intent.confidence, intent.source,
        )
        return {"intent": intent}

    def draft(state: PlanningState) -> dict[str, Any]:
        iteration = int(state.get("iteration") or 0) + 1
        plan = drafter.draft(
            state["request"], cards, state["live_view"], state.get("feedback"),
            state.get("intent"),
        )
        drafter_used = getattr(drafter, "last_used", "") or type(drafter).__name__
        return {"iteration": iteration, "last_plan": plan, "drafter_used": drafter_used}

    def gate(state: PlanningState) -> dict[str, Any]:
        plan = state["last_plan"]
        result = evaluate(plan, cards, state["live_view"])
        entry = {
            "iteration": state["iteration"],
            "drafter": state["drafter_used"],
            "gate_ok": result.ok,
            "reasons": list(result.reasons),
            "sub_questions": len(plan.sub_questions),
            "unsupported": len(plan.unsupported),
        }
        update: dict[str, Any] = {"gate_ok": result.ok, "trace": [entry]}
        if not result.ok:
            logger.info(
                "iteration %d rejected (%d reason(s)); revising",
                state["iteration"], len(result.reasons),
            )
            update["feedback"] = list(result.reasons)
        return update

    def finalize(state: PlanningState) -> dict[str, Any]:
        plan = state["last_plan"]
        logger.info(
            "plan converged on iteration %d (%s)", state["iteration"], state["drafter_used"]
        )
        plan.trace = list(state["trace"])
        plan.intent = state.get("intent")  # carry the classified intent onto the plan
        return {"plan": plan}

    def degrade(state: PlanningState) -> dict[str, Any]:
        logger.info("max iterations reached; degrading to partial plan")
        plan = degrade_to_partial(
            state.get("last_plan"),
            state["request"],
            state["live_view"],
            list(state.get("feedback") or []),
            list(state["trace"]),
            cards=cards,
            max_iterations=max_iterations,
        )
        plan.intent = state.get("intent")  # even a degraded plan reports its intent
        return {"plan": plan}

    def route_after_gate(state: PlanningState) -> str:
        if state["gate_ok"]:
            return "finalize"
        if state["iteration"] < max_iterations:
            return "draft"
        return "degrade"

    return {
        "classify": classify,
        "draft": draft,
        "gate": gate,
        "finalize": finalize,
        "degrade": degrade,
        "route_after_gate": route_after_gate,
    }
