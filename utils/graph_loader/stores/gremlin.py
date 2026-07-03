#!/usr/bin/env python3

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from utils.kg_builder.io import read_jsonl

from ..config import ADAPTER_VERSION
from ..models import AdapterMetadata, ReferentialIntegrityResult
from .base import GraphStore

_SAFE_LABEL = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_SAFE_REL = re.compile(r"^[A-Z][A-Z0-9_]*$")


def _sanitize_label(label: str) -> str:
    if not _SAFE_LABEL.match(label):
        raise ValueError(f"Unsafe Gremlin label: {label!r}")
    return label


def _to_screaming_snake(s: str) -> str:
    s = re.sub(r"([a-z])([A-Z])", r"\1_\2", s)
    return s.upper()


def _sanitize_rel_type(rel_type: str) -> str:
    normalized = _to_screaming_snake(rel_type)
    if not _SAFE_REL.match(normalized):
        raise ValueError(f"Unsafe Gremlin edge label: {rel_type!r}")
    return normalized


def vertex_upsert_traversal(node: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Return a Gremlin traversal and bindings for idempotent vertex upsert."""
    label = _sanitize_label(node["label"])
    bindings: dict[str, Any] = {
        "nodeId": node["id"],
        "vertexLabel": label,
        "nodeName": node.get("name"),
    }
    traversal = (
        "g.V().has('id', nodeId).fold().coalesce("
        "unfold(), addV(vertexLabel).property('id', nodeId)"
    )
    for key, value in node.get("properties", {}).items():
        binding_name = f"prop_{key}".replace("-", "_")
        bindings[binding_name] = value
        traversal += f".property('{key}', {binding_name})"
    if node.get("name") is not None:
        traversal += ".property('name', nodeName)"
    traversal += ")"
    return traversal, bindings


def edge_upsert_traversal(edge: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Return a Gremlin traversal and bindings for idempotent edge upsert."""
    rel_type = _sanitize_rel_type(edge["type"])
    bindings = {
        "sourceId": edge["source_id"],
        "targetId": edge["target_id"],
        "edgeId": edge["id"],
        "edgeLabel": rel_type,
    }
    traversal = (
        "g.V().has('id', sourceId).as('a').V().has('id', targetId).as('b')"
        ".coalesce(__.inE(edgeLabel).where(outV().as('a')), addE(edgeLabel).from('a').to('b'))"
        ".property('id', edgeId)"
    )
    return traversal, bindings


def load_gremlin_export_nodes(path: Path) -> list[dict[str, Any]]:
    return list(read_jsonl(path))


def load_gremlin_export_edges(path: Path) -> list[dict[str, Any]]:
    return list(read_jsonl(path))


class GremlinGraphStore(GraphStore):
    """Gremlin Server adapter for ATT&CK canonical graph loading."""

    def __init__(
        self,
        *,
        uri: str,
        export_files: dict[str, Path],
        batch_size: int = 500,
    ) -> None:
        self._uri = uri
        self._export_files = export_files
        self._batch_size = batch_size
        self._client: Any = None

    @property
    def metadata(self) -> AdapterMetadata:
        return AdapterMetadata(
            backend="gremlin",
            adapter_version=ADAPTER_VERSION,
            endpoint=self._uri,
        )

    def connect(self) -> None:
        from gremlin_python.driver import client
        from gremlin_python.driver.serializer import GraphSONSerializersV3d0

        self._client = client.Client(
            self._uri,
            "g",
            message_serializer=GraphSONSerializersV3d0(),
        )
        self._client.submit("g.V().limit(1)").all().result()

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def healthcheck(self) -> bool:
        if self._client is None:
            return False
        try:
            self._client.submit("g.V().limit(1)").all().result()
            return True
        except Exception:
            return False

    def ensure_schema(self, schema_artifacts: dict[str, Any] | None = None) -> None:
        _ = schema_artifacts

    def _submit(self, traversal: str, bindings: dict[str, Any]) -> None:
        assert self._client is not None
        self._client.submit(traversal, bindings=bindings).all().result()

    def upsert_nodes(self, nodes: list[dict[str, Any]]) -> int:
        written = 0
        for node in nodes:
            traversal, bindings = vertex_upsert_traversal(node)
            self._submit(traversal, bindings)
            written += 1
        return written

    def upsert_edges(self, edges: list[dict[str, Any]]) -> int:
        written = 0
        for edge in edges:
            traversal, bindings = edge_upsert_traversal(edge)
            self._submit(traversal, bindings)
            written += 1
        return written

    def count_nodes(self) -> int:
        assert self._client is not None
        result = self._client.submit("g.V().count()").all().result()
        return int(result[0])

    def count_edges(self) -> int:
        assert self._client is not None
        result = self._client.submit("g.E().count()").all().result()
        return int(result[0])

    def count_by_label(self, label: str) -> int:
        label = _sanitize_label(label)
        assert self._client is not None
        result = self._client.submit(
            "g.V().hasLabel(vertexLabel).count()",
            bindings={"vertexLabel": label},
        ).all().result()
        return int(result[0])

    def count_by_relationship_type(self, rel_type: str) -> int:
        rel_type = _sanitize_rel_type(rel_type)
        assert self._client is not None
        result = self._client.submit(
            "g.E().hasLabel(edgeLabel).count()",
            bindings={"edgeLabel": rel_type},
        ).all().result()
        return int(result[0])

    def referential_integrity(self) -> ReferentialIntegrityResult:
        assert self._client is not None
        missing = int(
            self._client.submit("g.V().not(has('id')).count()").all().result()[0]
        )
        dangling = int(
            self._client.submit(
                "g.E().where(__.or(__.outV().not(has('id')), "
                "__.inV().not(has('id')))).count()"
            ).all().result()[0]
        )
        details: list[str] = []
        if dangling:
            details.append(f"{dangling} edges have an endpoint vertex with no id property")
        if missing:
            details.append(f"{missing} vertices have no id property")
        return ReferentialIntegrityResult(
            dangling_edges=dangling, nodes_missing_id=missing, details=details
        )

    def sample_node(self, label: str | None = None) -> dict[str, Any] | None:
        assert self._client is not None
        if label:
            label = _sanitize_label(label)
            result = self._client.submit(
                "g.V().hasLabel(vertexLabel).limit(1).valueMap(true)",
                bindings={"vertexLabel": label},
            ).all().result()
        else:
            result = self._client.submit("g.V().limit(1).valueMap(true)").all().result()
        if not result:
            return None
        value_map = result[0]
        node_id = value_map.get("id", [None])[0] if isinstance(value_map.get("id"), list) else value_map.get("id")
        return {"id": node_id, "properties": value_map}
