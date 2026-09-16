#!/usr/bin/env python3
"""Relevance-ranked facet expansion — the loop's second chase strategy.

``extract_facet_frontier`` surfaces every unexpanded, non-zero facet a
``describe`` returned: ``MITIGATES × 6`` names six members that were counted but
never fetched. Until now nothing consumed it, so the retrieval loop was live but
inert — it could only chase *cross-source join keys*, which meant a single-source
question was declared sufficient after one pass by construction and an
open-ended question got counts instead of content.

This module closes that gap with two pure helpers:

* :func:`relevant_facets` — rank the frontier against what the analyst actually
  asked and keep the top few. A hub node exposes many facets; chasing all of them
  would trade silent truncation for an explosion, and chasing *none* is the
  current behaviour. Relevance is scored off the request text and the plan's own
  declared entities, so the loop fetches what the question implies.
* :func:`facet_sub_questions` — turn those entries into ordinary sub-questions.
  No new execution path: a sub-question naming the anchor id in its text and the
  relationship in ``entities`` routes through the existing neighbour templates,
  so the expansion hop is drafted, gated, executed and normalised exactly like a
  first-hop question.

Both are side-effect-free so the loop's termination stays inspectable.
"""

from __future__ import annotations

import re

from utils.planner.schema import Limits, Plan, SubQuestion

#: A facet entry: ``(anchor_id, rel, direction, neighbour_label, source)``.
FacetEntry = tuple[str, str, str, str, str]

_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(_WORD_RE.findall((text or "").lower()))


def _name_tokens(name: str) -> set[str]:
    """Tokens of a schema name: ``HAS_MITIGATION`` → {has, mitigation, mitigations}."""
    parts = {p for p in _WORD_RE.findall((name or "").lower()) if p}
    # The question says "mitigations"; the schema says MITIGATION. Match both.
    return parts | {f"{p}s" for p in parts}


def score_facet(entry: FacetEntry, request: str, plan_entities: set[str]) -> int:
    """How strongly this facet answers the request. Higher is more relevant.

    Deliberately simple and inspectable: an exact entity match the planner already
    declared is the strongest signal, a word the analyst used is next, and
    everything else scores zero and is not chased.
    """
    _anchor, rel, _direction, label, _source = entry
    want = _tokens(request)
    score = 0
    declared = {e.strip().upper() for e in plan_entities if e}
    if rel.upper() in declared:
        score += 10
    if label.upper() in declared:
        score += 8
    if _name_tokens(rel) & want:
        score += 5
    if _name_tokens(label) & want:
        score += 4
    return score


def relevant_facets(
    frontier: set[FacetEntry],
    *,
    request: str,
    plan: Plan,
    already_expanded: set[tuple[str, str, str]] | None = None,
    limit: int = 4,
    counts: dict[FacetEntry, int] | None = None,
    fallback: bool = False,
    fallback_max_members: int = 50,
) -> list[FacetEntry]:
    """The question-relevant facets worth an expansion hop, best first.

    A facet already expanded on an earlier hop is dropped, so the loop cannot
    re-fetch the same neighbourhood and spin.

    **Fallback (EXP-2026-09-024, plan Step 5).** When *no* facet scores — the
    request names a relation in words the card does not carry ("how do I
    defend against T1047", "what does G0016 rely on") — the anchor is right
    and the traversal is unknown, and answering with the anchor's one record
    is the measured T1/T2 failure (54 of 172 misses). With ``fallback`` on and
    the request not definitional, the anchor's smallest non-zero facets are
    expanded instead, up to ``limit`` of them and none larger than
    ``fallback_max_members``: the specific relations first, the hub-sized ones
    left as counts the analyst can ask about. Reads only the registry's facet
    block, so it carries to any card.
    """
    plan_entities: set[str] = set()
    for sq in plan.sub_questions:
        plan_entities |= {str(e) for e in sq.entities}
    seen = already_expanded or set()
    # A facet the plan ALREADY has a sub-question for is not a gap, whether or
    # not that hop has run yet. Reading it off the plan is exact and
    # backend-agnostic — the evidence-side check only sees an expanded
    # neighbourhood once the records carry an edge type, which not every
    # normalizer emits, so on its own it would call the same facet a gap forever.
    requested: list[tuple[str, set[str]]] = [
        ((sq.text or "").upper(), {str(e).strip().upper() for e in sq.entities})
        for sq in plan.sub_questions
    ]

    scored: list[tuple[int, FacetEntry]] = []
    for entry in frontier:
        anchor, rel, direction, _label, _source = entry
        if (anchor, rel, direction) in seen:
            continue
        if any(
            rel.upper() in rels and anchor.upper() in text
            for text, rels in requested
        ):
            continue  # this hop is already planned; not a gap
        score = score_facet(entry, request, plan_entities)
        if score > 0:
            scored.append((score, entry))
    # Deterministic order: score desc, then the tuple itself.
    scored.sort(key=lambda pair: (-pair[0], pair[1]))
    if scored or not fallback:
        return [entry for _score, entry in scored[:max(0, limit)]]

    from utils.planner.intent import is_definitional_request

    if is_definitional_request(request) or not counts:
        return []
    small: list[tuple[int, FacetEntry]] = []
    for entry in frontier:
        anchor, rel, direction, _label, _source = entry
        if (anchor, rel, direction) in seen:
            continue
        if any(rel.upper() in rels and anchor.upper() in text for text, rels in requested):
            continue
        count = counts.get(entry, 0)
        if 0 < count <= fallback_max_members:
            small.append((count, entry))
    small.sort(key=lambda pair: (pair[0], pair[1]))
    return [entry for _count, entry in small[:max(0, limit)]]


def card_relationship_name(card, edge_label: str) -> str | None:
    """The card's own name for a graph edge label, or ``None`` when unknown.

    A facet reports the **graph** edge label (``CHILD_OF``), but the source card
    declares relationships in its own vocabulary — and CAPEC's is mixed:
    ``ChildOf``/``ParentOf``/``PeerOf`` sit alongside ``HAS_MITIGATION`` and
    ``MAPS_TO``. Handing the raw edge label to a sub-question names a
    relationship the card does not have, so the specialist's boundary check
    rejects it and the expansion hop runs an empty query — the loop iterates and
    retrieves nothing. Resolving through the card keeps the expansion speaking
    the vocabulary the rest of the pipeline validates against.
    """
    try:
        declared = set(card.relationship_types)
    except Exception:  # noqa: BLE001 — a card without a schema is not fatal
        return None
    if edge_label in declared:
        return edge_label
    from utils.graph_loader.stores.gremlin import gremlin_edge_label

    for name in sorted(declared):
        try:
            if gremlin_edge_label(name) == edge_label:
                return name
        except Exception:  # noqa: BLE001
            continue
    return None


def facet_sub_questions(
    entries: list[FacetEntry], *, cards: dict, start_index: int = 0
) -> list[SubQuestion]:
    """Ordinary sub-questions that fetch each facet's members.

    The anchor id goes in the text (the specialist's resolve step reads ids out of
    the text, exactly as it does for a first-hop question) and the relationship
    goes in ``entities`` so the builder routes to its neighbour template rather
    than to ``describe`` — which is what produced the bare count in the first place.
    """
    out: list[SubQuestion] = []
    for offset, (anchor, rel, _direction, label, source) in enumerate(entries):
        card = cards.get(source)
        if card is None:
            continue
        rel_name = card_relationship_name(card, rel)
        if rel_name is None:
            continue  # the card cannot express this edge; nothing to ask for
        entities = [rel_name] + ([label] if label else [])
        out.append(
            SubQuestion(
                id=f"x{start_index + offset + 1}",
                source=source,
                # Phrased as an explicit enumeration on purpose. The composer's
                # structured-enumeration claim fires on an enumerative request or
                # when the id set outgrows the fact claim's sample; an expansion
                # hop usually returns a *small* set, so without the enumerative
                # phrasing neither trigger fires and the members this hop was
                # created to fetch never reach a claim — the loop retrieves them
                # and the answer still never says them.
                text=(
                    f"In {source}, list all {label or 'neighbours'} reached from "
                    f"{anchor} via {rel_name}"
                ),
                entities=entities,
                limits=Limits(**card.limits()),
                rationale=(
                    f"re-plan: {anchor} reported a non-zero {rel} facet whose members "
                    f"were counted but never fetched"
                ),
            )
        )
    return out
