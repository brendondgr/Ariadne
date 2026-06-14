#!/usr/bin/env python3

from __future__ import annotations

CAPEC_NODE_LABELS: frozenset[str] = frozenset(
    {
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
)

CAPEC_RELATIONSHIP_NATURES: frozenset[str] = frozenset(
    {
        "ChildOf",
        "ParentOf",
        "CanPrecede",
        "CanFollow",
        "PeerOf",
        "CanAlsoBe",
    }
)

CAPEC_DERIVED_RELATIONSHIP_TYPES: frozenset[str] = frozenset(
    {
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
)

CAPEC_RELATIONSHIP_TYPES: frozenset[str] = CAPEC_RELATIONSHIP_NATURES | CAPEC_DERIVED_RELATIONSHIP_TYPES

CAPEC_REQUIRED_NODE_PROPERTIES: dict[str, tuple[str, ...]] = {
    "AttackPattern": ("id", "name"),
    "Category": ("id", "name"),
    "View": ("id", "name"),
    "Weakness": ("id",),
    "TaxonomyEntry": ("id", "taxonomy_name"),
    "ExternalReference": ("id",),
    "ExecutionStep": ("id", "step"),
    "Skill": ("id",),
    "Consequence": ("id",),
    "Mitigation": ("id",),
}

CAPEC_ALLOWED_EDGE_PATTERNS: dict[str, frozenset[tuple[str, str]]] = {
    "ChildOf": frozenset({("AttackPattern", "AttackPattern")}),
    "ParentOf": frozenset({("AttackPattern", "AttackPattern")}),
    "CanPrecede": frozenset({("AttackPattern", "AttackPattern")}),
    "CanFollow": frozenset({("AttackPattern", "AttackPattern")}),
    "PeerOf": frozenset({("AttackPattern", "AttackPattern")}),
    "CanAlsoBe": frozenset({("AttackPattern", "AttackPattern")}),
    "EXPLOITS_WEAKNESS": frozenset({("AttackPattern", "Weakness")}),
    "MAPS_TO": frozenset({("AttackPattern", "TaxonomyEntry")}),
    "MEMBER_OF": frozenset({("AttackPattern", "Category")}),
    "IN_VIEW": frozenset({("AttackPattern", "View"), ("Category", "View")}),
    "HAS_EXECUTION_STEP": frozenset({("AttackPattern", "ExecutionStep")}),
    "NEXT_STEP": frozenset({("ExecutionStep", "ExecutionStep")}),
    "REQUIRES_SKILL": frozenset({("AttackPattern", "Skill")}),
    "HAS_CONSEQUENCE": frozenset({("AttackPattern", "Consequence")}),
    "HAS_MITIGATION": frozenset({("AttackPattern", "Mitigation")}),
    "HAS_REFERENCE": frozenset(
        {
            ("AttackPattern", "ExternalReference"),
            ("Category", "ExternalReference"),
            ("View", "ExternalReference"),
        }
    ),
}


def capec_canonical_labels(primary_label: str) -> list[str]:
    """Return ordered canonical labels for a CAPEC graph node."""
    return [primary_label, "CapecObject"]


def schema_cypher_lines() -> list[str]:
    """Return Neo4j schema description lines for CAPEC."""
    lines = ["// CAPEC graph schema (generated)"]
    for label in sorted(CAPEC_NODE_LABELS):
        lines.append(f"// :{label}")
    for rel_type in sorted(CAPEC_RELATIONSHIP_TYPES):
        lines.append(f"// ()-[:{rel_type}]->()")
    return lines


def constraints_cypher_lines() -> list[str]:
    """Return Neo4j constraint statements for CAPEC node labels."""
    lines = ["// CAPEC graph constraints (generated)"]
    for label in sorted(CAPEC_NODE_LABELS):
        lines.append(
            f"CREATE CONSTRAINT capec_{label.lower()}_id IF NOT EXISTS "
            f"FOR (n:{label}) REQUIRE n.id IS UNIQUE;"
        )
    return lines


def build_schema_document(schema_version: str) -> dict:
    """Build the CAPEC canonical schema.json payload."""
    return {
        "schema_version": schema_version,
        "dataset": "capec",
        "node_labels": sorted(CAPEC_NODE_LABELS),
        "relationship_types": sorted(CAPEC_RELATIONSHIP_TYPES),
        "relationship_natures": sorted(CAPEC_RELATIONSHIP_NATURES),
        "required_node_properties": {
            label: list(properties)
            for label, properties in sorted(CAPEC_REQUIRED_NODE_PROPERTIES.items())
        },
        "allowed_edge_patterns": {
            rel_type: [list(pattern) for pattern in sorted(patterns)]
            for rel_type, patterns in sorted(CAPEC_ALLOWED_EDGE_PATTERNS.items())
        },
    }
