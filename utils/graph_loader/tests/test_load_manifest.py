#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path

from utils.graph_loader.manifest import build_load_manifest, write_load_manifest
from utils.graph_loader.models import CountSummary, VerifyLoadedGraphResult
from utils.graph_loader.results import BackendLoadResult
from utils.graph_loader.stores.memory import MemoryGraphStore
from utils.graph_loader.manifest import write_backend_load_manifest


def test_load_manifest_written_after_success(tmp_path: Path) -> None:
    store = MemoryGraphStore()
    store.connect()
    expected = CountSummary(nodes=1, edges=0, nodes_by_label={"Technique": 1}, edges_by_type={})
    actual = CountSummary(nodes=1, edges=0, nodes_by_label={"Technique": 1}, edges_by_type={})
    verification = VerifyLoadedGraphResult(passed=True, expected=expected, actual=actual)
    result = BackendLoadResult(
        backend="memory",
        success=True,
        nodes_loaded=1,
        edges_loaded=0,
        verification=verification,
    )
    manifest_path = tmp_path / "load-manifest.json"
    canonical_manifest = tmp_path / "canonical-manifest.json"
    canonical_manifest.write_text("{}", encoding="utf-8")

    write_backend_load_manifest(
        store=store,
        result=result,
        dataset="attack",
        canonical_manifest_path=canonical_manifest,
        semantic_valid=True,
        expected_counts=expected,
        verification=verification,
        runtime_manifest_path=manifest_path,
    )

    assert manifest_path.exists()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["dataset"] == "attack"
    assert payload["backend"] == "memory"
    assert payload["semantic_validation_passed"] is True
    assert payload["verification"]["passed"] is True


def test_build_load_manifest_records_adapter_version() -> None:
    expected = CountSummary(nodes=2, edges=1)
    actual = expected
    verification = VerifyLoadedGraphResult(passed=True, expected=expected, actual=actual)
    manifest = build_load_manifest(
        dataset="attack",
        backend="neo4j",
        canonical_manifest_path=Path("data/graphs/attack/canonical/manifest.json"),
        canonical_manifest_hash="abc",
        semantic_valid=True,
        endpoint="bolt://localhost:5456",
        adapter_version="0.1.0",
        expected_counts=expected,
        verification=verification,
        nodes_loaded=2,
        edges_loaded=1,
    )
    assert manifest["adapter_version"] == "0.1.0"
