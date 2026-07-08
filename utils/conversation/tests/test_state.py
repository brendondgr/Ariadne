#!/usr/bin/env python3
"""Tests that ConversationState behaves correctly as LangGraph state.

Mirrors the orchestration state tests: build a trivial compiled StateGraph over
``ConversationState`` and prove (a) real contract objects round-trip untouched,
(b) the ``trace`` reducer accumulates deltas, and (c) scalar fields overwrite.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from utils.conversation.state import ConversationState
from utils.specialists.federation import FederatedEvidence
from utils.synthesis.contracts import SynthesizedAnswer


def _compile(*nodes):
    graph = StateGraph(ConversationState)
    prev = START
    for i, node in enumerate(nodes):
        name = f"n{i}"
        graph.add_node(name, node)
        graph.add_edge(prev, name)
        prev = name
    graph.add_edge(prev, END)
    return graph.compile()


def test_trace_accumulates_and_scalars_overwrite():
    def first(_state):
        return {"route": "graph", "trace": [{"step": "router"}]}

    def second(_state):
        return {"route": "quick", "trace": [{"step": "answer"}]}

    app = _compile(first, second)
    out = app.invoke({"question": "hi", "trace": []})

    # Last writer wins for a plain scalar.
    assert out["route"] == "quick"
    # The reducer concatenated both deltas.
    assert out["trace"] == [{"step": "router"}, {"step": "answer"}]


def test_contract_objects_pass_through_untouched():
    answer = SynthesizedAnswer(request="q", headline="head", narrative="body")
    evidence = FederatedEvidence(request="q")

    def node(_state):
        return {"answer": answer, "evidence": evidence}

    app = _compile(node)
    out = app.invoke({"question": "q"})

    assert out["answer"] is answer
    assert out["evidence"] is evidence
    assert out["answer"].headline == "head"


def test_validation_counter_overwrites():
    def bump(state):
        return {"validation_iterations": state.get("validation_iterations", 0) + 1}

    app = _compile(bump, bump)
    out = app.invoke({"question": "q", "validation_iterations": 0})
    assert out["validation_iterations"] == 2
