#!/usr/bin/env python3
"""Drafter selection — the hybrid wiring.

When the LLM is enabled, the planner uses a ``HybridDrafter`` that tries the
OpenAI-compatible LLM and falls back to the deterministic drafter whenever the
endpoint is unavailable. When the LLM is disabled, the deterministic drafter is
used directly. Either way the deterministic gate (out of scope of the drafter)
decides whether the resulting plan ships.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .cards import SourceCardView
from .config import PlannerConfig
from .discovery import LiveSourceView
from .drafter import DeterministicDrafter, PlanDrafter
from .llm_drafter import DrafterUnavailable, OpenAICompatibleDrafter
from .schema import Plan

if TYPE_CHECKING:
    from .intent import IntentClassification

logger = logging.getLogger("ariadne.planner.drafter")


class HybridDrafter:
    """Tries a primary drafter, falling back to a secondary on failure."""

    def __init__(self, primary: PlanDrafter, fallback: PlanDrafter) -> None:
        self._primary = primary
        self._fallback = fallback
        self.last_used: str = ""

    def draft(
        self,
        request: str,
        cards: dict[str, SourceCardView],
        live_view: LiveSourceView,
        feedback: list[str] | None = None,
        intent: "IntentClassification | None" = None,
    ) -> Plan:
        try:
            plan = self._primary.draft(request, cards, live_view, feedback, intent)
            self.last_used = type(self._primary).__name__
        except DrafterUnavailable as exc:
            logger.info("LLM drafter unavailable (%s); using deterministic fallback", exc)
            plan = self._fallback.draft(request, cards, live_view, feedback, intent)
            self.last_used = type(self._fallback).__name__
            plan.assumptions.append(f"LLM drafter unavailable ({exc}); used deterministic fallback")
            return plan

        # Primary succeeded but routed nothing (e.g. the LLM marked a
        # definitional name question unsupported). The deterministic drafter is
        # the floor: if it can build sub-questions the primary missed, prefer
        # it. If it also routes nothing, keep the primary plan's reasons.
        if not plan.sub_questions:
            floor = self._fallback.draft(request, cards, live_view, feedback, intent)
            if floor.sub_questions:
                logger.info("primary drafter routed nothing; using deterministic floor")
                floor.assumptions.append(
                    "primary drafter routed nothing; used deterministic floor"
                )
                self.last_used = type(self._fallback).__name__
                return floor
        return plan


def select_drafter(config: PlannerConfig) -> PlanDrafter:
    """Return the configured drafter (hybrid LLM when enabled, else deterministic)."""
    deterministic = DeterministicDrafter()
    if config.llm_enabled:
        logger.info(
            "LLM drafter enabled: %s (model=%s)", config.llm_base_url, config.llm_model
        )
        return HybridDrafter(OpenAICompatibleDrafter(config), deterministic)
    return deterministic
