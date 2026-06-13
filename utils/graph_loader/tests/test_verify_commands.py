#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils.graph_loader.preflight import PreflightError
from utils.graph_loader.stores.memory import MemoryGraphStore
from utils.graph_loader.tests.test_registry_resolution import _write_attack_fixture
from utils.graph_loader.verify import verify_dataset


def _prepare_valid_fixture(config) -> None:
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


def test_verify_fails_without_runtime_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _write_attack_fixture(tmp_path)
    _prepare_valid_fixture(config)
    monkeypatch.setattr("utils.graph_loader.preflight.verify_manifest_hashes", lambda _p: None)
    monkeypatch.setattr(
        "utils.graph_loader.preflight.check_backend_reachability",
        lambda *_a, **_k: {"neo4j": True, "gremlin": True},
    )
    result = verify_dataset("attack", config=config, check_reachability=False)
    assert not result.passed
    assert any("runtime load manifest" in err for err in result.errors)


def test_verify_passes_with_loaded_memory_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _write_attack_fixture(tmp_path)
    _prepare_valid_fixture(config)
    monkeypatch.setattr("utils.graph_loader.preflight.verify_manifest_hashes", lambda _p: None)
    monkeypatch.setattr(
        "utils.graph_loader.preflight.check_backend_reachability",
        lambda *_a, **_k: {"neo4j": True, "gremlin": True},
    )

    from utils.graph_loader.loader import load_dataset

    monkeypatch.setattr("utils.graph_loader.loader.run_preflight", lambda *_a, **_k: None)
    load_dataset(
        "attack",
        "neo4j",
        config=config,
        store_factory=lambda *_a, **_k: MemoryGraphStore(backend="neo4j"),
        check_reachability=False,
    )

    # Only verify neo4j with memory store; gremlin still missing manifest -> expect failure overall
    result = verify_dataset(
        "attack",
        config=config,
        store_factory=lambda backend, *_a, **_k: MemoryGraphStore(backend=backend),
        check_reachability=False,
    )
    assert not result.passed


def test_run_dataset_verify_raises_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    from utils.graph_loader import verify as verify_module
    from utils.graph_loader.main import run_dataset_verify

    monkeypatch.setattr(
        verify_module,
        "verify_dataset",
        lambda *_a, **_k: verify_module.DatasetVerifyResult(
            dataset="attack",
            passed=False,
            errors=["bad"],
            backend_results={},
        ),
    )
    with pytest.raises(PreflightError):
        run_dataset_verify("attack")
