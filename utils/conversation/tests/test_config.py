#!/usr/bin/env python3
"""Tests for conversation config resolution and DB-path override."""

from __future__ import annotations

from pathlib import Path

from utils.conversation.config import (
    ConversationConfig,
    ConversationLLMConfig,
    conversation_db_path,
)


def test_defaults_are_llm_off_and_bounded(monkeypatch):
    for var in (
        "CONVERSATION_LLM_ENABLED",
        "CONVERSATION_LLM_BASE_URL",
        "CONVERSATION_LLM_MODEL",
        "ARIADNE_CONVERSATION_MAX_VALIDATION_ITERS",
        "CONVERSATION_QUICK_ANSWER",
        "CONVERSATION_HISTORY_TURNS",
    ):
        monkeypatch.delenv(var, raising=False)

    cfg = ConversationConfig.from_env()
    assert cfg.llm.enabled is False
    assert cfg.max_validation_iters == 2
    assert cfg.quick_answer_enabled is True
    assert cfg.history_turns == 12
    assert cfg.llm.endpoint.endswith("/chat/completions")


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("CONVERSATION_LLM_ENABLED", "true")
    monkeypatch.setenv("CONVERSATION_LLM_MODEL", "my-model")
    monkeypatch.setenv("CONVERSATION_LLM_TIMEOUT_S", "12.5")
    monkeypatch.setenv("ARIADNE_CONVERSATION_MAX_VALIDATION_ITERS", "5")
    monkeypatch.setenv("CONVERSATION_QUICK_ANSWER", "false")
    monkeypatch.setenv("CONVERSATION_HISTORY_TURNS", "3")

    cfg = ConversationConfig.from_env()
    assert cfg.llm.enabled is True
    assert cfg.llm.model == "my-model"
    assert cfg.llm.timeout_s == 12.5
    assert cfg.max_validation_iters == 5
    assert cfg.quick_answer_enabled is False
    assert cfg.history_turns == 3


def test_db_path_override_wins(monkeypatch, tmp_path):
    custom = tmp_path / "custom" / "threads.db"
    monkeypatch.setenv("ARIADNE_CONVERSATION_DB", str(custom))
    assert conversation_db_path() == custom


def test_db_path_defaults_under_data_dir(monkeypatch):
    monkeypatch.delenv("ARIADNE_CONVERSATION_DB", raising=False)
    monkeypatch.setenv("ARIADNE_DATA_DIR", "somedata")
    path = conversation_db_path()
    assert path == Path("somedata") / "conversations.sqlite3"


def test_llm_config_endpoint_strips_trailing_slash():
    cfg = ConversationLLMConfig(base_url="http://host:1/v1/")
    assert cfg.endpoint == "http://host:1/v1/chat/completions"


def test_llm_config_inherits_synthesis_endpoint(monkeypatch):
    monkeypatch.delenv("CONVERSATION_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("CONVERSATION_LLM_MODEL", raising=False)
    monkeypatch.setenv("SYNTHESIS_LLM_BASE_URL", "http://my-llm:9000/v1")
    monkeypatch.setenv("SYNTHESIS_LLM_MODEL", "synthesis-model")
    cfg = ConversationLLMConfig.from_env()
    assert cfg.base_url == "http://my-llm:9000/v1"
    assert cfg.model == "synthesis-model"


def test_conversation_base_url_override_beats_synthesis(monkeypatch):
    monkeypatch.setenv("CONVERSATION_LLM_BASE_URL", "http://own:1/v1")
    monkeypatch.setenv("SYNTHESIS_LLM_BASE_URL", "http://synth:2/v1")
    assert ConversationLLMConfig.from_env().base_url == "http://own:1/v1"


def test_with_llm_enabled_turns_on_when_drafter_is_llm():
    cfg = ConversationConfig(llm=ConversationLLMConfig(enabled=False))
    assert cfg.with_llm_enabled(True).llm.enabled is True
    # Deterministic turns stay deterministic.
    assert cfg.with_llm_enabled(False).llm.enabled is False
    # Explicitly-enabled config is unchanged (and returns as-is).
    on = ConversationConfig(llm=ConversationLLMConfig(enabled=True))
    assert on.with_llm_enabled(False).llm.enabled is True
