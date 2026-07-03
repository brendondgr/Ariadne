#!/usr/bin/env python3

from __future__ import annotations

import re

ATTACK_NODE_LABELS: frozenset[str] = frozenset(
    {
        "Tactic",
        "Technique",
        "SubTechnique",
        "Group",
        "Software",
        "Mitigation",
        "Campaign",
        "DataComponent",
        "DetectionStrategy",
        "Analytic",
        "Matrix",
    }
)

ATTACK_RELATIONSHIP_TYPES: frozenset[str] = frozenset(
    {
        "USES",
        "MITIGATES",
        "ATTRIBUTED_TO",
        "HAS_SUBTECHNIQUE",
        "HAS_TECHNIQUE",
        "DETECTS",
        "HAS_TACTIC",
        "HAS_ANALYTIC",
        "MONITORS",
    }
)

_STIX_TO_NEO4J_REL: dict[str, str] = {
    "uses": "USES",
    "mitigates": "MITIGATES",
    "attributed-to": "ATTRIBUTED_TO",
    "subtechnique-of": "HAS_SUBTECHNIQUE",
    "detects": "DETECTS",
}


def neo4j_relationship_type(stix_relationship_type: str) -> str:
    """Normalize a STIX relationship_type into a valid Neo4j relationship label."""
    if stix_relationship_type in _STIX_TO_NEO4J_REL:
        return _STIX_TO_NEO4J_REL[stix_relationship_type]
    normalized = re.sub(r"[^A-Za-z0-9_]", "_", stix_relationship_type).upper()
    return normalized or "RELATED_TO"


def schema_cypher_lines() -> list[str]:
    """Return Neo4j schema description lines."""
    lines = ["// ATT&CK graph schema (generated)"]
    for label in sorted(ATTACK_NODE_LABELS):
        lines.append(f"// :{label}")
    for rel_type in sorted(ATTACK_RELATIONSHIP_TYPES):
        lines.append(f"// ()-[:{rel_type}]->()")
    return lines


def constraints_cypher_lines() -> list[str]:
    """Return Neo4j constraint statements for implemented node labels."""
    lines = ["// ATT&CK graph constraints (generated)"]
    for label in sorted(ATTACK_NODE_LABELS):
        lines.append(
            f"CREATE CONSTRAINT attack_{label.lower()}_id IF NOT EXISTS "
            f"FOR (n:{label}) REQUIRE n.id IS UNIQUE;"
        )
    # Identity contract: the STIX UUID (id) is the globally-unique backstop, and
    # (attack_id, stix_type) is the composite join key — an ATT&CK ID alone is
    # not unique across object types (e.g. T1055 can be both an attack-pattern
    # and a deprecated course-of-action).
    lines.append(
        "CREATE CONSTRAINT attack_stix_id_unique IF NOT EXISTS "
        "FOR (n:AttackObject) REQUIRE n.id IS UNIQUE;"
    )
    lines.append(
        "CREATE CONSTRAINT attack_id_type_unique IF NOT EXISTS "
        "FOR (n:AttackObject) REQUIRE (n.attack_id, n.stix_type) IS UNIQUE;"
    )
    return lines
