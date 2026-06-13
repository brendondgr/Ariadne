#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path

from ..config import LoaderConfig
from ..registry import DatasetLoadTarget
from .gremlin import GremlinGraphStore
from .memory import MemoryGraphStore
from .neo4j import Neo4jGraphStore


def create_graph_store(
    backend: str,
    target: DatasetLoadTarget,
    config: LoaderConfig,
):
    """Create a concrete GraphStore for the requested backend."""
    backend_target = target.backends[backend]
    export_files = backend_target.export_files

    if backend == "neo4j":
        return Neo4jGraphStore(
            uri=target.endpoints["neo4j"],
            user=config.neo4j_user,
            password=config.neo4j_password,
            export_files=export_files,
            batch_size=config.batch_size,
        )
    if backend == "gremlin":
        return GremlinGraphStore(
            uri=target.endpoints["gremlin"],
            export_files=export_files,
            batch_size=config.batch_size,
        )
    if backend == "memory":
        return MemoryGraphStore(backend="memory", endpoint="memory://local")
    raise ValueError(f"Unsupported graph store backend: {backend}")
