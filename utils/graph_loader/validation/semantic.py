#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from utils.kg_builder.io import read_jsonl
from utils.kg_builder.schema.attack import ATTACK_NODE_LABELS, ATTACK_RELATIONSHIP_TYPES
from utils.kg_builder.schema.capec import CAPEC_NODE_LABELS, CAPEC_RELATIONSHIP_TYPES

from ..models import SemanticValidationResult
from .references import (
    pattern_matches,
    validate_relationship_endpoints,
    validate_subtechnique_links,
    validate_tactic_technique_links,
)
from .rules import (
    ATTACK_EDGE_PATTERNS,
    EdgePattern,
    CAPEC_EDGE_PATTERNS,
    LABELS_REQUIRING_ATTACK_ID,
    REQUIRED_NODE_PROPERTIES,
)


class SemanticValidationError(Exception):
    """Raised when semantic validation fails."""


def validate_semantic_graph(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    *,
    schema: dict[str, Any] | None = None,
) -> SemanticValidationResult:
    """Validate domain semantics for a canonical graph dataset."""
    errors: list[str] = []
    schema = schema or {}
    dataset = schema.get("dataset", "attack")
    if dataset == "capec":
        allowed_labels = set(schema.get("node_labels", CAPEC_NODE_LABELS))
        allowed_types = set(schema.get("relationship_types", CAPEC_RELATIONSHIP_TYPES))
        edge_patterns = CAPEC_EDGE_PATTERNS
    elif dataset == "merged":
        # The C-015 counterfactual holds both catalogues, so both rule sets
        # apply and neither is relaxed. Without this branch `merged` fell to the
        # ATT&CK arm below and every CAPEC edge read as an illegal pattern — the
        # data was fine and the rule set was the wrong one.
        allowed_labels = set(
            schema.get("node_labels", ATTACK_NODE_LABELS | CAPEC_NODE_LABELS)
        )
        allowed_types = set(
            schema.get(
                "relationship_types", ATTACK_RELATIONSHIP_TYPES | CAPEC_RELATIONSHIP_TYPES
            )
        )
        edge_patterns = ATTACK_EDGE_PATTERNS | CAPEC_EDGE_PATTERNS
    elif dataset == "attack":
        allowed_labels = set(schema.get("node_labels", ATTACK_NODE_LABELS))
        allowed_types = set(schema.get("relationship_types", ATTACK_RELATIONSHIP_TYPES))
        edge_patterns = ATTACK_EDGE_PATTERNS
    else:
        # Every dataset outside the three MITRE rule sets: ``identity``
        # (EXP-2026-08-011) and any graph that arrived with a source card, such
        # as a Synapse ``export-ariadne`` directory. Unlike the branches above
        # this one has no hardcoded rule set to fall back on and does not want
        # one: the legal edge patterns ARE the schema the build shipped, so
        # they are read from it rather than restated here. A rule set restated
        # in code can drift from the catalog it describes; one derived from it
        # cannot.
        #
        # A schema that declares no ``relationship_endpoints`` at all gets no
        # pattern check (``None``), because "nothing declared" and "nothing
        # legal" are different claims and only the loader's other checks —
        # unknown label, unknown type, dangling endpoint, duplicate id — can
        # be made from the data alone.
        allowed_labels = set(schema.get("node_labels", ()))
        allowed_types = set(schema.get("relationship_types", ()))
        declared_endpoints = schema.get("relationship_endpoints")
        edge_patterns = (
            frozenset(
                EdgePattern(entry["source"], entry["type"], entry["target"])
                for entry in declared_endpoints
            )
            if declared_endpoints
            else None
        )

    seen_ids: set[str] = set()
    semantic_keys: set[tuple[str, str, str, str]] = set()
    labels_by_id = {node["id"]: node.get("label", "") for node in nodes}

    for node in nodes:
        node_id = node.get("id")
        if not node_id:
            errors.append("Node missing canonical id property.")
            continue
        if node_id in seen_ids:
            errors.append(f"Duplicate node id: {node_id}")
        seen_ids.add(node_id)

        label = node.get("label")
        if label not in allowed_labels:
            errors.append(f"Unknown node label {label!r} on node {node_id}")
        if not node.get("labels") or node["labels"][0] != label:
            errors.append(f"Node {node_id} labels[0] must match primary label {label!r}")

        props = node.get("properties", {})
        for required in REQUIRED_NODE_PROPERTIES:
            if required not in node and required not in props:
                errors.append(f"Node {node_id} missing required property {required!r}")

        # In the merged graph `Mitigation` holds both catalogues' entries and
        # only ATT&CK's carry an attack_id, so the marker label — not the
        # primary one — decides whether the requirement applies. Checking the
        # ATT&CK half of a merged store is worth the extra clause: dropping the
        # check entirely would let a merged load hide a defect the ordinary
        # load would have caught.
        is_attack_node = dataset == "attack" or (
            dataset == "merged" and "AttackObject" in (node.get("labels") or [])
        )
        if label in LABELS_REQUIRING_ATTACK_ID and is_attack_node:
            attack_id = props.get("attack_id")
            if not attack_id:
                errors.append(f"Node {node_id} ({label}) missing attack_id property.")

        if is_attack_node and "stix_type" in props and not props.get("stix_type"):
            errors.append(f"Node {node_id} has empty stix_type.")

    errors.extend(validate_relationship_endpoints(nodes, edges))
    if dataset in ("attack", "merged"):
        errors.extend(validate_tactic_technique_links(nodes, edges))
        errors.extend(validate_subtechnique_links(nodes, edges))

    for edge in edges:
        rel_type = edge.get("type")
        if rel_type not in allowed_types:
            errors.append(f"Unknown relationship type {rel_type!r} on edge {edge['id']}")

        source_label = labels_by_id.get(edge["source_id"], "")
        target_label = labels_by_id.get(edge["target_id"], "")
        if edge_patterns is not None and not any(
            pattern_matches(edge, labels_by_id, pattern) for pattern in edge_patterns
        ):
            errors.append(
                f"Illegal edge pattern {source_label} -[{rel_type}]-> {target_label} "
                f"on edge {edge['id']}"
            )

        semantic_key = (edge["type"], edge["source_id"], edge["target_id"], edge["id"])
        if semantic_key in semantic_keys:
            errors.append(f"Duplicate semantic edge key: {semantic_key}")
        semantic_keys.add(semantic_key)

    return SemanticValidationResult(
        valid=not errors,
        errors=errors,
        node_count=len(nodes),
        edge_count=len(edges),
    )


def validate_semantic_artifacts(
    nodes_path: Path,
    relationships_path: Path,
    schema_path: Path | None = None,
) -> SemanticValidationResult:
    """Load canonical JSONL artifacts and run semantic validation."""
    nodes = list(read_jsonl(nodes_path))
    edges = list(read_jsonl(relationships_path))
    schema: dict[str, Any] = {}
    if schema_path and schema_path.exists():
        with open(schema_path, encoding="utf-8") as f:
            schema = json.load(f)
    return validate_semantic_graph(nodes, edges, schema=schema)


def require_semantic_validation(result: SemanticValidationResult) -> None:
    if not result.valid:
        raise SemanticValidationError("; ".join(result.errors[:5]))
