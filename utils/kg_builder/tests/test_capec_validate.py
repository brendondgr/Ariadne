#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils.kg_builder.config import BuildConfig
from utils.kg_builder.models import CapecGraphMetadata, EdgeRecord, NodeRecord, NormalizedGraph
from utils.kg_builder.preprocess.capec import build_capec_graph
from utils.kg_builder.schema.capec import capec_canonical_labels
from utils.kg_builder.validate import ArtifactValidationError, validate_capec_graph, validate_graph

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture_graph(tmp_path: Path) -> NormalizedGraph:
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
    return build_capec_graph(BuildConfig.from_data_dir(tmp_path), write_pairs=False)


def test_validate_capec_fixture_graph_passes(tmp_path: Path) -> None:
    graph = _fixture_graph(tmp_path)
    validate_graph(graph)


def test_validate_capec_graph_rejects_duplicate_ids(tmp_path: Path) -> None:
    graph = _fixture_graph(tmp_path)
    duplicate = graph.nodes[0]
    graph.nodes.append(
        NodeRecord(
            id=duplicate.id,
            label=duplicate.label,
            labels=duplicate.labels,
            name=duplicate.name,
            properties=dict(duplicate.properties),
        )
    )
    with pytest.raises(ArtifactValidationError, match="Duplicate node ids"):
        validate_capec_graph(graph)


def test_validate_capec_graph_rejects_unknown_relationship_type(tmp_path: Path) -> None:
    graph = _fixture_graph(tmp_path)
    graph.relationships.append(
        EdgeRecord(
            id="capec:rel:INVALID:a->b",
            type="INVALID",
            source_id=graph.nodes[0].id,
            target_id=graph.nodes[1].id,
        )
    )
    with pytest.raises(ArtifactValidationError, match="Unknown CAPEC relationship type"):
        validate_capec_graph(graph)


def test_validate_capec_graph_rejects_dangling_reference(tmp_path: Path) -> None:
    graph = _fixture_graph(tmp_path)
    graph.relationships.append(
        EdgeRecord(
            id="capec:rel:ChildOf:a->missing",
            type="ChildOf",
            source_id=graph.nodes[0].id,
            target_id="capec:attack-pattern:99999",
        )
    )
    with pytest.raises(ArtifactValidationError, match="missing target node"):
        validate_capec_graph(graph)


def test_validate_capec_graph_rejects_missing_required_name() -> None:
    graph = NormalizedGraph(
        metadata=CapecGraphMetadata(source_path="fixture"),
        nodes=[
            NodeRecord(
                id="capec:attack-pattern:1",
                label="AttackPattern",
                labels=capec_canonical_labels("AttackPattern"),
            )
        ],
        relationships=[],
    )
    with pytest.raises(ArtifactValidationError, match="missing required name"):
        validate_capec_graph(graph)
