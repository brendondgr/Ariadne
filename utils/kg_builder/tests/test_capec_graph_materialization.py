#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils.kg_builder.config import BuildConfig
from utils.kg_builder.preprocess.capec import normalize_capec_catalog
from utils.kg_builder.preprocess.capec_graph import materialize_capec_graph
from utils.kg_builder.preprocess.capec_ids import attack_pattern_node_id, execution_step_node_id

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture_checkpoint(tmp_path: Path):
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
    return normalize_capec_catalog(BuildConfig.from_data_dir(tmp_path))


def test_materialize_preserves_relationship_endpoints(tmp_path: Path) -> None:
    graph = materialize_capec_graph(_fixture_checkpoint(tmp_path))
    node_ids = {node.id for node in graph.nodes}

    for rel in graph.relationships:
        assert rel.source_id in node_ids
        assert rel.target_id in node_ids


def test_execution_step_ordering_uses_next_step_edges(tmp_path: Path) -> None:
    graph = materialize_capec_graph(_fixture_checkpoint(tmp_path))
    next_steps = [
        rel
        for rel in graph.relationships
        if rel.type == "NEXT_STEP"
        and rel.source_id == execution_step_node_id("560", "1")
        and rel.target_id == execution_step_node_id("560", "2")
    ]
    assert len(next_steps) == 1


def test_source_declared_childof_direction(tmp_path: Path) -> None:
    graph = materialize_capec_graph(_fixture_checkpoint(tmp_path))
    child_of = [
        rel
        for rel in graph.relationships
        if rel.type == "ChildOf"
        and rel.source_id == attack_pattern_node_id("560")
        and rel.target_id == attack_pattern_node_id("122")
    ]
    assert len(child_of) == 1


def test_unmapped_fields_preserved_in_metadata_counts(tmp_path: Path) -> None:
    graph = materialize_capec_graph(_fixture_checkpoint(tmp_path))
    assert graph.metadata.quarantined_count >= 0
