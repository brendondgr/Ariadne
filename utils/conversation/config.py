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
from dataclasses import dataclass, replace
from pathlib import Path

from utils.config import data_dir, env_bool, env_int, env_str
from utils.llm.config import LLMSettings, settings_from_legacy
from utils.llm.config import resolve as resolve_llm

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
    #: Reasoning-token cap. 0 means "send no cap"; a positive value must stay
    #: below ``max_tokens`` or the model spends its whole allowance thinking and
    #: returns empty content.
    thinking_budget: int = 0

    # The bridge in utils.llm.config reads the ``llm_*`` spelling every other
    # stage's config uses. This group predates that convention and names its
    # fields bare, so the aliases below let one helper serve all five.
    @property
    def llm_enabled(self) -> bool:
        return self.enabled

    @property
    def llm_base_url(self) -> str:
        return self.base_url

    @property
    def llm_model(self) -> str:
        return self.model

    @property
    def llm_timeout_s(self) -> float:
        return self.timeout_s

    @property
    def llm_max_tokens(self) -> int:
        return self.max_tokens

    @property
    def llm_thinking_budget(self) -> int:
        return self.thinking_budget

    @property
    def endpoint(self) -> str:
        return self.base_url.rstrip("/") + "/chat/completions"

    @classmethod
    def from_env(cls) -> "ConversationLLMConfig":
        # This group used to chain CONVERSATION_LLM_* -> SYNTHESIS_LLM_* by hand,
        # which is how the chat pane ended up configured by a field labelled
        # "synthesis" in a settings modal that did not list the conversation
        # layer at all. The chain now goes through utils.llm like every other
        # stage: CONVERSATION_LLM_* -> ARIADNE_LLM_* -> the built-in default.
        #
        # SYNTHESIS_LLM_* survives as the *default* rather than as a link in the
        # lookup chain, which is the compatibility case that matters: an existing
        # .env that sets only the synthesis group resolves exactly as it did.
        # Once ARIADNE_LLM_* is set it wins over synthesis here, and that is
        # deliberate -- conversation is its own stage, and following another
        # stage's override was the hack that made the chat pane configurable
        # only through a field labelled "synthesis". An operator who genuinely
        # wants the two on one endpoint sets the primary group, and the modal
        # shows synthesis as "custom" so the override is visible rather than
        # inferred.
        synthesis = resolve_llm(
            "synthesis",
            defaults=LLMSettings(
                base_url=DEFAULT_LLM_BASE_URL, model=DEFAULT_LLM_MODEL,
                timeout_s=30.0, max_tokens=1024,
            ),
        )
        llm = resolve_llm("conversation", defaults=synthesis)
        return cls(
            enabled=env_bool("CONVERSATION_LLM_ENABLED", False),
            base_url=llm.base_url,
            model=llm.model,
            timeout_s=llm.timeout_s,
            # Inherit the synthesis output budget (like base_url/model/timeout)
            # so the answer agent honors the single max-tokens knob the operator
            # already raised. Without this fallback the visible answer stays
            # pinned at 1024 no matter what SYNTHESIS_LLM_MAX_TOKENS is set to,
            # and long replies get chopped mid-sentence. CONVERSATION_LLM_MAX_TOKENS
            # still overrides when an operator wants a distinct answer budget.
            max_tokens=llm.max_tokens,
            thinking_budget=llm.thinking_budget,
        )

    def llm_settings(self) -> LLMSettings:
        """Transport settings for this config (adds provider + credentials)."""
        return settings_from_legacy(self, "conversation")


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

    def with_llm_enabled(self, enabled: bool) -> "ConversationConfig":
        """Return a copy with the conversation LLM turned on when ``enabled``.

        The workbench's drafter toggle (``drafter == "llm"``) drives the whole
        agentic flow: when a turn uses the LLM, the orchestration (reference
        resolution), router (quick-vs-graph), and answer agents use it too —
        reusing the inherited endpoint. An explicit ``CONVERSATION_LLM_ENABLED``
        stays on regardless. Deterministic turns keep the reproducible path.
        """
        if enabled and not self.llm.enabled:
            return replace(self, llm=replace(self.llm, enabled=True))
        return self
