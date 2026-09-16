#!/usr/bin/env python3

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from utils.config import env_int, env_str

DEFAULT_NEO4J_URI = "bolt://localhost:5456"
DEFAULT_NEO4J_USER = "neo4j"
DEFAULT_NEO4J_PASSWORD = "password"
DEFAULT_GREMLIN_URI = "ws://localhost:6455/gremlin"

#: ``merged`` is the C-015 counterfactual: both catalogues in one graph. It is a
#: real dataset with its own canonical artifacts and card, but it lives under
#: ``data-merged/`` and is only ever loaded with ``ARIADNE_DATA_DIR`` pointed
#: there, so listing it here cannot expose it to a default-configured run.
SUPPORTED_DATASETS = frozenset({"attack", "capec", "merged", "identity"})
LOAD_BACKENDS = frozenset({"neo4j", "gremlin"})
GRAPH_ACTIONS = frozenset({"neo4j", "gremlin", "all", "verify", "fixture-qa", "health"})

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


def discover_card_datasets(config: "LoaderConfig") -> frozenset[str]:
    """Every dataset that has a source card under ``<data_dir>/source_cards``.

    The four names in ``SUPPORTED_DATASETS`` are the ones this repository
    builds itself. A graph produced elsewhere in the same canonical contract
    (a Synapse ``export-ariadne`` directory, say) announces itself with a card,
    and that card is the whole registration: the planner already discovers
    sources this way (``utils.planner.cards.load_source_cards``), so the loader
    accepting the same set is what lets one copied directory become a source.
    """
    cards_dir = config.source_cards_dir()
    if not cards_dir.is_dir():
        return frozenset()
    return frozenset(
        path.stem.lower()
        for path in cards_dir.glob("*.json")
        if path.is_file() and not path.name.endswith(".overlay.json")
    )


def is_supported_dataset(dataset: str, config: "LoaderConfig") -> bool:
    """True for a built-in dataset or any dataset with a source card on disk."""
    name = dataset.lower().strip()
    return name in SUPPORTED_DATASETS or name in discover_card_datasets(config)
