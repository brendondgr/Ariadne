#!/usr/bin/env python3

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import LOAD_BACKENDS, SUPPORTED_DATASETS, LoaderConfig

__all__ = [
    "SUPPORTED_DATASETS",   # re-exported: this module had its own copy until
                            # 2026-08-20, and adding a dataset to the one in
                            # config.py left this one behind, so the loader
                            # rejected a dataset the config had allowed.
    "LoaderResolutionError",
    "BackendLoadTarget",
    "DatasetLoadTarget",
    "resolve_dataset",
]


class LoaderResolutionError(Exception):
    """Raised when a dataset or backend cannot be resolved for loading."""


@dataclass(frozen=True)
class BackendLoadTarget:
    """Resolved backend export paths for a single graph store."""

    backend: str
    export_files: dict[str, Path]
    runtime_manifest_path: Path


@dataclass(frozen=True)
class DatasetLoadTarget:
    """Resolved load target for a built dataset and requested backend action."""

    dataset: str
    backend: str
    source_card_path: Path
    source_card: dict[str, Any]
    canonical_dir: Path
    manifest_path: Path
    manifest: dict[str, Any]
    schema_path: Path
    nodes_path: Path
    relationships_path: Path
    backends: dict[str, BackendLoadTarget]
    endpoints: dict[str, str]


def _read_json(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _resolve_path(base: Path, value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def _require_file(path: Path, context: str) -> None:
    if not path.exists():
        raise LoaderResolutionError(f"Missing {context}: {path}")


def _resolve_backend_exports(
    *,
    dataset: str,
    backend: str,
    manifest: dict[str, Any],
    source_card: dict[str, Any],
    config: LoaderConfig,
) -> BackendLoadTarget:
    if backend not in LOAD_BACKENDS:
        raise LoaderResolutionError(f"Unsupported backend: {backend}")

    manifest_exports = manifest.get("exports", {}).get(backend, {})
    card_exports = source_card.get("exports", {}).get(backend, {})
    merged_exports = {**card_exports, **manifest_exports}
    if not merged_exports:
        raise LoaderResolutionError(
            f"Dataset {dataset!r} has no {backend} export paths in manifest or source card."
        )

    export_files = {
        name: _resolve_path(config.data_dir.parent, path_str)
        for name, path_str in merged_exports.items()
    }
    for name, path in export_files.items():
        _require_file(path, f"{backend} export file {name}")

    runtime_manifest = config.runtime_dir(dataset, backend) / "load-manifest.json"
    return BackendLoadTarget(
        backend=backend,
        export_files=export_files,
        runtime_manifest_path=runtime_manifest,
    )


def resolve_dataset(
    dataset: str,
    backend: str,
    config: LoaderConfig | None = None,
) -> DatasetLoadTarget:
    """Resolve a built dataset and backend into concrete artifact paths."""
    config = config or LoaderConfig.from_data_dir()
    dataset = dataset.lower().strip()

    if dataset not in SUPPORTED_DATASETS:
        raise LoaderResolutionError(f"Unsupported dataset: {dataset}")

    source_card_path = config.source_cards_dir() / f"{dataset}.json"
    _require_file(source_card_path, "source card")

    source_card = _read_json(source_card_path)
    canonical_dir = _resolve_path(config.data_dir.parent, source_card["canonical_dir"])
    manifest_path = _resolve_path(config.data_dir.parent, source_card["canonical_manifest"])
    _require_file(manifest_path, "canonical manifest")

    manifest = _read_json(manifest_path)
    canonical_manifest = manifest.get("canonical", {})
    nodes_path = _resolve_path(
        config.data_dir.parent,
        canonical_manifest.get("nodes_jsonl", str(canonical_dir / "nodes.jsonl")),
    )
    relationships_path = _resolve_path(
        config.data_dir.parent,
        canonical_manifest.get(
            "relationships_jsonl", str(canonical_dir / "relationships.jsonl")
        ),
    )
    schema_path = _resolve_path(
        config.data_dir.parent,
        canonical_manifest.get("schema_json", str(canonical_dir / "schema.json")),
    )

    for path, label in (
        (nodes_path, "canonical nodes.jsonl"),
        (relationships_path, "canonical relationships.jsonl"),
        (schema_path, "canonical schema.json"),
    ):
        _require_file(path, label)

    endpoints = {
        "neo4j": source_card.get("endpoints", {}).get("neo4j") or config.neo4j_uri,
        "gremlin": source_card.get("endpoints", {}).get("gremlin") or config.gremlin_uri,
    }

    if backend == "all":
        backend_names = sorted(LOAD_BACKENDS)
    elif backend in LOAD_BACKENDS:
        backend_names = [backend]
    elif backend == "verify":
        backend_names = sorted(LOAD_BACKENDS)
    else:
        raise LoaderResolutionError(f"Unsupported graph action for resolution: {backend}")

    backends: dict[str, BackendLoadTarget] = {}
    for name in backend_names:
        backends[name] = _resolve_backend_exports(
            dataset=dataset,
            backend=name,
            manifest=manifest,
            source_card=source_card,
            config=config,
        )

    return DatasetLoadTarget(
        dataset=dataset,
        backend=backend,
        source_card_path=source_card_path,
        source_card=source_card,
        canonical_dir=canonical_dir,
        manifest_path=manifest_path,
        manifest=manifest,
        schema_path=schema_path,
        nodes_path=nodes_path,
        relationships_path=relationships_path,
        backends=backends,
        endpoints=endpoints,
    )
