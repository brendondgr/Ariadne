#!/usr/bin/env python3

from __future__ import annotations

import logging
import socket

from .config import GRAPH_ACTIONS, LoaderConfig
from .loader import load_dataset
from .registry import LoaderResolutionError
from .verify import run_dataset_verify as _verify_dataset

logger = logging.getLogger(__name__)

DEFAULT_ENDPOINTS = {
    "neo4j": ("127.0.0.1", 5456),
    "gremlin": ("127.0.0.1", 6455),
}


def _tcp_reachable(host: str, port: int, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _parse_endpoint(uri: str, fallback: tuple[str, int]) -> tuple[str, int]:
    if uri.startswith("bolt://"):
        host_port = uri.removeprefix("bolt://").split("/", 1)[0]
        host, _, port = host_port.partition(":")
        return host, int(port or "7687")
    if uri.startswith("ws://") or uri.startswith("wss://"):
        stripped = uri.split("://", 1)[1]
        host_port = stripped.split("/", 1)[0]
        host, _, port = host_port.partition(":")
        return host, int(port or "8182")
    return fallback


def run_graph_health(config: LoaderConfig | None = None) -> dict[str, bool]:
    """Check Neo4j and Gremlin endpoint reachability without loading data."""
    config = config or LoaderConfig.from_data_dir()
    results: dict[str, bool] = {}

    neo4j_host, neo4j_port = _parse_endpoint(config.neo4j_uri, DEFAULT_ENDPOINTS["neo4j"])
    gremlin_host, gremlin_port = _parse_endpoint(
        config.gremlin_uri, DEFAULT_ENDPOINTS["gremlin"]
    )

    results["neo4j"] = _tcp_reachable(neo4j_host, neo4j_port)
    results["gremlin"] = _tcp_reachable(gremlin_host, gremlin_port)

    for backend, healthy in results.items():
        status = "reachable" if healthy else "unreachable"
        logger.info("Graph backend %s is %s", backend, status)

    if not all(results.values()):
        raise ConnectionError("One or more graph backends are unreachable.")

    return results


def run_dataset_verify(dataset: str, config: LoaderConfig | None = None) -> None:
    """No-load dataset verification."""
    _verify_dataset(dataset, config=config)


def run_dataset_load(
    dataset: str,
    graph: str,
    config: LoaderConfig | None = None,
) -> None:
    """Load a built dataset into the requested graph backend(s)."""
    result = load_dataset(dataset, graph, config=config)
    if not result.success:
        errors = [backend.error for backend in result.backends if backend.error]
        raise RuntimeError("; ".join(error for error in errors if error))
    logger.info(
        "Loaded dataset %s into %s",
        dataset,
        ", ".join(backend.backend for backend in result.backends if backend.success),
    )


def run_graph_command(
    *,
    dataset: str | None,
    graph: str | None,
    config: LoaderConfig | None = None,
) -> None:
    """Dispatch --dataset/--graph CLI combinations."""
    if graph is None:
        raise ValueError("--graph is required for dataset loading and health checks.")

    graph = graph.lower()
    if graph not in GRAPH_ACTIONS:
        raise ValueError(
            f"Invalid --graph value {graph!r}. "
            f"Choose from: {', '.join(sorted(GRAPH_ACTIONS))}."
        )

    if graph == "health":
        run_graph_health(config)
        return

    if dataset is None:
        raise ValueError("--dataset is required unless --graph health is used.")

    dataset = dataset.lower()

    if graph == "verify":
        run_dataset_verify(dataset, config)
        return

    run_dataset_load(dataset, graph, config)


def main(argv: list[str] | None = None) -> int:
    _ = argv
    logger.error("graph_loader.main.main is invoked via root CLI only.")
    return 1
