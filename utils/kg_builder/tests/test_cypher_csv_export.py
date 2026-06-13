#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils.kg_builder.config import BuildConfig
from utils.kg_builder.exporters.cypher import export_cypher_artifacts
from utils.kg_builder.exporters.jsonl import export_canonical_artifacts
from utils.kg_builder.exporters.neo4j_csv import export_neo4j_csv_artifacts
from utils.kg_builder.preprocess.attack import AttackPreprocessor
from utils.kg_builder.schema.attack import ATTACK_NODE_LABELS, ATTACK_RELATIONSHIP_TYPES

FIXTURES = Path(__file__).parent / "fixtures"


def _graph_from_fixture():
    config = BuildConfig.from_data_dir("data")
    with open(FIXTURES / "preprocess_attack_bundle.json", encoding="utf-8") as f:
        bundle = json.load(f)
    return AttackPreprocessor(config).preprocess(bundle)


def test_cypher_artifacts_are_deterministic(tmp_path: Path) -> None:
    neo4j_dir = tmp_path / "exports" / "neo4j"
    paths = export_cypher_artifacts(neo4j_dir)
    schema = paths["schema"].read_text(encoding="utf-8")
    constraints = paths["constraints"].read_text(encoding="utf-8")

    for label in ATTACK_NODE_LABELS:
        assert f":{label}" in schema
        assert f"FOR (n:{label}) REQUIRE n.id IS UNIQUE" in constraints

    for rel_type in ATTACK_RELATIONSHIP_TYPES:
        assert rel_type in schema


def test_neo4j_csv_row_counts_match_canonical(tmp_path: Path) -> None:
    graph = _graph_from_fixture()
    canonical_dir = tmp_path / "canonical"
    jsonl_paths = export_canonical_artifacts(graph, canonical_dir)
    neo4j_dir = tmp_path / "exports" / "neo4j"

    nodes = [json.loads(line) for line in jsonl_paths["nodes"].read_text(encoding="utf-8").splitlines() if line.strip()]
    rels = [
        json.loads(line)
        for line in jsonl_paths["relationships"].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    csv_paths = export_neo4j_csv_artifacts(nodes, rels, neo4j_dir)

    node_jsonl_count = len(nodes)
    rel_jsonl_count = len(rels)
    node_csv_count = sum(1 for _ in open(csv_paths["nodes"], encoding="utf-8")) - 1
    rel_csv_count = sum(1 for _ in open(csv_paths["relationships"], encoding="utf-8")) - 1

    assert node_jsonl_count == node_csv_count == len(graph.nodes)
    assert rel_jsonl_count == rel_csv_count == len(graph.relationships)

    csv_text = csv_paths["nodes"].read_text(encoding="utf-8")
    assert "properties_json" in csv_text
