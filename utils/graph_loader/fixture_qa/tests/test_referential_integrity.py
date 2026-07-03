#!/usr/bin/env python3
"""Tests for the live referential-integrity store method (via MemoryGraphStore)."""

from __future__ import annotations

from utils.graph_loader.stores.memory import MemoryGraphStore


def _store(nodes, edges) -> MemoryGraphStore:
    store = MemoryGraphStore()
    store.connect()
    store.upsert_nodes(nodes)
    store.upsert_edges(edges)
    return store


def test_clean_graph_passes() -> None:
    nodes = [
        {"id": "a", "label": "Group"},
        {"id": "b", "label": "Technique"},
    ]
    edges = [{"id": "e1", "type": "USES", "source_id": "a", "target_id": "b"}]
    result = _store(nodes, edges).referential_integrity()
    assert result.passed
    assert result.dangling_edges == 0
    assert result.nodes_missing_id == 0
    assert result.details == []


def test_dangling_edge_detected() -> None:
    nodes = [{"id": "a", "label": "Group"}]
    edges = [{"id": "e1", "type": "USES", "source_id": "a", "target_id": "ghost"}]
    result = _store(nodes, edges).referential_integrity()
    assert not result.passed
    assert result.dangling_edges == 1
    assert any("missing node id" in d for d in result.details)


def test_node_missing_id_detected() -> None:
    store = MemoryGraphStore()
    store.connect()
    # bypass id-keyed upsert to simulate an id-less node
    store._nodes["placeholder"] = {"id": "", "label": "Group"}
    result = store.referential_integrity()
    assert not result.passed
    assert result.nodes_missing_id == 1
