#!/usr/bin/env python3
"""Plan-level evaluation for the planning agent.

The planner is scored on its **plan output** — source-selection accuracy,
sub-question quality, unnecessary source calls, and schema adherence —
decoupled from whether downstream phases later succeed (briefing §6.1).
"""

from __future__ import annotations

from .corpus import ExpectedCase, load_corpus, run_case, run_corpus
from .scorer import CaseScore, aggregate, score_plan

__all__ = [
    "ExpectedCase",
    "load_corpus",
    "run_case",
    "run_corpus",
    "CaseScore",
    "score_plan",
    "aggregate",
]
