#!/usr/bin/env python3
"""The ``describe`` primitive contract and its facet helpers.

``describe(id_or_title)`` returns **every** property on the anchor node plus a
compact *facet block*: a count of adjacent nodes grouped by ``(relationship,
direction, neighbour label)``. The facet block is what makes the whole design
safe — it gives the planner a complete, honest picture of a node's neighbourhood
in at most a handful of lines (max 7 facet rows in ATT&CK, 13 in CAPEC), so it
can decide what to fetch next with full information instead of being handed 25
arbitrary neighbours and no indication that hundreds were dropped.

Two facts make this cheap:

* A facet is a **count**, so the block is bounded at a fraction of a kilobyte
  regardless of whether the node has 4 neighbours or 858.
* A facet derived from live edges can never carry a false zero — absence of a row
  is absence of edges. To let a model assert absence *confidently* ("this
  Technique has no sub-techniques"), :func:`merge_zero_facets` folds in the
  *plausible* facets for the anchor's label from the schema registry, each with a
  real zero count.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

# A facet direction is from the anchor's point of view (matches the registry):
#   "out" — the anchor is the edge source
#   "in"  — the anchor is the edge target
OUT = "out"
IN = "in"


@dataclass(frozen=True, order=True)
class Facet:
    """One row of the facet block: how many neighbours of one kind the node has."""

    rel_type: str
    direction: str
    neighbour_label: str
    count: int = 0

    def key(self) -> tuple[str, str, str]:
        """The identity of the facet, ignoring the count."""
        return (self.rel_type, self.direction, self.neighbour_label)

    def with_count(self, count: int) -> "Facet":
        return Facet(self.rel_type, self.direction, self.neighbour_label, count)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rel": self.rel_type,
            "direction": self.direction,
            "label": self.neighbour_label,
            "count": self.count,
        }


def fold_facets(edges: Iterable[tuple[str, str, str]]) -> list[Facet]:
    """Count per-edge ``(rel_type, direction, neighbour_label)`` tuples into facets.

    Used by a backend (Gremlin) that returns individual edges rather than
    aggregating server-side; the resulting block is deterministically ordered.
    """
    counts: dict[tuple[str, str, str], int] = {}
    for rel_type, direction, neighbour_label in edges:
        if not rel_type:
            continue
        key = (rel_type, direction, neighbour_label or "")
        counts[key] = counts.get(key, 0) + 1
    facets = [Facet(rel, direction, label, count) for (rel, direction, label), count in counts.items()]
    return sorted(facets)


def facets_from_count_rows(rows: Any) -> list[Facet]:
    """Parse a Cypher aggregation's ``{rel, outgoing, label, count}`` rows into facets.

    ``outgoing`` is a boolean (``startNode(r) = n``); everything else is a string
    or a number. A row missing a relationship type is skipped.
    """
    facets: list[Facet] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        rel = str(row.get("rel") or "").strip()
        if not rel:
            continue
        direction = OUT if row.get("outgoing") else IN
        label = str(row.get("label") or "").strip()
        count = row.get("count")
        facets.append(
            Facet(rel, direction, label, int(count) if isinstance(count, (int, float)) else 0)
        )
    return facets


def merge_with_card(observed: Iterable[Facet], card: Any, label: str) -> list[Facet]:
    """Fold the card's plausible facets for ``label`` in as honest zeros.

    A thin adapter around :func:`merge_zero_facets` that reaches the schema
    registry through the source card view. Degrades gracefully (observed facets
    only) when the registry is unavailable — e.g. the canonical artifacts are
    absent in a fresh checkout.
    """
    try:
        plausible = card.label_facets(label)
    except Exception:  # noqa: BLE001 — a missing registry must never sink a result
        plausible = ()
    return merge_zero_facets(observed, plausible)


def merge_zero_facets(observed: Iterable[Facet], plausible: Iterable[Any]) -> list[Facet]:
    """Fold plausible-but-unobserved facets in as real zeros, then sort.

    ``observed`` are facets with live counts (> 0); ``plausible`` are the
    registry's :class:`~utils.specialists.schema.registry.PlausibleFacet` entries
    for the anchor's label. A plausible facet whose ``(rel, direction, label)`` was
    not observed is emitted with ``count=0`` — an honest absence the model can
    assert, rather than a silent gap. Observed counts always win.
    """
    by_key: dict[tuple[str, str, str], Facet] = {}
    for facet in observed:
        by_key[facet.key()] = facet
    for p in plausible:
        key = (p.rel_type, p.direction, p.neighbour_label)
        if key not in by_key:
            by_key[key] = Facet(p.rel_type, p.direction, p.neighbour_label, 0)
    return sorted(by_key.values())


@dataclass(frozen=True)
class DescribeRequest:
    """Ask for the full record + facet block of one anchor node."""

    dataset: str
    anchor: Any  # a ResolvedAnchor (id or title)
    include_zero_facets: bool = True

    def to_dict(self) -> dict[str, Any]:
        anchor = self.anchor
        return {
            "dataset": self.dataset,
            "anchor": anchor.to_dict() if hasattr(anchor, "to_dict") else anchor,
            "include_zero_facets": self.include_zero_facets,
        }


@dataclass(frozen=True)
class DescribeResult:
    """The full record of one node plus its bounded facet block."""

    primary_id: str
    label: str
    name: str
    properties: dict[str, Any] = field(default_factory=dict)
    facets: list[Facet] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "primary_id": self.primary_id,
            "label": self.label,
            "name": self.name,
            "properties": dict(self.properties),
            "facets": [f.to_dict() for f in self.facets],
        }
