#!/usr/bin/env python3

from __future__ import annotations

import logging
from typing import Any, Callable

from utils.kg_builder.io import read_jsonl

from .config import LOAD_BACKENDS, LoaderConfig
from .manifest import write_backend_load_manifest
from .models import CountSummary
from .preflight import run_preflight
from .registry import resolve_dataset
from .results import BackendLoadResult, DatasetLoadResult
from .stores.factory import create_graph_store
from .stores.gremlin import load_gremlin_export_edges, load_gremlin_export_nodes
from .validation.semantic import validate_semantic_artifacts

logger = logging.getLogger(__name__)


def _expected_counts(manifest: dict[str, Any]) -> CountSummary:
    counts = manifest.get("counts", {})
    return CountSummary(
        nodes=int(counts.get("nodes", 0)),
        edges=int(counts.get("relationships", 0)),
        nodes_by_label=dict(counts.get("nodes_by_label", {})),
        edges_by_type=dict(counts.get("relationships_by_type", {})),
    )


def _batched(records: list[dict[str, Any]], batch_size: int) -> list[list[dict[str, Any]]]:
    return [records[i : i + batch_size] for i in range(0, len(records), batch_size)]


def _load_backend_records(
    dataset_target,
    backend: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if backend == "gremlin":
        exports = dataset_target.backends["gremlin"].export_files
        nodes = load_gremlin_export_nodes(exports["nodes_jsonl"])
        edges = load_gremlin_export_edges(exports["relationships_jsonl"])
        return nodes, edges

    nodes = list(read_jsonl(dataset_target.nodes_path))
    edges = list(read_jsonl(dataset_target.relationships_path))
    return nodes, edges


def load_backend(
    *,
    dataset: str,
    backend: str,
    config: LoaderConfig | None = None,
    store_factory: Callable[..., Any] | None = None,
    check_reachability: bool = True,
) -> BackendLoadResult:
    """Load one backend projection for a built dataset."""
    config = config or LoaderConfig.from_data_dir()
    store_factory = store_factory or create_graph_store
    target = resolve_dataset(dataset, backend, config)

    run_preflight(target, backends=[backend], check_reachability=check_reachability)
    semantic = validate_semantic_artifacts(
        target.nodes_path,
        target.relationships_path,
        target.schema_path,
    )
    if not semantic.valid:
        return BackendLoadResult(
            backend=backend,
            success=False,
            error="; ".join(semantic.errors[:3]),
        )

    nodes, edges = _load_backend_records(target, backend)
    expected = _expected_counts(target.manifest)
    backend_target = target.backends[backend]

    try:
        store = store_factory(backend, target, config)
        store.connect()
        schema_artifacts = {
            name: str(path) for name, path in backend_target.export_files.items()
        }
        store.ensure_schema(schema_artifacts)

        nodes_loaded = 0
        for batch in _batched(nodes, config.batch_size):
            nodes_loaded += store.upsert_nodes(batch)

        edges_loaded = 0
        for batch in _batched(edges, config.batch_size):
            edges_loaded += store.upsert_edges(batch)

        verification = store.verify_loaded_graph(expected)
        result = BackendLoadResult(
            backend=backend,
            success=verification.passed,
            nodes_loaded=nodes_loaded,
            edges_loaded=edges_loaded,
            verification=verification,
            error=None if verification.passed else "; ".join(verification.errors[:3]),
        )
        if verification.passed:
            write_backend_load_manifest(
                store=store,
                result=result,
                dataset=dataset,
                canonical_manifest_path=target.manifest_path,
                semantic_valid=True,
                expected_counts=expected,
                verification=verification,
                runtime_manifest_path=backend_target.runtime_manifest_path,
            )
        return result
    except Exception as exc:
        logger.exception("Backend load failed for %s/%s", dataset, backend)
        return BackendLoadResult(backend=backend, success=False, error=str(exc))
    finally:
        if "store" in locals():
            store.close()


def load_dataset(
    dataset: str,
    graph_action: str,
    *,
    config: LoaderConfig | None = None,
    store_factory: Callable[..., Any] | None = None,
    check_reachability: bool = True,
) -> DatasetLoadResult:
    """Load a dataset into one or more graph backends."""
    config = config or LoaderConfig.from_data_dir()

    if graph_action == "all":
        backends = sorted(LOAD_BACKENDS)
    else:
        backends = [graph_action]

    # Resolve once up front so missing artifacts fail before any writes.
    resolve_dataset(dataset, graph_action, config)

    results: list[BackendLoadResult] = []
    for backend in backends:
        results.append(
            load_backend(
                dataset=dataset,
                backend=backend,
                config=config,
                store_factory=store_factory,
                check_reachability=check_reachability,
            )
        )

    return DatasetLoadResult(dataset=dataset, graph_action=graph_action, backends=results)
