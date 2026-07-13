#!/usr/bin/env python3
"""The universal extraction primitives — ``describe`` and ``expand``.

These two backend-agnostic contracts replace the closed registry of hand-written
query templates. ``describe`` returns every property on an anchor node plus a
bounded *facet block* (a count of adjacent nodes grouped by relationship,
direction, and neighbour label); ``expand`` returns the members of one facet,
identity-only, paged with an explicit truncation signal. Neither knows anything
about ATT&CK or CAPEC — they read whatever the node actually has.
"""

from __future__ import annotations

from .describe import (
    DescribeRequest,
    DescribeResult,
    Facet,
    facets_from_count_rows,
    fold_facets,
    merge_with_card,
    merge_zero_facets,
)

__all__ = [
    "DescribeRequest",
    "DescribeResult",
    "Facet",
    "facets_from_count_rows",
    "fold_facets",
    "merge_with_card",
    "merge_zero_facets",
]
