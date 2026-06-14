#!/usr/bin/env python3

from __future__ import annotations

from utils.kg_builder.schema.capec import (
    CAPEC_ALLOWED_EDGE_PATTERNS,
    CAPEC_DERIVED_RELATIONSHIP_TYPES,
    CAPEC_NODE_LABELS,
    CAPEC_RELATIONSHIP_NATURES,
    CAPEC_RELATIONSHIP_TYPES,
    CAPEC_REQUIRED_NODE_PROPERTIES,
    build_schema_document,
    capec_canonical_labels,
)


def test_capec_node_labels_include_required_entities() -> None:
    required = {
        "AttackPattern",
        "Category",
        "View",
        "Weakness",
        "TaxonomyEntry",
        "ExternalReference",
        "ExecutionStep",
        "Skill",
        "Consequence",
        "Mitigation",
    }
    assert required.issubset(CAPEC_NODE_LABELS)


def test_capec_relationship_types_include_natures_and_derived_edges() -> None:
    for nature in ("ChildOf", "ParentOf", "CanPrecede", "CanFollow"):
        assert nature in CAPEC_RELATIONSHIP_NATURES
        assert nature in CAPEC_RELATIONSHIP_TYPES

    derived = {
        "EXPLOITS_WEAKNESS",
        "MAPS_TO",
        "MEMBER_OF",
        "IN_VIEW",
        "HAS_EXECUTION_STEP",
        "NEXT_STEP",
        "REQUIRES_SKILL",
        "HAS_CONSEQUENCE",
        "HAS_MITIGATION",
        "HAS_REFERENCE",
    }
    assert derived.issubset(CAPEC_DERIVED_RELATIONSHIP_TYPES)
    assert derived.issubset(CAPEC_RELATIONSHIP_TYPES)


def test_capec_required_properties_and_edge_patterns() -> None:
    assert CAPEC_REQUIRED_NODE_PROPERTIES["AttackPattern"] == ("id", "name")
    assert ("AttackPattern", "Weakness") in CAPEC_ALLOWED_EDGE_PATTERNS["EXPLOITS_WEAKNESS"]
    assert ("AttackPattern", "TaxonomyEntry") in CAPEC_ALLOWED_EDGE_PATTERNS["MAPS_TO"]
    assert ("ExecutionStep", "ExecutionStep") in CAPEC_ALLOWED_EDGE_PATTERNS["NEXT_STEP"]


def test_build_schema_document_includes_dataset_metadata() -> None:
    schema = build_schema_document("1.0")
    assert schema["dataset"] == "capec"
    assert "AttackPattern" in schema["node_labels"]
    assert "MAPS_TO" in schema["relationship_types"]


def test_capec_canonical_labels_include_capec_object() -> None:
    assert capec_canonical_labels("AttackPattern") == ["AttackPattern", "CapecObject"]
