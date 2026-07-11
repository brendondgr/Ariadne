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


def union_sets(left: set, right: set) -> set:
    """Reducer: union two sets (idempotent accumulate for frontier/visited).

    Mirrors ``merge_dicts``: the iterative-retrieval loop returns only the
    delta of newly discovered join-keys/entities per hop, and this folds them
    into the running set without re-emitting the whole collection.
    """
    return set(left) | set(right)


class PipelineState(TypedDict, total=False):
    """State for the top-level Q/A super-graph."""

    # Inputs (set once at invocation).
    question: str
    mode: str  # "query" | "plan"
    use_llm: bool
    deadline: float  # time.monotonic() deadline for the whole run
    started_at: float  # time.monotonic() at run start (for total_ms)
    # The caller-owned PipelineRun, mutated at the same boundaries the
    # pre-LangGraph pipeline did (SSE reads run.timings mid-stream).
    run: Any

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

    # Iterative retrieval loop.
    #   ``hop`` — current iteration (0 on entry), incremented at each re-plan;
    #     the ``assess`` node forces sufficiency once it reaches ``max_hops``.
    #   ``frontier`` — union of ``(join_value, source)`` join-keys surfaced by
    #     specialists across all hops (the pool the re-planner chases).
    #   ``visited`` — union of ``(entity_id, source)`` records already
    #     retrieved, so a re-plan never re-queries a settled node.
    #   ``assessment`` — the last sufficiency verdict (an
    #     ``agents.assess.contracts.Assessment``; typed ``Any`` here to keep
    #     ``state`` free of a dependency on the assess package).
    hop: int
    frontier: Annotated[set[tuple[str, str]], union_sets]
    visited: Annotated[set[tuple[str, str]], union_sets]
    assessment: Any

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
    """State for the compose → verify → narrate synthesis subgraph.

    Verification runs *before* the best-effort LLM narrative, mirroring
    ``synthesize()``: the verifier gates claims; the narrator only rewrites
    the prose ``narrative`` on the already-verified answer.
    """

    evidence: FederatedEvidence
    draft: SynthesizedAnswer  # composed claims, pre-verification
    answer: SynthesizedAnswer  # verified answer (narrative applied last)
