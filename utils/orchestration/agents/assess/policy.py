#!/usr/bin/env python3
"""Sufficiency policy for the ``assess`` node.

The default judge is **deterministic** so the LLM-off build stays
byte-reproducible: evidence is *sufficient* when

  (a) every declared cross-source join has resolved to at least one record
      that appears under *both* of the join's sources (join closure), **and**
  (b) the most recent hop surfaced no new join-keys or entities (novelty
      exhausted).

Either condition failing — with hops remaining — triggers a re-plan. The hop
cap is a hard short-circuit layered on top: once ``hop >= max_hops`` the verdict
is forced ``sufficient`` regardless of the predicate, guaranteeing termination.

An LLM "what's missing" critic is opt-in (``assess_mode == "llm"``). It is
injected (``critic=``) so it stays testable and, per the standing fallback
policy, *any* failure degrades cleanly to the deterministic verdict with the
fallback recorded in ``Assessment.mode``.
"""

from __future__ import annotations

import logging
from typing import Callable

from utils.orchestration.agents.assess.contracts import Assessment
from utils.orchestration.agents.assess.frontier import (
    extract_facet_frontier,
    extract_frontier,
)
from utils.planner.join_keys import CANONICAL_JOIN_KEYS
from utils.planner.schema import JoinDeclaration, Plan
from utils.specialists.federation import FederatedEvidence

logger = logging.getLogger("ariadne.orchestration.assess")

# An LLM critic takes the request + evidence + the deterministic verdict and
# returns a refined Assessment, or raises to signal "unavailable" (→ fallback).
LLMCritic = Callable[[str, FederatedEvidence, Assessment], Assessment]


def _join_satisfied(evidence: FederatedEvidence, join: JoinDeclaration) -> bool:
    """True when some join value is carried by records under *both* sources."""
    wanted = set(join.sources)
    if len(wanted) < 2:
        return True  # a degenerate single-source "join" needs no correlation
    for entries in evidence.join_index().values():
        if wanted <= {e["source"] for e in entries}:
            return True
    return False


def _open_joins(evidence: FederatedEvidence, plan: Plan) -> list[str]:
    """Return the descriptions of declared joins that have *not* closed."""
    open_joins: list[str] = []
    for join in plan.joins:
        if not _join_satisfied(evidence, join):
            open_joins.append(
                f"join '{join.key}' across {', '.join(sorted(join.sources))} "
                "has no cross-source match yet"
            )
    return open_joins


def _chaseable_frontier(
    evidence: FederatedEvidence, plan: Plan
) -> set[tuple[str, str]]:
    """The ``(join_value, source)`` keys a re-plan could still *productively* chase.

    A key is chaseable when a producer source surfaced it, it has not yet
    resolved across sources, and the consumer side of its declared join has not
    been queried yet (the first-cut cross-source expansion). This mirrors
    :meth:`PlanningAgent.replan` exactly, so the loop re-plans **iff** there is
    real work to do — no wasted cycles, and termination once the chase is dry.
    """
    frontier = extract_frontier(evidence.results, plan)
    if not frontier:
        return set()
    queried = set(evidence.by_source().keys())
    resolved = set(evidence.cross_source_join_values())
    join_sources = {s for join in plan.joins for s in join.sources}

    chaseable: set[tuple[str, str]] = set()
    for key in CANONICAL_JOIN_KEYS:
        producer = next((e for e in key.endpoints if e.via_edge), None)
        consumer = next((e for e in key.endpoints if e.via_edge is None), None)
        if producer is None or consumer is None:
            continue
        if producer.dataset not in join_sources or consumer.dataset not in join_sources:
            continue
        if consumer.dataset in queried:
            continue  # nothing more to chase cross-source into an already-run source
        for value, source in frontier:
            if source == producer.dataset and value not in resolved:
                chaseable.add((value, source))
    return chaseable


def expandable_facets(
    evidence: FederatedEvidence,
) -> set[tuple[str, str, str, str, str]]:
    """The unexpanded, non-zero facets a facet-driven re-plan could still chase.

    A ``describe`` result whose facet block shows ``MITIGATES × 6`` names six
    unfetched members — exactly the frontier the old templates never produced,
    which is why the retrieval loop was live but inert. This surfaces that pool
    (an ``expand`` request per entry) for an LLM critic or a future deterministic
    facet-expansion policy. It is deliberately kept *out* of the reproducible
    join-closure verdict below: the deterministic loop's termination remains
    governed solely by cross-source join chasing, so the byte-reproducible
    LLM-off build is unchanged — a facet frontier informs a smarter re-plan
    without destabilising the guarantee that the loop terminates.
    """
    return extract_facet_frontier(evidence.results)


def deterministic_assessment(
    *,
    evidence: FederatedEvidence,
    plan: Plan,
    prior_frontier: set[tuple[str, str]],
    prior_visited: set[tuple[str, str]],
    hop: int,
) -> Assessment:
    """The reproducible sufficiency verdict (no hop-cap applied).

    Evidence is *sufficient* when there is nothing left to productively chase:
    no ``_chaseable_frontier``. This subsumes the intent of the join-closure +
    novelty rule — the loop keeps going exactly while an unresolved join-key can
    still be carried into a not-yet-queried source, and stops (synthesizing with
    what it has) the moment the chase is dry, whether the join closed or simply
    cannot. ``prior_frontier``/``prior_visited`` are accepted for signature
    stability but the decision reads straight off the accumulated evidence.
    """
    # No declared join ⇒ no cross-source expansion is possible; one pass is all
    # this plan can do, so it is sufficient by construction.
    if not plan.joins:
        return Assessment(
            sufficient=True, gaps=[], missing_entities=[], hop=hop,
            hop_capped=False, mode="deterministic",
            reason="no declared cross-source join; single pass is sufficient",
        )

    open_joins = _open_joins(evidence, plan)
    chaseable = _chaseable_frontier(evidence, plan)
    sufficient = not chaseable
    missing_entities = sorted({v for v, _ in chaseable})

    gaps = list(open_joins)
    if chaseable:
        keys = ", ".join(sorted(f"{v} ({s})" for v, s in chaseable))
        gaps.append(f"unresolved join-keys still chaseable: {keys}")

    if sufficient:
        reason = (
            "join closure reached; nothing left to chase" if not open_joins
            else "no declared join resolved and nothing left to chase; synthesizing partial"
        )
    else:
        reason = "unresolved join-keys can still be chased into an un-queried source"

    return Assessment(
        sufficient=sufficient,
        gaps=gaps,
        missing_entities=missing_entities,
        hop=hop,
        hop_capped=False,
        mode="deterministic",
        reason=reason,
    )


def assess(
    *,
    evidence: FederatedEvidence,
    plan: Plan,
    prior_frontier: set[tuple[str, str]],
    prior_visited: set[tuple[str, str]],
    hop: int,
    max_hops: int,
    assess_mode: str = "deterministic",
    use_llm: bool = False,
    critic: LLMCritic | None = None,
) -> Assessment:
    """Judge sufficiency, applying the hop-cap short-circuit last.

    The hop cap wins over everything: at ``hop >= max_hops`` the loop is forced
    out to synthesis with ``sufficient=True`` and ``hop_capped=True``, even if
    the predicate would have re-planned. This is the termination guarantee.
    """
    verdict = deterministic_assessment(
        evidence=evidence,
        plan=plan,
        prior_frontier=prior_frontier,
        prior_visited=prior_visited,
        hop=hop,
    )

    if assess_mode == "llm":
        if use_llm and critic is not None:
            try:
                verdict = critic(plan.request, evidence, verdict)
            except Exception as exc:  # any failure → clean deterministic fallback
                logger.info(
                    "LLM sufficiency critic unavailable (%s); using deterministic judge",
                    exc,
                )
                verdict = _with_mode(verdict, "deterministic (llm fallback)")
        else:
            # Requested but the LLM is off / no critic wired: degrade cleanly.
            verdict = _with_mode(verdict, "deterministic (llm fallback)")

    # Hop-cap short-circuit — forced termination, recorded honestly.
    if hop >= max_hops and not verdict.sufficient:
        return Assessment(
            sufficient=True,
            gaps=list(verdict.gaps),
            missing_entities=list(verdict.missing_entities),
            hop=hop,
            hop_capped=True,
            mode=verdict.mode,
            reason=f"hop cap reached ({hop}/{max_hops}); forcing synthesis",
        )
    return verdict


def _with_mode(verdict: Assessment, mode: str) -> Assessment:
    return Assessment(
        sufficient=verdict.sufficient,
        gaps=list(verdict.gaps),
        missing_entities=list(verdict.missing_entities),
        hop=verdict.hop,
        hop_capped=verdict.hop_capped,
        mode=mode,
        reason=verdict.reason,
    )
