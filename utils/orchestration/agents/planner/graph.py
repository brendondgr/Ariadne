#!/usr/bin/env python3
"""Planner subgraph wiring: classify → canonicalize → draft → gate → (…).

The bounded self-evaluating loop from the planning briefing (§5) as a
LangGraph ``StateGraph``: the gate's conditional edge either accepts the
draft, feeds its rejection reasons back into another draft, or — at the
iteration cap — degrades to the best honest partial plan.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from utils.orchestration.state import PlanningState
from utils.planner.cards import SourceCardView
from utils.planner.config import PlannerConfig
from utils.planner.drafter import PlanDrafter
from utils.planner.intent import DeterministicIntentClassifier, IntentClassifier

from .nodes import build_nodes


def build_planning_graph(
    drafter: PlanDrafter,
    cards: dict[str, SourceCardView],
    max_iterations: int,
    classifier: IntentClassifier | None = None,
    config: PlannerConfig | None = None,
) -> CompiledStateGraph:
    """Compile the classify → canonicalize → draft → gate → revise/degrade loop."""
    nodes = build_nodes(
        drafter, cards, max_iterations,
        classifier or DeterministicIntentClassifier(),
        config,
    )

    graph = StateGraph(PlanningState)
    graph.add_node("classify", nodes["classify"])
    graph.add_node("canonicalize", nodes["canonicalize"])
    graph.add_node("draft", nodes["draft"])
    graph.add_node("gate", nodes["gate"])
    graph.add_node("finalize", nodes["finalize"])
    graph.add_node("degrade", nodes["degrade"])

    graph.add_edge(START, "classify")
    # Canonicalize sits between the two so the deterministic fill can read the
    # classified intent, and so everything downstream still receives only a
    # request string. With the flag off the node is a pass-through.
    graph.add_edge("classify", "canonicalize")
    graph.add_edge("canonicalize", "draft")
    graph.add_edge("draft", "gate")
    graph.add_conditional_edges(
        "gate",
        nodes["route_after_gate"],
        {"finalize": "finalize", "draft": "draft", "degrade": "degrade"},
    )
    graph.add_edge("finalize", END)
    graph.add_edge("degrade", END)
    return graph.compile()
