#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from utils.graph_loader.preflight import (
    PreflightError,
    check_backend_reachability,
    run_preflight,
)
from utils.graph_loader.registry import LoaderResolutionError, resolve_dataset
from utils.graph_loader.tests.test_registry_resolution import _write_attack_fixture
from utils.graph_loader.validation.semantic import SemanticValidationError


def test_preflight_passes_for_valid_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _write_attack_fixture(tmp_path)
    # Write semantically valid minimal graph
    canonical = config.data_dir / "graphs" / "attack" / "canonical"
    nodes = [
        {
            "id": "g1",
            "label": "Group",
            "labels": ["Group", "AttackObject"],
            "properties": {"attack_id": "G0001", "stix_type": "intrusion-set"},
        },
        {
            "id": "t1",
            "label": "Technique",
            "labels": ["Technique", "AttackObject"],
            "properties": {"attack_id": "T1000", "stix_type": "attack-pattern"},
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

    manifest_path = canonical / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["counts"] = {"nodes": 2, "relationships": 1, "nodes_by_label": {}, "relationships_by_type": {}}
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
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

    target = resolve_dataset("attack", "neo4j", config)
    monkeypatch.setattr(
        "utils.graph_loader.preflight.verify_manifest_hashes",
        lambda _path: None,
    )
    monkeypatch.setattr(
        "utils.graph_loader.preflight.check_backend_reachability",
        lambda *_a, **_k: {"neo4j": True},
    )
    result = run_preflight(target, backends=["neo4j"], check_reachability=True)
    assert result.semantic_valid
    assert result.node_count == 2


def test_preflight_fails_on_missing_export(tmp_path: Path) -> None:
    config = _write_attack_fixture(tmp_path)
    (config.data_dir / "graphs" / "attack" / "exports" / "neo4j" / "nodes.csv").unlink()
    with pytest.raises(LoaderResolutionError, match="nodes_csv"):
        resolve_dataset("attack", "neo4j", config)


def test_preflight_semantic_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _write_attack_fixture(tmp_path)
    canonical = config.data_dir / "graphs" / "attack" / "canonical"
    (canonical / "nodes.jsonl").write_text(
        json.dumps(
            {
                "id": "bad",
                "label": "Alien",
                "labels": ["Alien"],
                "properties": {"id": "bad"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (canonical / "relationships.jsonl").write_text("", encoding="utf-8")
    target = resolve_dataset("attack", "neo4j", config)
    monkeypatch.setattr(
        "utils.graph_loader.preflight.verify_manifest_hashes",
        lambda _path: None,
    )
    monkeypatch.setattr(
        "utils.graph_loader.preflight.validate_canonical_artifacts",
        lambda _dir: {"nodes": 1, "relationships": 0},
    )
    with pytest.raises(SemanticValidationError):
        run_preflight(target, backends=["neo4j"], check_reachability=False)


def test_preflight_unreachable_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
    target = resolve_dataset("attack", "neo4j", config)
    monkeypatch.setattr(
        "utils.graph_loader.preflight.verify_manifest_hashes",
        lambda _path: None,
    )
    monkeypatch.setattr(
        "utils.graph_loader.preflight.check_backend_reachability",
        lambda *_a, **_k: {"neo4j": False},
    )
    with pytest.raises(PreflightError, match="unreachable"):
        run_preflight(target, backends=["neo4j"], check_reachability=True)
