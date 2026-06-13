#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..io import ensure_dir, write_jsonl
from ..models import EdgeRecord, NodeRecord

# Gremlin/TinkerPop property values must be scalars; nested structures are JSON-encoded.
GREMLIN_PROPERTY_SERIALIZATION = "json_string_for_nested"


def _serialize_gremlin_properties(properties: dict[str, Any]) -> dict[str, Any]:
    serialized: dict[str, Any] = {}
    for key, value in properties.items():
        if isinstance(value, (dict, list)):
            serialized[key] = json.dumps(value, sort_keys=True)
        elif value is None:
            continue
        else:
            serialized[key] = value
    return serialized


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
