#!/usr/bin/env python3

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class GraphNode:
    """Database-neutral graph node."""

    id: str
    label: str
    attack_id: str | None = None
    name: str | None = None
    description: str | None = None
    stix_type: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GraphRelationship:
    """Database-neutral directed graph relationship."""

    id: str
    type: str
    source_id: str
    target_id: str
    stix_type: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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
class NormalizedGraph:
    """Normalized graph model — database-neutral pipeline boundary."""

    metadata: GraphMetadata
    nodes: list[GraphNode]
    relationships: list[GraphRelationship]

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
