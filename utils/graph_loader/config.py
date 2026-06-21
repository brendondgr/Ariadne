#!/usr/bin/env python3

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from utils.config import env_int, env_str

DEFAULT_NEO4J_URI = "bolt://localhost:5456"
DEFAULT_NEO4J_USER = "neo4j"
DEFAULT_NEO4J_PASSWORD = "password"
DEFAULT_GREMLIN_URI = "ws://localhost:6455/gremlin"

SUPPORTED_DATASETS = frozenset({"attack", "capec"})
LOAD_BACKENDS = frozenset({"neo4j", "gremlin"})
GRAPH_ACTIONS = frozenset({"neo4j", "gremlin", "all", "verify", "health"})

DEFAULT_BATCH_SIZE = 500
ADAPTER_VERSION = "0.1.0"


@dataclass(frozen=True)
class LoaderConfig:
    """Configuration for runtime graph loading."""

    data_dir: Path
    batch_size: int = DEFAULT_BATCH_SIZE
    neo4j_uri: str = DEFAULT_NEO4J_URI
    neo4j_user: str = DEFAULT_NEO4J_USER
    neo4j_password: str = DEFAULT_NEO4J_PASSWORD
    gremlin_uri: str = DEFAULT_GREMLIN_URI

    @classmethod
    def from_data_dir(cls, data_dir: str | Path | None = None) -> LoaderConfig:
        if data_dir is None:
            data_dir = env_str("ARIADNE_DATA_DIR", "data")
        root = Path(data_dir)
        return cls(
            data_dir=root,
            batch_size=env_int("ARIADNE_LOAD_BATCH_SIZE", DEFAULT_BATCH_SIZE),
            neo4j_uri=env_str("NEO4J_URI", DEFAULT_NEO4J_URI),
            neo4j_user=env_str("NEO4J_USER", DEFAULT_NEO4J_USER),
            neo4j_password=env_str("NEO4J_PASSWORD", DEFAULT_NEO4J_PASSWORD),
            gremlin_uri=env_str("GREMLIN_URI", DEFAULT_GREMLIN_URI),
        )

    def source_cards_dir(self) -> Path:
        return self.data_dir / "source_cards"

    def graphs_dir(self, dataset: str) -> Path:
        return self.data_dir / "graphs" / dataset

    def runtime_dir(self, dataset: str, backend: str) -> Path:
        return self.graphs_dir(dataset) / "runtime" / backend
