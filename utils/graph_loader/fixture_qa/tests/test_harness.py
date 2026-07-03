#!/usr/bin/env python3
"""End-to-end tests for the fixture-QA harness with an injected live store."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils.graph_loader.config import LoaderConfig
from utils.graph_loader.fixture_qa.harness import (
    FixtureQAError,
    run_fixture_qa,
    run_fixture_qa_command,
)
from utils.graph_loader.stores.memory import MemoryGraphStore

# Two live Technique nodes + one revoked (excluded) technique in raw.
_RAW_BUNDLE = {
    "type": "bundle",
    "id": "bundle--test",
    "objects": [
        {"type": "attack-pattern", "id": "attack-pattern--t1"},
        {"type": "attack-pattern", "id": "attack-pattern--t2"},
        {"type": "attack-pattern", "id": "attack-pattern--rev", "revoked": True},
        {"type": "intrusion-set", "id": "intrusion-set--g1"},
    ],
}

_CANONICAL_NODES = [
    {"id": "attack-pattern--t1", "label": "Technique", "labels": ["Technique"],
     "properties": {"attack_id": "T1", "stix_type": "attack-pattern"}},
    {"id": "attack-pattern--t2", "label": "Technique", "labels": ["Technique"],
     "properties": {"attack_id": "T2", "stix_type": "attack-pattern"}},
    {"id": "intrusion-set--g1", "label": "Group", "labels": ["Group"],
     "properties": {"attack_id": "G1", "stix_type": "intrusion-set"}},
]
_CANONICAL_EDGES = [
    {"id": "e1", "type": "USES", "source_id": "intrusion-set--g1",
     "target_id": "attack-pattern--t1", "properties": {}},
]


def _build_attack_dataset(tmp_path: Path) -> LoaderConfig:
    data_dir = tmp_path / "data"
    canonical_dir = data_dir / "graphs" / "attack" / "canonical"
    neo4j_dir = data_dir / "graphs" / "attack" / "exports" / "neo4j"
    gremlin_dir = data_dir / "graphs" / "attack" / "exports" / "gremlin"
    runtime_dir = data_dir / "graphs" / "attack" / "runtime" / "neo4j"
    source_cards_dir = data_dir / "source_cards"
    raw_dir = data_dir / "raw" / "attack" / "v19.0"
    for d in (canonical_dir, neo4j_dir, gremlin_dir, runtime_dir, source_cards_dir, raw_dir):
        d.mkdir(parents=True)

    (raw_dir / "enterprise-attack.json").write_text(json.dumps(_RAW_BUNDLE), encoding="utf-8")

    (canonical_dir / "nodes.jsonl").write_text(
        "\n".join(json.dumps(n) for n in _CANONICAL_NODES) + "\n", encoding="utf-8"
    )
    (canonical_dir / "relationships.jsonl").write_text(
        "\n".join(json.dumps(e) for e in _CANONICAL_EDGES) + "\n", encoding="utf-8"
    )
    (canonical_dir / "schema.json").write_text(
        json.dumps({"schema_version": "1.0", "node_labels": ["Technique", "Group"],
                    "relationship_types": ["USES"]}), encoding="utf-8"
    )
    for name in ("nodes.csv", "relationships.csv", "schema.cypher", "constraints.cypher"):
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
        "counts": {
            "nodes": 3,
            "relationships": 1,
            "nodes_by_label": {"Technique": 2, "Group": 1},
            "relationships_by_type": {"USES": 1},
        },
        "metadata": {"filtered_revoked": 1, "filtered_deprecated": 0},
    }
    manifest_path = canonical_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    source_card = {
        "dataset": "attack",
        "canonical_dir": str(canonical_dir),
        "canonical_manifest": str(manifest_path),
        "exports": manifest["exports"],
        "endpoints": {"neo4j": "", "gremlin": ""},
        "node_labels": ["Technique", "Group"],
        "relationship_types": ["USES"],
        "schema_version": "1.0",
        "runtime_backend": "neo4j",
    }
    (source_cards_dir / "attack.json").write_text(json.dumps(source_card), encoding="utf-8")
    # Presence of the runtime manifest marks the neo4j backend as "loaded".
    (runtime_dir / "load-manifest.json").write_text(json.dumps({"backend": "neo4j"}), encoding="utf-8")
    return LoaderConfig.from_data_dir(data_dir)


def _memory_store_factory(nodes, edges):
    def factory(backend, target, config):
        store = MemoryGraphStore(backend=backend)
        store.connect()
        store.upsert_nodes(nodes)
        store.upsert_edges(edges)
        return store
    return factory


def test_harness_passes_when_everything_reconciles(tmp_path: Path) -> None:
    config = _build_attack_dataset(tmp_path)
    report = run_fixture_qa(
        "attack",
        loader_config=config,
        store_factory=_memory_store_factory(_CANONICAL_NODES, _CANONICAL_EDGES),
    )
    assert report.passed, report.errors
    names = {c.name for c in report.checks}
    assert "raw_vs_manifest_nodes" in names
    assert "excluded_counts_raw_vs_manifest" in names
    assert "no_revoked_deprecated_leakage" in names
    assert "manifest_vs_live_counts[neo4j]" in names
    assert "referential_integrity[neo4j]" in names
    # report artifact written
    assert Path(report.report_path).exists()


def test_harness_detects_live_count_drift(tmp_path: Path) -> None:
    config = _build_attack_dataset(tmp_path)
    # Live store is missing a node -> manifest_vs_live must fail.
    report = run_fixture_qa(
        "attack",
        loader_config=config,
        store_factory=_memory_store_factory(_CANONICAL_NODES[:2], _CANONICAL_EDGES),
        write_report=False,
    )
    assert not report.passed
    assert any("manifest_vs_live_counts" in e for e in report.errors)


def test_harness_detects_dangling_edge(tmp_path: Path) -> None:
    config = _build_attack_dataset(tmp_path)
    bad_edges = [
        {"id": "e1", "type": "USES", "source_id": "intrusion-set--g1", "target_id": "ghost"}
    ]
    report = run_fixture_qa(
        "attack",
        loader_config=config,
        store_factory=_memory_store_factory(_CANONICAL_NODES, bad_edges),
        write_report=False,
    )
    assert not report.passed
    assert any("referential_integrity" in e for e in report.errors)


def test_command_raises_on_failure(tmp_path: Path, monkeypatch) -> None:
    config = _build_attack_dataset(tmp_path)
    # Corrupt the raw excluded count so excluded_counts check fails.
    manifest_path = config.data_dir / "graphs" / "attack" / "canonical" / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["metadata"]["filtered_revoked"] = 99
    manifest_path.write_text(json.dumps(manifest))

    import utils.graph_loader.fixture_qa.harness as h
    monkeypatch.setattr(
        h, "create_graph_store", _memory_store_factory(_CANONICAL_NODES, _CANONICAL_EDGES)
    )
    with pytest.raises(FixtureQAError):
        run_fixture_qa_command("attack", config=config)
