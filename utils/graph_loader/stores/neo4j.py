#!/usr/bin/env python3

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..config import ADAPTER_VERSION
from ..models import AdapterMetadata, ReferentialIntegrityResult
from .base import GraphStore

_SAFE_LABEL = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_SAFE_REL = re.compile(r"^[A-Z][A-Z0-9_]*$")


def _sanitize_label(label: str) -> str:
    if not _SAFE_LABEL.match(label):
        raise ValueError(f"Unsafe Neo4j label: {label!r}")
    return label


def _sanitize_rel_type(rel_type: str) -> str:
    if not _SAFE_REL.match(rel_type):
        raise ValueError(f"Unsafe Neo4j relationship type: {rel_type!r}")
    return rel_type


def node_merge_cypher(node: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Build a parameterized MERGE statement for one canonical node."""
    label = _sanitize_label(node["label"])
    props = dict(node.get("properties", {}))
    params = {
        "id": node["id"],
        "name": node.get("name"),
        "attack_id": props.get("attack_id"),
        "stix_type": props.get("stix_type"),
        "properties_json": json.dumps(props, sort_keys=True),
    }
    query = (
        f"MERGE (n:{label} {{id: $id}}) "
        "SET n.name = $name, n.attack_id = $attack_id, "
        "n.stix_type = $stix_type, n.properties_json = $properties_json"
    )
    for extra in node.get("labels", [])[1:]:
        extra_label = _sanitize_label(extra)
        query += f" SET n:{extra_label}"
    return query, params


def relationship_merge_cypher(edge: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Build a parameterized MERGE statement for one canonical edge."""
    rel_type = _sanitize_rel_type(edge["type"])
    params = {
        "id": edge["id"],
        "source_id": edge["source_id"],
        "target_id": edge["target_id"],
    }
    query = (
        "MATCH (a {id: $source_id}) "
        "MATCH (b {id: $target_id}) "
        f"MERGE (a)-[r:{rel_type}]->(b) SET r.id = $id"
    )
    return query, params


def parse_constraints_cypher(path: Path) -> list[str]:
    statements: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("CREATE CONSTRAINT"):
            statements.append(stripped if stripped.endswith(";") else f"{stripped};")
    return statements


class Neo4jGraphStore(GraphStore):
    """Neo4j Bolt adapter for ATT&CK canonical graph loading."""

    def __init__(
        self,
        *,
        uri: str,
        user: str,
        password: str,
        export_files: dict[str, Path],
        batch_size: int = 500,
    ) -> None:
        self._uri = uri
        self._user = user
        self._password = password
        self._export_files = export_files
        self._batch_size = batch_size
        self._driver: Any = None

    @property
    def metadata(self) -> AdapterMetadata:
        return AdapterMetadata(
            backend="neo4j",
            adapter_version=ADAPTER_VERSION,
            endpoint=self._uri,
        )

    def connect(self) -> None:
        from neo4j import GraphDatabase

        self._driver = GraphDatabase.driver(self._uri, auth=(self._user, self._password))
        self._driver.verify_connectivity()

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def healthcheck(self) -> bool:
        if self._driver is None:
            return False
        try:
            self._driver.verify_connectivity()
            return True
        except Exception:
            return False

    def ensure_schema(self, schema_artifacts: dict[str, Any] | None = None) -> None:
        artifacts = schema_artifacts or {}
        constraints_path = artifacts.get("constraints_cypher") or self._export_files.get(
            "constraints_cypher"
        )
        if constraints_path is None:
            return
        statements = parse_constraints_cypher(Path(constraints_path))
        assert self._driver is not None
        with self._driver.session() as session:
            for statement in statements:
                session.run(statement)

    def upsert_nodes(self, nodes: list[dict[str, Any]]) -> int:
        assert self._driver is not None
        written = 0
        with self._driver.session() as session:
            for node in nodes:
                query, params = node_merge_cypher(node)
                session.run(query, params)
                written += 1
        return written

    def upsert_edges(self, edges: list[dict[str, Any]]) -> int:
        assert self._driver is not None
        written = 0
        with self._driver.session() as session:
            for edge in edges:
                query, params = relationship_merge_cypher(edge)
                session.run(query, params)
                written += 1
        return written

    def count_nodes(self) -> int:
        assert self._driver is not None
        with self._driver.session() as session:
            record = session.run("MATCH (n) RETURN count(n) AS c").single()
            return int(record["c"])

    def count_edges(self) -> int:
        assert self._driver is not None
        with self._driver.session() as session:
            record = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()
            return int(record["c"])

    def count_by_label(self, label: str) -> int:
        label = _sanitize_label(label)
        assert self._driver is not None
        with self._driver.session() as session:
            record = session.run(f"MATCH (n:{label}) RETURN count(n) AS c").single()
            return int(record["c"])

    def count_by_relationship_type(self, rel_type: str) -> int:
        rel_type = _sanitize_rel_type(rel_type)
        assert self._driver is not None
        with self._driver.session() as session:
            record = session.run(f"MATCH ()-[r:{rel_type}]->() RETURN count(r) AS c").single()
            return int(record["c"])

    def referential_integrity(self) -> ReferentialIntegrityResult:
        assert self._driver is not None
        with self._driver.session() as session:
            dangling = int(
                session.run(
                    "MATCH (a)-[r]->(b) WHERE a.id IS NULL OR b.id IS NULL "
                    "RETURN count(r) AS c"
                ).single()["c"]
            )
            missing = int(
                session.run(
                    "MATCH (n) WHERE n.id IS NULL RETURN count(n) AS c"
                ).single()["c"]
            )
        details: list[str] = []
        if dangling:
            details.append(f"{dangling} edges have an endpoint with no id property")
        if missing:
            details.append(f"{missing} nodes have no id property")
        return ReferentialIntegrityResult(
            dangling_edges=dangling, nodes_missing_id=missing, details=details
        )

    def orphan_ids(self, limit: int = 5000) -> list[str]:
        assert self._driver is not None
        with self._driver.session() as session:
            result = session.run(
                "MATCH (n) WHERE NOT (n)--() RETURN n.id AS id ORDER BY id LIMIT $limit",
                limit=limit,
            )
            return [str(record["id"]) for record in result]

    def list_constraint_names(self) -> list[str]:
        assert self._driver is not None
        with self._driver.session() as session:
            result = session.run("SHOW CONSTRAINTS YIELD name RETURN name")
            return sorted(str(record["name"]) for record in result)

    def sample_node(self, label: str | None = None) -> dict[str, Any] | None:
        assert self._driver is not None
        if label:
            label = _sanitize_label(label)
            query = f"MATCH (n:{label}) RETURN n.id AS id, n.name AS name, labels(n) AS labels LIMIT 1"
        else:
            query = "MATCH (n) RETURN n.id AS id, n.name AS name, labels(n) AS labels LIMIT 1"
        with self._driver.session() as session:
            record = session.run(query).single()
            if record is None:
                return None
            return {
                "id": record["id"],
                "name": record["name"],
                "labels": list(record["labels"]),
            }
