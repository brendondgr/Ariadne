"""Service layer for reading canonical graph files from disk.

Provides ``load_canonical_graph`` which reads nodes.jsonl / relationships.jsonl /
manifest.json from the canonical directory for a given dataset and returns a
dict shaped exactly like ``GraphPayloadResponse``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from utils.graph_loader.config import LoaderConfig

from utils.planner.cards import load_card_backends

# Fallback backend labels for the built-ins when no card is on disk.
_DATASET_BACKEND: dict[str, str] = {
    "attack": "neo4j",
    "capec": "gremlin",
}


def dataset_backend(dataset: str, config: LoaderConfig) -> str:
    """The backend label for ``dataset``: its card's ``runtime_backend``, else
    the built-in fallback, else ``"unknown"``."""
    return (
        load_card_backends(config.data_dir).get(dataset)
        or _DATASET_BACKEND.get(dataset, "unknown")
    )

_DESC_PREVIEW_LEN = 280


def _canonical_dir(dataset: str, config: LoaderConfig) -> Path:
    return config.graphs_dir(dataset) / "canonical"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_canonical_graph(
    dataset: str,
    config: LoaderConfig | None = None,
) -> dict[str, Any]:
    """Read canonical graph files and return a response-shaped dict.

    Parameters
    ----------
    dataset:
        One of ``"attack"`` or ``"capec"``.
    config:
        Optional ``LoaderConfig``; resolved via ``LoaderConfig.from_data_dir()``
        when not supplied.

    Raises
    ------
    FileNotFoundError
        When the canonical directory or one of the required JSONL files is absent.
    """
    config = config or LoaderConfig.from_data_dir()
    canonical = _canonical_dir(dataset, config)

    if not canonical.exists():
        raise FileNotFoundError(
            f"Canonical directory not found for dataset '{dataset}': {canonical}"
        )

    nodes_path = canonical / "nodes.jsonl"
    rels_path = canonical / "relationships.jsonl"

    for p in (nodes_path, rels_path):
        if not p.exists():
            raise FileNotFoundError(f"Required file missing: {p}")

    # -- Nodes ----------------------------------------------------------------
    raw_nodes = _read_jsonl(nodes_path)
    nodes: list[dict[str, Any]] = []
    for raw in raw_nodes:
        props: dict[str, Any] = dict(raw.get("properties") or {})
        # Drop external_references (largest field).
        props.pop("external_references", None)
        # Truncate description to a short preview.
        desc = props.get("description")
        if isinstance(desc, str) and len(desc) > _DESC_PREVIEW_LEN:
            props["description"] = desc[:_DESC_PREVIEW_LEN]

        nodes.append(
            {
                "id": raw["id"],
                "label": raw["label"],
                "labels": raw.get("labels") or [],
                "name": raw.get("name") or "",
                "properties": props,
            }
        )

    # -- Edges ----------------------------------------------------------------
    raw_rels = _read_jsonl(rels_path)
    edges: list[dict[str, Any]] = [
        {
            "id": r["id"],
            "source": r["source_id"],
            "target": r["target_id"],
            "type": r["type"],
        }
        for r in raw_rels
    ]

    # -- Manifest -------------------------------------------------------------
    manifest_path = canonical / "manifest.json"
    if manifest_path.exists():
        with open(manifest_path, encoding="utf-8") as fh:
            manifest = json.load(fh)
        counts_raw = manifest.get("counts", {})
        counts = {
            "nodes": counts_raw.get("nodes", len(nodes)),
            "relationships": counts_raw.get("relationships", len(edges)),
        }
        nodes_by_label: dict[str, int] = counts_raw.get("nodes_by_label") or {}
    else:
        counts = {"nodes": len(nodes), "relationships": len(edges)}
        nodes_by_label = {}

    return {
        "dataset": dataset,
        "backend": dataset_backend(dataset, config),
        "counts": counts,
        "nodes_by_label": nodes_by_label,
        "nodes": nodes,
        "edges": edges,
    }
