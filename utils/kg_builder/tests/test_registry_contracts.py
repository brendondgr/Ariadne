#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path

from utils.kg_builder.config import BuildConfig
from utils.kg_builder.main import KGBuildRunner
from utils.kg_builder.registry import (
    build_attack_source_card,
    build_capec_source_card,
    write_attack_source_card,
    write_capec_source_card,
)


def test_attack_source_card_resolves_manifest_and_exports(tmp_path: Path) -> None:
    config = BuildConfig.from_data_dir(tmp_path)
    paths = config.paths()

    canonical_dir = paths.graph_canonical_dir
    canonical_dir.mkdir(parents=True)
    manifest = {
        "schema_version": "1.0",
        "canonical": {
            "nodes_jsonl": str(canonical_dir / "nodes.jsonl"),
            "relationships_jsonl": str(canonical_dir / "relationships.jsonl"),
            "schema_json": str(canonical_dir / "schema.json"),
        },
        "exports": {
            "neo4j": {"nodes_csv": str(paths.graph_neo4j_export_dir / "nodes.csv")},
            "gremlin": {"nodes_jsonl": str(paths.graph_gremlin_export_dir / "nodes.jsonl")},
        },
    }
    manifest_path = canonical_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    schema = {
        "schema_version": "1.0",
        "node_labels": ["Technique", "Tactic"],
        "relationship_types": ["USES"],
    }
    with open(canonical_dir / "schema.json", "w", encoding="utf-8") as f:
        json.dump(schema, f)

    card = build_attack_source_card(config, manifest_path)
    assert card.dataset == "attack"
    assert card.runtime_backend == "neo4j"
    assert card.schema_version == "1.0"
    assert "Technique" in card.node_labels
    assert card.exports["gremlin"]["nodes_jsonl"].endswith("nodes.jsonl")

    card_path = write_attack_source_card(config, manifest_path)
    assert card_path.exists()


def test_capec_source_card_resolves_manifest_and_exports(tmp_path: Path) -> None:
    config = BuildConfig.from_data_dir(tmp_path)
    paths = config.paths()

    canonical_dir = paths.capec_graph_canonical_dir
    canonical_dir.mkdir(parents=True)
    manifest = {
        "schema_version": "1.0",
        "exports": {
            "neo4j": {"nodes_csv": str(paths.capec_graph_neo4j_export_dir / "nodes.csv")},
            "gremlin": {"nodes_jsonl": str(paths.capec_graph_gremlin_export_dir / "nodes.jsonl")},
        },
    }
    manifest_path = canonical_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    schema = {
        "schema_version": "1.0",
        "dataset": "capec",
        "node_labels": ["AttackPattern", "Category"],
        "relationship_types": ["ChildOf", "MAPS_TO"],
    }
    with open(canonical_dir / "schema.json", "w", encoding="utf-8") as f:
        json.dump(schema, f)

    card = build_capec_source_card(config, manifest_path)
    assert card.dataset == "capec"
    assert card.runtime_backend == "gremlin"
    assert "AttackPattern" in card.node_labels

    card_path = write_capec_source_card(config, manifest_path)
    assert card_path.exists()
