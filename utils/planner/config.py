#!/usr/bin/env python3
"""Configuration for the federated planning agent.

Every tunable knob is read from the environment through the central
``utils.config`` helpers so the planner honors the project's single ``.env``
file with sensible fallbacks. Real shell/CI env vars always win.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from utils.config import env_int, env_str

# Discovery / connection defaults mirror utils.graph_loader.config so the
# planner probes the same endpoints the loader writes to.
DEFAULT_NEO4J_URI = "bolt://localhost:5456"
DEFAULT_NEO4J_USER = "neo4j"
DEFAULT_NEO4J_PASSWORD = "password"
DEFAULT_GREMLIN_URI = "ws://localhost:6455/gremlin"

# Drafting defaults: the local OpenAI-compatible endpoint.
DEFAULT_LLM_BASE_URL = "http://localhost:9090/v1"
DEFAULT_LLM_MODEL = "default-model"


def _env_float(name: str, default: float) -> float:
    """Return a float env var, falling back to ``default`` when unset/invalid."""
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class PlannerConfig:
    """Resolved configuration for one planning run."""

    data_dir: Path
    # Discovery / liveness.
    neo4j_uri: str = DEFAULT_NEO4J_URI
    neo4j_user: str = DEFAULT_NEO4J_USER
    neo4j_password: str = DEFAULT_NEO4J_PASSWORD
    gremlin_uri: str = DEFAULT_GREMLIN_URI
    probe_timeout_s: float = 4.0
    cache_ttl_s: float = 5.0
    # A live graph must hold at least this many nodes to count as "loaded"
    # (a bare connect is not enough — see briefing §2.2 content probe).
    min_live_nodes: int = 1
    # Loop control.
    max_iterations: int = 3
    # LLM drafter (OpenAI-compatible). Disabled by default; the deterministic
    # drafter is always the fallback.
    llm_enabled: bool = False
    llm_base_url: str = DEFAULT_LLM_BASE_URL
    llm_model: str = DEFAULT_LLM_MODEL
    llm_timeout_s: float = 30.0

    def source_cards_dir(self) -> Path:
        return self.data_dir / "source_cards"

    def endpoint_for(self, backend: str) -> str:
        """Return the configured endpoint URI for a runtime backend."""
        if backend == "neo4j":
            return self.neo4j_uri
        if backend == "gremlin":
            return self.gremlin_uri
        raise ValueError(f"Unknown backend: {backend!r}")

    @classmethod
    def from_env(cls, data_dir: str | Path | None = None) -> "PlannerConfig":
        """Build a config from the environment with documented fallbacks."""
        if data_dir is None:
            data_dir = env_str("ARIADNE_DATA_DIR", "data")
        # PLANNER_LLM_ENABLED controls whether the LLM drafter is even tried;
        # we treat the common truthy spellings as enabled.
        llm_enabled = os.environ.get("PLANNER_LLM_ENABLED", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        return cls(
            data_dir=Path(data_dir),
            neo4j_uri=env_str("NEO4J_URI", DEFAULT_NEO4J_URI),
            neo4j_user=env_str("NEO4J_USER", DEFAULT_NEO4J_USER),
            neo4j_password=env_str("NEO4J_PASSWORD", DEFAULT_NEO4J_PASSWORD),
            gremlin_uri=env_str("GREMLIN_URI", DEFAULT_GREMLIN_URI),
            probe_timeout_s=_env_float("PLANNER_PROBE_TIMEOUT_S", 4.0),
            cache_ttl_s=_env_float("PLANNER_CACHE_TTL_S", 5.0),
            min_live_nodes=env_int("PLANNER_MIN_LIVE_NODES", 1),
            max_iterations=env_int("PLANNER_MAX_ITERATIONS", 3),
            llm_enabled=llm_enabled,
            llm_base_url=env_str("PLANNER_LLM_BASE_URL", DEFAULT_LLM_BASE_URL),
            llm_model=env_str("PLANNER_LLM_MODEL", DEFAULT_LLM_MODEL),
            llm_timeout_s=_env_float("PLANNER_LLM_TIMEOUT_S", 30.0),
        )
