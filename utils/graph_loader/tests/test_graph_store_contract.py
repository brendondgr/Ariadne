#!/usr/bin/env python3

from __future__ import annotations

import pytest

from utils.graph_loader.models import CountSummary
from utils.graph_loader.stores.memory import MemoryGraphStore


def test_memory_store_contract_lifecycle() -> None:
    store = MemoryGraphStore()
    store.connect()
    assert store.healthcheck()

    store.ensure_schema({})
    store.upsert_nodes(
        [
            {
                "id": "n1",
                "label": "Technique",
                "labels": ["Technique", "AttackObject"],
                "properties": {"attack_id": "T1000"},
            }
        ]
    )
    store.upsert_edges(
        [
            {
                "id": "e1",
                "type": "USES",
                "source_id": "n1",
                "target_id": "n1",
            }
        ]
    )

    assert store.count_nodes() == 1
    assert store.count_edges() == 1
    assert store.count_by_label("Technique") == 1
    assert store.sample_node("Technique") is not None

    expected = CountSummary(nodes=1, edges=1, nodes_by_label={"Technique": 1}, edges_by_type={"USES": 1})
    result = store.verify_loaded_graph(expected)
    assert result.passed

    store.close()
    assert not store.healthcheck()


def test_idempotent_edge_upsert() -> None:
    store = MemoryGraphStore()
    store.connect()
    edge = {
        "id": "e1",
        "type": "USES",
        "source_id": "a",
        "target_id": "b",
    }
    store.upsert_edges([edge])
    store.upsert_edges([edge])
    assert store.count_edges() == 1


def test_memory_store_constraint_names(tmp_path) -> None:
    from pathlib import Path

    constraints = tmp_path / "constraints.cypher"
    constraints.write_text(
        "// generated\n"
        "CREATE CONSTRAINT attack_stix_id_unique IF NOT EXISTS "
        "FOR (n:AttackObject) REQUIRE n.id IS UNIQUE;\n"
        "CREATE CONSTRAINT attack_id_type_unique IF NOT EXISTS "
        "FOR (n:AttackObject) REQUIRE (n.attack_id, n.stix_type) IS UNIQUE;\n",
        encoding="utf-8",
    )
    store = MemoryGraphStore()
    store.connect()
    assert store.list_constraint_names() == []
    store.ensure_schema({"constraints_cypher": str(constraints)})
    assert store.list_constraint_names() == [
        "attack_id_type_unique",
        "attack_stix_id_unique",
    ]
