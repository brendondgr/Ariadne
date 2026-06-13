#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path

from .io import read_jsonl
from .models import NormalizedGraph
from .schema.attack import ATTACK_NODE_LABELS, ATTACK_RELATIONSHIP_TYPES


class ArtifactValidationError(Exception):
    """Raised when graph artifacts fail validation."""


def validate_graph(graph: NormalizedGraph) -> None:
    """Validate normalized graph internal consistency."""
    node_ids = {n.id for n in graph.nodes}
    if len(node_ids) != len(graph.nodes):
        raise ArtifactValidationError("Duplicate node ids detected.")

    for node in graph.nodes:
        if node.label not in ATTACK_NODE_LABELS:
            raise ArtifactValidationError(f"Unknown node label: {node.label}")

    for rel in graph.relationships:
        if rel.type not in ATTACK_RELATIONSHIP_TYPES:
            raise ArtifactValidationError(f"Unknown relationship type: {rel.type}")
        if rel.source_id not in node_ids:
            raise ArtifactValidationError(
                f"Relationship {rel.id} missing source node: {rel.source_id}"
            )
        if rel.target_id not in node_ids:
            raise ArtifactValidationError(
                f"Relationship {rel.id} missing target node: {rel.target_id}"
            )


def validate_jsonl_artifacts(nodes_path: Path, relationships_path: Path) -> None:
    """Validate JSONL artifact endpoint integrity."""
    node_ids = {record["id"] for record in read_jsonl(nodes_path)}
    for rel in read_jsonl(relationships_path):
        if rel["source_id"] not in node_ids:
            raise ArtifactValidationError(
                f"Relationship {rel['id']} missing source node: {rel['source_id']}"
            )
        if rel["target_id"] not in node_ids:
            raise ArtifactValidationError(
                f"Relationship {rel['id']} missing target node: {rel['target_id']}"
            )
