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
    extract_frontier,
    update_visited,
)
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


def _joins_closed(evidence: FederatedEvidence, plan: Plan) -> list[str]:
    """Return the descriptions of declared joins that have *not* closed."""
    open_joins: list[str] = []
    for join in plan.joins:
        if not _join_satisfied(evidence, join):
            open_joins.append(
                f"join '{join.key}' across {', '.join(sorted(join.sources))} "
                "has no cross-source match yet"
            )
    return open_joins


def deterministic_assessment(
    *,
    evidence: FederatedEvidence,
    plan: Plan,
    prior_frontier: set[tuple[str, str]],
    prior_visited: set[tuple[str, str]],
    hop: int,
) -> Assessment:
    """The reproducible join-closure + novelty verdict (no hop-cap applied)."""
    results = list(evidence.results)

    # No declared join ⇒ no cross-source expansion is possible; a single pass is
    # all this plan can do, so it is sufficient by construction. This keeps the
    # common single-source question a one-shot (no wasted re-plan cycle).
    if not plan.joins:
        return Assessment(
            sufficient=True,
            gaps=[],
            missing_entities=[],
            hop=hop,
            hop_capped=False,
            mode="deterministic",
            reason="no declared cross-source join; single pass is sufficient",
        )

    new_frontier = extract_frontier(results, plan) - set(prior_frontier)
    new_visited = update_visited(set(prior_visited), results)
    novelty_exhausted = not new_frontier and not new_visited

    open_joins = _joins_closed(evidence, plan)
    join_closure = not open_joins

    # Join values surfaced anywhere but not yet matched across sources are the
    # concrete seeds a re-plan should chase into the opposite source.
    full_frontier = extract_frontier(results, plan) | set(prior_frontier)
    resolved = set(evidence.cross_source_join_values())
    missing_entities = sorted({v for v, _ in full_frontier} - resolved)

    sufficient = join_closure and novelty_exhausted

    gaps = list(open_joins)
    if new_frontier:
        keys = ", ".join(sorted(f"{v} ({s})" for v, s in new_frontier))
        gaps.append(f"unexpanded join-keys discovered this hop: {keys}")
    elif new_visited and not join_closure:
        gaps.append("new records surfaced this hop; joins may still close")

    if sufficient:
        reason = "join closure reached and novelty exhausted"
    elif not join_closure:
        reason = "declared join(s) not yet resolved across sources"
    else:
        reason = "new join-keys surfaced this hop; more to chase"

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
