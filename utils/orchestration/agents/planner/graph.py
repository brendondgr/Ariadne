#!/usr/bin/env python3
"""Planner subgraph wiring: draft → gate → (finalize | draft | degrade).

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
from utils.planner.drafter import PlanDrafter

from .nodes import build_nodes


def build_planning_graph(
    drafter: PlanDrafter,
    cards: dict[str, SourceCardView],
    max_iterations: int,
) -> CompiledStateGraph:
    """Compile the draft → gate → revise/degrade loop for one agent's collaborators."""
    nodes = build_nodes(drafter, cards, max_iterations)

    graph = StateGraph(PlanningState)
    graph.add_node("draft", nodes["draft"])
    graph.add_node("gate", nodes["gate"])
    graph.add_node("finalize", nodes["finalize"])
    graph.add_node("degrade", nodes["degrade"])

    graph.add_edge(START, "draft")
    graph.add_edge("draft", "gate")
    graph.add_conditional_edges(
        "gate",
        nodes["route_after_gate"],
        {"finalize": "finalize", "draft": "draft", "degrade": "degrade"},
    )
    graph.add_edge("finalize", END)
    graph.add_edge("degrade", END)
    return graph.compile()
