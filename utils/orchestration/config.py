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

from utils.config import env_int

# LangGraph's default recursion limit (25) is too small for the specialist
# loop on multi-hop plans plus the planner's revise cycle; each loop step is
# one "superstep". Generous, but still a hard stop against runaway cycles.
DEFAULT_RECURSION_LIMIT = 200


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

    @classmethod
    def from_env(cls) -> "OrchestrationConfig":
        return cls(
            checkpointer=_env_flag("ORCH_CHECKPOINTER"),
            recursion_limit=env_int("ORCH_RECURSION_LIMIT", DEFAULT_RECURSION_LIMIT),
        )
