#!/usr/bin/env python3
"""Declared-path search over the derived schema registry.

The registry exposes, per label, the ``(rel_type, direction, neighbour_label)``
facets observed in the canonical graph. That is a directed edge list, so
"how do I get from a Technique to an Analytic" is an ordinary breadth-first
search over it — no hand-written question shape required.

This module exists so the two ``SPECIALIST_GENERIC_ONLY`` branches (Cypher and
Gremlin) share one search rather than growing two subtly different ones. It is
imported only from those branches; nothing in the default cascade calls it.
"""

from __future__ import annotations

from typing import Any

# A hop as the search reports it: the edge to walk, the direction to walk it,
# and the label it lands on.
Hop = tuple[str, str, str]


def shortest_paths(
    registry: Any,
    dataset: str,
    anchor_label: str,
    *,
    max_hops: int,
) -> dict[str, list[Hop]]:
    """Breadth-first shortest path from ``anchor_label`` to every reachable label.

    Returns a mapping of label to the hop sequence that reaches it. The anchor
    maps to the empty path. Labels beyond ``max_hops`` are absent rather than
    truncated, so a caller never receives a partial route it might mistake for a
    complete one.
    """
    paths: dict[str, list[Hop]] = {anchor_label: []}
    frontier = [anchor_label]
    for _ in range(max_hops):
        nxt: list[str] = []
        for label in frontier:
            for facet in registry.label_facets(label, dataset=dataset) or []:
                target = facet.neighbour_label
                if not target or target in paths:
                    continue
                paths[target] = [
                    *paths[label],
                    (facet.rel_type, facet.direction, target),
                ]
                nxt.append(target)
        if not nxt:
            break
        frontier = nxt
    return paths


def edge_prefixes(
    paths: dict[str, list[Hop]], wanted: list[str]
) -> list[tuple[tuple[str, str], ...]]:
    """Every ``(rel, direction)`` prefix needed to reach the wanted labels.

    Prefixes rather than whole paths, so an intermediate node is retrieved in its
    own right — the ``DetectionStrategy`` between a ``Technique`` and its
    ``Analytic`` is part of the answer, not scaffolding.

    Deduplicated on the ``(rel, direction)`` sequence and **not** on the terminal
    label: a question names a label loosely while an edge reaches whatever the
    schema says it reaches. "Which techniques does Mimikatz use" resolves the
    label ``Technique``, but ``USES`` out of ``Software`` lands on ``Technique``
    *and* ``SubTechnique``, so keying on the label would split one branch into
    two and filtering a pattern to it would drop the other.
    """
    prefixes: dict[tuple[tuple[str, str], ...], None] = {}
    for label in wanted:
        path = paths.get(label)
        if not path:
            continue
        for i in range(1, len(path) + 1):
            prefixes.setdefault(
                tuple((rel, direction) for rel, direction, _ in path[:i]), None
            )
    return sorted(prefixes, key=len)
