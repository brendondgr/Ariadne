#!/usr/bin/env python3
"""Tests for LLM auto-titling and its deterministic fallback."""

from __future__ import annotations

from utils.conversation.config import ConversationConfig, ConversationLLMConfig
from utils.conversation.llm import LLMUnavailable
from utils.conversation.naming import deterministic_title, title_for


class _StubLLM:
    def __init__(self, reply="", *, enabled=True, fail=False):
        self._reply = reply
        self.enabled = enabled
        self._fail = fail

    def complete(self, messages, **kwargs):
        if self._fail:
            raise LLMUnavailable("boom")
        return self._reply


def _cfg(enabled):
    return ConversationConfig(llm=ConversationLLMConfig(enabled=enabled))


def test_deterministic_title_short_question():
    assert deterministic_title("Which techniques map to CAPEC-98?") == (
        "Which techniques map to CAPEC-98?"
    )


def test_deterministic_title_empty():
    assert deterministic_title("   ") == "New conversation"


def test_deterministic_title_truncates_long():
    long = "Explain in exhaustive detail every single mitigation for phishing techniques across ATTACK"
    title = deterministic_title(long)
    assert title.endswith("…")
    assert len(title) <= 62


def test_title_for_llm_off_uses_deterministic():
    cfg = _cfg(enabled=False)
    assert title_for("Map CAPEC-98", cfg, _StubLLM(enabled=False)) == "Map CAPEC-98"


def test_title_for_llm_on_uses_model_reply():
    cfg = _cfg(enabled=True)
    title = title_for("what maps to CAPEC-98?", cfg, _StubLLM('"Phishing Mappings"'))
    assert title == "Phishing Mappings"


def test_title_for_llm_failure_falls_back():
    cfg = _cfg(enabled=True)
    title = title_for("Map CAPEC-98", cfg, _StubLLM(fail=True))
    assert title == "Map CAPEC-98"


def test_title_for_strips_and_bounds_model_reply():
    cfg = _cfg(enabled=True)
    long_reply = "This Is An Excessively Long Generated Title That Runs On Well Past The Limit"
    title = title_for("q", cfg, _StubLLM(long_reply))
    assert len(title) <= 62


def test_title_for_clamps_to_five_words():
    cfg = _cfg(enabled=True)
    title = title_for("q", cfg, _StubLLM("Phishing Mitigations Across MITRE ATTACK Techniques Detail"))
    assert title == "Phishing Mitigations Across MITRE ATTACK"
    assert len(title.split()) == 5
