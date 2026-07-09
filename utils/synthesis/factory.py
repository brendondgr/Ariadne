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
from .narrator import compose_narrative

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

    Claims are composed **deterministically** (grounded by construction, fast,
    and correct — nothing to fabricate). When the LLM is enabled, its role is the
    natural-language ``narrative`` via the dedicated prose narrator: reliable and
    cheap, where regenerating the full claims JSON over large evidence truncates.
    """
    config = config or SynthesisConfig.from_env()
    composer = composer or DeterministicComposer(config)
    # The chain runs as a LangGraph subgraph (compose → verify → narrate);
    # imported here because utils.orchestration imports this module.
    from utils.orchestration.agents.synthesis.graph import build_synthesis_graph

    graph = build_synthesis_graph(composer, config)
    out = graph.invoke({"evidence": evidence})
    return out["answer"]


def apply_llm_narrative(
    answer: SynthesizedAnswer, evidence: FederatedEvidence, config: SynthesisConfig
) -> None:
    """Best-effort: replace the narrative with an LLM-written prose answer.

    Runs only when the LLM is enabled and we don't already have a good LLM
    narrative (the claims composer's own ``final_answer`` when it succeeded).
    A dedicated small prose call is reliable where the full claims-JSON call
    truncates; on any failure the deterministic narrative is kept and the reason
    recorded.
    """
    if not config.llm_enabled:
        return
    if not answer.claims:
        # No grounded fact to narrate: keep the deterministic clarification
        # (an honest, actionable "couldn't find X — name it or give an id")
        # rather than let the model write prose over an empty evidence set.
        return
    if answer.composer == "llm" and answer.narrative.strip():
        return  # the claims composer already produced a fluent LLM answer
    try:
        answer.narrative = compose_narrative(evidence, config)
    except ComposerUnavailable as exc:
        logger.info("LLM narrator unavailable (%s); keeping deterministic answer", exc)
        answer.fallback_reason = answer.fallback_reason or f"LLM narrator unavailable ({exc})"
