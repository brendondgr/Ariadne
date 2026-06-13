#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils.graph_loader.loader import load_dataset
from utils.graph_loader.stores.memory import MemoryGraphStore
from utils.graph_loader.tests.test_registry_resolution import _write_attack_fixture


def _memory_store_factory(backend: str, target, config):
    _ = config
    store = MemoryGraphStore(backend=backend, endpoint=f"memory://{backend}")
    store._target = target
    return store


def test_loader_orchestration_all_reports_independent_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _write_attack_fixture(tmp_path)
    canonical = config.data_dir / "graphs" / "attack" / "canonical"
    nodes = [
        {
            "id": "g1",
            "label": "Group",
            "labels": ["Group"],
            "properties": {"attack_id": "G1", "stix_type": "intrusion-set"},
        },
        {
            "id": "t1",
            "label": "Technique",
            "labels": ["Technique"],
            "properties": {"attack_id": "T1", "stix_type": "attack-pattern"},
        },
    ]
    edges = [{"id": "e1", "type": "USES", "source_id": "g1", "target_id": "t1", "properties": {}}]
    (canonical / "nodes.jsonl").write_text(
        "\n".join(json.dumps(n) for n in nodes) + "\n",
        encoding="utf-8",
    )
    (canonical / "relationships.jsonl").write_text(
        "\n".join(json.dumps(e) for e in edges) + "\n",
        encoding="utf-8",
    )
    (canonical / "schema.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "node_labels": ["Group", "Technique"],
                "relationship_types": ["USES"],
            }
        ),
        encoding="utf-8",
    )
    manifest_path = canonical / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["counts"] = {
        "nodes": 2,
        "relationships": 1,
        "nodes_by_label": {"Group": 1, "Technique": 1},
        "relationships_by_type": {"USES": 1},
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    monkeypatch.setattr(
        "utils.graph_loader.loader.run_preflight",
        lambda *_a, **_k: None,
    )

    call_count = {"n": 0}

    def flaky_factory(backend, target, config):
        call_count["n"] += 1
        if backend == "gremlin":
            raise RuntimeError("gremlin down")
        return _memory_store_factory(backend, target, config)

    result = load_dataset(
        "attack",
        "all",
        config=config,
        store_factory=flaky_factory,
        check_reachability=False,
    )
    assert call_count["n"] == 2
    assert not result.success
    assert any(b.backend == "neo4j" and b.success for b in result.backends)
    assert any(b.backend == "gremlin" and not b.success for b in result.backends)


def test_idempotent_memory_load_twice(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _write_attack_fixture(tmp_path)
    canonical = config.data_dir / "graphs" / "attack" / "canonical"
    nodes = [
        {
            "id": "g1",
            "label": "Group",
            "labels": ["Group"],
            "properties": {"attack_id": "G1", "stix_type": "intrusion-set"},
        },
        {
            "id": "t1",
            "label": "Technique",
            "labels": ["Technique"],
            "properties": {"attack_id": "T1", "stix_type": "attack-pattern"},
        },
    ]
    edges = [{"id": "e1", "type": "USES", "source_id": "g1", "target_id": "t1", "properties": {}}]
    (canonical / "nodes.jsonl").write_text(
        "\n".join(json.dumps(n) for n in nodes) + "\n",
        encoding="utf-8",
    )
    (canonical / "relationships.jsonl").write_text(
        "\n".join(json.dumps(e) for e in edges) + "\n",
        encoding="utf-8",
    )
    (canonical / "schema.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "node_labels": ["Group", "Technique"],
                "relationship_types": ["USES"],
            }
        ),
        encoding="utf-8",
    )
    manifest_path = canonical / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["counts"] = {
        "nodes": 2,
        "relationships": 1,
        "nodes_by_label": {"Group": 1, "Technique": 1},
        "relationships_by_type": {"USES": 1},
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    monkeypatch.setattr("utils.graph_loader.loader.run_preflight", lambda *_a, **_k: None)

    first = load_dataset(
        "attack",
        "neo4j",
        config=config,
        store_factory=_memory_store_factory,
        check_reachability=False,
    )
    second = load_dataset(
        "attack",
        "neo4j",
        config=config,
        store_factory=_memory_store_factory,
        check_reachability=False,
    )
    assert first.success and second.success
    assert first.backends[0].nodes_loaded == 2
    assert second.backends[0].edges_loaded == 1
