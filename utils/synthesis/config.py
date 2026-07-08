#!/usr/bin/env python3
"""Configuration for the synthesis agent.

Mirrors the planner/specialist pattern: every knob reads from the environment
through ``utils.config`` helpers so the single ``.env`` file governs it, with
the LLM composer disabled by default — the deterministic composer is always
the fallback, and the verifier runs regardless of which composer drafted.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from utils.config import env_int, env_str

DEFAULT_LLM_BASE_URL = "http://localhost:9090/v1"
DEFAULT_LLM_MODEL = "default-model"


def _env_float(name: str, default: float) -> float:
    """Return a float env var, falling back to ``default`` when unset/invalid."""
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class SynthesisConfig:
    """Resolved configuration for one synthesis run."""

    # LLM composer (OpenAI-compatible). Disabled by default; the deterministic
    # composer is always the fallback and the verifier gates both.
    llm_enabled: bool = False
    llm_base_url: str = DEFAULT_LLM_BASE_URL
    llm_model: str = DEFAULT_LLM_MODEL
    llm_timeout_s: float = 30.0
    llm_max_tokens: int = 8192
    # How many record citations a single claim may carry (mirrors the API's
    # inline-citation cap so answers stay readable).
    max_citations: int = 8

    @classmethod
    def from_env(cls) -> "SynthesisConfig":
        """Build a config from the environment with documented fallbacks."""
        llm_enabled = os.environ.get("SYNTHESIS_LLM_ENABLED", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        return cls(
            llm_enabled=llm_enabled,
            llm_base_url=env_str("SYNTHESIS_LLM_BASE_URL", DEFAULT_LLM_BASE_URL),
            llm_model=env_str("SYNTHESIS_LLM_MODEL", DEFAULT_LLM_MODEL),
            llm_timeout_s=_env_float("SYNTHESIS_LLM_TIMEOUT_S", 30.0),
            llm_max_tokens=env_int("SYNTHESIS_LLM_MAX_TOKENS", 4096),
            max_citations=env_int("SYNTHESIS_MAX_CITATIONS", 8),
        )
