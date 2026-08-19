#!/usr/bin/env python3

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..models import (
    AdapterMetadata,
    CountSummary,
    ReferentialIntegrityResult,
    VerifyLoadedGraphResult,
)


class GraphStore(ABC):
    """Backend-independent contract for graph loading and verification."""

    @property
    @abstractmethod
    def metadata(self) -> AdapterMetadata:
        """Return adapter metadata for manifests and logging."""

    @abstractmethod
    def connect(self) -> None:
        """Open a connection to the graph backend."""

    @abstractmethod
    def close(self) -> None:
        """Close the graph backend connection."""

    @abstractmethod
    def healthcheck(self) -> bool:
        """Return True when the backend endpoint is reachable."""

    @abstractmethod
    def ensure_schema(self, schema_artifacts: dict[str, Any]) -> None:
        """Apply backend-specific schema or constraints."""

    @abstractmethod
    def upsert_nodes(self, nodes: list[dict[str, Any]]) -> int:
        """Upsert canonical nodes; return rows written."""

    @abstractmethod
    def upsert_edges(self, edges: list[dict[str, Any]]) -> int:
        """Upsert canonical edges; return rows written."""

    @abstractmethod
    def count_nodes(self) -> int:
        """Return total node count in the live graph."""

    @abstractmethod
    def count_edges(self) -> int:
        """Return total edge/relationship count in the live graph."""

    @abstractmethod
    def count_by_label(self, label: str) -> int:
        """Return node count for a primary label."""

    @abstractmethod
    def count_by_relationship_type(self, rel_type: str) -> int:
        """Return edge count for a relationship type."""

    @abstractmethod
    def sample_node(self, label: str | None = None) -> dict[str, Any] | None:
        """Return a representative node for spot checks."""

    @abstractmethod
    def referential_integrity(self) -> ReferentialIntegrityResult:
        """Return live counts of dangling edges and id-less nodes.

        A healthy fixture has zero of both: every edge connects two nodes that
        exist and every node carries the canonical ``id`` used as the join key.
        """

    @abstractmethod
    def orphan_ids(self, limit: int = 5000) -> list[str]:
        """Return ids of nodes with no edges in either direction (islands).

        Every returned id must be explained: either a documented allow-list
        entry (declared not-traversable in the source card) or a loader bug.
        """

    def list_constraint_names(self) -> list[str]:
        """Return names of live schema constraints.

        Backends without schema constraints (Gremlin/TinkerPop) return an empty
        list; the fixture-QA harness only asserts constraint presence on
        backends that report support via a non-empty result.
        """
        return []

    def verify_loaded_graph(self, expected: CountSummary) -> VerifyLoadedGraphResult:
        """Compare live counts against canonical manifest expectations.

        The totals here are graph-wide (`MATCH (n) RETURN count(n)`), which is
        the right check for the one-dataset-per-store arrangement every backend
        uses today and the wrong one for a deliberately merged store: loading
        ATT&CK and then CAPEC into a single instance leaves 9138 nodes where
        CAPEC's manifest expects 4769, and `Mitigation` holds both catalogues'
        mitigations. The data landed correctly and the invariant is simply not
        the invariant any more.

        ``ARIADNE_ALLOW_MERGED_GRAPH=1`` downgrades that mismatch from an error
        to a reported warning, for the C-015 counterfactual store only. It is an
        explicit opt-in rather than a silent tolerance because on a normal
        single-dataset load a count mismatch means something is genuinely wrong
        and must keep failing loudly.
        """
        import os

        merged = os.environ.get("ARIADNE_ALLOW_MERGED_GRAPH", "").strip().lower() in {
            "1", "true", "yes", "on",
        }
        actual = CountSummary(
            nodes=self.count_nodes(),
            edges=self.count_edges(),
            nodes_by_label={
                label: self.count_by_label(label)
                for label in expected.nodes_by_label
            },
            edges_by_type={
                rel_type: self.count_by_relationship_type(rel_type)
                for rel_type in expected.edges_by_type
            },
        )
        errors: list[str] = []
        # In a merged store every count is a superset of one dataset's
        # expectation, so "at least as many as expected" is the strongest
        # statement available. A count *below* expectation still fails: that
        # means records did not land, which is a real failure in any store.
        def _short(actual_count: int, expected_count: int) -> bool:
            return actual_count < expected_count if merged else actual_count != expected_count

        if _short(actual.nodes, expected.nodes):
            errors.append(f"node count {actual.nodes} != expected {expected.nodes}")
        if _short(actual.edges, expected.edges):
            errors.append(f"edge count {actual.edges} != expected {expected.edges}")
        for label, count in expected.nodes_by_label.items():
            actual_count = actual.nodes_by_label.get(label, 0)
            if _short(actual_count, count):
                errors.append(
                    f"label {label} count {actual_count} != expected {count}"
                )
        for rel_type, count in expected.edges_by_type.items():
            actual_count = actual.edges_by_type.get(rel_type, 0)
            if _short(actual_count, count):
                errors.append(
                    f"relationship {rel_type} count {actual_count} != expected {count}"
                )
        return VerifyLoadedGraphResult(
            passed=not errors,
            expected=expected,
            actual=actual,
            errors=errors,
        )

    def __enter__(self) -> GraphStore:
        self.connect()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
