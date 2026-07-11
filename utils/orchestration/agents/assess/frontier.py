#!/usr/bin/env python3
"""Deterministic evidence-delta extraction for the iterative retrieval loop.

Two pure helpers answer, for the specialist evidence accumulated so far:

* ``extract_frontier`` — which ``(join_value, source)`` join-keys have we
  surfaced? This is the pool the re-planner chases: a join value that one
  source's records carry is a candidate seed for the *other* side of a
  declared cross-source join.
* ``update_visited`` — which ``(entity_id, source)`` records are *new* this
  hop? The delta doubles as the novelty signal (empty ⇒ nothing new surfaced)
  and folds cleanly through the ``union_sets`` state reducer.

Keeping this side-effect-free and backend-agnostic (it reads only the
normalized ``join_values``/``primary_id`` the specialists already emit) keeps
the novelty check honest and the ``assess`` node thin.
"""

from __future__ import annotations

from collections.abc import Iterable

from utils.planner.schema import Plan
from utils.specialists.contracts import SpecialistResult


def _joinable_sources(plan: Plan) -> set[str]:
    """Sources that participate in at least one declared cross-source join.

    Join-key chasing is only worthwhile where the plan actually declares a
    bridge between sources; a source with no declared join has no *other* side
    to chase into, so its join values never enter the frontier.
    """
    sources: set[str] = set()
    for join in plan.joins:
        sources.update(join.sources)
    return sources


def extract_frontier(
    results: Iterable[SpecialistResult], plan: Plan
) -> set[tuple[str, str]]:
    """Every ``(join_value, source)`` chase-worthy join-key in ``results``.

    Scoped to sources that appear in a declared join (``plan.joins``): the
    first-cut expansion strategy is deterministic join-key chasing, so a value
    only enters the frontier when a declared join could carry it to another
    source. Reads the normalized ``join_values`` the specialists emit, so it is
    independent of Cypher/Gremlin specifics.
    """
    joinable = _joinable_sources(plan)
    frontier: set[tuple[str, str]] = set()
    for result in results:
        source = result.task.source
        if source not in joinable:
            continue
        for record in result.records:
            for value in record.join_values:
                if value:
                    frontier.add((value, source))
    return frontier


def update_visited(
    visited: set[tuple[str, str]], results: Iterable[SpecialistResult]
) -> set[tuple[str, str]]:
    """The ``(entity_id, source)`` pairs newly retrieved this hop.

    Returns only the *delta* relative to ``visited`` — entities not already
    settled — so an empty return is an honest "this hop surfaced no new node"
    signal, and the result unions straight into the running ``visited`` set.
    """
    delta: set[tuple[str, str]] = set()
    for result in results:
        source = result.task.source
        for record in result.records:
            if not record.primary_id:
                continue
            pair = (record.primary_id, source)
            if pair not in visited:
                delta.add(pair)
    return delta
