#!/usr/bin/env python3

from __future__ import annotations

import pytest

from utils.graph_loader.stores.neo4j import (
    node_merge_cypher,
    parse_constraints_cypher,
    relationship_merge_cypher,
)


def test_node_merge_cypher_uses_primary_label() -> None:
    node = {
        "id": "n1",
        "label": "Technique",
        "labels": ["Technique", "AttackObject"],
        "name": "Test",
        "properties": {"attack_id": "T1000", "stix_type": "attack-pattern"},
    }
    query, params = node_merge_cypher(node)
    assert "MERGE (n:Technique {id: $id})" in query
    assert "SET n:AttackObject" in query
    assert params["id"] == "n1"
    assert params["attack_id"] == "T1000"


def test_relationship_merge_cypher() -> None:
    edge = {
        "id": "e1",
        "type": "USES",
        "source_id": "a",
        "target_id": "b",
    }
    query, params = relationship_merge_cypher(edge)
    assert "MERGE (a)-[r:USES]->(b)" in query
    assert params["source_id"] == "a"


def test_parse_constraints_cypher(tmp_path) -> None:
    path = tmp_path / "constraints.cypher"
    path.write_text(
        "// comment\nCREATE CONSTRAINT attack_technique_id IF NOT EXISTS FOR (n:Technique) REQUIRE n.id IS UNIQUE;\n",
        encoding="utf-8",
    )
    statements = parse_constraints_cypher(path)
    assert len(statements) == 1
    assert statements[0].startswith("CREATE CONSTRAINT")


def test_unsafe_label_rejected() -> None:
    with pytest.raises(ValueError):
        node_merge_cypher({"id": "1", "label": "Bad-Label", "labels": ["Bad-Label"], "properties": {}})
