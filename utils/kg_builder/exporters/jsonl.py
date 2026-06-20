#!/usr/bin/env python3

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from ..dataset import dataset_for_graph
from ..io import write_json, write_jsonl
from ..models import NormalizedGraph
from ..schema.attack import ATTACK_NODE_LABELS, ATTACK_RELATIONSHIP_TYPES
from ..schema.capec import build_schema_document as build_capec_schema_document

# Cap example values so a long `description` doesn't bloat schema.json / the card.
_EXAMPLE_MAX_LEN = 120


def _json_type(value: Any) -> str:
    """Map a Python property value to its JSON-schema-style type name."""
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "string"


def _example_value(value: Any) -> Any:
    """Return a compact, representative example value for a property."""
    if isinstance(value, str) and len(value) > _EXAMPLE_MAX_LEN:
        return value[:_EXAMPLE_MAX_LEN] + "…"
    return value


def introspect_node_properties(node_dicts: list[dict[str, Any]]) -> dict[str, Any]:
    """Introspect per-label property keys, types, coverage, and an example value.

    Returns ``{label: {prop: {"type", "optional", "example"}}}`` so a specialist
    can choose WHERE filters and RETURN fields without guessing. ``optional`` is
    True when the key is absent on some node of that label. Types are introspected
    from actual values; a key with mixed types reports a sorted list of them.
    """
    label_counts: dict[str, int] = defaultdict(int)
    # label -> prop -> {count, types(set), example}
    seen: dict[str, dict[str, dict[str, Any]]] = defaultdict(lambda: defaultdict(
        lambda: {"count": 0, "types": set(), "example": None}
    ))

    for node in node_dicts:
        label = node["label"]
        label_counts[label] += 1
        # `id`/`name` are canonical top-level node fields in some backends (e.g. the
        # CAPEC Gremlin export) and folded into `properties` in others (ATT&CK).
        # Surface them uniformly so a specialist always sees the identity/display
        # fields regardless of how the backend stores them.
        merged: dict[str, Any] = {}
        for identity in ("id", "name"):
            if node.get(identity) is not None:
                merged[identity] = node[identity]
        merged.update(node.get("properties", {}))
        for key, value in merged.items():
            slot = seen[label][key]
            slot["count"] += 1
            slot["types"].add(_json_type(value))
            if slot["example"] is None and value not in (None, "", [], {}):
                slot["example"] = _example_value(value)

    result: dict[str, Any] = {}
    for label in sorted(seen):
        total = label_counts[label]
        props: dict[str, Any] = {}
        for key in sorted(seen[label]):
            slot = seen[label][key]
            types = sorted(slot["types"])
            props[key] = {
                "type": types[0] if len(types) == 1 else types,
                "optional": slot["count"] < total,
                "example": slot["example"],
            }
        result[label] = props
    return result


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

    node_dicts = [n.to_dict() for n in graph.nodes]
    write_jsonl(nodes_path, node_dicts)
    write_jsonl(rels_path, [r.to_dict() for r in graph.relationships])

    schema = canonical_schema_dict(dataset=dataset, schema_version=schema_version)
    schema["node_properties"] = introspect_node_properties(node_dicts)
    write_json(schema_path, schema, sort_keys=True)

    return {
        "nodes": nodes_path,
        "relationships": rels_path,
        "schema": schema_path,
    }


def export_jsonl_artifacts(graph: NormalizedGraph, output_dir: Path) -> dict[str, Path]:
    """Write nodes.jsonl and relationships.jsonl (alias for canonical export)."""
    return export_canonical_artifacts(graph, output_dir)
