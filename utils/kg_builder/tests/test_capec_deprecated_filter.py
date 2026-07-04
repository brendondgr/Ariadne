#!/usr/bin/env python3
"""Retired-CAPEC exclusion at canonical build.

CAPEC now mirrors ATT&CK's exclude-at-load policy: attack patterns, categories,
and views whose ``Status`` is ``Deprecated`` or ``Obsolete`` are dropped during
materialization, along with their exclusive children and any edge that would
point at them — so retired entries never enter the canonical graph as islands.
"""

from __future__ import annotations

from utils.kg_builder.preprocess.capec_graph import materialize_capec_graph
from utils.kg_builder.preprocess.capec_ids import (
    attack_pattern_node_id,
    category_node_id,
    view_node_id,
)
from utils.kg_builder.preprocess.capec_models import CapecPairsCheckpoint, CapecPairsMetadata


def _checkpoint() -> CapecPairsCheckpoint:
    metadata = CapecPairsMetadata(
        source_path="test.xml",
        capec_version="3.9",
        catalog_version="3.9",
        catalog_date="2026-01-01",
        namespace="capec",
        build_scope="test",
    )
    attack_patterns = [
        {
            "id": "560",
            "Name": "Use of Known Domain Credentials",
            "Status": "Stable",
            # relates to a retired pattern (999) and a live one (122)
            "related_attack_patterns": [
                {"nature": "ChildOf", "capec_id": "999"},
                {"nature": "PeerOf", "capec_id": "122"},
            ],
            "mitigations": [{"description": "Rotate credentials"}],
        },
        {"id": "122", "Name": "Privilege Abuse", "Status": "Stable"},
        {
            "id": "999",
            "Name": "Retired Pattern",
            "Status": "Deprecated",
            "mitigations": [{"description": "Should never appear"}],
        },
    ]
    categories = [
        {"id": "1000", "Name": "Live Category", "Status": "Draft", "members": ["560", "999"]},
        {"id": "9000", "Name": "Retired Category", "Status": "Obsolete", "members": ["560"]},
    ]
    views = [
        {"id": "3000", "Name": "Live View", "Status": "Stable", "members": ["1000", "560"]},
        {"id": "8000", "Name": "Retired View", "Status": "Deprecated", "members": ["560"]},
    ]
    return CapecPairsCheckpoint(
        metadata=metadata,
        attack_patterns=attack_patterns,
        categories=categories,
        views=views,
    )


def test_retired_nodes_and_children_excluded() -> None:
    graph = materialize_capec_graph(_checkpoint())
    node_ids = {node.id for node in graph.nodes}

    assert attack_pattern_node_id("999") not in node_ids
    assert category_node_id("9000") not in node_ids
    assert view_node_id("8000") not in node_ids
    # the retired pattern's exclusive child mitigation must be gone too
    assert not any(node.label == "Mitigation" and "Should never appear"
                   in str(node.properties) for node in graph.nodes)
    # live entries survive
    assert attack_pattern_node_id("560") in node_ids
    assert attack_pattern_node_id("122") in node_ids
    assert category_node_id("1000") in node_ids
    assert view_node_id("3000") in node_ids

    assert graph.metadata.skipped_count == 3


def test_no_edges_point_at_retired_ids() -> None:
    graph = materialize_capec_graph(_checkpoint())
    node_ids = {node.id for node in graph.nodes}

    # no dangling edges whatsoever
    for rel in graph.relationships:
        assert rel.source_id in node_ids
        assert rel.target_id in node_ids

    # the ChildOf edge to the retired pattern (999) is not created
    assert not any(
        rel.type == "ChildOf" and rel.target_id == attack_pattern_node_id("999")
        for rel in graph.relationships
    )
    # the PeerOf edge to the live pattern (122) is preserved
    assert any(
        rel.type == "PeerOf"
        and rel.source_id == attack_pattern_node_id("560")
        and rel.target_id == attack_pattern_node_id("122")
        for rel in graph.relationships
    )
    # MEMBER_OF into the retired category is not created
    assert not any(
        rel.type == "MEMBER_OF" and rel.target_id == category_node_id("9000")
        for rel in graph.relationships
    )
    # IN_VIEW into the retired view is not created
    assert not any(
        rel.type == "IN_VIEW" and rel.target_id == view_node_id("8000")
        for rel in graph.relationships
    )


def test_filter_disabled_keeps_retired_nodes() -> None:
    graph = materialize_capec_graph(_checkpoint(), filter_deprecated=False)
    node_ids = {node.id for node in graph.nodes}

    assert attack_pattern_node_id("999") in node_ids
    assert category_node_id("9000") in node_ids
    assert view_node_id("8000") in node_ids
    assert graph.metadata.skipped_count == 0
    # still no dangling edges
    for rel in graph.relationships:
        assert rel.source_id in node_ids
        assert rel.target_id in node_ids
