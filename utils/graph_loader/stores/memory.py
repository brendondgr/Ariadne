#!/usr/bin/env python3

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..config import ADAPTER_VERSION
from ..models import AdapterMetadata, CountSummary, ReferentialIntegrityResult
from .base import GraphStore


class MemoryGraphStore(GraphStore):
    """In-memory GraphStore for contract and orchestration tests."""

    def __init__(self, backend: str = "memory", endpoint: str = "memory://local") -> None:
        self._backend = backend
        self._endpoint = endpoint
        self._connected = False
        self._nodes: dict[str, dict[str, Any]] = {}
        self._edges: list[dict[str, Any]] = []
        self._edge_keys: set[tuple[str, str, str, str]] = set()
        self._constraint_names: list[str] = []

    @property
    def metadata(self) -> AdapterMetadata:
        return AdapterMetadata(
            backend=self._backend,
            adapter_version=ADAPTER_VERSION,
            endpoint=self._endpoint,
        )

    def connect(self) -> None:
        self._connected = True

    def close(self) -> None:
        self._connected = False

    def healthcheck(self) -> bool:
        return self._connected

    def ensure_schema(self, schema_artifacts: dict[str, Any]) -> None:
        constraints_path = (schema_artifacts or {}).get("constraints_cypher")
        if constraints_path is None:
            return
        try:
            text = Path(constraints_path).read_text(encoding="utf-8")
        except OSError:
            return
        self._constraint_names = sorted(
            set(re.findall(r"CREATE CONSTRAINT (\w+) IF NOT EXISTS", text))
        )

    def list_constraint_names(self) -> list[str]:
        return list(self._constraint_names)

    def upsert_nodes(self, nodes: list[dict[str, Any]]) -> int:
        written = 0
        for node in nodes:
            self._nodes[node["id"]] = node
            written += 1
        return written

    def upsert_edges(self, edges: list[dict[str, Any]]) -> int:
        written = 0
        for edge in edges:
            key = (edge["id"], edge["type"], edge["source_id"], edge["target_id"])
            if key in self._edge_keys:
                continue
            self._edge_keys.add(key)
            self._edges.append(edge)
            written += 1
        return written

    def count_nodes(self) -> int:
        return len(self._nodes)

    def count_edges(self) -> int:
        return len(self._edges)

    def count_by_label(self, label: str) -> int:
        return sum(1 for node in self._nodes.values() if node.get("label") == label)

    def count_by_relationship_type(self, rel_type: str) -> int:
        return sum(1 for edge in self._edges if edge.get("type") == rel_type)

    def sample_node(self, label: str | None = None) -> dict[str, Any] | None:
        for node in self._nodes.values():
            if label is None or node.get("label") == label:
                return node
        return None

    def referential_integrity(self) -> ReferentialIntegrityResult:
        missing = sum(1 for node in self._nodes.values() if not node.get("id"))
        dangling = sum(
            1
            for edge in self._edges
            if edge.get("source_id") not in self._nodes
            or edge.get("target_id") not in self._nodes
        )
        details: list[str] = []
        if dangling:
            details.append(f"{dangling} edges reference a missing node id")
        if missing:
            details.append(f"{missing} nodes have no id property")
        return ReferentialIntegrityResult(
            dangling_edges=dangling, nodes_missing_id=missing, details=details
        )

    def snapshot_counts(self) -> CountSummary:
        labels: dict[str, int] = {}
        for node in self._nodes.values():
            lbl = node.get("label", "Unknown")
            labels[lbl] = labels.get(lbl, 0) + 1
        types: dict[str, int] = {}
        for edge in self._edges:
            rel_type = edge.get("type", "Unknown")
            types[rel_type] = types.get(rel_type, 0) + 1
        return CountSummary(nodes=len(self._nodes), edges=len(self._edges), nodes_by_label=labels, edges_by_type=types)
