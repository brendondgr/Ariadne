#!/usr/bin/env python3
"""Synthesis subgraph wiring: compose → verify → narrate, unconditionally.

There are no conditional edges here on purpose: every draft is verified, and
the narrator node itself decides (via config) whether it has anything to do.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from utils.orchestration.state import SynthesisState
from utils.synthesis.config import SynthesisConfig

from .nodes import build_nodes


def build_synthesis_graph(
    composer, config: SynthesisConfig
) -> CompiledStateGraph:
    """Compile the compose → verify → narrate chain for one composer/config."""
    nodes = build_nodes(composer, config)

    graph = StateGraph(SynthesisState)
    graph.add_node("compose", nodes["compose"])
    graph.add_node("verify", nodes["verify"])
    graph.add_node("narrate", nodes["narrate"])
    graph.add_edge(START, "compose")
    graph.add_edge("compose", "verify")
    graph.add_edge("verify", "narrate")
    graph.add_edge("narrate", END)
    return graph.compile()
