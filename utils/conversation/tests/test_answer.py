#!/usr/bin/env python3
"""Tests for the final Answer agent (quick + graph paths, fallbacks)."""

from __future__ import annotations

from dataclasses import replace

from utils.conversation.agents.answer import (
    compose_answer,
    evidence_brief,
    make_answer_node,
)
from utils.conversation.config import ConversationConfig, ConversationLLMConfig
from utils.conversation.llm import CompletionResult, LLMUnavailable
from utils.specialists.contracts import EvidenceRecord
from utils.synthesis.contracts import SynthesizedAnswer


class _Result:
    def __init__(self, records):
        self.records = records


class _Evidence:
    def __init__(self, results):
        self.results = results


def _capec98_evidence():
    rec = EvidenceRecord(
        primary_id="CAPEC-98",
        id_scheme="capec-id",
        label="AttackPattern",
        name="Phishing",
        properties={
            "description": "Phishing is a social engineering technique where an attacker masquerades as a legitimate entity.",
            "Abstraction": "Standard",
            "Status": "Draft",
        },
        related=[
            {"id": "x", "name": "Phishing", "label": "TaxonomyEntry"},
            {"id": "y", "name": "Phishing for Information"},
        ],
    )
    return _Evidence([_Result([rec])])


class _StubLLM:
    def __init__(self, reply="", *, enabled=True, fail=False, finish_reason="stop"):
        self._reply = reply
        self.enabled = enabled
        self._fail = fail
        self._finish_reason = finish_reason

    def complete_verbose(self, messages, **kwargs):
        if self._fail:
            raise LLMUnavailable("boom")
        return CompletionResult(content=self._reply, finish_reason=self._finish_reason)


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


def test_graph_path_truncated_reply_gets_note_and_tidy():
    # A length stop returns partial content: the analyst must see an explicit
    # truncation note, and the dangling "(T1561." id fragment is trimmed off.
    partial = (
        "Disk wiping (T1561) interrupts availability by corrupting raw disk data. "
        "This is generally achieved through two methods: Disk Content Wipe (T1561."
    )
    ans = SynthesizedAnswer(request="q", narrative="grounded body")
    state = {"route": "graph", "question": "tell me about disk wiping", "answer": ans}
    text, composer = compose_answer(
        state, _cfg(), _StubLLM(partial, finish_reason="length")
    )
    assert composer == "llm"
    assert "truncated" in text.lower()
    assert "CONVERSATION_LLM_MAX_TOKENS" in text
    # The hanging, incomplete "(T1561." parenthetical is stripped.
    assert "Disk Content Wipe" in text
    assert "(T1561." not in text


def test_graph_path_truncated_empty_falls_back_to_deterministic():
    # A length stop that yielded no visible content keeps the complete verified
    # narrative rather than emitting an empty/near-empty truncated reply.
    ans = SynthesizedAnswer(request="q", narrative="grounded body")
    state = {"route": "graph", "question": "q", "answer": ans}
    text, composer = compose_answer(
        state, _cfg(), _StubLLM("", finish_reason="length")
    )
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


def test_evidence_brief_surfaces_description_and_related():
    brief = evidence_brief(_capec98_evidence())
    assert "CAPEC-98" in brief
    assert "social engineering technique" in brief
    assert "Abstraction: Standard" in brief
    assert "Phishing for Information" in brief


def test_evidence_brief_none_is_empty():
    assert evidence_brief(None) == ""


def _many_records_evidence(n):
    recs = [
        EvidenceRecord(
            primary_id=f"T{1000 + i}",
            id_scheme="attack-id",
            label="Technique",
            name=f"Technique {i}",
            properties={"description": "D" * 500},
        )
        for i in range(n)
    ]
    return _Evidence([_Result(recs)])


def test_evidence_brief_bounded_by_total_size():
    # A record-heavy turn must not inflate the answer prompt without limit.
    from utils.conversation.agents.answer import _MAX_BRIEF_CHARS

    brief = evidence_brief(_many_records_evidence(50))
    assert len(brief) <= _MAX_BRIEF_CHARS + 200  # budget + the omitted marker line
    assert "omitted here to keep the answer prompt within budget" in brief
    # The first record is always present.
    assert "T1000" in brief


def test_evidence_brief_small_set_has_no_omitted_marker():
    brief = evidence_brief(_capec98_evidence())
    assert "omitted" not in brief


def test_evidence_brief_always_includes_first_even_if_oversized():
    # A single record larger than the whole budget is still surfaced (never empty).
    big = EvidenceRecord(
        primary_id="T9999",
        id_scheme="attack-id",
        label="Technique",
        name="Huge",
        properties={"description": "X" * 5000},
    )
    brief = evidence_brief(_Evidence([_Result([big])]))
    assert "T9999" in brief


def test_graph_path_feeds_evidence_details_to_llm():
    seen = {}

    class _Capture:
        enabled = True

        def complete_verbose(self, messages, **kwargs):
            seen["content"] = messages[-1]["content"]
            return CompletionResult(content="Here's more on phishing.")

    ans = SynthesizedAnswer(request="q", narrative="CAPEC-98 maps to T1566 and T1598.")
    state = {
        "route": "graph",
        "question": "tell me more",
        "answer": ans,
        "evidence": _capec98_evidence(),
    }
    text, composer = compose_answer(state, _cfg(), _Capture())
    assert composer == "llm"
    # The retrieved description reached the model as grounded detail.
    assert "GRAPH EVIDENCE DETAILS" in seen["content"]
    assert "social engineering technique" in seen["content"]


def test_graph_path_without_evidence_omits_brief():
    seen = {}

    class _Capture:
        enabled = True

        def complete_verbose(self, messages, **kwargs):
            seen["content"] = messages[-1]["content"]
            return CompletionResult(content="ok")

    ans = SynthesizedAnswer(request="q", narrative="body")
    compose_answer({"route": "graph", "question": "q", "answer": ans}, _cfg(), _Capture())
    assert "GRAPH EVIDENCE DETAILS" not in seen["content"]


def test_answer_node_writes_final_payload_and_trace():
    ans = SynthesizedAnswer(request="q", narrative="body")
    node = make_answer_node(_cfg(enabled=False), _StubLLM(enabled=False))
    out = node({"route": "graph", "question": "q", "answer": ans})
    assert out["final_answer"] == "body"
    assert out["final"]["route"] == "graph"
    assert out["final"]["composer"] == "deterministic"
    assert out["trace"][0]["node"] == "answer"
