#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils.kg_builder.config import BuildConfig
from utils.kg_builder.exporters.jsonl import export_jsonl_artifacts
from utils.kg_builder.preprocess.attack import AttackPreprocessor
from utils.kg_builder.validate import (
    ArtifactValidationError,
    validate_graph,
    validate_jsonl_artifacts,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _graph_from_fixture() -> object:
    config = BuildConfig.from_data_dir("data")
    with open(FIXTURES / "preprocess_attack_bundle.json", encoding="utf-8") as f:
        bundle = json.load(f)
    return AttackPreprocessor(config).preprocess(bundle)


def test_jsonl_export_and_endpoint_integrity(tmp_path: Path) -> None:
    graph = _graph_from_fixture()
    paths = export_jsonl_artifacts(graph, tmp_path)
    validate_jsonl_artifacts(paths["nodes"], paths["relationships"])

    node_lines = paths["nodes"].read_text(encoding="utf-8").strip().splitlines()
    for line in node_lines:
        json.loads(line)


def test_jsonl_fails_on_missing_endpoint(tmp_path: Path) -> None:
    graph = _graph_from_fixture()
    paths = export_jsonl_artifacts(graph, tmp_path)

    rels = paths["relationships"].read_text(encoding="utf-8").splitlines()
    broken = json.loads(rels[0])
    broken["target_id"] = "missing-node-id"
    paths["relationships"].write_text(json.dumps(broken) + "\n", encoding="utf-8")

    with pytest.raises(ArtifactValidationError, match="missing target node"):
        validate_jsonl_artifacts(paths["nodes"], paths["relationships"])


@pytest.mark.skipif(
    not Path("data/raw/attack/v19.0/enterprise-attack.json").exists(),
    reason="Real ATT&CK dataset not downloaded",
)
def test_full_attack_build_writes_jsonl_artifacts() -> None:
    from utils.kg_builder.main import KGBuildRunner

    runner = KGBuildRunner()
    runner.build_attack()

    output = Path("data/graphs/attack")
    nodes_path = output / "nodes.jsonl"
    rels_path = output / "relationships.jsonl"
    manifest_path = output / "manifest.json"

    assert nodes_path.exists()
    assert rels_path.exists()
    assert manifest_path.exists()

    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    assert manifest["counts"]["nodes"] > 0
    assert manifest["counts"]["relationships"] > 0

    validate_jsonl_artifacts(nodes_path, rels_path)
