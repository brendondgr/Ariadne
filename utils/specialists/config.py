#!/usr/bin/env python3
"""Configuration for the query specialists.

Every knob is read from the central ``.env`` through ``utils.config`` helpers,
mirroring ``utils.planner.config.PlannerConfig`` so the specialists connect to
exactly the same endpoints the planner probes and the loader writes to. The
source card's ``connection.uri`` is intentionally **not** used for connecting —
it is a stale enrichment default; the env is the connection source of truth.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from utils.config import endpoint_overrides, env_int, env_str
from utils.llm.config import LLMSettings, settings_from_legacy
from utils.llm.config import resolve as resolve_llm

# Mirror the planner/loader connection defaults (the live Docker stack).
DEFAULT_NEO4J_URI = "bolt://localhost:5456"
DEFAULT_NEO4J_USER = "neo4j"
DEFAULT_NEO4J_PASSWORD = "password"
DEFAULT_GREMLIN_URI = "ws://localhost:6455/gremlin"

DEFAULT_LLM_BASE_URL = "http://localhost:9090/v1"
DEFAULT_LLM_MODEL = "default-model"


def _env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class SpecialistConfig:
    """Resolved configuration for one specialist run."""

    data_dir: Path
    neo4j_uri: str = DEFAULT_NEO4J_URI
    neo4j_user: str = DEFAULT_NEO4J_USER
    neo4j_password: str = DEFAULT_NEO4J_PASSWORD
    gremlin_uri: str = DEFAULT_GREMLIN_URI
    # Hard ceiling applied on top of the per-task card limit (belt-and-suspenders).
    max_result_rows: int = 1000
    query_timeout_ms: int = 5000
    # Capped redraft loop: how many times a rejected draft may be revised.
    max_retries: int = 2
    # Page size for the `expand` primitive: how many facet members one page
    # returns. Larger pages fetch more per call; smaller pages page more often.
    # Left as a knob pending the product decision on paging policy (plan §2).
    expand_page_size: int = 50
    # Optional LLM seam (off by default; deterministic building always works).
    llm_enabled: bool = False
    # Whether a language model writes the query STRING, rather than a template
    # being filled. Deliberately NOT folded into `llm_enabled`: that flag is
    # already set true by Arms B, C, F and H to mean "LLM drafter / LLM
    # synthesis", and it sat unread by any builder. Consuming it here would have
    # silently swapped the query builder under four committed arms and
    # invalidated the whole arm table. This is the C-012 baseline's switch and
    # nothing else reads it.
    llm_query_builder: bool = False
    llm_base_url: str = DEFAULT_LLM_BASE_URL
    llm_model: str = DEFAULT_LLM_MODEL
    llm_timeout_s: float = 30.0
    llm_max_tokens: int = 2048

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
        if backend == "neo4j":
            return self.neo4j_uri
        if backend == "gremlin":
            return self.gremlin_uri
        raise ValueError(f"Unknown backend: {backend!r}")

    @classmethod
    def from_env(cls, data_dir: str | Path | None = None) -> "SpecialistConfig":
        if data_dir is None:
            data_dir = env_str("ARIADNE_DATA_DIR", "data")
        llm = resolve_llm(
            "specialist",
            defaults=LLMSettings(
                base_url=DEFAULT_LLM_BASE_URL, model=DEFAULT_LLM_MODEL,
                timeout_s=30.0, max_tokens=2048,
            ),
        )
        return cls(
            data_dir=Path(data_dir),
            neo4j_uri=env_str("NEO4J_URI", DEFAULT_NEO4J_URI),
            neo4j_user=env_str("NEO4J_USER", DEFAULT_NEO4J_USER),
            neo4j_password=env_str("NEO4J_PASSWORD", DEFAULT_NEO4J_PASSWORD),
            gremlin_uri=env_str("GREMLIN_URI", DEFAULT_GREMLIN_URI),
            max_result_rows=env_int("SPECIALIST_MAX_RESULT_ROWS", 1000),
            query_timeout_ms=env_int("SPECIALIST_QUERY_TIMEOUT_MS", 5000),
            max_retries=env_int("SPECIALIST_MAX_RETRIES", 2),
            expand_page_size=env_int("SPECIALIST_EXPAND_PAGE_SIZE", 50),
            llm_enabled=llm.enabled,
            llm_query_builder=os.environ.get(
                "SPECIALIST_LLM_QUERY_BUILDER", ""
            ).strip().lower() in {"1", "true", "yes", "on"},
            llm_base_url=llm.base_url,
            llm_model=llm.model,
            llm_timeout_s=llm.timeout_s,
            llm_max_tokens=llm.max_tokens,
        )

    def llm_settings(self) -> LLMSettings:
        """Transport settings for this config (adds provider + credentials)."""
        return settings_from_legacy(self, "specialist")
