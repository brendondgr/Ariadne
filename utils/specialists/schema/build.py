#!/usr/bin/env python3
"""Derive a :class:`SchemaRegistry` by walking the canonical artifacts.

The canonical ``nodes.jsonl`` gives label -> property keys directly (a node's
primary ``label`` and its ``properties`` dict). The ``relationships.jsonl`` gives
the ``(source_label, rel_type, target_label)`` triples once each edge's endpoint
ids are resolved to labels through the node map. Deriving from these files —
rather than introspecting a live database — keeps the registry available offline,
in hermetic tests, and without a running Neo4j or Gremlin server.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any

from utils.graph_loader.stores.neo4j import _native_property_values

from .idscheme import SchemeLearner
from .registry import DECLARED, DatasetSchema, SchemaRegistry


def canonical_dir(data_dir: str | Path, dataset: str) -> Path:
    """``<data_dir>/graphs/<dataset>/canonical``."""
    return Path(data_dir) / "graphs" / dataset / "canonical"


def discover_datasets(data_dir: str | Path) -> list[str]:
    """Every dataset under ``<data_dir>/graphs`` that has a canonical nodes file."""
    graphs = Path(data_dir) / "graphs"
    if not graphs.is_dir():
        return []
    found: list[str] = []
    for child in sorted(graphs.iterdir()):
        if (child / "canonical" / "nodes.jsonl").is_file():
            found.append(child.name)
    return found


def _iter_jsonl(path: Path):
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


#: A property is filter vocabulary only if it takes few, short values. Both
#: bounds matter and neither is arbitrary. The 32 admits every categorical
#: property the two catalogues carry — CAPEC ``Abstraction`` and ``Status`` have
#: three values each, ATT&CK ``x_mitre_platforms`` eleven to fourteen — and
#: excludes the free-text and per-record fields that are not filters at all
#: (``Campaign.name`` has 56). The 48 characters keeps a description out even
#: where a small corpus happens to have few of them.
_MAX_VOCABULARY_VALUES = 32
_MAX_VOCABULARY_VALUE_CHARS = 48


def _observe_values(
    vocabulary: dict[str, set[str] | None], properties: Any
) -> None:
    """Record one node's short string values, dropping a property that overflows.

    A list-valued property contributes each of its entries: ``x_mitre_platforms``
    is a list and the thing a question filters on is one platform, not the tuple.
    A property that passes the cap is set to ``None`` and stays ``None``, so the
    vocabulary never holds a partial value set that a caller could mistake for a
    complete one.
    """
    if not isinstance(properties, dict):
        return
    for key, value in properties.items():
        if vocabulary.get(key, ...) is None:
            continue
        items = value if isinstance(value, (list, tuple)) else [value]
        seen = vocabulary.setdefault(key, set())
        for item in items:
            if not isinstance(item, str):
                continue
            text = item.strip()
            if not text or len(text) > _MAX_VOCABULARY_VALUE_CHARS:
                continue
            seen.add(text)
            if len(seen) > _MAX_VOCABULARY_VALUES:
                vocabulary[key] = None
                break


def build_dataset_schema(
    dataset: str,
    nodes_path: str | Path,
    relationships_path: str | Path,
) -> DatasetSchema:
    """Walk one dataset's canonical node/relationship files into a schema.

    The node's primary ``label`` (the first entry the loader writes, which is
    also what a Neo4j ``head(labels(n))`` returns) is authoritative for keying
    both properties and edge endpoints.
    """
    id_to_label: dict[str, str] = {}
    label_property_keys: dict[str, set[str]] = defaultdict(set)
    # ``{label: {property: set(values) | None}}``. ``None`` marks a property that
    # exceeded the cardinality cap and is therefore dropped from the vocabulary
    # rather than truncated — see ``DatasetSchema.label_value_vocabulary``.
    value_vocabulary: dict[str, dict[str, set[str] | None]] = defaultdict(dict)
    list_properties: dict[str, set[str]] = defaultdict(set)
    # ``None`` marks a property seen holding something no store can index.
    native_properties: dict[str, dict[str, bool]] = defaultdict(dict)
    learner = SchemeLearner()

    for node in _iter_jsonl(Path(nodes_path)):
        node_id = node.get("id")
        label = node.get("label")
        if not node_id or not label:
            continue
        id_to_label[node_id] = label
        # Learn what an identifier looks like for this label while the node is
        # in hand — the same walk that records property keys.
        learner.observe_node(node)
        properties = node.get("properties") or {}
        if isinstance(properties, dict):
            label_property_keys[label].update(properties.keys())
        else:
            # Ensure the label is registered even with an empty property set.
            label_property_keys.setdefault(label, set())
        # `name` is a first-class column on the canonical node, not an entry in
        # its `properties` dict, so scanning `properties` alone never recorded
        # it -- on any dataset, ATT&CK included. It is queryable as `n.name` in
        # Cypher and `values('name')` in Gremlin, so a schema that omits it
        # understates what can be filtered on.
        #
        # It was omitted, and the cost was concrete: the name-lookup guard could
        # not be derived from the schema, so it stayed a hard-coded list of
        # eight ATT&CK labels and no name lookup could match on any other
        # source (EXP-2026-08-011).
        if node.get("name"):
            label_property_keys[label].add("name")
        _observe_values(value_vocabulary[label], properties)
        if isinstance(properties, dict):
            native = _native_property_values(properties)
            for key, value in properties.items():
                if isinstance(value, (list, tuple)):
                    list_properties[label].add(key)
                # One non-native observation disqualifies the property: the
                # store cannot hold it for THAT node, so a filter on it would
                # silently miss that node.
                was = native_properties[label].get(key, True)
                native_properties[label][key] = was and key in native

    triples: set[tuple[str, str, str]] = set()
    for edge in _iter_jsonl(Path(relationships_path)):
        rel_type = edge.get("type")
        source_label = id_to_label.get(edge.get("source_id"))
        target_label = id_to_label.get(edge.get("target_id"))
        # An edge with an endpoint outside the node file (dangling) contributes
        # no honest triple — absence of the endpoint is absence of structure.
        if rel_type and source_label and target_label:
            triples.add((source_label, rel_type, target_label))

    return DatasetSchema(
        dataset=dataset,
        label_property_keys={
            label: frozenset(keys) for label, keys in label_property_keys.items()
        },
        triples=frozenset(triples),
        label_id_schemes=learner.result(),
        label_value_vocabulary={
            label: {
                prop: frozenset(values)
                for prop, values in properties.items()
                if values is not None
            }
            for label, properties in value_vocabulary.items()
        },
        label_list_properties={
            label: frozenset(keys) for label, keys in list_properties.items()
        },
        label_native_properties={
            label: frozenset(key for key, ok in keys.items() if ok)
            for label, keys in native_properties.items()
        },
    )


def build_declared_schema(catalog: Any, dataset: str | None = None) -> DatasetSchema:
    """Build a :class:`DatasetSchema` from a declared catalog, without instances.

    The sibling of :func:`build_dataset_schema`, and deliberately a sibling
    rather than a branch inside it: the scan path is the evidence behind every
    measured arm on record, and the safest way to add a second path is one that
    cannot execute a line of the first.

    ``catalog`` is a
    :class:`utils.kg_builder.catalog.declared.DeclaredCatalog`. It is typed
    loosely here so this module keeps no import edge into ``kg_builder`` — the
    schema package is read by the specialists at query time and has no business
    depending on the builder.

    **Identifier schemes are deliberately left empty.** ``label_id_schemes`` is
    learned from values, and a catalog has none. An empty map makes
    :meth:`DatasetSchema.value_verdict` answer ``undetermined`` to everything,
    which is the honest answer and exactly what ``idscheme``'s docstring
    prescribes for a source whose values have not been seen: *"it admits
    everything, because nothing has been learned about it."* The alternative —
    inventing schemes from declared value types — would manufacture confident
    verdicts out of a type name, and ``STRING`` says nothing about shape. That
    the binding guard therefore cannot fire on this source is a measured
    consequence (EXP-2026-08-011 H4), not a gap to paper over.

    Once instances exist, a caller wanting schemes can build the observed schema
    from them and keep the declared triples; the two are independent.
    """
    node_attributes = catalog.node_attributes
    return DatasetSchema(
        dataset=dataset or catalog.name,
        label_property_keys={
            label: frozenset(attrs) for label, attrs in node_attributes.items()
        },
        triples=frozenset(t.key() for t in catalog.triples),
        label_id_schemes={},
        provenance=DECLARED,
        inferred_triples=frozenset(t.key() for t in catalog.inferred_triples()),
    )


def build_registry(
    data_dir: str | Path = "data",
    datasets: list[str] | None = None,
) -> SchemaRegistry:
    """Build a registry for every discovered dataset (or the named subset)."""
    names = datasets if datasets is not None else discover_datasets(data_dir)
    schemas: dict[str, DatasetSchema] = {}
    for name in names:
        canonical = canonical_dir(data_dir, name)
        nodes = canonical / "nodes.jsonl"
        relationships = canonical / "relationships.jsonl"
        if not nodes.is_file() or not relationships.is_file():
            continue
        schemas[name] = build_dataset_schema(name, nodes, relationships)
    return SchemaRegistry(datasets=schemas)


def _default_data_dir() -> str:
    return os.environ.get("ARIADNE_DATA_DIR", "data")


@lru_cache(maxsize=8)
def _cached_registry(data_dir: str) -> SchemaRegistry:
    return build_registry(data_dir)


def get_registry(data_dir: str | Path | None = None) -> SchemaRegistry:
    """Return a process-cached registry for ``data_dir`` (env default if None).

    Building walks the canonical files once; subsequent calls for the same path
    are free. Callers that mutate the canonical artifacts within a process (only
    tests do) can reset via ``get_registry.cache_clear()``.
    """
    resolved = str(Path(data_dir if data_dir is not None else _default_data_dir()))
    return _cached_registry(resolved)


# Expose the underlying cache controls on the public entry point.
get_registry.cache_clear = _cached_registry.cache_clear  # type: ignore[attr-defined]
get_registry.cache_info = _cached_registry.cache_info  # type: ignore[attr-defined]
