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
