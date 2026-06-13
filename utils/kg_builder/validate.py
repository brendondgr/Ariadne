#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

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


def validate_manifest_counts(manifest_path: Path, pairs_path: Path) -> None:
    """Ensure manifest counts match the processed pairs checkpoint."""
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    with open(pairs_path, encoding="utf-8") as f:
        pairs = json.load(f)
    if manifest["counts"] != pairs["counts"]:
        raise ArtifactValidationError("Manifest counts do not match processed pairs checkpoint.")


def validate_deterministic_ordering(nodes_path: Path, relationships_path: Path) -> None:
    """Ensure JSONL records are sorted deterministically by id."""
    node_ids = [record["id"] for record in read_jsonl(nodes_path)]
    if node_ids != sorted(node_ids):
        raise ArtifactValidationError("nodes.jsonl is not sorted by id.")

    rel_keys = [
        (r["type"], r["source_id"], r["target_id"], r["id"])
        for r in read_jsonl(relationships_path)
    ]
    if rel_keys != sorted(rel_keys):
        raise ArtifactValidationError("relationships.jsonl is not sorted deterministically.")


def manifest_file_hashes(manifest_path: Path) -> dict[str, str]:
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    return manifest.get("hashes", {})


def compute_artifact_hashes(artifact_paths: dict[str, str]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for name, path_str in artifact_paths.items():
        path = Path(path_str)
        digest = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                digest.update(chunk)
        hashes[name] = digest.hexdigest()
    return hashes


def validate_reproducibility(previous_manifest: dict[str, Any], current_manifest: dict[str, Any]) -> None:
    """Compare manifests from repeated builds with unchanged input."""
    if previous_manifest.get("counts") != current_manifest.get("counts"):
        raise ArtifactValidationError("Counts changed between reproducible builds.")
    if previous_manifest.get("hashes") != current_manifest.get("hashes"):
        raise ArtifactValidationError("Artifact hashes changed between reproducible builds.")
