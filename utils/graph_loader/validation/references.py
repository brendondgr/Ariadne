#!/usr/bin/env python3

from __future__ import annotations

from typing import Any

from .rules import ATTACK_EDGE_PATTERNS, EdgePattern


def _node_label_index(nodes: list[dict[str, Any]]) -> dict[str, str]:
    return {node["id"]: node["label"] for node in nodes}


def validate_relationship_endpoints(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> list[str]:
    """Ensure every edge references existing node endpoints."""
    node_ids = {node["id"] for node in nodes}
    errors: list[str] = []
    for edge in edges:
        if edge["source_id"] not in node_ids:
            errors.append(
                f"Relationship {edge['id']} references missing source {edge['source_id']}"
            )
        if edge["target_id"] not in node_ids:
            errors.append(
                f"Relationship {edge['id']} references missing target {edge['target_id']}"
            )
    return errors


def validate_tactic_technique_links(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> list[str]:
    """Ensure HAS_TECHNIQUE edges originate from Tactic nodes."""
    labels = _node_label_index(nodes)
    errors: list[str] = []
    for edge in edges:
        if edge["type"] != "HAS_TECHNIQUE":
            continue
        source_label = labels.get(edge["source_id"])
        if source_label != "Tactic":
            errors.append(
                f"HAS_TECHNIQUE edge {edge['id']} must start at Tactic, got {source_label!r}"
            )
    return errors


def validate_subtechnique_links(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> list[str]:
    """Ensure HAS_SUBTECHNIQUE edges connect Technique to SubTechnique."""
    labels = _node_label_index(nodes)
    errors: list[str] = []
    for edge in edges:
        if edge["type"] != "HAS_SUBTECHNIQUE":
            continue
        source_label = labels.get(edge["source_id"])
        target_label = labels.get(edge["target_id"])
        if source_label != "Technique" or target_label != "SubTechnique":
            errors.append(
                f"HAS_SUBTECHNIQUE edge {edge['id']} must be Technique->SubTechnique, "
                f"got {source_label!r}->{target_label!r}"
            )
    return errors


def pattern_matches(edge: dict[str, Any], labels: dict[str, str], pattern: EdgePattern) -> bool:
    return (
        labels.get(edge["source_id"]) == pattern.source_label
        and edge["type"] == pattern.relationship_type
        and labels.get(edge["target_id"]) == pattern.target_label
    )
