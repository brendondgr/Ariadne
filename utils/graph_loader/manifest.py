#!/usr/bin/env python3

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from utils.kg_builder.io import ensure_dir, file_sha256

from .models import CountSummary, VerifyLoadedGraphResult
from .results import BackendLoadResult
from .stores.base import GraphStore


def build_load_manifest(
    *,
    dataset: str,
    backend: str,
    canonical_manifest_path: Path,
    canonical_manifest_hash: str,
    semantic_valid: bool,
    endpoint: str,
    adapter_version: str,
    expected_counts: CountSummary,
    verification: VerifyLoadedGraphResult,
    nodes_loaded: int,
    edges_loaded: int,
) -> dict[str, Any]:
    return {
        "dataset": dataset,
        "backend": backend,
        "loaded_timestamp": datetime.now(timezone.utc).isoformat(),
        "canonical_manifest": str(canonical_manifest_path),
        "canonical_manifest_hash": canonical_manifest_hash,
        "semantic_validation_passed": semantic_valid,
        "endpoint": endpoint,
        "adapter_version": adapter_version,
        "nodes_loaded": nodes_loaded,
        "edges_loaded": edges_loaded,
        "expected_counts": {
            "nodes": expected_counts.nodes,
            "edges": expected_counts.edges,
            "nodes_by_label": expected_counts.nodes_by_label,
            "relationships_by_type": expected_counts.edges_by_type,
        },
        "verification": {
            "passed": verification.passed,
            "actual_counts": {
                "nodes": verification.actual.nodes,
                "edges": verification.actual.edges,
                "nodes_by_label": verification.actual.nodes_by_label,
                "relationships_by_type": verification.actual.edges_by_type,
            },
            "errors": verification.errors,
        },
    }


def write_load_manifest(path: Path, manifest: dict[str, Any]) -> Path:
    ensure_dir(path.parent)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
        f.write("\n")
    return path


def write_backend_load_manifest(
    *,
    store: GraphStore,
    result: BackendLoadResult,
    dataset: str,
    canonical_manifest_path: Path,
    semantic_valid: bool,
    expected_counts: CountSummary,
    verification: VerifyLoadedGraphResult,
    runtime_manifest_path: Path,
) -> Path:
    manifest = build_load_manifest(
        dataset=dataset,
        backend=store.metadata.backend,
        canonical_manifest_path=canonical_manifest_path,
        canonical_manifest_hash=file_sha256(canonical_manifest_path),
        semantic_valid=semantic_valid,
        endpoint=store.metadata.endpoint,
        adapter_version=store.metadata.adapter_version,
        expected_counts=expected_counts,
        verification=verification,
        nodes_loaded=result.nodes_loaded,
        edges_loaded=result.edges_loaded,
    )
    path = write_load_manifest(runtime_manifest_path, manifest)
    result.runtime_manifest_path = str(path)
    return path
