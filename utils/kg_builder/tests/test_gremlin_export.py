#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path

from utils.kg_builder.config import BuildConfig
from utils.kg_builder.exporters.gremlin import export_gremlin_artifacts
from utils.kg_builder.exporters.jsonl import export_canonical_artifacts
from utils.kg_builder.preprocess.attack import AttackPreprocessor

FIXTURES = Path(__file__).parent / "fixtures"


def _graph_from_fixture():
    config = BuildConfig.from_data_dir("data")
    with open(FIXTURES / "preprocess_attack_bundle.json", encoding="utf-8") as f:
        bundle = json.load(f)
    return AttackPreprocessor(config).preprocess(bundle)


def test_gremlin_export_preserves_ids_and_direction(tmp_path: Path) -> None:
    graph = _graph_from_fixture()
    canonical_dir = tmp_path / "canonical"
    canonical_paths = export_canonical_artifacts(graph, canonical_dir)

    nodes = [
        json.loads(line)
        for line in canonical_paths["nodes"].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rels = [
        json.loads(line)
        for line in canonical_paths["relationships"].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    gremlin_dir = tmp_path / "exports" / "gremlin"
    gremlin_paths = export_gremlin_artifacts(nodes, rels, gremlin_dir)

    gremlin_nodes = [
        json.loads(line)
        for line in gremlin_paths["nodes"].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    gremlin_rels = [
        json.loads(line)
        for line in gremlin_paths["relationships"].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert len(gremlin_nodes) == len(nodes)
    assert len(gremlin_rels) == len(rels)

    canonical_ids = {n["id"] for n in nodes}
    for node in gremlin_nodes:
        assert node["id"] in canonical_ids
        assert node["label"] == node["labels"][0]

    for edge in gremlin_rels:
        assert edge["source_id"] in canonical_ids
        assert edge["target_id"] in canonical_ids
        assert edge["type"]


def test_gremlin_serializes_nested_properties(tmp_path: Path) -> None:
    graph = _graph_from_fixture()
    nodes = [n.to_dict() for n in graph.nodes]
    rels = [r.to_dict() for r in graph.relationships]

    gremlin_paths = export_gremlin_artifacts(nodes, rels, tmp_path)
    technique = None
    for line in gremlin_paths["nodes"].read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record["label"] == "Technique":
            technique = record
            break

    assert technique is not None
    refs = technique["properties"]["external_references"]
    assert isinstance(refs, str)
    assert json.loads(refs)[0]["external_id"] == "T9999"
