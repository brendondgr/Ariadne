#!/usr/bin/env python3
"""Tests for the final Answer agent (quick + graph paths, fallbacks)."""

from __future__ import annotations

from dataclasses import replace

from utils.conversation.agents.answer import compose_answer, make_answer_node
from utils.conversation.config import ConversationConfig, ConversationLLMConfig
from utils.conversation.llm import LLMUnavailable
from utils.synthesis.contracts import SynthesizedAnswer


class _StubLLM:
    def __init__(self, reply="", *, enabled=True, fail=False):
        self._reply = reply
        self.enabled = enabled
        self._fail = fail

    def complete(self, messages, **kwargs):
        if self._fail:
            raise LLMUnavailable("boom")
        return self._reply


def _cfg(enabled=True, **over):
    base = ConversationConfig(llm=ConversationLLMConfig(enabled=enabled))
    return replace(base, **over)


def test_graph_path_llm_off_passes_narrative_verbatim():
    ans = SynthesizedAnswer(request="q", narrative="T1598 is Phishing for Information.")
    state = {"route": "graph", "question": "more on T1598", "answer": ans}
    text, composer = compose_answer(state, _cfg(enabled=False), _StubLLM(enabled=False))
    assert text == "T1598 is Phishing for Information."
    assert composer == "deterministic"


def test_graph_path_llm_on_wraps_narrative():
    ans = SynthesizedAnswer(request="q", narrative="grounded body")
    state = {"route": "graph", "question": "q", "answer": ans}
    text, composer = compose_answer(
        state, _cfg(), _StubLLM("Sure! grounded body, in context.")
    )
    assert composer == "llm"
    assert "grounded body" in text


def test_graph_path_llm_failure_falls_back_to_narrative():
    ans = SynthesizedAnswer(request="q", narrative="grounded body")
    state = {"route": "graph", "question": "q", "answer": ans}
    text, composer = compose_answer(state, _cfg(), _StubLLM(fail=True))
    assert text == "grounded body"
    assert composer == "deterministic"


def test_graph_path_no_evidence_is_honest():
    state = {"route": "graph", "question": "q", "answer": SynthesizedAnswer(request="q")}
    text, composer = compose_answer(state, _cfg(enabled=False), _StubLLM(enabled=False))
    assert "couldn't find" in text.lower()
    assert composer == "deterministic"


def test_quick_path_deterministic_summarizes_facts():
    history = [
        {"role": "user", "content": "which techniques map to CAPEC-98?"},
        {
            "role": "assistant",
            "content": "CAPEC-98 maps to T1566 and T1598.",
            "facts": ["CAPEC-98 maps to T1566 (Phishing)", "CAPEC-98 maps to T1598"],
        },
    ]
    state = {"route": "quick", "question": "remind me what it mapped to", "history": history}
    text, composer = compose_answer(state, _cfg(enabled=False), _StubLLM(enabled=False))
    assert composer == "deterministic"
    assert "T1566" in text and "T1598" in text


def test_quick_path_no_facts_asks_for_clarification():
    state = {"route": "quick", "question": "hey", "history": []}
    text, composer = compose_answer(state, _cfg(enabled=False), _StubLLM(enabled=False))
    assert composer == "deterministic"
    assert "clarify" in text.lower()


def test_quick_path_llm_answers_from_memory():
    history = [{"role": "assistant", "content": "prior", "facts": ["fact A"]}]
    state = {"route": "quick", "question": "recap", "history": history}
    text, composer = compose_answer(state, _cfg(), _StubLLM("Earlier we established fact A."))
    assert composer == "llm"
    assert "fact A" in text


def test_answer_node_writes_final_payload_and_trace():
    ans = SynthesizedAnswer(request="q", narrative="body")
    node = make_answer_node(_cfg(enabled=False), _StubLLM(enabled=False))
    out = node({"route": "graph", "question": "q", "answer": ans})
    assert out["final_answer"] == "body"
    assert out["final"]["route"] == "graph"
    assert out["final"]["composer"] == "deterministic"
    assert out["trace"][0]["node"] == "answer"
