#!/usr/bin/env python3
"""A dataset that arrives with a source card resolves, validates and loads.

The four built-in names are what this repository builds itself. A graph
produced elsewhere in the same canonical contract — a Synapse
``export-ariadne`` directory — announces itself with a card and a schema that
declares its own labels, types and edge patterns. These tests pin that the
loader accepts such a directory on the card alone, rejects the same directory
without the card, and validates the load from the shipped schema rather than
from a MITRE rule set.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils.graph_loader.config import (
    LoaderConfig,
    discover_card_datasets,
    is_supported_dataset,
)
from utils.graph_loader.registry import LoaderResolutionError, resolve_dataset
from utils.graph_loader.validation.semantic import validate_semantic_graph

DATASET = "mygraph"

NODES = [
    {"id": "node-a", "label": "Treatment", "labels": ["Treatment"], "name": "Aspirin",
     "properties": {"aliases": ["ASA"], "evidence": [{"quote": "q"}]}},
    {"id": "node-b", "label": "Condition", "labels": ["Condition"], "name": "Headache",
     "properties": {}},
]
EDGES = [
    {"id": "rel-1", "type": "helps_with", "source_id": "node-a", "target_id": "node-b",
     "properties": {"confidence": {"aggregate": 0.9}}},
]
SCHEMA = {
    "schema_version": "1.0",
    "dataset": DATASET,
    "node_labels": ["Condition", "Treatment"],
    "relationship_types": ["helps_with"],
    "relationship_endpoints": [
        {"source": "Treatment", "type": "helps_with", "target": "Condition"},
    ],
    "allowed_edge_patterns": {"helps_with": [["Treatment", "Condition"]]},
    "node_properties": {},
}


def _write_external_fixture(tmp_path: Path, *, with_card: bool = True) -> LoaderConfig:
    data_dir = tmp_path / "data"
    canonical = data_dir / "graphs" / DATASET / "canonical"
    neo4j_dir = data_dir / "graphs" / DATASET / "exports" / "neo4j"
    gremlin_dir = data_dir / "graphs" / DATASET / "exports" / "gremlin"
    cards_dir = data_dir / "source_cards"
    for directory in (canonical, neo4j_dir, gremlin_dir, cards_dir):
        directory.mkdir(parents=True)

    (canonical / "nodes.jsonl").write_text(
        "".join(json.dumps(n) + "\n" for n in NODES), encoding="utf-8"
    )
    (canonical / "relationships.jsonl").write_text(
        "".join(json.dumps(e) + "\n" for e in EDGES), encoding="utf-8"
    )
    (canonical / "schema.json").write_text(json.dumps(SCHEMA), encoding="utf-8")

    prefix = f"data/graphs/{DATASET}"
    exports = {
        "neo4j": {
            "nodes_csv": f"{prefix}/exports/neo4j/nodes.csv",
            "relationships_csv": f"{prefix}/exports/neo4j/relationships.csv",
            "schema_cypher": f"{prefix}/exports/neo4j/schema.cypher",
            "constraints_cypher": f"{prefix}/exports/neo4j/constraints.cypher",
        },
        "gremlin": {
            "nodes_jsonl": f"{prefix}/exports/gremlin/nodes.jsonl",
            "relationships_jsonl": f"{prefix}/exports/gremlin/relationships.jsonl",
        },
    }
    for backend, files in exports.items():
        for rel_path in files.values():
            (tmp_path / rel_path).write_text("x\n", encoding="utf-8")

    manifest = {
        "build_timestamp": "2026-09-16T00:00:00+00:00",
        "dataset": DATASET,
        "schema_version": "1.0",
        "counts": {"nodes": 2, "relationships": 1,
                   "nodes_by_label": {"Condition": 1, "Treatment": 1},
                   "relationships_by_type": {"helps_with": 1}},
        "canonical": {
            "nodes_jsonl": f"{prefix}/canonical/nodes.jsonl",
            "relationships_jsonl": f"{prefix}/canonical/relationships.jsonl",
            "schema_json": f"{prefix}/canonical/schema.json",
        },
        "exports": exports,
    }
    (canonical / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    if with_card:
        card = {
            "dataset": DATASET,
            "canonical_manifest": f"{prefix}/canonical/manifest.json",
            "schema_version": "1.0",
            "runtime_backend": "neo4j",
            "node_labels": SCHEMA["node_labels"],
            "relationship_types": SCHEMA["relationship_types"],
            "node_properties": {},
            "canonical_dir": f"{prefix}/canonical",
            "exports": exports,
            "endpoints": {"neo4j": "", "gremlin": ""},
            "safety": {"allowed_edge_patterns": SCHEMA["allowed_edge_patterns"]},
            "identity": {"join_key": ["id"], "unique_backstop": "id"},
        }
        (cards_dir / f"{DATASET}.json").write_text(json.dumps(card), encoding="utf-8")
    # An overlay file is authoring convenience, never a dataset.
    (cards_dir / "overlays").mkdir()
    (cards_dir / "attack.overlay.json").write_text("{}", encoding="utf-8")
    return LoaderConfig(data_dir=data_dir)


def test_card_backed_dataset_is_discovered_and_supported(tmp_path: Path) -> None:
    config = _write_external_fixture(tmp_path)
    assert discover_card_datasets(config) == frozenset({DATASET})
    assert is_supported_dataset(DATASET, config)
    assert is_supported_dataset("MyGraph", config)
    assert is_supported_dataset("attack", config)  # built-ins never need a card
    assert not is_supported_dataset("nothing", config)


def test_card_backed_dataset_resolves_for_every_backend(tmp_path: Path) -> None:
    config = _write_external_fixture(tmp_path)
    target = resolve_dataset(DATASET, "neo4j", config)
    assert target.dataset == DATASET
    assert target.nodes_path.is_file() and target.schema_path.is_file()
    assert set(target.backends) == {"neo4j"}
    assert target.backends["neo4j"].export_files["constraints_cypher"].is_file()
    assert target.endpoints["neo4j"] == config.neo4j_uri

    both = resolve_dataset(DATASET, "verify", config)
    assert set(both.backends) == {"neo4j", "gremlin"}


def test_same_directory_without_a_card_is_rejected(tmp_path: Path) -> None:
    config = _write_external_fixture(tmp_path, with_card=False)
    with pytest.raises(LoaderResolutionError, match="no source card"):
        resolve_dataset(DATASET, "neo4j", config)


def test_semantic_validation_reads_the_shipped_schema() -> None:
    result = validate_semantic_graph(NODES, EDGES, schema=SCHEMA)
    assert result.valid, result.errors

    stray = dict(NODES[1], label="Symptom", labels=["Symptom"])
    result = validate_semantic_graph([NODES[0], stray], EDGES, schema=SCHEMA)
    assert any("Unknown node label 'Symptom'" in e for e in result.errors)

    reversed_edge = dict(EDGES[0], source_id="node-b", target_id="node-a")
    result = validate_semantic_graph(NODES, [reversed_edge], schema=SCHEMA)
    assert any("Illegal edge pattern Condition -[helps_with]-> Treatment" in e for e in result.errors)


def test_no_declared_endpoints_means_no_pattern_check() -> None:
    schema = {k: v for k, v in SCHEMA.items() if k != "relationship_endpoints"}
    reversed_edge = dict(EDGES[0], source_id="node-b", target_id="node-a")
    result = validate_semantic_graph(NODES, [reversed_edge], schema=schema)
    assert result.valid, result.errors

    unknown_type = dict(EDGES[0], type="cures")
    result = validate_semantic_graph(NODES, [unknown_type], schema=schema)
    assert any("Unknown relationship type 'cures'" in e for e in result.errors)


def test_attack_default_is_unchanged_without_a_dataset_key() -> None:
    """A schema with no ``dataset`` key still validates as ATT&CK, as before."""
    result = validate_semantic_graph(NODES, EDGES, schema={})
    assert any("Unknown node label 'Treatment'" in e for e in result.errors)
