#!/usr/bin/env python3
"""Composer selection — the hybrid wiring, plus the one-call synthesis entry.

Mirrors the planner's drafter factory: when the LLM is enabled, a
``HybridComposer`` tries the OpenAI-compatible endpoint and falls back to the
deterministic composer whenever it is unavailable, recording the fallback
reason on the answer. Either way, ``synthesize`` runs the deterministic
``verify_answer`` pass over whatever was drafted — the verifier is not
optional and does not care which composer wrote the draft.
"""

from __future__ import annotations

import logging
from typing import Protocol

from utils.specialists.federation import FederatedEvidence

from .composer import DeterministicComposer
from .config import SynthesisConfig
from .contracts import SynthesizedAnswer
from .llm_composer import ComposerUnavailable, OpenAICompatibleComposer
from .verifier import verify_answer

logger = logging.getLogger("ariadne.synthesis.factory")


class AnswerComposer(Protocol):
    """Anything that drafts a ``SynthesizedAnswer`` from federated evidence."""

    name: str

    def compose(self, evidence: FederatedEvidence) -> SynthesizedAnswer: ...


class HybridComposer:
    """Tries a primary composer, falling back to a secondary on failure."""

    name = "hybrid"

    def __init__(self, primary: AnswerComposer, fallback: AnswerComposer) -> None:
        self._primary = primary
        self._fallback = fallback
        self.last_used: str = ""

    def compose(self, evidence: FederatedEvidence) -> SynthesizedAnswer:
        try:
            answer = self._primary.compose(evidence)
            self.last_used = self._primary.name
            return answer
        except ComposerUnavailable as exc:
            logger.info(
                "LLM composer unavailable (%s); using deterministic fallback", exc
            )
            answer = self._fallback.compose(evidence)
            self.last_used = self._fallback.name
            answer.fallback_reason = f"LLM composer unavailable ({exc})"
            return answer


def select_composer(config: SynthesisConfig) -> AnswerComposer:
    """Return the configured composer (hybrid LLM when enabled, else deterministic)."""
    deterministic = DeterministicComposer(config)
    if config.llm_enabled:
        logger.info(
            "LLM composer enabled: %s (model=%s)", config.llm_base_url, config.llm_model
        )
        return HybridComposer(OpenAICompatibleComposer(config), deterministic)
    return deterministic


def synthesize(
    evidence: FederatedEvidence,
    config: SynthesisConfig | None = None,
    *,
    composer: AnswerComposer | None = None,
) -> SynthesizedAnswer:
    """Draft and verify the final answer — the single entry point.

    The returned answer always carries a ``VerificationReport``; unsupported
    claims are already flagged and excluded from ``rendered_claims()``, and
    abstentions are enforced against the evidence.
    """
    config = config or SynthesisConfig.from_env()
    composer = composer or select_composer(config)
    return verify_answer(composer.compose(evidence), evidence)
