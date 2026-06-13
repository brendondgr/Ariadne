#!/usr/bin/env python3

from __future__ import annotations

import csv
from pathlib import Path

from ..io import ensure_dir
from ..models import NormalizedGraph


def export_neo4j_csv_artifacts(graph: NormalizedGraph, output_dir: Path) -> dict[str, Path]:
    """Write Neo4j-compatible CSV node and relationship files."""
    ensure_dir(output_dir)
    nodes_path = output_dir / "nodes.csv"
    rels_path = output_dir / "relationships.csv"

    with open(nodes_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["id:ID", "label:LABEL", "name", "attack_id", "stix_type"],
        )
        writer.writeheader()
        for node in graph.nodes:
            writer.writerow(
                {
                    "id:ID": node.id,
                    "label:LABEL": node.label,
                    "name": node.name or "",
                    "attack_id": node.attack_id or "",
                    "stix_type": node.stix_type or "",
                }
            )

    with open(rels_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[":START_ID", ":END_ID", ":TYPE"],
        )
        writer.writeheader()
        for rel in graph.relationships:
            writer.writerow(
                {
                    ":START_ID": rel.source_id,
                    ":END_ID": rel.target_id,
                    ":TYPE": rel.type,
                }
            )

    return {"nodes": nodes_path, "relationships": rels_path}
