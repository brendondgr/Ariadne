#!/usr/bin/env python3
"""Shared LangGraph state for the conversational orchestration graph.

Like ``utils.orchestration.state``, this schema *wraps* the existing frozen
contracts (``Plan``, ``SynthesizedAnswer``, ``FederatedEvidence``) rather than
redefining them — the conversation graph is only the envelope they travel in.

The graph flow the state supports:

    Orchestration (resolve references from memory)
      -> Router (quick vs graph)
          -> quick:  Answer (memory-grounded) -> END
          -> graph:  Graph Extraction -> Validation
                        -> insufficient & under cap: back to Graph Extraction
                        -> sufficient (or cap):       Answer (final) -> END
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from utils.specialists.federation import FederatedEvidence
from utils.synthesis.contracts import SynthesizedAnswer


class ConversationState(TypedDict, total=False):
    """State for one conversational turn through the orchestration graph."""

    # -- inputs (set once at invocation) ---------------------------------
    question: str  # the raw user message for this turn
    # Prior turns, oldest first: {"role": "user"|"assistant", "content": str,
    # "facts": list[str] (verified facts from an assistant turn, optional)}.
    history: list[dict[str, Any]]
    conversation_id: str
    mode: str  # "query" | "plan"
    use_llm: bool
    deadline: float  # time.monotonic() deadline for the whole turn
    started_at: float  # time.monotonic() at turn start
    run: Any  # caller-owned PipelineRun reused by graph extraction

    # -- orchestration (reference resolution) ----------------------------
    # The user message rewritten into a standalone question using memory,
    # e.g. "tell me more about T1598" -> "Provide details on ATT&CK technique
    # T1598 (Phishing for Information)".
    resolved_question: str

    # -- router (redirect decision) --------------------------------------
    route: str  # "quick" | "graph"
    route_reason: str

    # -- graph extraction (wraps the existing pipeline) ------------------
    # Extra hints fed back into extraction when validation asks for a retry
    # (e.g. {"focus": ["mitigations for T1598"], "reason": "..."}).
    extraction_params: dict[str, Any]
    live_view: Any
    plan: Any
    evidence: FederatedEvidence
    answer: SynthesizedAnswer  # the grounded synthesis result

    # -- validation (sufficiency gate + bounded retry) -------------------
    validation_iterations: int  # completed extraction attempts
    validation_verdict: str  # "pass" | "insufficient"
    validation_reason: str
    validation_missing: list[str]

    # -- answer (final conversational reply) -----------------------------
    final_answer: str
    final: dict[str, Any]  # assembled payload emitted as the `final` event
    status: str
    exit_code: int

    # -- trace (accumulated across nodes) --------------------------------
    trace: Annotated[list[dict[str, Any]], operator.add]
