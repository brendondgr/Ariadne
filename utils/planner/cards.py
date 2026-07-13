#!/usr/bin/env python3
"""Typed source-card view for the planner.

The planner's only ground truth is the source cards. It must route over the
**introspected** structural fields (``node_labels``, ``relationship_types``,
``allowed_edge_patterns``) and treat ``entity_descriptions`` as human context,
not routing truth (briefing §1.1). This module gives the rest of the planner a
stable, enriched, read-only view and a consistency check.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .card_enrichment import enrich


class CardConsistencyError(Exception):
    """Raised when a card's introspected structure is internally inconsistent."""


@dataclass(frozen=True)
class SourceCardView:
    """Read-only, enriched view of one source card.

    Structural fields are the routing truth; authored sections (filled by the
    enrichment layer) carry safety, provenance, and human glosses.
    """

    dataset: str
    runtime_backend: str
    node_labels: frozenset[str]
    relationship_types: frozenset[str]
    node_properties: dict[str, Any]
    allowed_edge_patterns: dict[str, list[list[str]]]
    safety: dict[str, Any]
    provenance: dict[str, Any]
    entity_descriptions: dict[str, Any]
    connection: dict[str, Any]
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    # -- structural membership (routing truth) -----------------------------

    def has_label(self, label: str) -> bool:
        return label in self.node_labels

    def has_relationship(self, rel_type: str) -> bool:
        return rel_type in self.relationship_types

    def has_entity(self, entity: str) -> bool:
        """True when ``entity`` is a known node label or relationship type."""
        return self.has_label(entity) or self.has_relationship(entity)

    def unknown_entities(self, entities: list[str]) -> list[str]:
        """Return the subset of ``entities`` not present in this card."""
        return [e for e in entities if not self.has_entity(e)]

    # -- safety limits ------------------------------------------------------

    def limits(self) -> dict[str, int]:
        """Return the numeric traversal/result limits from the safety block."""
        safety = self.safety or {}
        return {
            "max_traversal_depth": int(safety.get("max_traversal_depth", 0)),
            "max_result_rows": int(safety.get("max_result_rows", 0)),
            "query_timeout_ms": int(safety.get("query_timeout_ms", 0)),
        }

    # -- short structural fingerprint for the drafter/probe ----------------

    def expected_probe_labels(self) -> list[str]:
        """A couple of labels the content probe expects to exist when loaded."""
        return sorted(self.node_labels)[:2]

    # -- canonical-derived schema registry (universal extraction) ----------

    def schema_registry(self, data_dir: str | Path | None = None) -> Any:
        """The process-cached :class:`SchemaRegistry` covering this card's graph.

        Exposed here so the anchor resolver and the registry-backed validators
        can consult real, canonical-derived structure — plausible facets and
        observed property keys — through the same view the planner already
        routes over. Imported lazily to avoid a package-init cycle (the schema
        package pulls in nothing from the planner).
        """
        from utils.specialists.schema import get_registry

        return get_registry(data_dir)

    def label_facets(self, label: str, data_dir: str | Path | None = None) -> Any:
        """Plausible ``(rel, direction, neighbour label)`` facets for ``label``."""
        return self.schema_registry(data_dir).label_facets(label, dataset=self.dataset)

    def label_property_keys(
        self, label: str, data_dir: str | Path | None = None
    ) -> frozenset[str]:
        """Observed property keys for ``label`` in this card's dataset."""
        return self.schema_registry(data_dir).label_properties(
            label, dataset=self.dataset
        )

    @classmethod
    def from_card_dict(cls, card: dict[str, Any]) -> "SourceCardView":
        enriched = enrich(card)
        safety = enriched.get("safety") or {}
        return cls(
            dataset=enriched.get("dataset", ""),
            runtime_backend=enriched.get("runtime_backend", ""),
            node_labels=frozenset(enriched.get("node_labels", [])),
            relationship_types=frozenset(enriched.get("relationship_types", [])),
            node_properties=enriched.get("node_properties", {}),
            allowed_edge_patterns=safety.get("allowed_edge_patterns", {}),
            safety=safety,
            provenance=enriched.get("provenance", {}),
            entity_descriptions=enriched.get("entity_descriptions", {}),
            connection=enriched.get("connection", {}),
            raw=enriched,
        )


def assert_card_consistency(view: SourceCardView) -> None:
    """Validate a card's introspected structure is internally consistent.

    A consistent card is a precondition the planner assumes and the self-eval
    gate re-checks. We verify that every ``allowed_edge_patterns`` entry names a
    declared relationship type and references only declared node labels — i.e.
    the structural fields do not contradict each other (briefing §1.1).
    """
    errors: list[str] = []

    if not view.node_labels:
        errors.append("card has no node_labels")
    if not view.runtime_backend:
        errors.append("card has no runtime_backend")

    for rel_type, patterns in (view.allowed_edge_patterns or {}).items():
        if rel_type not in view.relationship_types:
            errors.append(
                f"allowed_edge_patterns references undeclared relationship {rel_type!r}"
            )
        for pair in patterns:
            if len(pair) != 2:
                errors.append(f"edge pattern for {rel_type!r} is not a [source, target] pair: {pair!r}")
                continue
            source, target = pair
            for label in (source, target):
                if label not in view.node_labels:
                    errors.append(
                        f"edge pattern for {rel_type!r} references undeclared label {label!r}"
                    )

    if errors:
        raise CardConsistencyError(
            f"Inconsistent source card {view.dataset!r}: " + "; ".join(errors)
        )


def load_source_cards(
    data_dir: str | Path = "data",
    *,
    check_consistency: bool = True,
) -> dict[str, SourceCardView]:
    """Load and enrich every source card under ``<data_dir>/source_cards``.

    Returns a mapping of dataset name -> SourceCardView. Each card is enriched
    with authored safety/provenance/glosses and (optionally) checked for
    internal consistency.
    """
    cards_dir = Path(data_dir) / "source_cards"
    views: dict[str, SourceCardView] = {}
    if not cards_dir.exists():
        return views
    for card_path in sorted(cards_dir.glob("*.json")):
        with open(card_path, encoding="utf-8") as f:
            raw = json.load(f)
        view = SourceCardView.from_card_dict(raw)
        if check_consistency:
            assert_card_consistency(view)
        views[view.dataset] = view
    return views
