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

from utils.config import env_bool, env_int, env_str

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
    # Cap on the reasoning model's *thinking* tokens (server-side
    # ``thinking_token_budget``). skynet is a reasoning model: uncapped, it can
    # spend the whole ``llm_max_tokens`` budget thinking and return empty content
    # (the "raise max_tokens?" fallback). Capping thinking reserves the rest for
    # the actual answer. 0 means "derive as half of llm_max_tokens".
    llm_thinking_budget: int = 0
    # How many record citations a single claim may carry (mirrors the API's
    # inline-citation cap so answers stay readable).
    max_citations: int = 8

    # --- Verifier gates -----------------------------------------------------
    # The four predicates in `_verify_claim`, individually disableable so the
    # verifier can be ablated (EXP-2026-08-014). **All four default to True and
    # must stay that way**: the default path is the one every committed figure
    # was measured on, and a flag that flips a default silently invalidates the
    # recorded answers. Disabling one does not delete the check's *reasons* —
    # it stops them turning a claim `unsupported`, so the ablation can count
    # exactly what each gate cuts and inspect what it would have said.
    gate_cited: bool = True          # a claim must carry at least one citation
    gate_resolvable: bool = True     # each citation must resolve to a retrieved record
    gate_grounded: bool = True       # each entity id must appear in the cited records
    gate_correlated: bool = True     # a correlation must be backed by the join index

    def thinking_budget(self) -> int:
        """The reasoning-token cap to send, deriving half of max_tokens if unset."""
        return self.llm_thinking_budget or (self.llm_max_tokens // 2)

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
            llm_thinking_budget=env_int("SYNTHESIS_LLM_THINKING_BUDGET", 0),
            max_citations=env_int("SYNTHESIS_MAX_CITATIONS", 8),
            gate_cited=env_bool("VERIFY_GATE_CITED", True),
            gate_resolvable=env_bool("VERIFY_GATE_RESOLVABLE", True),
            gate_grounded=env_bool("VERIFY_GATE_GROUNDED", True),
            gate_correlated=env_bool("VERIFY_GATE_CORRELATED", True),
        )

    def gates_all_on(self) -> bool:
        """True when no gate is ablated — the condition every figure assumes."""
        return all(
            (self.gate_cited, self.gate_resolvable, self.gate_grounded, self.gate_correlated)
        )

    def disabled_gates(self) -> tuple[str, ...]:
        """The ablated gate names, for the run manifest."""
        return tuple(
            name
            for name, on in (
                ("cited", self.gate_cited),
                ("resolvable", self.gate_resolvable),
                ("grounded", self.gate_grounded),
                ("correlated", self.gate_correlated),
            )
            if not on
        )
