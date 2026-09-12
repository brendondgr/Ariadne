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


def chain_paths(
    registry: Any,
    dataset: str,
    labels_in_order: list[str],
    *,
    max_hops: int,
) -> list[Hop] | None:
    """The route that visits ``labels_in_order`` **in order**, leg by leg.

    ``shortest_paths`` answers "how do I get from the anchor to label X", which
    is the wrong question whenever a request names an intermediate.
    ``Campaign -> Software -> Technique`` asks for the techniques used by the
    campaign's *tools*; the shortest route from ``Campaign`` to ``Technique`` is
    the direct ``USES`` edge, so the search returns the campaign's own four
    techniques and the ``Software`` in the middle is never bound. The answer is
    well-formed, cited, and about a different question. That single substitution
    is the largest mechanism behind the generic arm's judged loss —
    `EXP-2026-09-017` A-2, 56 development questions at a mean of 0.4625, 30.9% of
    the points lost.

    This searches between each *consecutive pair* instead and concatenates, so
    every named label is bound and every intermediate is retrieved in its own
    right. ``max_hops`` bounds each leg, not the whole route: a three-label
    request whose legs are one hop each is two hops long however tight the
    per-leg bound is.

    Returns ``None`` — never a partial route — when fewer than two legs are
    requested, when a label repeats, or when any leg is unreachable. A caller
    that receives ``None`` falls back to the star walk, which is what the system
    did before this existed, so a chain that cannot be resolved costs nothing.
    """
    labels = [label for label in labels_in_order if label]
    if len(labels) < 3 or len(set(labels)) != len(labels):
        return None

    route: list[Hop] = []
    for source, target in zip(labels, labels[1:]):
        leg = shortest_paths(registry, dataset, source, max_hops=max_hops).get(target)
        if not leg:
            return None
        route.extend(leg)
    return route


def relation_chain(
    registry: Any,
    dataset: str,
    root_label: str,
    rel_names: list[str],
    *,
    wanted_labels: tuple[str, ...] = (),
) -> list[Hop] | None:
    """Walk the *named* relationships in order, taking each direction from the schema.

    ``chain_paths`` routes between consecutive **labels**, which cannot express
    the commonest two-hop shape in the bank: ``AttackPattern -CanAlsoBe->
    AttackPattern -HAS_CONSEQUENCE-> Consequence`` names only two distinct
    labels, because the intermediate is the same label as the anchor. Twenty-seven
    of the thirty-six single-source two-hop development questions look like that.
    What the plan does carry, in order, is the *relationships*.

    Direction is resolved rather than assumed: for each named relationship the
    registry is asked which facets of the current label carry it, and the walk
    takes one. Where a relationship exists in both directions the tie is broken
    towards a neighbour label the request actually named, then towards
    ``out`` — a deterministic rule, not a guess about meaning.

    Returns ``None`` — never a partial route — for fewer than two relationships
    or when any leg has no declared facet, so a caller falls back to the star
    walk it would have used anyway.
    """
    names = [name for name in rel_names if name]
    if len(names) < 2 or not root_label:
        return None

    route: list[Hop] = []
    current = root_label
    for name in names:
        facets = [
            facet
            for facet in (registry.label_facets(current, dataset=dataset) or [])
            if facet.rel_type == name and facet.neighbour_label
        ]
        if not facets:
            return None
        facets.sort(
            key=lambda facet: (
                facet.neighbour_label not in wanted_labels,
                facet.direction != "out",
                facet.neighbour_label,
            )
        )
        # A self-referential relationship declared both ways — ``ChildOf`` and
        # ``CanAlsoBe`` on ``AttackPattern`` — reaches its own label in either
        # direction, so the schema cannot say which the question means. "More
        # specific cases of CAPEC-26" is inbound; "what CAPEC-26 is a case of" is
        # outbound; the words carry it and the plan does not.
        #
        # **Walk it undirected rather than picking one.** Preferring ``out``
        # measured worse than not chaining at all (seven questions lost gold
        # coverage, dev mean 0.6655 -> 0.6534), and declining left 27 development
        # questions unchained, which is why `H1` came in at +0.063 against a
        # +0.10 threshold. Undirected is neither: it is not a guess, it costs one
        # traversal step rather than two, and because the edge returns to its own
        # label the next leg is unaffected. It retrieves a superset of the right
        # answer where a direction would sometimes retrieve the complement.
        ambiguous = {
            facet.direction for facet in facets if facet.neighbour_label == current
        }
        chosen = facets[0]
        if len(ambiguous) > 1:
            route.append((chosen.rel_type, "both", current))
            continue
        route.append((chosen.rel_type, chosen.direction, chosen.neighbour_label))
        current = chosen.neighbour_label
    return route
