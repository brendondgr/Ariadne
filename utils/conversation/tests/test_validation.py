#!/usr/bin/env python3
"""Tests for the Validation agent (sufficiency gate + bounded retry)."""

from __future__ import annotations

from dataclasses import replace

from utils.conversation.agents.validation import (
    VERDICT_INSUFFICIENT,
    VERDICT_PASS,
    evaluate_sufficiency,
    make_validation_node,
)
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


def test_llm_off_always_passes():
    verdict, _, missing = evaluate_sufficiency(
        "q", SynthesizedAnswer(request="q"), _cfg(enabled=False), _StubLLM(enabled=False)
    )
    assert verdict == VERDICT_PASS
    assert missing == []


def test_llm_error_passes():
    verdict, _, _ = evaluate_sufficiency(
        "q", SynthesizedAnswer(request="q"), _cfg(), _StubLLM(fail=True)
    )
    assert verdict == VERDICT_PASS


def test_llm_sufficient():
    stub = _StubLLM('{"sufficient": true, "reason": "complete"}')
    verdict, reason, missing = evaluate_sufficiency(
        "q", SynthesizedAnswer(request="q", narrative="x"), _cfg(), stub
    )
    assert verdict == VERDICT_PASS
    assert reason == "complete"
    assert missing == []


def test_llm_insufficient_reports_missing():
    stub = _StubLLM(
        '{"sufficient": false, "missing": ["mitigations"], "reason": "no mitigations"}'
    )
    verdict, reason, missing = evaluate_sufficiency(
        "q", SynthesizedAnswer(request="q", narrative="x"), _cfg(), stub
    )
    assert verdict == VERDICT_INSUFFICIENT
    assert missing == ["mitigations"]
    assert reason == "no mitigations"


def test_node_insufficient_sets_extraction_params():
    stub = _StubLLM('{"sufficient": false, "missing": ["m"], "reason": "r"}')
    node = make_validation_node(_cfg(max_validation_iters=3), stub)
    out = node({"resolved_question": "q", "answer": SynthesizedAnswer(request="q")})
    assert out["validation_verdict"] == VERDICT_INSUFFICIENT
    assert out["validation_iterations"] == 1
    assert out["extraction_params"] == {"focus": ["m"], "reason": "r"}


def test_node_enforces_retry_cap():
    # On the 2nd attempt with cap=2, it must force pass regardless of the LLM.
    stub = _StubLLM('{"sufficient": false, "missing": ["m"], "reason": "r"}')
    node = make_validation_node(_cfg(max_validation_iters=2), stub)
    out = node(
        {
            "resolved_question": "q",
            "answer": SynthesizedAnswer(request="q"),
            "validation_iterations": 1,
        }
    )
    assert out["validation_verdict"] == VERDICT_PASS
    assert out["validation_iterations"] == 2
    assert out["trace"][0]["capped"] is True
    assert "extraction_params" not in out


def test_node_pass_has_no_extraction_params():
    stub = _StubLLM('{"sufficient": true, "reason": "ok"}')
    node = make_validation_node(_cfg(max_validation_iters=3), stub)
    out = node({"resolved_question": "q", "answer": SynthesizedAnswer(request="q")})
    assert out["validation_verdict"] == VERDICT_PASS
    assert "extraction_params" not in out
