#!/usr/bin/env python3
"""Shared LangGraph state schemas for the orchestration graphs.

The state *wraps* the existing frozen contracts — ``utils.planner.schema.Plan``,
``utils.specialists.contracts.SpecialistResult``,
``utils.specialists.federation.FederatedEvidence``,
``utils.synthesis.contracts.SynthesizedAnswer`` — rather than redefining them.
Ninety-eight test modules and the SSE ``to_dict()`` JSON contracts depend on
those shapes; the graph state is only the envelope they travel in.

Three schemas, one per graph:

* ``PipelineState`` — the super-graph (probe → plan → specialists → bundle →
  synthesize). Specialist results/skips/sequencing/timings accumulate via
  ``operator.add`` reducers so each loop iteration returns only its delta.
* ``PlanningState`` — the planner subgraph's draft → gate → revise/degrade
  loop (trace accumulates; feedback/iteration are overwritten per cycle).
* ``SynthesisState`` — the synthesis subgraph's compose → narrate → verify
  chain (plain overwrite semantics; each node hands the answer forward).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from utils.planner.discovery import LiveSourceView
from utils.planner.schema import Plan
from utils.specialists.contracts import SpecialistResult
from utils.specialists.federation import FederatedEvidence
from utils.synthesis.contracts import SynthesizedAnswer


def merge_dicts(left: dict, right: dict) -> dict:
    """Reducer: shallow-merge dict updates (later keys win)."""
    return {**left, **right}


class PipelineState(TypedDict, total=False):
    """State for the top-level Q/A super-graph."""

    # Inputs (set once at invocation).
    question: str
    mode: str  # "query" | "plan"
    use_llm: bool
    deadline: float  # time.monotonic() deadline for the whole run
    started_at: float  # time.monotonic() at run start (for total_ms)

    # Probe / plan stages (overwrite).
    live_view: LiveSourceView
    plan: Plan

    # Specialist loop (accumulate per iteration).
    results: Annotated[list[SpecialistResult], operator.add]
    skipped: Annotated[list[dict[str, Any]], operator.add]
    sequencing: Annotated[list[dict[str, Any]], operator.add]
    specialist_timings: Annotated[list[dict[str, Any]], operator.add]
    by_id: Annotated[dict[str, SpecialistResult], merge_dicts]
    cursor: int  # index of the next sub-question in execution order

    # Bundle / synthesis / outcome (overwrite).
    evidence: FederatedEvidence
    answer: SynthesizedAnswer
    status: str
    exit_code: int
    timings: Annotated[dict[str, Any], merge_dicts]


class PlanningState(TypedDict, total=False):
    """State for the planner's draft → gate → revise/degrade subgraph."""

    request: str
    live_view: LiveSourceView
    iteration: int
    feedback: list[str] | None
    last_plan: Plan | None
    drafter_used: str
    gate_ok: bool
    trace: Annotated[list[dict], operator.add]
    plan: Plan  # the final (converged or degraded) plan


class SynthesisState(TypedDict, total=False):
    """State for the compose → narrate → verify synthesis subgraph."""

    evidence: FederatedEvidence
    draft: SynthesizedAnswer  # composed claims, pre-verification
    narrative: str | None  # LLM prose (None when disabled/unavailable)
    narrative_fallback: str | None  # reason the narrator was skipped/failed
    answer: SynthesizedAnswer  # the verified final answer
