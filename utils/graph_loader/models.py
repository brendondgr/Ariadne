#!/usr/bin/env python3

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CountSummary:
    """Node and edge counts for verification."""

    nodes: int
    edges: int
    nodes_by_label: dict[str, int] = field(default_factory=dict)
    edges_by_type: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class SemanticValidationResult:
    """Outcome of semantic graph validation before loading."""

    valid: bool
    errors: list[str]
    node_count: int
    edge_count: int


@dataclass(frozen=True)
class VerifyLoadedGraphResult:
    """Post-load graph verification against canonical expectations."""

    passed: bool
    expected: CountSummary
    actual: CountSummary
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ReferentialIntegrityResult:
    """Live referential-integrity check for a loaded graph."""

    dangling_edges: int
    nodes_missing_id: int
    details: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.dangling_edges == 0 and self.nodes_missing_id == 0


@dataclass(frozen=True)
class AdapterMetadata:
    """Metadata about a graph store adapter."""

    backend: str
    adapter_version: str
    endpoint: str


@dataclass
class CanonicalGraphData:
    """Canonical nodes and edges read for loading."""

    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    expected_counts: CountSummary
