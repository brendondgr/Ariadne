#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..dataset import dataset_for_graph
from ..io import write_json, write_jsonl
from ..models import NormalizedGraph
from ..schema.attack import ATTACK_NODE_LABELS, ATTACK_RELATIONSHIP_TYPES
from ..schema.capec import build_schema_document as build_capec_schema_document


def canonical_schema_dict(*, dataset: str = "attack", schema_version: str = "1.0") -> dict[str, Any]:
    """Return canonical schema vocabulary for a dataset."""
    if dataset == "capec":
        return build_capec_schema_document(schema_version)
    return {
        "schema_version": schema_version,
        "dataset": "attack",
        "node_labels": sorted(ATTACK_NODE_LABELS),
        "relationship_types": sorted(ATTACK_RELATIONSHIP_TYPES),
    }


def export_canonical_artifacts(
    graph: NormalizedGraph,
    canonical_dir: Path,
    *,
    schema_version: str = "1.0",
) -> dict[str, Path]:
    """Write canonical truth artifacts: JSONL nodes/edges and schema.json."""
    dataset = dataset_for_graph(graph)
    nodes_path = canonical_dir / "nodes.jsonl"
    rels_path = canonical_dir / "relationships.jsonl"
    schema_path = canonical_dir / "schema.json"

    write_jsonl(nodes_path, [n.to_dict() for n in graph.nodes])
    write_jsonl(rels_path, [r.to_dict() for r in graph.relationships])
    write_json(
        schema_path,
        canonical_schema_dict(dataset=dataset, schema_version=schema_version),
        sort_keys=True,
    )

    return {
        "nodes": nodes_path,
        "relationships": rels_path,
        "schema": schema_path,
    }


def export_jsonl_artifacts(graph: NormalizedGraph, output_dir: Path) -> dict[str, Path]:
    """Write nodes.jsonl and relationships.jsonl (alias for canonical export)."""
    return export_canonical_artifacts(graph, output_dir)
