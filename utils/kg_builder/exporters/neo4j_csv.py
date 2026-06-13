#!/usr/bin/env python3

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from ..io import ensure_dir, write_text
from ..models import EdgeRecord, NodeRecord
from ..schema.attack import constraints_cypher_lines, schema_cypher_lines


def _primary_label(node: dict[str, Any] | NodeRecord) -> str:
    if isinstance(node, NodeRecord):
        return node.label
    labels = node.get("labels")
    if labels:
        return labels[0]
    return node["label"]


def _node_field(node: dict[str, Any] | NodeRecord, key: str, default: str = "") -> str:
    if isinstance(node, NodeRecord):
        value = node.properties.get(key)
        if value is None and key == "attack_id":
            return default
        return str(value) if value is not None else default
    props = node.get("properties", {})
    value = props.get(key)
    return str(value) if value is not None else default


def _serialize_neo4j_property(value: Any) -> str:
    """Serialize nested values for Neo4j CSV import."""
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return str(value)


def export_cypher_artifacts(output_dir: Path) -> dict[str, Path]:
    """Write schema.cypher and constraints.cypher to Neo4j export directory."""
    ensure_dir(output_dir)
    schema_path = output_dir / "schema.cypher"
    constraints_path = output_dir / "constraints.cypher"
    write_text(schema_path, "\n".join(schema_cypher_lines()) + "\n")
    write_text(constraints_path, "\n".join(constraints_cypher_lines()) + "\n")
    return {"schema": schema_path, "constraints": constraints_path}


def export_neo4j_csv_artifacts(
    nodes: list[dict[str, Any]] | list[NodeRecord],
    edges: list[dict[str, Any]] | list[EdgeRecord],
    output_dir: Path,
) -> dict[str, Path]:
    """Write Neo4j-compatible CSV files derived from canonical records."""
    ensure_dir(output_dir)
    nodes_path = output_dir / "nodes.csv"
    rels_path = output_dir / "relationships.csv"

    with open(nodes_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["id:ID", "label:LABEL", "name", "attack_id", "stix_type", "properties_json"],
        )
        writer.writeheader()
        for node in nodes:
            if isinstance(node, NodeRecord):
                node_dict = node.to_dict()
            else:
                node_dict = node
            writer.writerow(
                {
                    "id:ID": node_dict["id"],
                    "label:LABEL": _primary_label(node_dict),
                    "name": node_dict.get("name") or "",
                    "attack_id": _node_field(node_dict, "attack_id"),
                    "stix_type": _node_field(node_dict, "stix_type"),
                    "properties_json": _serialize_neo4j_property(node_dict.get("properties", {})),
                }
            )

    with open(rels_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[":START_ID", ":END_ID", ":TYPE"],
        )
        writer.writeheader()
        for edge in edges:
            if isinstance(edge, EdgeRecord):
                edge_dict = edge.to_dict()
            else:
                edge_dict = edge
            writer.writerow(
                {
                    ":START_ID": edge_dict["source_id"],
                    ":END_ID": edge_dict["target_id"],
                    ":TYPE": edge_dict["type"],
                }
            )

    return {"nodes": nodes_path, "relationships": rels_path}
