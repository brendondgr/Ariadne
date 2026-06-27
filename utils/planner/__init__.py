#!/usr/bin/env python3
"""Federated planning agent for Ariadne.

The planner reads source cards, learns which graphs are live, classifies an
analyst request, and emits a machine-readable plan (target sources,
sub-questions, join keys, traversal limits, unsupported parts). It routes; it
never queries. The model drafts the plan, but a fully deterministic
self-evaluation gate decides whether it ships.
"""

from __future__ import annotations

from .agent import PlanningAgent
from .cards import SourceCardView, load_source_cards
from .config import PlannerConfig
from .schema import Plan

__all__ = [
    "PlanningAgent",
    "PlannerConfig",
    "Plan",
    "SourceCardView",
    "load_source_cards",
]
