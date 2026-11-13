"""One place for every path, port, sample size and threshold the kill tests use.

Values come from the environment (``.env`` via :func:`utils.config.load_env`)
with ``KILLTESTS_*`` overrides, so a smoke run and the full run differ only in
environment, never in code.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from utils.config import load_env

REPO = Path(__file__).resolve().parents[2]


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class KillTestConfig:
    out_dir: Path
    relay_url: str
    relay_models: tuple[str, ...]
    relay_concurrency: int
    relay_max_tokens: int
    decider_url: str
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    gremlin_uri: str
    # T1
    t1_neo4j_uri: str
    t1_gremlin_uri: str
    t1_questions: int
    # T2
    t2_top_anchors: int
    t2_max_interpretations: int
    t2_filter_floor: float
    # T3
    t3_entities: int
    t3_alpha: float
    t3_spi_labels: int
    smoke: bool
    seed: int = 20261113
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "KillTestConfig":
        load_env()
        smoke = _env("KILLTESTS_SMOKE", "0").strip().lower() in {"1", "true", "yes"}
        default_out = "logs/killtests-2026-11" + ("/smoke" if smoke else "")
        models = tuple(m.strip() for m in _env("KILLTESTS_MODELS", "default-model").split(",") if m.strip())
        return cls(
            out_dir=REPO / _env("KILLTESTS_OUT", default_out),
            relay_url=_env("KILLTESTS_RELAY_URL", "http://localhost:9090/v1"),
            relay_models=models,
            relay_concurrency=_env_int("KILLTESTS_CONCURRENCY", 32),
            relay_max_tokens=max(2048, _env_int("KILLTESTS_MAX_TOKENS", 4096)),
            decider_url=_env("KILLTESTS_DECIDER_URL", "http://localhost:7500"),
            neo4j_uri=_env("NEO4J_URI", "bolt://localhost:5456"),
            neo4j_user=_env("NEO4J_USER", "neo4j"),
            neo4j_password=_env("NEO4J_PASSWORD", ""),
            gremlin_uri=_env("GREMLIN_URI", "ws://localhost:6455/gremlin"),
            t1_neo4j_uri=_env("KILLTESTS_T1_NEO4J_URI", "bolt://localhost:5470"),
            t1_gremlin_uri=_env("KILLTESTS_T1_GREMLIN_URI", "ws://localhost:6470/gremlin"),
            t1_questions=_env_int("KILLTESTS_T1_QUESTIONS", 10 if smoke else 200),
            t2_top_anchors=_env_int("KILLTESTS_T2_TOP_ANCHORS", 5),
            t2_max_interpretations=_env_int("KILLTESTS_T2_MAX_INTERP", 40),
            t2_filter_floor=_env_float("KILLTESTS_T2_FILTER_FLOOR", 0.05),
            t3_entities=_env_int("KILLTESTS_T3_ENTITIES", 50 if smoke else 1000),
            t3_alpha=_env_float("KILLTESTS_T3_ALPHA", 0.10),
            t3_spi_labels=_env_int("KILLTESTS_T3_SPI_LABELS", 30),
            smoke=smoke,
        )


def get() -> KillTestConfig:
    return KillTestConfig.from_env()
