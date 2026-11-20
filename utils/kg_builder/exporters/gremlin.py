#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..io import ensure_dir, write_jsonl
from ..models import EdgeRecord, NodeRecord
from ..property_encoding import stored_properties

# Gremlin and Neo4j store a property value the same way (see
# ``utils/kg_builder/property_encoding.py``): scalars as they are, homogeneous
# scalar lists as list values, empty lists and None not at all, and maps or
# lists of maps as JSON text. Until 2026-11-20 every list was JSON text here.
GREMLIN_PROPERTY_SERIALIZATION = "scalar_lists_as_lists_json_string_for_objects"


def _serialize_gremlin_properties(properties: dict[str, Any]) -> dict[str, Any]:
    return stored_properties(properties)


def _gremlin_node_record(node: dict[str, Any] | NodeRecord) -> dict[str, Any]:
    if isinstance(node, NodeRecord):
        node_dict = node.to_dict()
    else:
        node_dict = node
    labels = node_dict.get("labels") or [node_dict["label"]]
    return {
        "id": node_dict["id"],
        "label": labels[0],
        "labels": labels,
        "name": node_dict.get("name"),
        "properties": _serialize_gremlin_properties(node_dict.get("properties", {})),
    }


def _gremlin_edge_record(edge: dict[str, Any] | EdgeRecord) -> dict[str, Any]:
    if isinstance(edge, EdgeRecord):
        edge_dict = edge.to_dict()
    else:
        edge_dict = edge
    return {
        "id": edge_dict["id"],
        "type": edge_dict["type"],
        "source_id": edge_dict["source_id"],
        "target_id": edge_dict["target_id"],
        "properties": _serialize_gremlin_properties(edge_dict.get("properties", {})),
    }


def export_gremlin_artifacts(
    nodes: list[dict[str, Any]] | list[NodeRecord],
    edges: list[dict[str, Any]] | list[EdgeRecord],
    output_dir: Path,
) -> dict[str, Path]:
    """Write Gremlin-ready node and relationship JSONL from canonical records."""
    ensure_dir(output_dir)
    nodes_path = output_dir / "nodes.jsonl"
    rels_path = output_dir / "relationships.jsonl"

    node_records = [_gremlin_node_record(n) for n in nodes]
    edge_records = [_gremlin_edge_record(e) for e in edges]

    node_records.sort(key=lambda r: r["id"])
    edge_records.sort(key=lambda r: (r["type"], r["source_id"], r["target_id"], r["id"]))

    write_jsonl(nodes_path, node_records)
    write_jsonl(rels_path, edge_records)

    return {"nodes": nodes_path, "relationships": rels_path, "serialization": GREMLIN_PROPERTY_SERIALIZATION}
