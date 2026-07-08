#!/usr/bin/env python3
"""Configuration for the conversational threads layer.

Every knob is env-driven with documented defaults, mirroring the
planner/specialist/synthesis/orchestration config idiom: the LLM is off by
default so the whole layer degrades to deterministic fallbacks (router -> graph,
validation -> pass, answer -> synthesis narrative, title -> truncated question),
keeping LLM-off builds reproducible.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from utils.config import data_dir, env_bool, env_int, env_str

# Default database file, relative to the resolved data directory.
DEFAULT_DB_NAME = "conversations.sqlite3"

# OpenAI-compatible LLM defaults (match the synthesis/planner idiom).
DEFAULT_LLM_BASE_URL = "http://localhost:9090/v1"
DEFAULT_LLM_MODEL = "default-model"


def _env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


def conversation_db_path() -> Path:
    """Resolve the conversation SQLite path.

    ``ARIADNE_CONVERSATION_DB`` wins when set (absolute or relative). Otherwise
    the DB lives at ``<ARIADNE_DATA_DIR>/conversations.sqlite3`` (``data/`` by
    default, which is gitignored).
    """
    override = os.environ.get("ARIADNE_CONVERSATION_DB", "").strip()
    if override:
        return Path(override)
    return Path(env_str("ARIADNE_DATA_DIR", data_dir())) / DEFAULT_DB_NAME


@dataclass(frozen=True)
class ConversationLLMConfig:
    """Shared OpenAI-compatible LLM knobs for the conversational agents.

    One group serves the router, answer, validation, and naming agents — they
    are lightweight classification/short-generation calls, so they do not need
    the per-agent tuning the pipeline stages have.
    """

    enabled: bool = False
    base_url: str = DEFAULT_LLM_BASE_URL
    model: str = DEFAULT_LLM_MODEL
    timeout_s: float = 30.0
    max_tokens: int = 1024

    @property
    def endpoint(self) -> str:
        return self.base_url.rstrip("/") + "/chat/completions"

    @classmethod
    def from_env(cls) -> "ConversationLLMConfig":
        return cls(
            enabled=env_bool("CONVERSATION_LLM_ENABLED", False),
            base_url=env_str("CONVERSATION_LLM_BASE_URL", DEFAULT_LLM_BASE_URL),
            model=env_str("CONVERSATION_LLM_MODEL", DEFAULT_LLM_MODEL),
            timeout_s=_env_float("CONVERSATION_LLM_TIMEOUT_S", 30.0),
            max_tokens=env_int("CONVERSATION_LLM_MAX_TOKENS", 1024),
        )


@dataclass(frozen=True)
class ConversationConfig:
    """Resolved configuration for one conversational turn."""

    llm: ConversationLLMConfig = ConversationLLMConfig()
    # Max re-extraction attempts when validation reports insufficient evidence.
    max_validation_iters: int = 2
    # Whether the router may pick the memory-grounded quick path at all.
    quick_answer_enabled: bool = True
    # How many prior turns to feed the router/answer agents (last-N).
    history_turns: int = 12
    # Where threads persist.
    db_path: str = ""

    @classmethod
    def from_env(cls) -> "ConversationConfig":
        return cls(
            llm=ConversationLLMConfig.from_env(),
            max_validation_iters=env_int(
                "ARIADNE_CONVERSATION_MAX_VALIDATION_ITERS", 2
            ),
            quick_answer_enabled=env_bool("CONVERSATION_QUICK_ANSWER", True),
            history_turns=env_int("CONVERSATION_HISTORY_TURNS", 12),
            db_path=str(conversation_db_path()),
        )
