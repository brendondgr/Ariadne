#!/usr/bin/env python3
"""Both stores and the Gremlin exporter encode a property value the same way.

The rule (operator-algebra.md §1, §9 amendment 4): string lists are list
values, an empty list is not stored, a map or list of maps is JSON text
(``sort_keys=True``). Relationship properties follow the node rule.
"""

from __future__ import annotations

import json
import re

import pytest

from utils.graph_loader.stores.gremlin import (
    MAX_BINDINGS,
    edge_upsert_batches,
    edge_upsert_traversal,
    vertex_upsert_batches,
)
from utils.graph_loader.stores.neo4j import (
    _native_property_values,
    node_merge_cypher,
    relationship_merge_cypher,
)
from utils.kg_builder.exporters.gremlin import _gremlin_edge_record, _gremlin_node_record
from utils.kg_builder.property_encoding import NOT_STORED, stored_properties, stored_value

REFS = [{"source_name": "mitre-attack", "external_id": "T1055"}]
REFS_TEXT = json.dumps(REFS, sort_keys=True)

PROPS = {
    "x_mitre_platforms": ["Windows", "Linux"],
    "techniques": [],
    "external_references": REFS,
    "nested": {"b": 1, "a": 2},
    "Abstraction": "Standard",
    "x_mitre_version": 2,
    "revoked": False,
    "gone": None,
}


def _node(props=PROPS):
    return {"id": "n1", "label": "Technique", "labels": ["Technique"], "name": "N", "properties": dict(props)}


def _neo4j_node_values() -> dict:
    query, params = node_merge_cypher(_node())
    out = {}
    for key, param in re.findall(r"SET n\.`(\w+)` = \$(\w+)", query):
        out[key] = params[param]
    return out


def _gremlin_vertex_values(node) -> dict:
    out = {}
    for traversal, bindings in vertex_upsert_batches(node):
        for key, name in re.findall(r"\.property\('(\w+)', (\w+)\)", traversal):
            if name in bindings and name.startswith("p"):
                out[key] = bindings[name]
    return out


# -- the shared rule -----------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (["a", "b"], ["a", "b"]),
        (("a",), ["a"]),
        ([], NOT_STORED),
        (None, NOT_STORED),
        ("x", "x"),
        (3, 3),
        (False, False),
        (REFS, REFS_TEXT),
        ({"b": 1, "a": 2}, '{"a": 2, "b": 1}'),
        (["a", 1], '["a", 1]'),          # mixed: not a list property
        ([True, 1], "[true, 1]"),        # bool is not int here
        ([["a"]], '[["a"]]'),            # nested list
    ],
)
def test_stored_value(value, expected) -> None:
    assert stored_value(value) == expected


def test_stored_properties_is_idempotent() -> None:
    once = stored_properties(PROPS)
    assert stored_properties(once) == once


# -- both encoders agree -------------------------------------------------------


def test_string_list_is_a_list_in_both_engines() -> None:
    assert _neo4j_node_values()["x_mitre_platforms"] == ["Windows", "Linux"]
    assert _gremlin_vertex_values(_node())["x_mitre_platforms"] == ["Windows", "Linux"]
    exported = _gremlin_node_record(_node())["properties"]
    assert exported["x_mitre_platforms"] == ["Windows", "Linux"]


def test_empty_list_is_absent_in_both_engines() -> None:
    assert "techniques" not in _neo4j_node_values()
    assert "techniques" not in _gremlin_vertex_values(_node())
    assert "techniques" not in _gremlin_node_record(_node())["properties"]


def test_list_of_maps_is_json_text_in_both_engines() -> None:
    assert _neo4j_node_values()["external_references"] == REFS_TEXT
    assert _gremlin_vertex_values(_node())["external_references"] == REFS_TEXT
    assert _gremlin_node_record(_node())["properties"]["external_references"] == REFS_TEXT


def test_both_engines_store_the_same_node_properties() -> None:
    neo = _neo4j_node_values()
    grem = _gremlin_vertex_values(_node())
    grem.pop("name")  # Neo4j sets name explicitly, outside the property loop
    assert neo == grem
    # And loading an already-exported record writes exactly the same values.
    exported = dict(_node(), properties=_gremlin_node_record(_node())["properties"])
    assert _gremlin_vertex_values(exported) == _gremlin_vertex_values(_node())


def test_json_text_is_stored_but_not_native() -> None:
    native = _native_property_values(PROPS)
    assert "external_references" not in native and "nested" not in native
    assert native["x_mitre_platforms"] == ["Windows", "Linux"]
    assert "techniques" not in native


# -- relationship properties -----------------------------------------------------

EDGE = {
    "id": "relationship--1",
    "type": "USES",
    "source_id": "a",
    "target_id": "b",
    "properties": {
        "description": "uses it",
        "log_source_names": ["sysmon"],
        "empty": [],
        "refs": REFS,
        "id": "payload-id",
    },
}


def test_neo4j_edge_properties_are_written() -> None:
    query, params = relationship_merge_cypher(EDGE)
    written = {k: params[p] for k, p in re.findall(r"SET r\.`(\w+)` = \$(\w+)", query)}
    assert written == {
        "description": "uses it",
        "log_source_names": ["sysmon"],
        "refs": REFS_TEXT,
    }
    assert params["id"] == "relationship--1"


def test_gremlin_edge_properties_are_written() -> None:
    traversal, bindings = edge_upsert_traversal(EDGE)
    written = {
        k: bindings[n] for k, n in re.findall(r"\.property\('(\w+)', (\w+)\)", traversal) if n.startswith("p")
    }
    assert written == {
        "description": "uses it",
        "log_source_names": ["sysmon"],
        "refs": REFS_TEXT,
    }
    assert bindings["edgeId"] == "relationship--1"
    assert "payload-id" not in bindings.values()


def test_exported_edge_properties_use_the_rule() -> None:
    record = _gremlin_edge_record(EDGE)
    assert record["properties"]["log_source_names"] == ["sysmon"]
    assert "empty" not in record["properties"]
    assert record["properties"]["refs"] == REFS_TEXT


def test_gremlin_edge_upsert_stays_within_the_binding_limit() -> None:
    wide = dict(EDGE, properties={f"prop_{i}": f"v{i}" for i in range(40)})
    batches = edge_upsert_batches(wide)
    assert len(batches) > 1
    written = set()
    for traversal, bindings in batches:
        assert len(bindings) <= MAX_BINDINGS, traversal
        written.update(re.findall(r"\.property\('(\w+)'", traversal))
    assert {f"prop_{i}" for i in range(40)} <= written
    # Later submissions address the edge by id and never create one.
    for traversal, bindings in batches[1:]:
        assert traversal.startswith("g.E().has('id', edgeId)")
        assert "addE" not in traversal
        assert bindings["edgeId"] == "relationship--1"
    with pytest.raises(ValueError, match="edge_upsert_batches"):
        edge_upsert_traversal(wide)


def test_edge_merge_stays_keyed_on_the_id() -> None:
    q1, p1 = relationship_merge_cypher(EDGE)
    q2, p2 = relationship_merge_cypher(EDGE)
    assert (q1, p1) == (q2, p2)
    assert "MERGE (a)-[r:USES {id: $id}]->(b)" in q1
    # Properties are SET after the MERGE, never part of its pattern.
    assert q1.index("MERGE") < q1.index("SET r.")
    assert "description" not in q1[: q1.index("SET")]

    traversal, bindings = edge_upsert_traversal(EDGE)
    assert ".coalesce(__.inE(edgeLabel).has('id', edgeId).where(outV().as('a'))" in traversal
    assert "addE(edgeLabel).from('a').to('b').property('id', edgeId))" in traversal
    # Properties apply after the coalesce, to a created or a matched edge alike.
    assert traversal.index("coalesce(") < traversal.index(".property('description'")
    assert edge_upsert_traversal(EDGE) == (traversal, bindings)


def test_edge_without_properties_is_unchanged() -> None:
    bare = {"id": "e1", "type": "USES", "source_id": "a", "target_id": "b"}
    query, params = relationship_merge_cypher(bare)
    assert params == {"id": "e1", "source_id": "a", "target_id": "b"}
    assert "SET" not in query
    traversal, bindings = edge_upsert_traversal(bare)
    assert set(bindings) == {"sourceId", "targetId", "edgeId", "edgeLabel"}
