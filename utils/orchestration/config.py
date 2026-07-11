#!/usr/bin/env python3
"""Configuration for the LangGraph orchestration layer.

Every knob is env-driven (``ORCH_*``) with documented defaults, mirroring the
planner/specialist/synthesis config idiom. The pipeline deadline stays with
``PIPELINE_TIMEOUT_S`` (read in ``utils.specialists.pipeline``) so the
orchestration layer does not fork that contract.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from utils.config import env_int, env_str

# LangGraph's default recursion limit (25) is too small for the specialist
# loop on multi-hop plans plus the planner's revise cycle; each loop step is
# one "superstep". Generous, but still a hard stop against runaway cycles.
DEFAULT_RECURSION_LIMIT = 200

# The iterative retrieval loop is gated behind this hop cap. ``1`` reproduces
# the historical plan-once-then-execute behavior exactly (a single specialist
# pass, no re-plan); raise it to enable the assess → re-plan → specialists
# cycle. It is a hard termination guard alongside ``PIPELINE_TIMEOUT_S`` and
# ``recursion_limit``.
DEFAULT_MAX_HOPS = 1

# Sufficiency-judge mode for the ``assess`` node. ``deterministic`` uses the
# join-closure + novelty predicate (keeps the LLM-off build reproducible);
# ``llm`` opts into an LLM "what's missing" critic that falls back to the
# deterministic judge when the LLM is unavailable.
VALID_ASSESS_MODES = ("deterministic", "llm")
DEFAULT_ASSESS_MODE = "deterministic"


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class OrchestrationConfig:
    """Resolved configuration for compiling/running the orchestration graphs."""

    # Compile the super-graph with an in-memory checkpointer (one thread per
    # query run). Off by default: Ariadne queries are request-scoped and the
    # checkpointer only helps interactive graph debugging / time travel.
    checkpointer: bool = False
    # Passed as the run config's recursion_limit for every graph invocation.
    recursion_limit: int = DEFAULT_RECURSION_LIMIT
    # Hard cap on assess → re-plan → specialists iterations. ``1`` disables the
    # loop (single pass); the assess node forces sufficiency once ``hop`` hits
    # this cap so the loop always terminates.
    max_hops: int = DEFAULT_MAX_HOPS
    # Sufficiency-judge mode: "deterministic" (default) or "llm".
    assess_mode: str = DEFAULT_ASSESS_MODE

    @classmethod
    def from_env(cls) -> "OrchestrationConfig":
        return cls(
            checkpointer=_env_flag("ORCH_CHECKPOINTER"),
            recursion_limit=env_int("ORCH_RECURSION_LIMIT", DEFAULT_RECURSION_LIMIT),
            max_hops=_resolve_max_hops(env_int("ORCH_MAX_HOPS", DEFAULT_MAX_HOPS)),
            assess_mode=_resolve_assess_mode(env_str("ORCH_ASSESS_MODE", DEFAULT_ASSESS_MODE)),
        )


def _resolve_max_hops(value: int) -> int:
    """Clamp the hop cap to at least 1 (a zero/negative cap would deadlock)."""
    return value if value >= 1 else DEFAULT_MAX_HOPS


def _resolve_assess_mode(value: str) -> str:
    """Fall back to the deterministic judge for any unrecognized mode."""
    mode = value.strip().lower()
    return mode if mode in VALID_ASSESS_MODES else DEFAULT_ASSESS_MODE
