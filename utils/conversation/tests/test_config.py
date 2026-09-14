#!/usr/bin/env python3
"""Tests for conversation config resolution and DB-path override."""

from __future__ import annotations

from pathlib import Path

import pytest

from utils.conversation.config import (
    ConversationConfig,
    ConversationLLMConfig,
    conversation_db_path,
)
from utils.llm.config import FIELD_SUFFIX, STAGES, env_key


@pytest.fixture(autouse=True)
def _clean_llm_env(monkeypatch):
    """Clear every LLM variable before each test.

    These tests assert what config resolves to from a KNOWN environment, and
    ``api/main.py`` calls ``load_env()`` at import time -- so collecting api/ in
    the same pytest run drops the developer's real .env into os.environ before a
    single test executes. Without this fixture the assertions silently start
    measuring that file instead of the values the test set up, and the failure
    looks like a resolution bug rather than a leak.
    """
    for key in [env_key(f) for f in FIELD_SUFFIX] + [
        env_key(f, stage) for stage in STAGES for f in FIELD_SUFFIX
    ]:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("LLM_THINKING_BUDGET", raising=False)


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


def test_max_tokens_inherits_synthesis_budget(monkeypatch):
    # The answer agent's output budget must honor the synthesis max-tokens knob
    # when no conversation-specific value is set — otherwise long replies get
    # chopped at the 1024 default.
    monkeypatch.delenv("CONVERSATION_LLM_MAX_TOKENS", raising=False)
    monkeypatch.setenv("SYNTHESIS_LLM_MAX_TOKENS", "24000")
    assert ConversationLLMConfig.from_env().max_tokens == 24000


def test_conversation_max_tokens_override_beats_synthesis(monkeypatch):
    monkeypatch.setenv("CONVERSATION_LLM_MAX_TOKENS", "2048")
    monkeypatch.setenv("SYNTHESIS_LLM_MAX_TOKENS", "24000")
    assert ConversationLLMConfig.from_env().max_tokens == 2048


def test_max_tokens_defaults_to_1024_when_nothing_set(monkeypatch):
    monkeypatch.delenv("CONVERSATION_LLM_MAX_TOKENS", raising=False)
    monkeypatch.delenv("SYNTHESIS_LLM_MAX_TOKENS", raising=False)
    assert ConversationLLMConfig.from_env().max_tokens == 1024


def test_with_llm_enabled_is_two_way():
    """The caller decides, in both directions.

    This used to assert the opposite for an already-enabled config -- that
    `with_llm_enabled(False)` left it on, so an explicit
    CONVERSATION_LLM_ENABLED could not be overridden per turn. But `enabled` is
    resolved from the shared LLM group, so ARIADNE_LLM_ENABLED=true enabled the
    layer implicitly and nothing could switch it back: a turn the workbench
    labelled deterministic still made four model calls, 1.09s of pipeline inside
    a 43.27s turn (EXP-2026-09-020 A-8). The assertion was pinning the defect.
    """
    off = ConversationConfig(llm=ConversationLLMConfig(enabled=False))
    assert off.with_llm_enabled(True).llm.enabled is True
    assert off.with_llm_enabled(False).llm.enabled is False

    on = ConversationConfig(llm=ConversationLLMConfig(enabled=True))
    assert on.with_llm_enabled(True).llm.enabled is True
    assert on.with_llm_enabled(False).llm.enabled is False

    # A no-op call still returns the same object rather than a copy.
    assert on.with_llm_enabled(True) is on
    assert off.with_llm_enabled(False) is off
