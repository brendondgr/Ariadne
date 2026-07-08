#!/usr/bin/env python3
"""Specialist loop wiring: cycle over sub-questions in dependency order.

A deliberate *sequential* conditional-edge cycle — not a ``Send`` fan-out —
because consumers are seeded from producers' results and the committed
evaluation baselines depend on deterministic ordering (see the migration
plan's §2 assumption).
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from utils.orchestration.state import PipelineState
from utils.specialists.config import SpecialistConfig

from .nodes import build_nodes


def build_specialists_graph(
    cards: dict[str, Any],
    specialist_config: SpecialistConfig,
    injected: dict[str, Any] | None = None,
) -> CompiledStateGraph:
    """Compile the sequential specialist-execution loop."""
    nodes = build_nodes(cards, specialist_config, injected)

    def route(state: PipelineState) -> str:
        return "run_specialist" if nodes["has_next"](state) else END

    graph = StateGraph(PipelineState)
    graph.add_node("run_specialist", nodes["run_specialist"])
    graph.add_conditional_edges(START, route, {"run_specialist": "run_specialist", END: END})
    graph.add_conditional_edges(
        "run_specialist", route, {"run_specialist": "run_specialist", END: END}
    )
    return graph.compile()
