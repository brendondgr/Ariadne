#!/usr/bin/env python3
"""Configuration for the LLM evaluator (LLM-as-judge).

Mirrors the synthesis/planner/specialist pattern exactly: every knob reads from
the environment through ``utils.config`` helpers so the single ``.env`` file
governs it, with the LLM judge **disabled by default**. When it is off, the
deterministic proxy judge fills the same metric keys, so the LLM-off build
stays byte-reproducible; the "no metric depends on an LLM judge" invariant of
``utils.evaluation`` is preserved unless an operator opts in.
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
class EvalConfig:
    """Resolved configuration for one LLM-judge run."""

    # LLM judge (OpenAI-compatible). Disabled by default; the deterministic
    # proxy judge is always the fallback and always fills the same metric keys.
    llm_enabled: bool = False
    llm_base_url: str = DEFAULT_LLM_BASE_URL
    llm_model: str = DEFAULT_LLM_MODEL
    llm_timeout_s: float = 30.0
    llm_max_tokens: int = 1024
    # How many answers the LLM judge scores per run when enabled (the
    # deterministic proxy always covers every answer regardless of this cap).
    sample_size: int = 20
    # How many LLM judge calls run concurrently. The calls are independent HTTP
    # posts; the served model batches them, so real speedup is throughput-bound
    # (typically 3-5x at 8, not 8x). The report stays byte-identical — verdicts
    # are placed back by index regardless of completion order.
    judge_workers: int = 8

    @classmethod
    def from_env(cls) -> "EvalConfig":
        """Build a config from the environment with documented fallbacks."""
        llm_enabled = os.environ.get("EVAL_LLM_ENABLED", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        return cls(
            llm_enabled=llm_enabled,
            llm_base_url=env_str("EVAL_LLM_BASE_URL", DEFAULT_LLM_BASE_URL),
            llm_model=env_str("EVAL_LLM_MODEL", DEFAULT_LLM_MODEL),
            llm_timeout_s=_env_float("EVAL_LLM_TIMEOUT_S", 30.0),
            llm_max_tokens=env_int("EVAL_LLM_MAX_TOKENS", 1024),
            sample_size=env_int("EVAL_LLM_SAMPLE_SIZE", 20),
            judge_workers=env_int("EVAL_LLM_JUDGE_WORKERS", 8),
        )
