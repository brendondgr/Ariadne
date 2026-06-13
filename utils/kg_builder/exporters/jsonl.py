#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path

from ..io import write_jsonl
from ..models import NormalizedGraph


def export_jsonl_artifacts(graph: NormalizedGraph, output_dir: Path) -> dict[str, Path]:
    """Write nodes.jsonl and relationships.jsonl."""
    nodes_path = output_dir / "nodes.jsonl"
    rels_path = output_dir / "relationships.jsonl"
    write_jsonl(nodes_path, [n.to_dict() for n in graph.nodes])
    write_jsonl(rels_path, [r.to_dict() for r in graph.relationships])
    return {"nodes": nodes_path, "relationships": rels_path}
