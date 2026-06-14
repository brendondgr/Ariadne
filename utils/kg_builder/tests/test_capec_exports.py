#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path

from utils.kg_builder.config import BuildConfig
from utils.kg_builder.exporters.cypher import export_cypher_artifacts
from utils.kg_builder.exporters.gremlin import export_gremlin_artifacts
from utils.kg_builder.exporters.jsonl import export_canonical_artifacts
from utils.kg_builder.exporters.neo4j_csv import export_neo4j_csv_artifacts
from utils.kg_builder.preprocess.capec import build_capec_graph
from utils.kg_builder.validate import validate_jsonl_artifacts

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture_graph(tmp_path: Path):
    raw_dir = tmp_path / "raw" / "capec" / "v3.9"
    raw_dir.mkdir(parents=True)
    xml_path = raw_dir / "capec_latest.xml"
    xml_path.write_text(
        (FIXTURES / "minimal_capec_catalog.xml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (tmp_path / "versions.json").write_text(
        json.dumps({"attack_version": "19.0", "capec_version": "3.9"}),
        encoding="utf-8",
    )
    config = BuildConfig.from_data_dir(tmp_path)
    return config, build_capec_graph(config, write_pairs=False)


def test_capec_canonical_export_writes_schema_and_jsonl(tmp_path: Path) -> None:
    _, graph = _fixture_graph(tmp_path)
    canonical_dir = tmp_path / "graphs" / "capec" / "canonical"
    paths = export_canonical_artifacts(graph, canonical_dir)

    schema = json.loads(paths["schema"].read_text(encoding="utf-8"))
    assert schema["dataset"] == "capec"
    assert "AttackPattern" in schema["node_labels"]
    assert "MAPS_TO" in schema["relationship_types"]
    validate_jsonl_artifacts(paths["nodes"], paths["relationships"])


def test_capec_backend_exports_match_canonical_counts(tmp_path: Path) -> None:
    _, graph = _fixture_graph(tmp_path)
    canonical_dir = tmp_path / "graphs" / "capec" / "canonical"
    export_paths = export_canonical_artifacts(graph, canonical_dir)

    node_count = len(export_paths["nodes"].read_text(encoding="utf-8").strip().splitlines())
    rel_count = len(export_paths["relationships"].read_text(encoding="utf-8").strip().splitlines())

    neo4j_dir = tmp_path / "graphs" / "capec" / "exports" / "neo4j"
    gremlin_dir = tmp_path / "graphs" / "capec" / "exports" / "gremlin"
    export_cypher_artifacts(neo4j_dir, dataset="capec")
    csv_paths = export_neo4j_csv_artifacts(graph.nodes, graph.relationships, neo4j_dir, dataset="capec")
    gremlin_paths = export_gremlin_artifacts(graph.nodes, graph.relationships, gremlin_dir)

    neo4j_node_rows = len(csv_paths["nodes"].read_text(encoding="utf-8").strip().splitlines()) - 1
    gremlin_node_rows = len(gremlin_paths["nodes"].read_text(encoding="utf-8").strip().splitlines())
    gremlin_rel_rows = len(gremlin_paths["relationships"].read_text(encoding="utf-8").strip().splitlines())

    assert neo4j_node_rows == node_count
    assert gremlin_node_rows == node_count
    assert gremlin_rel_rows == rel_count
    assert "CREATE CONSTRAINT capec_attackpattern_id" in (
        neo4j_dir / "constraints.cypher"
    ).read_text(encoding="utf-8")
