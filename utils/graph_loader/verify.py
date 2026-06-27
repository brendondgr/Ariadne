#!/usr/bin/env python3

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from utils.kg_builder.io import file_sha256

from .config import LOAD_BACKENDS, LoaderConfig
from .loader import _expected_counts
from .models import CountSummary
from .preflight import PreflightError, run_preflight
from .registry import resolve_dataset
from .stores.factory import create_graph_store
from .validation.semantic import validate_semantic_artifacts

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DatasetVerifyResult:
    """Outcome of a no-load dataset verification run."""

    dataset: str
    passed: bool
    errors: list[str]
    backend_results: dict[str, dict[str, Any]]


def _load_runtime_manifest(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def verify_dataset(
    dataset: str,
    *,
    config: LoaderConfig | None = None,
    store_factory: Callable[..., Any] | None = None,
    check_reachability: bool = True,
) -> DatasetVerifyResult:
    """Verify built artifacts and live backend counts without loading."""
    config = config or LoaderConfig.from_data_dir()
    store_factory = store_factory or create_graph_store
    target = resolve_dataset(dataset, "verify", config)
    errors: list[str] = []
    backend_results: dict[str, dict[str, Any]] = {}

    try:
        run_preflight(target, backends=sorted(LOAD_BACKENDS), check_reachability=check_reachability)
    except (PreflightError, Exception) as exc:
        errors.append(str(exc))

    semantic = validate_semantic_artifacts(
        target.nodes_path,
        target.relationships_path,
        target.schema_path,
    )
    if not semantic.valid:
        errors.extend(semantic.errors[:5])

    expected = _expected_counts(target.manifest)
    canonical_hash = file_sha256(target.manifest_path)

    for backend in sorted(LOAD_BACKENDS):
        backend_info: dict[str, Any] = {"backend": backend}
        runtime_manifest_path = target.backends[backend].runtime_manifest_path
        runtime_manifest = _load_runtime_manifest(runtime_manifest_path)
        backend_info["runtime_manifest_exists"] = runtime_manifest is not None

        if runtime_manifest is None:
            logger.debug("No runtime manifest for %s (%s) — backend was never loaded; skipping.", backend, runtime_manifest_path)
            backend_info["skipped"] = True
            backend_results[backend] = backend_info
            continue

        if runtime_manifest.get("canonical_manifest_hash") != canonical_hash:
            errors.append(
                f"Stale runtime manifest for {backend}: canonical hash mismatch."
            )

        store = store_factory(backend, target, config)
        try:
            store.connect()
            verification = store.verify_loaded_graph(expected)
            backend_info["verification"] = {
                "passed": verification.passed,
                "actual": {
                    "nodes": verification.actual.nodes,
                    "edges": verification.actual.edges,
                },
                "errors": verification.errors,
            }
            if not verification.passed:
                errors.extend(verification.errors)
        except Exception as exc:
            errors.append(f"{backend} verification failed: {exc}")
        finally:
            store.close()

        backend_results[backend] = backend_info

    return DatasetVerifyResult(
        dataset=dataset,
        passed=not errors,
        errors=errors,
        backend_results=backend_results,
    )


def run_dataset_verify(dataset: str, config: LoaderConfig | None = None) -> DatasetVerifyResult:
    """CLI-facing dataset verification."""
    result = verify_dataset(dataset, config=config)
    if result.passed:
        logger.info("Dataset %s verification passed.", dataset)
    else:
        logger.error("Dataset %s verification failed: %s", dataset, result.errors[:3])
        raise PreflightError("; ".join(result.errors[:5]))
    return result
