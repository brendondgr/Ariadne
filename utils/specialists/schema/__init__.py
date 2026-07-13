#!/usr/bin/env python3
"""Canonical-derived schema registry for the universal extraction primitives.

Both universal primitives — ``describe`` (full node properties + a bounded facet
block) and ``expand`` (the members of one facet) — read from this registry rather
than from any hand-written, per-label knowledge. The registry answers two
questions, and only these two:

* **What property keys does a node of label L carry?** (``label_properties``) —
  so ``describe`` knows the shape of "all properties" without a live DB.
* **What ``(relationship, direction, neighbour label)`` facets are *plausible*
  for a node of label L?** (``label_facets``) — so a facet block can show an
  honest **zero** ("this Technique has no sub-techniques") instead of merely
  failing to observe an edge, and so a structured primitive request can be
  validated ("does ``(Technique, MITIGATES, in, Mitigation)`` exist?").

It is derived from the canonical artifacts (``nodes.jsonl`` /
``relationships.jsonl``) rather than by introspecting a running graph, so it is
available offline, in tests, and without Neo4j or Gremlin. Nothing in here knows
anything about ATT&CK or CAPEC by name — a new MITRE edge type appears in the
registry the moment the canonical artifacts carry it, with no code change.
"""

from __future__ import annotations

from .build import (
    build_dataset_schema,
    build_registry,
    canonical_dir,
    discover_datasets,
    get_registry,
)
from .registry import DatasetSchema, PlausibleFacet, SchemaRegistry
from .validate import (
    describe_request_reasons,
    expand_request_reasons,
    is_valid_expand,
)

__all__ = [
    "DatasetSchema",
    "PlausibleFacet",
    "SchemaRegistry",
    "build_dataset_schema",
    "build_registry",
    "canonical_dir",
    "describe_request_reasons",
    "discover_datasets",
    "expand_request_reasons",
    "get_registry",
    "is_valid_expand",
]
