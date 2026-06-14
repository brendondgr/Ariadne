#!/usr/bin/env python3

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class NodeRecord:
    """Backend-neutral canonical graph node."""

    id: str
    label: str
    labels: list[str]
    name: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NodeRecord:
        labels = data.get("labels")
        if labels is None:
            labels = [data["label"]]
        return cls(
            id=data["id"],
            label=data["label"],
            labels=list(labels),
            name=data.get("name"),
            properties=dict(data.get("properties", {})),
        )


@dataclass
class EdgeRecord:
    """Backend-neutral canonical graph edge."""

    id: str
    type: str
    source_id: str
    target_id: str
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EdgeRecord:
        return cls(
            id=data["id"],
            type=data["type"],
            source_id=data["source_id"],
            target_id=data["target_id"],
            properties=dict(data.get("properties", {})),
        )


# Backward-compatible aliases used during preprocessing.
GraphNode = NodeRecord
GraphRelationship = EdgeRecord


def attack_canonical_labels(primary_label: str) -> list[str]:
    """Return ordered canonical labels for an ATT&CK graph node."""
    return [primary_label, "AttackObject", "STIXObject"]


@dataclass
class GraphMetadata:
    """Build metadata for processed pairs and manifests."""

    source_path: str
    bundle_id: str | None
    attack_version: str
    object_count: int
    filtered_deprecated: int = 0
    filtered_revoked: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CapecGraphMetadata:
    """Build metadata for CAPEC graph artifacts."""

    source_path: str
    dataset: str = "capec"
    source_version: str = ""
    source_date: str = ""
    namespace: str = ""
    build_scope: str = ""
    object_count: int = 0
    quarantined_count: int = 0
    skipped_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class NormalizedGraph:
    """Normalized graph model — database-neutral pipeline boundary."""

    metadata: GraphMetadata | CapecGraphMetadata
    nodes: list[NodeRecord]
    relationships: list[EdgeRecord]

    @property
    def counts(self) -> dict[str, int]:
        label_counts: dict[str, int] = {}
        for node in self.nodes:
            label_counts[node.label] = label_counts.get(node.label, 0) + 1
        type_counts: dict[str, int] = {}
        for rel in self.relationships:
            type_counts[rel.type] = type_counts.get(rel.type, 0) + 1
        return {
            "nodes": len(self.nodes),
            "relationships": len(self.relationships),
            "nodes_by_label": label_counts,
            "relationships_by_type": type_counts,
        }

    def to_pairs_dict(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata.to_dict(),
            "nodes": [n.to_dict() for n in self.nodes],
            "relationships": [r.to_dict() for r in self.relationships],
            "counts": self.counts,
        }
