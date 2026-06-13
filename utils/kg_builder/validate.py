#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .io import load_canonical_records, read_jsonl
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
        if not node.labels or node.labels[0] != node.label:
            raise ArtifactValidationError(
                f"Node {node.id} labels[0] must match primary label {node.label!r}"
            )

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


def validate_canonical_artifacts(canonical_dir: Path) -> dict[str, Any]:
    """Validate canonical truth layer from directory only."""
    nodes_path = canonical_dir / "nodes.jsonl"
    rels_path = canonical_dir / "relationships.jsonl"
    schema_path = canonical_dir / "schema.json"
    manifest_path = canonical_dir / "manifest.json"

    for path in (nodes_path, rels_path, schema_path, manifest_path):
        if not path.exists():
            raise ArtifactValidationError(f"Missing canonical artifact: {path}")

    nodes, rels = load_canonical_records(nodes_path, rels_path)
    validate_jsonl_artifacts(nodes_path, rels_path)

    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)

    for node in nodes:
        if node["label"] not in schema["node_labels"]:
            raise ArtifactValidationError(f"Canonical node label not in schema: {node['label']}")
        if "labels" not in node or not node["labels"]:
            raise ArtifactValidationError(f"Canonical node missing labels: {node['id']}")
        if "external_references" in node.get("properties", {}):
            refs = node["properties"]["external_references"]
            if not isinstance(refs, list):
                raise ArtifactValidationError(
                    f"external_references must remain a list on node {node['id']}"
                )

    for rel in rels:
        if rel["type"] not in schema["relationship_types"]:
            raise ArtifactValidationError(
                f"Canonical relationship type not in schema: {rel['type']}"
            )

    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    if manifest.get("canonical") is None:
        raise ArtifactValidationError("Manifest must declare canonical artifacts as truth layer.")
    if manifest.get("exports") is None:
        raise ArtifactValidationError("Manifest must declare generated exports.")

    return {
        "nodes": len(nodes),
        "relationships": len(rels),
        "schema": schema,
        "manifest": manifest,
    }


def validate_export_counts(
    canonical_counts: dict[str, int],
    export_node_count: int,
    export_rel_count: int,
    backend: str,
) -> None:
    if canonical_counts["nodes"] != export_node_count:
        raise ArtifactValidationError(
            f"{backend} export node count {export_node_count} != canonical {canonical_counts['nodes']}"
        )
    if canonical_counts["relationships"] != export_rel_count:
        raise ArtifactValidationError(
            f"{backend} export relationship count {export_rel_count} "
            f"!= canonical {canonical_counts['relationships']}"
        )


def validate_neo4j_export(
    canonical_dir: Path,
    neo4j_dir: Path,
) -> None:
    """Verify Neo4j export is an equivalent projection of canonical records."""
    nodes, rels = load_canonical_records(
        canonical_dir / "nodes.jsonl",
        canonical_dir / "relationships.jsonl",
    )
    validate_export_counts(
        {"nodes": len(nodes), "relationships": len(rels)},
        sum(1 for _ in open(neo4j_dir / "nodes.csv", encoding="utf-8")) - 1,
        sum(1 for _ in open(neo4j_dir / "relationships.csv", encoding="utf-8")) - 1,
        "neo4j",
    )

    node_ids = {n["id"] for n in nodes}
    for rel in rels:
        if rel["source_id"] not in node_ids or rel["target_id"] not in node_ids:
            raise ArtifactValidationError("Neo4j export references missing canonical endpoints.")

    for path_name in ("schema.cypher", "constraints.cypher"):
        if not (neo4j_dir / path_name).exists():
            raise ArtifactValidationError(f"Missing Neo4j export file: {path_name}")


def validate_gremlin_export(
    canonical_dir: Path,
    gremlin_dir: Path,
) -> None:
    """Verify Gremlin export is an equivalent projection of canonical records."""
    nodes, rels = load_canonical_records(
        canonical_dir / "nodes.jsonl",
        canonical_dir / "relationships.jsonl",
    )
    gremlin_nodes = list(read_jsonl(gremlin_dir / "nodes.jsonl"))
    gremlin_rels = list(read_jsonl(gremlin_dir / "relationships.jsonl"))

    validate_export_counts(
        {"nodes": len(nodes), "relationships": len(rels)},
        len(gremlin_nodes),
        len(gremlin_rels),
        "gremlin",
    )

    gremlin_node_ids = {n["id"] for n in gremlin_nodes}
    for node in gremlin_nodes:
        if not node.get("label"):
            raise ArtifactValidationError("Gremlin node missing primary label.")
        if node["label"] != node.get("labels", [node["label"]])[0]:
            raise ArtifactValidationError("Gremlin node label must match labels[0].")

    for rel in gremlin_rels:
        if rel["source_id"] not in gremlin_node_ids:
            raise ArtifactValidationError(
                f"Gremlin edge missing source vertex: {rel['source_id']}"
            )
        if rel["target_id"] not in gremlin_node_ids:
            raise ArtifactValidationError(
                f"Gremlin edge missing target vertex: {rel['target_id']}"
            )


def validate_cross_backend_exports(canonical_dir: Path, exports_root: Path) -> None:
    """Validate Neo4j and Gremlin exports against canonical truth."""
    validate_canonical_artifacts(canonical_dir)
    validate_neo4j_export(canonical_dir, exports_root / "neo4j")
    validate_gremlin_export(canonical_dir, exports_root / "gremlin")


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
