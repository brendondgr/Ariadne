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
from utils.llm.config import LLMSettings, settings_from_legacy
from utils.llm.config import resolve as resolve_llm

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
    # Whether that 0 was *chosen*. Both "no reasoning" and "nobody configured a
    # cap" are the integer 0, and they are not the same request: omitting the
    # key cost 11.27 s and 313 completion tokens where an explicit 0 cost 1.28 s
    # and 31. Only a caller that means it sets this; `from_env` never does, so
    # every recorded arm keeps sending what it sent.
    llm_thinking_budget_explicit: bool = False
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

    # --- LLM claims composer (Q20) -----------------------------------------
    # `llm_enabled` has always meant "let a model write the *narrative prose*
    # over already-verified claims". It must keep meaning exactly that, because
    # arms `llm` and `gold_llm` set it and every figure C-002, C-005 and C-006
    # rest on was measured with it true.
    #
    # This flag is the separate switch that lets a model *propose the claims
    # themselves*, via `OpenAICompatibleComposer`. It defaults False, so no
    # recorded arm moves; EXP-2026-08-018 turns it on to answer Q20 -- whether
    # the verifier's gates do anything once something can construct a claim that
    # violates them.
    llm_claims: bool = False

    def thinking_budget(self) -> int:
        """The reasoning-token cap to send. 0 means "send no cap".

        This used to return ``llm_max_tokens // 2`` when unset, which made the
        budget move whenever the token cap moved and gave the project a third
        source of truth for one number (the others being the global
        ``LLM_THINKING_BUDGET`` and this field). A default that changes in
        response to an unrelated field is not a default, so the derivation is
        gone: the value is whatever ``ARIADNE_LLM_THINKING_BUDGET`` or
        ``SYNTHESIS_LLM_THINKING_BUDGET`` says, and 0 -- which is what every run
        predating the cap sent -- means no cap at all.

        BEHAVIOUR CHANGE: a deployment that set ``SYNTHESIS_LLM_MAX_TOKENS`` and
        left the budget unset previously got half of it implicitly and now gets
        no cap. Set the budget explicitly to keep one.
        """
        return self.llm_thinking_budget

    @classmethod
    def from_env(cls) -> "SynthesisConfig":
        """Build a config from the environment with documented fallbacks."""
        llm = resolve_llm(
            "synthesis",
            defaults=LLMSettings(
                base_url=DEFAULT_LLM_BASE_URL, model=DEFAULT_LLM_MODEL,
                timeout_s=30.0, max_tokens=4096,
            ),
        )
        return cls(
            llm_enabled=llm.enabled,
            llm_base_url=llm.base_url,
            llm_model=llm.model,
            llm_timeout_s=llm.timeout_s,
            llm_max_tokens=llm.max_tokens,
            llm_thinking_budget=llm.thinking_budget,
            max_citations=env_int("SYNTHESIS_MAX_CITATIONS", 8),
            gate_cited=env_bool("VERIFY_GATE_CITED", True),
            gate_resolvable=env_bool("VERIFY_GATE_RESOLVABLE", True),
            gate_grounded=env_bool("VERIFY_GATE_GROUNDED", True),
            gate_correlated=env_bool("VERIFY_GATE_CORRELATED", True),
            llm_claims=env_bool("SYNTHESIS_LLM_CLAIMS", False),
        )

    def llm_settings(self) -> LLMSettings:
        """Transport settings for this config (adds provider + credentials)."""
        return settings_from_legacy(self, "synthesis")

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
