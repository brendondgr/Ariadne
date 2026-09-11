#!/usr/bin/env python3

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..config import ADAPTER_VERSION
from ..models import AdapterMetadata, ReferentialIntegrityResult
from .base import GraphStore

#: Names interpolated into Cypher must be identifier-shaped. The rule's job is
#: to reject anything that could close the identifier and continue the query —
#: backticks, quotes, whitespace, punctuation — which is why it is an allowlist
#: rather than an escape.
#:
#: Labels and relationship types share one rule. They did not until 2026-08-20:
#: the relationship rule was `^[A-Z][A-Z0-9_]*$`, screaming-snake only. That was
#: never a considered decision about safety — case has no bearing on what the
#: rule blocks — it was an accident of which names the loader had ever seen.
#: Ten of CAPEC's fifteen relationship names are ones this repo invents, because
#: the source XML expresses those links by nesting rather than by naming them,
#: and they are screaming-snake by house style. The other five — ChildOf,
#: CanPrecede, CanFollow, PeerOf, CanAlsoBe — are copied verbatim from the
#: `Nature` attribute of the CAPEC XML and are CamelCase. CAPEC had only ever
#: been loaded into Gremlin, which has no such rule, so MITRE's own spelling met
#: this validator for the first time when the merged-graph store (C-015) was
#: built, and it was refused.
#:
#: The alternative — renaming those five on the way in — was rejected: it would
#: make a query written against the merged store fail to port to the Gremlin
#: store holding the same data, inside the one experiment that is about queries
#: porting between stores. See DECISIONS.md D-016.
_SAFE_LABEL = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_SAFE_REL = _SAFE_LABEL


def _sanitize_label(label: str) -> str:
    if not _SAFE_LABEL.match(label):
        raise ValueError(f"Unsafe Neo4j label: {label!r}")
    return label


def _sanitize_rel_type(rel_type: str) -> str:
    if not _SAFE_REL.match(rel_type):
        raise ValueError(f"Unsafe Neo4j relationship type: {rel_type!r}")
    return rel_type


#: Property names the loader sets explicitly. A canonical property with one of
#: these names is already carried and must not be written twice.
_CORE_NODE_PROPERTIES = frozenset({"id", "name", "attack_id", "stix_type"})

#: Property names safe to backtick-quote into a SET clause. Same allowlist
#: rule, and the same reason, as :data:`_SAFE_LABEL`.
_SAFE_PROPERTY = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def _native_property_values(props: dict[str, Any]) -> dict[str, Any]:
    """The canonical properties Neo4j can hold as real, queryable properties.

    Neo4j stores scalars and homogeneous lists of scalars directly; it cannot
    store a nested map or a list of maps. Until 2026-09-11 the loader wrote
    **four** real properties and serialised everything else into one
    ``properties_json`` string, which made every other field invisible to a
    ``WHERE`` clause. The derived schema registry reads the canonical node files
    and reports those fields as real, so a query built from the schema filtered
    on a property the store did not have and matched nothing, silently — 23
    development questions lost their whole gold coverage to that before it was
    found (`Q55`, `EXP-2026-09-018` Step 4).

    ``properties_json`` is still written, unchanged and complete, so
    :func:`unpack_properties` and every reader built on it keep working. This
    only *adds* the queryable copy.
    """
    native: dict[str, Any] = {}
    for key, value in props.items():
        if key in _CORE_NODE_PROPERTIES or not _SAFE_PROPERTY.match(key):
            continue
        if isinstance(value, (str, int, float, bool)):
            native[key] = value
        elif isinstance(value, (list, tuple)):
            items = list(value)
            if items and all(isinstance(i, (str, int, float, bool)) for i in items):
                native[key] = items
    return native


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
    for key, value in sorted(_native_property_values(props).items()):
        param = f"p_{key}"
        params[param] = value
        query += f" SET n.`{key}` = ${param}"
    for extra in node.get("labels", [])[1:]:
        extra_label = _sanitize_label(extra)
        query += f" SET n:{extra_label}"
    return query, params


def unpack_properties(properties_json: Any) -> dict[str, Any]:
    """JSON-parse a node's flattened ``properties_json`` blob back into a dict.

    The loader flattens the canonical ``properties`` dict into a single
    ``properties_json`` string on write (see :func:`node_merge_cypher`) so the
    store stays schema-flexible. The ``describe`` primitive reverses that on
    read: it returns ``n.properties_json`` from the graph and calls this helper
    to recover **every** property, so a node's description is reachable without a
    reload or a promotion to first-class Neo4j properties. Robust to the value
    already being a dict (a future migration) or missing/malformed (returns an
    empty dict rather than raising, so one bad node never sinks a whole result).
    """
    if properties_json is None:
        return {}
    if isinstance(properties_json, dict):
        return dict(properties_json)
    if isinstance(properties_json, str):
        try:
            parsed = json.loads(properties_json)
        except (ValueError, TypeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


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
