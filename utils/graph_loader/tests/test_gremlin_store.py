#!/usr/bin/env python3

from __future__ import annotations

import pytest

from utils.graph_loader.stores.gremlin import edge_upsert_traversal, vertex_upsert_traversal


def test_vertex_upsert_traversal_bindings() -> None:
    node = {
        "id": "v1",
        "label": "Technique",
        "name": "Test",
        "properties": {"attack_id": "T1000"},
    }
    traversal, bindings = vertex_upsert_traversal(node)
    assert "nodeId" in bindings
    assert "addV(vertexLabel)" in traversal
    assert bindings["nodeId"] == "v1"


def test_edge_upsert_traversal_bindings() -> None:
    edge = {
        "id": "e1",
        "type": "USES",
        "source_id": "a",
        "target_id": "b",
    }
    traversal, bindings = edge_upsert_traversal(edge)
    assert bindings["edgeLabel"] == "USES"
    assert "addE(edgeLabel)" in traversal


def test_unsafe_gremlin_label_rejected() -> None:
    with pytest.raises(ValueError):
        vertex_upsert_traversal({"id": "1", "label": "Bad Label", "properties": {}})


def test_vertex_upsert_batches_stay_within_the_server_limit() -> None:
    """A wide node must not exceed TinkerPop's stock maxParameters.

    Widening the ATT&CK build's property policy produced nodes of ~17
    properties, and the single-submission form died with "contains 17 bindings
    which is more than is allowed by the server 16 configuration".
    """
    from utils.graph_loader.stores.gremlin import MAX_BINDINGS, vertex_upsert_batches

    node = {
        "id": "campaign--4fd53ccc",
        "label": "Campaign",
        "name": "3CX Supply Chain Attack",
        "properties": {f"prop_{i}": f"v{i}" for i in range(24)},
    }
    batches = vertex_upsert_batches(node)
    assert len(batches) > 1, "this node is meant to need more than one submission"
    for traversal, bindings in batches:
        assert len(bindings) <= MAX_BINDINGS, traversal


def test_every_property_survives_batching() -> None:
    from utils.graph_loader.stores.gremlin import vertex_upsert_batches

    props = {f"prop_{i}": i for i in range(24)}
    node = {"id": "n1", "label": "Campaign", "name": "n", "properties": props}
    written = "".join(t for t, _ in vertex_upsert_batches(node))
    for key in props:
        assert f".property('{key}'" in written, f"{key} was dropped"
    assert ".property('name'" in written


def test_later_batches_attach_to_the_vertex_the_first_one_created() -> None:
    from utils.graph_loader.stores.gremlin import vertex_upsert_batches

    node = {"id": "n1", "label": "Campaign", "properties": {f"p{i}": i for i in range(24)}}
    batches = vertex_upsert_batches(node)
    assert batches[0][0].startswith("g.V().has('id', nodeId).fold().coalesce(")
    for traversal, bindings in batches[1:]:
        assert traversal.startswith("g.V().has('id', nodeId)")
        assert "addV" not in traversal
        assert bindings["nodeId"] == "n1"


def test_binding_names_cannot_collide_between_similar_keys() -> None:
    """Two keys that sanitize alike must not share a binding name."""
    from utils.graph_loader.stores.gremlin import vertex_upsert_batches

    node = {"id": "n1", "label": "Campaign", "properties": {"a-b": 1, "a_b": 2}}
    traversal, bindings = vertex_upsert_batches(node)[0]
    assert bindings["p0"] == 1 and bindings["p1"] == 2


def test_the_single_submission_form_refuses_to_truncate() -> None:
    import pytest

    from utils.graph_loader.stores.gremlin import vertex_upsert_traversal

    node = {"id": "n1", "label": "Campaign", "properties": {f"p{i}": i for i in range(24)}}
    with pytest.raises(ValueError, match="vertex_upsert_batches"):
        vertex_upsert_traversal(node)


def test_a_payload_id_cannot_redefine_the_vertex_identity() -> None:
    """CAPEC's REF-97 carried properties.id="REF-97" under a longer node id.

    Written after the identity property, it silently renamed the vertex: the
    edge pointing at the real id then matched nothing and was dropped without an
    error, and a reload created a duplicate instead of matching.
    """
    from utils.graph_loader.stores.gremlin import vertex_upsert_batches

    node = {
        "id": "capec:external-reference:REF-97",
        "label": "ExternalReference",
        "properties": {"id": "REF-97", "title": "a reference"},
    }
    traversal, bindings = vertex_upsert_batches(node)[0]
    assert bindings["nodeId"] == "capec:external-reference:REF-97"
    assert "REF-97" not in [v for k, v in bindings.items() if k.startswith("p")]
    assert traversal.count(".property('id'") == 1
