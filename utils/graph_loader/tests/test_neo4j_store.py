#!/usr/bin/env python3

from __future__ import annotations

import pytest

import json

from utils.graph_loader.stores.neo4j import (
    node_merge_cypher,
    parse_constraints_cypher,
    relationship_merge_cypher,
    unpack_properties,
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


# -- relationship type names -------------------------------------------------
#
# The rule was screaming-snake only until 2026-08-20, which refused the five
# names CAPEC's own XML supplies (`Nature="ChildOf"` and friends). Widening it
# to match the label rule is a change to a *safety* validator, so both halves
# are pinned: the names that must now pass, and the ones that must still not.


@pytest.mark.parametrize(
    "rel_type",
    ["ChildOf", "CanPrecede", "CanFollow", "PeerOf", "CanAlsoBe", "ParentOf"],
)
def test_capecs_own_relationship_names_are_accepted(rel_type: str) -> None:
    """MITRE spells these CamelCase; the merged store must name them as MITRE does."""
    query, _ = relationship_merge_cypher(
        {"id": "e1", "type": rel_type, "source_id": "a", "target_id": "b"}
    )
    assert f"MERGE (a)-[r:{rel_type}]->(b)" in query


def test_this_repos_own_relationship_names_still_pass() -> None:
    query, _ = relationship_merge_cypher(
        {"id": "e1", "type": "EXPLOITS_WEAKNESS", "source_id": "a", "target_id": "b"}
    )
    assert "MERGE (a)-[r:EXPLOITS_WEAKNESS]->(b)" in query


@pytest.mark.parametrize(
    "rel_type",
    [
        "Can Follow",          # whitespace
        "Can`Follow",          # a backtick would close the identifier
        "Can-Follow",          # punctuation
        "`x`]->() DETACH DELETE (n)-[:`y",   # the injection the rule exists for
        "1ChildOf",            # leading digit
        "",                    # empty
        "Can'Follow",          # quote
    ],
)
def test_unsafe_relationship_names_are_still_rejected(rel_type: str) -> None:
    with pytest.raises(ValueError):
        relationship_merge_cypher(
            {"id": "e1", "type": rel_type, "source_id": "a", "target_id": "b"}
        )


def test_unpack_properties_roundtrips_the_flattened_blob() -> None:
    props = {
        "attack_id": "T1055.011",
        "description": "a long description",
        "external_references": [{"external_id": "T1055.011"}],
        "x_mitre_platforms": ["Windows"],
    }
    # The store writes properties as a JSON string; describe reads it back whole.
    _, params = node_merge_cypher(
        {"id": "n1", "label": "SubTechnique", "labels": ["SubTechnique"], "name": "X", "properties": props}
    )
    assert isinstance(params["properties_json"], str)
    assert unpack_properties(params["properties_json"]) == props


def test_unpack_properties_is_robust() -> None:
    assert unpack_properties(None) == {}
    assert unpack_properties("") == {}
    assert unpack_properties("not json") == {}
    assert unpack_properties("[1, 2, 3]") == {}  # valid JSON, wrong shape
    # Tolerates an already-parsed dict (a future first-class-properties migration).
    assert unpack_properties({"a": 1}) == {"a": 1}
    assert unpack_properties(json.dumps({"k": "v"})) == {"k": "v"}
