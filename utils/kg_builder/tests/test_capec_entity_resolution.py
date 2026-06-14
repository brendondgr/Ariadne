#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils.kg_builder.config import BuildConfig
from utils.kg_builder.preprocess.capec import normalize_capec_catalog
from utils.kg_builder.preprocess.capec_graph import materialize_capec_graph
from utils.kg_builder.preprocess.capec_ids import (
    attack_pattern_node_id,
    execution_step_node_id,
    external_reference_node_id,
    relationship_id,
    taxonomy_node_id,
    weakness_node_id,
)

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


def test_stable_capec_entity_ids() -> None:
    assert attack_pattern_node_id("560") == "capec:attack-pattern:560"
    assert weakness_node_id("522") == "cwe:522"
    assert taxonomy_node_id("ATTACK", "1550.002") == "capec:taxonomy:ATTACK:1550.002"
    assert external_reference_node_id("REF-42") == "capec:external-reference:REF-42"
    assert execution_step_node_id("560", "1") == "capec:attack-pattern:560:step:1"
    assert (
        relationship_id("ChildOf", "capec:attack-pattern:560", "capec:attack-pattern:122")
        == "capec:rel:ChildOf:capec:attack-pattern:560->capec:attack-pattern:122"
    )


def test_entity_ids_do_not_collide_with_attack_stix_ids() -> None:
    stix_like = "attack-pattern--00000000-0000-0000-0000-000000000001"
    assert attack_pattern_node_id("560").startswith("capec:")
    assert attack_pattern_node_id("560") != stix_like


def test_materialize_fixture_graph_nodes_and_relationships(tmp_path: Path) -> None:
    checkpoint = _fixture_checkpoint(tmp_path)
    graph = materialize_capec_graph(checkpoint)

    node_ids = {node.id for node in graph.nodes}
    assert attack_pattern_node_id("560") in node_ids
    assert weakness_node_id("522") in node_ids
    assert external_reference_node_id("REF-42") in node_ids
    assert execution_step_node_id("560", "1") in node_ids
    assert taxonomy_node_id("ATTACK", "1550.002") in node_ids

    rel_types = {rel.type for rel in graph.relationships}
    assert "ChildOf" in rel_types
    assert "HAS_EXECUTION_STEP" in rel_types
    assert "NEXT_STEP" in rel_types
    assert "EXPLOITS_WEAKNESS" in rel_types
    assert "MAPS_TO" in rel_types
    assert "HAS_REFERENCE" in rel_types
    assert "MEMBER_OF" in rel_types


def test_materialize_graph_is_deterministically_sorted(tmp_path: Path) -> None:
    graph = materialize_capec_graph(_fixture_checkpoint(tmp_path))
    node_ids = [node.id for node in graph.nodes]
    rel_ids = [rel.id for rel in graph.relationships]
    assert node_ids == sorted(node_ids)
    assert rel_ids == sorted(rel_ids)


@pytest.mark.skipif(
    not Path("data/raw/capec/v3.9/capec_latest.xml").exists(),
    reason="Real CAPEC dataset not downloaded",
)
def test_materialize_real_capec_graph_has_expected_counts() -> None:
    from utils.kg_builder.preprocess.capec import preprocess_capec

    checkpoint = preprocess_capec(BuildConfig.from_data_dir("data"))
    graph = materialize_capec_graph(checkpoint)

    assert graph.counts["nodes"] > 0
    assert graph.counts["relationships"] > 0
    assert graph.counts["nodes_by_label"]["AttackPattern"] > 0
    assert graph.counts["nodes_by_label"]["Weakness"] > 0
    assert graph.counts["nodes_by_label"]["TaxonomyEntry"] > 0
    assert graph.counts["nodes_by_label"]["ExternalReference"] > 0
    assert graph.counts["nodes_by_label"]["ExecutionStep"] > 0
