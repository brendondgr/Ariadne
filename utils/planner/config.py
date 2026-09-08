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

from utils.config import endpoint_overrides, env_int, env_str
from utils.llm.config import LLMSettings, settings_from_legacy
from utils.llm.config import resolve as resolve_llm

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
    # LLM intent classifier (same endpoint as the drafter). Disabled by default;
    # the deterministic classifier is always the fallback.
    intent_llm_enabled: bool = False
    # The hybrid rewrite stage. `rewrite_enabled` turns on the deterministic
    # fill and the canonical renderer; `rewrite_model_enabled` additionally lets
    # a model fill the slots the deterministic pass left unbound, choosing only
    # from candidate lists it cannot add to. Both default **off**: with them off
    # the pipeline is byte-identical to the shipped engine, which every step of
    # the 2026-09-08 plan re-proves against the captured reference.
    rewrite_enabled: bool = False
    rewrite_model_enabled: bool = False
    #: Where the model's picks are cached, keyed by prompt version, served model
    #: and question. Unset means the process default (see rewrite_cache.py).
    rewrite_cache_dir: str | None = None
    llm_base_url: str = DEFAULT_LLM_BASE_URL
    llm_model: str = DEFAULT_LLM_MODEL
    llm_timeout_s: float = 30.0
    # Generous default: the model is a reasoning model that spends tokens before
    # emitting the JSON plan, so the cap must cover reasoning + the plan.
    llm_max_tokens: int = 4096

    def source_cards_dir(self) -> Path:
        return self.data_dir / "source_cards"

    def endpoint_for(self, backend: str, dataset: str | None = None) -> str:
        """The URI for ``backend``, or for ``dataset`` when it names its own.

        ``dataset`` is what makes two sources on one backend addressable. Absent
        an ``ARIADNE_ENDPOINT_<DATASET>`` override this returns the backend-wide
        URI exactly as before, so every existing caller is unaffected.
        """
        if dataset:
            override = endpoint_overrides().get(str(dataset).lower())
            if override:
                return override
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
        _truthy = {"1", "true", "yes", "on"}
        intent_llm_enabled = (
            os.environ.get("PLANNER_INTENT_LLM_ENABLED", "").strip().lower() in _truthy
        )
        rewrite_enabled = os.environ.get("ARIADNE_REWRITE", "").strip().lower() in _truthy
        rewrite_model_enabled = (
            os.environ.get("ARIADNE_REWRITE_MODEL", "").strip().lower() in _truthy
        )
        # The LLM group resolves through utils.llm: PLANNER_LLM_* still wins when
        # set, but falls back to ARIADNE_LLM_* so one endpoint configures every
        # stage. With neither set this is exactly the previous default.
        llm = resolve_llm(
            "planner",
            defaults=LLMSettings(
                base_url=DEFAULT_LLM_BASE_URL, model=DEFAULT_LLM_MODEL,
                timeout_s=30.0, max_tokens=4096,
            ),
        )
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
            llm_enabled=llm.enabled,
            intent_llm_enabled=intent_llm_enabled,
            rewrite_enabled=rewrite_enabled,
            rewrite_model_enabled=rewrite_model_enabled,
            rewrite_cache_dir=env_str("ARIADNE_REWRITE_CACHE_DIR", "") or None,
            llm_base_url=llm.base_url,
            llm_model=llm.model,
            llm_timeout_s=llm.timeout_s,
            llm_max_tokens=llm.max_tokens,
        )

    def llm_settings(self) -> LLMSettings:
        """Transport settings for this config (adds provider + credentials)."""
        return settings_from_legacy(self, "planner")
