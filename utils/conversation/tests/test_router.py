#!/usr/bin/env python3
"""Tests for the redirect (router) agent."""

from __future__ import annotations

from dataclasses import replace

from utils.conversation.agents.router import (
    ROUTE_GRAPH,
    ROUTE_QUICK,
    classify_route,
    make_router_node,
)
from utils.conversation.config import ConversationConfig, ConversationLLMConfig
from utils.conversation.llm import LLMUnavailable


class _StubLLM:
    def __init__(self, reply="", *, enabled=True, fail=False):
        self._reply = reply
        self.enabled = enabled
        self._fail = fail
        self.calls = 0

    def complete(self, messages, **kwargs):
        self.calls += 1
        if self._fail:
            raise LLMUnavailable("boom")
        return self._reply


def _cfg(**over):
    base = ConversationConfig(llm=ConversationLLMConfig(enabled=True))
    return replace(base, **over)


def test_llm_disabled_defaults_to_graph():
    cfg = _cfg(llm=ConversationLLMConfig(enabled=False))
    route, reason = classify_route("What maps to CAPEC-98?", [], cfg, _StubLLM(enabled=False))
    assert route == ROUTE_GRAPH
    assert "default" in reason.lower() or "disabled" in reason.lower()


def test_quick_disabled_forces_graph_without_calling_llm():
    cfg = _cfg(quick_answer_enabled=False)
    stub = _StubLLM('{"route": "quick", "reason": "x"}')
    route, _ = classify_route("summarize", [], cfg, stub)
    assert route == ROUTE_GRAPH
    assert stub.calls == 0


def test_llm_picks_quick():
    stub = _StubLLM('{"route": "quick", "reason": "meta question"}')
    route, reason = classify_route("what did we just discuss?", [], _cfg(), stub)
    assert route == ROUTE_QUICK
    assert reason == "meta question"


def test_llm_picks_graph():
    stub = _StubLLM('here you go: {"route": "graph", "reason": "new fact"}')
    route, reason = classify_route("mitigations for T1598?", [], _cfg(), stub)
    assert route == ROUTE_GRAPH
    assert reason == "new fact"


def test_unparseable_reply_defaults_to_graph():
    route, _ = classify_route("q", [], _cfg(), _StubLLM("not json at all"))
    assert route == ROUTE_GRAPH


def test_unknown_route_value_defaults_to_graph():
    route, _ = classify_route("q", [], _cfg(), _StubLLM('{"route": "banana"}'))
    assert route == ROUTE_GRAPH


def test_llm_error_defaults_to_graph():
    route, _ = classify_route("q", [], _cfg(), _StubLLM(fail=True))
    assert route == ROUTE_GRAPH


def test_router_node_writes_state_and_trace():
    node = make_router_node(_cfg(), _StubLLM('{"route": "quick", "reason": "r"}'))
    out = node({"question": "hi", "resolved_question": "hi", "history": []})
    assert out["route"] == ROUTE_QUICK
    assert out["route_reason"] == "r"
    assert out["trace"][0]["node"] == "router"


def test_router_node_prefers_resolved_question():
    seen = {}

    class _Capture(_StubLLM):
        def complete(self, messages, **kwargs):
            seen["content"] = messages[-1]["content"]
            return '{"route": "graph", "reason": "r"}'

    node = make_router_node(_cfg(), _Capture(enabled=True))
    node({"question": "more?", "resolved_question": "details on T1598", "history": []})
    assert "T1598" in seen["content"]
