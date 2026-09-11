#!/usr/bin/env python3
"""The registry data model: labels, property keys, and plausible facet triples.

A :class:`DatasetSchema` is the derived structure for one graph (``attack`` or
``capec``): the property keys observed per label, and the distinct
``(source_label, rel_type, target_label)`` triples observed across its edges.
Everything the primitives need is a projection of those two facts. A
:class:`SchemaRegistry` bundles the per-dataset schemas so a caller that already
knows its dataset can ask directly, and so a validator can check a structured
request against real structure.

The types are deliberately backend-agnostic — a ``PlausibleFacet`` is a
``(relationship, direction, neighbour label)`` regardless of whether the edge is
walked in Cypher (``-[r]-``) or Gremlin (``bothE()``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from .idscheme import (
    CONSISTENT,
    ID_PROPERTY,
    UNDETERMINED,
    PropertySchemes,
    combine_verdicts,
)

# A facet direction is expressed from the *anchor's* point of view:
#   "out" — the anchor is the edge source  (anchor)-[r]->(neighbour)
#   "in"  — the anchor is the edge target  (neighbour)-[r]->(anchor)
OUT = "out"
IN = "in"
_DIRECTIONS = (OUT, IN)

# How a schema's triples were obtained. The distinction is not cosmetic:
#
#   OBSERVED — derived by walking canonical instances. A triple is present
#              because *some node actually has such an edge*. This is what every
#              schema in this repository was until EXP-2026-08-011.
#   DECLARED — read from a catalog somebody else operates. A triple is present
#              because *the catalog permits such an edge*, whether or not any
#              node currently has one.
#
# A facet block asserting an honest zero means "this label can have such an edge
# and this node has none" under OBSERVED. Under DECLARED the same zero also
# admits "no node anywhere has one yet", which is a weaker statement. Carrying
# the flag lets a caller that cares tell the two apart instead of guessing.
OBSERVED = "observed"
DECLARED = "declared"


@dataclass(frozen=True, order=True)
class PlausibleFacet:
    """One ``(relationship, direction, neighbour label)`` a label may exhibit.

    "Plausible" means *some* node of this label has such an edge somewhere in the
    canonical graph — not that this particular node does. That is exactly what
    lets a facet block assert an honest zero: the facet is plausible for the
    label, but its live count on this node is 0.
    """

    rel_type: str
    direction: str
    neighbour_label: str

    def key(self) -> tuple[str, str, str]:
        return (self.rel_type, self.direction, self.neighbour_label)


def _opposite(direction: str) -> str:
    return IN if direction == OUT else OUT


@dataclass(frozen=True)
class DatasetSchema:
    """Derived schema for one dataset.

    ``label_property_keys`` maps a label to the union of property keys observed on
    its nodes. ``triples`` is the set of distinct ``(source_label, rel_type,
    target_label)`` observed across the dataset's edges — small (tens of entries),
    because it counts *kinds* of edges, not edges.
    """

    dataset: str
    label_property_keys: dict[str, frozenset[str]]
    triples: frozenset[tuple[str, str, str]]
    # ``{label: {property: PropertySchemes}}`` — the identifier shapes observed
    # per property, so a caller can ask whether a bound value could inhabit the
    # property a query filters. Defaulted so a schema may be constructed without
    # it; an empty map answers ``undetermined`` to everything, which is correct.
    label_id_schemes: dict[str, dict[str, PropertySchemes]] = field(
        default_factory=dict
    )
    # ``{label: {property: frozenset(values)}}`` — the distinct values observed
    # for *low-cardinality* properties, which is what a filter can be bound
    # against. A property with more distinct values than the cap is absent
    # rather than truncated: a partial vocabulary would let a caller conclude a
    # value is not real when the walk simply stopped early. Defaulted so a
    # schema may be constructed without it; an empty map binds nothing, which is
    # the correct behaviour for a caller that refuses to guess.
    label_value_vocabulary: dict[str, dict[str, frozenset[str]]] = field(
        default_factory=dict
    )
    # ``{label: frozenset(properties)}`` — properties observed holding a *list*
    # rather than a scalar. A filter on ``x_mitre_platforms`` is membership in a
    # list; one on ``Abstraction`` is equality with a string. The predicate a
    # builder emits differs, and getting it wrong silently matches nothing.
    label_list_properties: dict[str, frozenset[str]] = field(default_factory=dict)
    # ``{label: frozenset(properties)}`` — properties a store can hold as real,
    # queryable properties rather than packing into a blob: scalars and
    # homogeneous lists of scalars. The rule is the loader's
    # (``utils/graph_loader/stores/neo4j.py`` ``_native_property_values``) and
    # a contract test asserts the two agree. A builder must not emit a WHERE
    # clause on a property the store cannot answer for: it matches nothing,
    # silently, which is `Q55`.
    label_native_properties: dict[str, frozenset[str]] = field(default_factory=dict)
    # How ``triples`` was obtained — :data:`OBSERVED` or :data:`DECLARED`. See
    # the constants for why the difference is carried rather than flattened.
    # Defaulted to OBSERVED so every existing construction keeps its meaning.
    provenance: str = OBSERVED
    # The subset of ``triples`` that no source declared and this project added to
    # make an incompletely-delivered catalog functional. Always empty for an
    # OBSERVED schema. Non-empty means results traversing these edges are
    # confounded by our own reconstruction and must be reported separately.
    inferred_triples: frozenset[tuple[str, str, str]] = frozenset()

    # -- provenance ---------------------------------------------------------

    @property
    def is_declared(self) -> bool:
        return self.provenance == DECLARED

    def is_inferred_triple(self, source: str, rel_type: str, target: str) -> bool:
        """Was this edge kind added by us rather than declared by the source?"""
        return (source, rel_type, target) in self.inferred_triples

    # -- labels & properties ------------------------------------------------

    def labels(self) -> frozenset[str]:
        return frozenset(self.label_property_keys)

    def has_label(self, label: str) -> bool:
        return label in self.label_property_keys

    def label_properties(self, label: str) -> frozenset[str]:
        """Property keys observed on nodes of ``label`` (empty for an unknown label)."""
        return self.label_property_keys.get(label, frozenset())

    # -- identifier schemes -------------------------------------------------

    def id_schemes(self, label: str, prop: str = ID_PROPERTY) -> PropertySchemes | None:
        """The learned shapes for ``label.prop``, or ``None`` if never observed."""
        return self.label_id_schemes.get(label, {}).get(prop)

    def observed_values(self, label: str, prop: str) -> frozenset[str]:
        """Distinct values observed for ``label.prop``, when few enough to list.

        Empty means "cannot say", never "none exist": a high-cardinality
        property is omitted from the vocabulary entirely, so a caller must read
        an empty set as an absence of evidence rather than evidence of absence.
        """
        return self.label_value_vocabulary.get(label, {}).get(prop, frozenset())

    def is_list_property(self, label: str, prop: str) -> bool:
        """Was ``label.prop`` observed holding a list rather than a scalar?"""
        return prop in self.label_list_properties.get(label, frozenset())

    def is_native_property(self, label: str, prop: str) -> bool:
        """Can a store hold ``label.prop`` as a real, queryable property?"""
        return prop in self.label_native_properties.get(label, frozenset())

    def value_verdict(self, label: str, prop: str, value: Any) -> str:
        """Can ``value`` inhabit ``label.prop``? Three-valued; see ``idscheme``.

        An unobserved ``(label, property)`` is ``undetermined`` rather than a
        mismatch: the pair may be absent because this snapshot never carried it,
        and absence of evidence must not read as evidence of absence.
        """
        schemes = self.id_schemes(label, prop)
        if schemes is None:
            return UNDETERMINED
        return schemes.admits(value)

    def labels_for_id(self, value: Any) -> frozenset[str]:
        """Every label some property of which admits ``value``'s shape.

        One label is an inference; several is an ambiguity the caller must not
        resolve by guessing; none means the value belongs to no learned scheme.
        Open (opaque) properties contribute nothing — they admit everything, so
        they would make every label a candidate.
        """
        hits: set[str] = set()
        for label, properties in self.label_id_schemes.items():
            for schemes in properties.values():
                if schemes.is_open:
                    continue
                if schemes.admits(value) == CONSISTENT:
                    hits.add(label)
                    break
        return frozenset(hits)

    # -- facets -------------------------------------------------------------

    def label_facets(self, label: str) -> tuple[PlausibleFacet, ...]:
        """Every plausible facet for ``label``, both directions, sorted.

        For each triple where ``label`` is the source, an ``out`` facet toward the
        target label; for each triple where ``label`` is the target, an ``in``
        facet toward the source label. Deterministically ordered so a facet block
        is stable across runs.
        """
        facets: set[PlausibleFacet] = set()
        for source, rel, target in self.triples:
            if source == label:
                facets.add(PlausibleFacet(rel, OUT, target))
            if target == label:
                facets.add(PlausibleFacet(rel, IN, source))
        return tuple(sorted(facets))

    def facet_exists(
        self,
        anchor_label: str,
        rel_type: str,
        direction: str,
        neighbour_label: str | None = None,
    ) -> bool:
        """Is ``(anchor_label, rel_type, direction[, neighbour_label])`` real here?

        This is the structural check the registry-backed validators use in place
        of matching relationship types with a regex over a query string. When
        ``neighbour_label`` is ``None`` the check is satisfied by any neighbour
        label — "does the anchor have *any* outbound MITIGATES edge kind?".
        """
        if direction not in _DIRECTIONS:
            return False
        for source, rel, target in self.triples:
            if rel != rel_type:
                continue
            if direction == OUT and source == anchor_label:
                if neighbour_label is None or target == neighbour_label:
                    return True
            if direction == IN and target == anchor_label:
                if neighbour_label is None or source == neighbour_label:
                    return True
        return False


@dataclass(frozen=True)
class SchemaRegistry:
    """A read-only bundle of per-dataset schemas."""

    datasets: dict[str, DatasetSchema]

    def dataset(self, name: str) -> DatasetSchema | None:
        return self.datasets.get(name)

    def dataset_names(self) -> tuple[str, ...]:
        return tuple(sorted(self.datasets))

    def _select(self, dataset: str | None) -> Iterable[DatasetSchema]:
        if dataset is not None:
            schema = self.datasets.get(dataset)
            return (schema,) if schema is not None else ()
        return self.datasets.values()

    def has_label(self, label: str, dataset: str | None = None) -> bool:
        return any(s.has_label(label) for s in self._select(dataset))

    def label_properties(
        self, label: str, dataset: str | None = None
    ) -> frozenset[str]:
        """Union of property keys for ``label`` across the selected dataset(s)."""
        keys: set[str] = set()
        for schema in self._select(dataset):
            keys |= schema.label_properties(label)
        return frozenset(keys)

    def label_facets(
        self, label: str, dataset: str | None = None
    ) -> tuple[PlausibleFacet, ...]:
        """Plausible facets for ``label`` across the selected dataset(s), sorted."""
        facets: set[PlausibleFacet] = set()
        for schema in self._select(dataset):
            facets.update(schema.label_facets(label))
        return tuple(sorted(facets))

    def facet_exists(
        self,
        anchor_label: str,
        rel_type: str,
        direction: str,
        neighbour_label: str | None = None,
        dataset: str | None = None,
    ) -> bool:
        return any(
            schema.facet_exists(anchor_label, rel_type, direction, neighbour_label)
            for schema in self._select(dataset)
        )

    def value_verdict(
        self, label: str, prop: str, value: Any, dataset: str | None = None
    ) -> str:
        """Fold :meth:`DatasetSchema.value_verdict` across the selected dataset(s)."""
        return combine_verdicts(
            schema.value_verdict(label, prop, value) for schema in self._select(dataset)
        )

    def is_list_property(
        self, label: str, prop: str, dataset: str | None = None
    ) -> bool:
        """True when any selected dataset observed ``label.prop`` as a list."""
        return any(
            schema.is_list_property(label, prop) for schema in self._select(dataset)
        )

    def is_native_property(
        self, label: str, prop: str, dataset: str | None = None
    ) -> bool:
        """True only when EVERY selected dataset can hold it natively.

        All, not any: a filter emitted against a store that cannot answer for
        the property matches nothing rather than erroring.
        """
        schemas = list(self._select(dataset))
        return bool(schemas) and all(
            schema.is_native_property(label, prop) for schema in schemas
        )

    def observed_values(
        self, label: str, prop: str, dataset: str | None = None
    ) -> frozenset[str]:
        """Union :meth:`DatasetSchema.observed_values` across the selected dataset(s)."""
        values: set[str] = set()
        for schema in self._select(dataset):
            values.update(schema.observed_values(label, prop))
        return frozenset(values)

    def labels_for_id(self, value: Any, dataset: str | None = None) -> frozenset[str]:
        """Union of :meth:`DatasetSchema.labels_for_id` across the selected dataset(s)."""
        hits: set[str] = set()
        for schema in self._select(dataset):
            hits |= schema.labels_for_id(value)
        return frozenset(hits)
