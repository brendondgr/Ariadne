#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils.graph_loader.config import LoaderConfig
from utils.graph_loader.registry import LoaderResolutionError, resolve_dataset


def _write_attack_fixture(tmp_path: Path) -> LoaderConfig:
    data_dir = tmp_path / "data"
    canonical_dir = data_dir / "graphs" / "attack" / "canonical"
    neo4j_dir = data_dir / "graphs" / "attack" / "exports" / "neo4j"
    gremlin_dir = data_dir / "graphs" / "attack" / "exports" / "gremlin"
    source_cards_dir = data_dir / "source_cards"

    for directory in (canonical_dir, neo4j_dir, gremlin_dir, source_cards_dir):
        directory.mkdir(parents=True)

    for name in ("nodes.jsonl", "relationships.jsonl"):
        (canonical_dir / name).write_text("{}\n", encoding="utf-8")
    (canonical_dir / "schema.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "node_labels": ["Technique"],
                "relationship_types": ["USES"],
            }
        ),
        encoding="utf-8",
    )

    neo4j_files = ("nodes.csv", "relationships.csv", "schema.cypher", "constraints.cypher")
    for name in neo4j_files:
        (neo4j_dir / name).write_text("x\n", encoding="utf-8")

    for name in ("nodes.jsonl", "relationships.jsonl"):
        (gremlin_dir / name).write_text("{}\n", encoding="utf-8")

    manifest = {
        "canonical": {
            "nodes_jsonl": str(canonical_dir / "nodes.jsonl"),
            "relationships_jsonl": str(canonical_dir / "relationships.jsonl"),
            "schema_json": str(canonical_dir / "schema.json"),
        },
        "exports": {
            "neo4j": {
                "nodes_csv": str(neo4j_dir / "nodes.csv"),
                "relationships_csv": str(neo4j_dir / "relationships.csv"),
                "schema_cypher": str(neo4j_dir / "schema.cypher"),
                "constraints_cypher": str(neo4j_dir / "constraints.cypher"),
            },
            "gremlin": {
                "nodes_jsonl": str(gremlin_dir / "nodes.jsonl"),
                "relationships_jsonl": str(gremlin_dir / "relationships.jsonl"),
            },
        },
        "counts": {"nodes": 1, "relationships": 1},
    }
    manifest_path = canonical_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    source_card = {
        "dataset": "attack",
        "canonical_dir": str(canonical_dir),
        "canonical_manifest": str(manifest_path),
        "exports": manifest["exports"],
        "endpoints": {"neo4j": "", "gremlin": ""},
        "node_labels": ["Technique"],
        "relationship_types": ["USES"],
        "schema_version": "1.0",
        "runtime_backend": "neo4j",
    }
    (source_cards_dir / "attack.json").write_text(json.dumps(source_card), encoding="utf-8")
    return LoaderConfig.from_data_dir(data_dir)


def test_attack_resolves_neo4j_exports(tmp_path: Path) -> None:
    config = _write_attack_fixture(tmp_path)
    target = resolve_dataset("attack", "neo4j", config)

    assert target.dataset == "attack"
    assert target.backend == "neo4j"
    assert "neo4j" in target.backends
    assert "gremlin" not in target.backends
    assert target.backends["neo4j"].export_files["nodes_csv"].exists()
    assert target.nodes_path.exists()


def test_attack_resolves_all_backends(tmp_path: Path) -> None:
    config = _write_attack_fixture(tmp_path)
    target = resolve_dataset("attack", "all", config)

    assert set(target.backends) == {"gremlin", "neo4j"}


def test_missing_manifest_fails(tmp_path: Path) -> None:
    config = _write_attack_fixture(tmp_path)
    (config.data_dir / "graphs" / "attack" / "canonical" / "manifest.json").unlink()
    with pytest.raises(LoaderResolutionError, match="canonical manifest"):
        resolve_dataset("attack", "neo4j", config)


def test_missing_neo4j_export_fails(tmp_path: Path) -> None:
    config = _write_attack_fixture(tmp_path)
    (config.data_dir / "graphs" / "attack" / "exports" / "neo4j" / "nodes.csv").unlink()
    with pytest.raises(LoaderResolutionError, match="neo4j export"):
        resolve_dataset("attack", "neo4j", config)


def test_unsupported_backend_fails(tmp_path: Path) -> None:
    config = _write_attack_fixture(tmp_path)
    with pytest.raises(LoaderResolutionError, match="Unsupported graph action"):
        resolve_dataset("attack", "postgres", config)


def _write_capec_fixture(tmp_path: Path) -> LoaderConfig:
    data_dir = tmp_path / "data"
    canonical_dir = data_dir / "graphs" / "capec" / "canonical"
    neo4j_dir = data_dir / "graphs" / "capec" / "exports" / "neo4j"
    gremlin_dir = data_dir / "graphs" / "capec" / "exports" / "gremlin"
    source_cards_dir = data_dir / "source_cards"

    for directory in (canonical_dir, neo4j_dir, gremlin_dir, source_cards_dir):
        directory.mkdir(parents=True)

    for name in ("nodes.jsonl", "relationships.jsonl"):
        (canonical_dir / name).write_text("{}\n", encoding="utf-8")
    (canonical_dir / "schema.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "dataset": "capec",
                "node_labels": ["AttackPattern"],
                "relationship_types": ["ChildOf"],
            }
        ),
        encoding="utf-8",
    )

    for name in ("nodes.csv", "relationships.csv", "schema.cypher", "constraints.cypher"):
        (neo4j_dir / name).write_text("x\n", encoding="utf-8")
    for name in ("nodes.jsonl", "relationships.jsonl"):
        (gremlin_dir / name).write_text("{}\n", encoding="utf-8")

    manifest = {
        "dataset": "capec",
        "canonical": {
            "nodes_jsonl": str(canonical_dir / "nodes.jsonl"),
            "relationships_jsonl": str(canonical_dir / "relationships.jsonl"),
            "schema_json": str(canonical_dir / "schema.json"),
        },
        "exports": {
            "neo4j": {
                "nodes_csv": str(neo4j_dir / "nodes.csv"),
                "relationships_csv": str(neo4j_dir / "relationships.csv"),
                "schema_cypher": str(neo4j_dir / "schema.cypher"),
                "constraints_cypher": str(neo4j_dir / "constraints.cypher"),
            },
            "gremlin": {
                "nodes_jsonl": str(gremlin_dir / "nodes.jsonl"),
                "relationships_jsonl": str(gremlin_dir / "relationships.jsonl"),
            },
        },
        "counts": {"nodes": 1, "relationships": 1},
    }
    manifest_path = canonical_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    source_card = {
        "dataset": "capec",
        "canonical_dir": str(canonical_dir),
        "canonical_manifest": str(manifest_path),
        "exports": manifest["exports"],
        "endpoints": {"neo4j": "", "gremlin": ""},
        "node_labels": ["AttackPattern"],
        "relationship_types": ["ChildOf"],
        "schema_version": "1.0",
        "runtime_backend": "gremlin",
    }
    (source_cards_dir / "capec.json").write_text(json.dumps(source_card), encoding="utf-8")
    return LoaderConfig.from_data_dir(data_dir)


def test_capec_resolves_gremlin_exports(tmp_path: Path) -> None:
    config = _write_capec_fixture(tmp_path)
    target = resolve_dataset("capec", "gremlin", config)

    assert target.dataset == "capec"
    assert target.source_card["runtime_backend"] == "gremlin"
    assert "gremlin" in target.backends
    assert target.backends["gremlin"].export_files["nodes_jsonl"].exists()


def test_capec_missing_source_card_fails(tmp_path: Path) -> None:
    config = LoaderConfig.from_data_dir(tmp_path / "data")
    with pytest.raises(LoaderResolutionError, match="source card"):
        resolve_dataset("capec", "gremlin", config)
