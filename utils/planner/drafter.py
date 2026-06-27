#!/usr/bin/env python3
"""Plan drafters.

A drafter turns an analyst request into a *draft* plan. It is the one
probabilistic seam in the planner, so it lives behind a small protocol: the
deterministic gate (which grades the draft) and the loop (which bounds the
revision) never depend on which drafter produced the plan.

Two drafters implement the protocol:

* ``DeterministicDrafter`` — card-grounded keyword routing. It builds plans that
  pass the gate *by construction* (routes only to live sources, uses only
  entities present in the card, draws limits from the card, and only joins on a
  resolvable canonical key). It is the always-available default and fallback.
* ``OpenAICompatibleDrafter`` (in ``llm_drafter.py``) — the hybrid LLM path.

The deterministic drafter records its source-selection rationale (§3.1), avoids
redundant sub-questions and covers each live-relevant source (§3.2), marks
unsupported parts without fabricating (§3.3), and states assumptions for
ambiguity (§3.4).
"""

from __future__ import annotations

import re
from typing import Protocol

from .cards import SourceCardView
from .discovery import LiveSourceView
from .join_keys import resolve_join_key
from .schema import (
    JoinDeclaration,
    Limits,
    Plan,
    SubQuestion,
    UnsupportedPart,
)

_STOPWORDS = frozenset(
    """a an and are as at be by for from has have in into is it its of on or that the
    their to was were what which who whom with you your they them then this these those
    one more most can could may appear appears used use uses level over particular""".split()
)


class PlanDrafter(Protocol):
    """Produces a draft plan; the gate decides whether it ships."""

    def draft(
        self,
        request: str,
        cards: dict[str, SourceCardView],
        live_view: LiveSourceView,
        feedback: list[str] | None = None,
    ) -> Plan: ...


# -- tokenisation helpers ---------------------------------------------------


def _split_identifier(name: str) -> list[str]:
    """Split CamelCase / SCREAMING_SNAKE identifiers into lowercase words."""
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
    spaced = spaced.replace("_", " ")
    return [w.lower() for w in spaced.split() if w]


def _tokens(text: str) -> set[str]:
    raw = re.findall(r"[a-zA-Z][a-zA-Z0-9]+", text.lower())
    out: set[str] = set()
    for w in raw:
        if w in _STOPWORDS or len(w) < 3:
            continue
        out.add(w)
        if w.endswith("s") and len(w) > 3:
            out.add(w[:-1])  # crude singularisation
    return out


def _concept_index(card: SourceCardView) -> dict[str, set[str]]:
    """Map a concept token -> the set of card entities (labels/rels) it evokes."""
    index: dict[str, set[str]] = {}

    def add(token: str, entity: str) -> None:
        if token in _STOPWORDS or len(token) < 3:
            return
        index.setdefault(token, set()).add(entity)
        if token.endswith("s") and len(token) > 3:
            index.setdefault(token[:-1], set()).add(entity)

    for label in card.node_labels:
        for tok in _split_identifier(label):
            add(tok, label)
    for rel in card.relationship_types:
        for tok in _split_identifier(rel):
            add(tok, rel)

    glosses = card.entity_descriptions or {}
    for kind in ("nodes", "relationships"):
        for entity, text in (glosses.get(kind) or {}).items():
            if entity not in card.node_labels and entity not in card.relationship_types:
                continue
            for tok in _tokens(text):
                add(tok, entity)
    return index


def _match_card(request_tokens: set[str], card: SourceCardView) -> tuple[int, list[str]]:
    """Return (score, matched_entities) for a card against the request tokens."""
    index = _concept_index(card)
    matched: set[str] = set()
    hit_tokens = 0
    for tok in request_tokens:
        entities = index.get(tok)
        if entities:
            hit_tokens += 1
            matched.update(entities)
    return hit_tokens, sorted(matched)


class DeterministicDrafter:
    """Card-grounded, rule-based drafter that produces gate-valid plans."""

    def draft(
        self,
        request: str,
        cards: dict[str, SourceCardView],
        live_view: LiveSourceView,
        feedback: list[str] | None = None,
    ) -> Plan:
        request_tokens = _tokens(request)
        plan = Plan(request=request)
        rationale_parts: list[str] = []
        selected_live: list[str] = []

        # Score every source; route to the live ones, flag the down ones.
        scored = {ds: _match_card(request_tokens, card) for ds, card in cards.items()}
        relevant = sorted(
            (ds for ds, (score, _ents) in scored.items() if score > 0),
            key=lambda ds: (-scored[ds][0], ds),
        )

        for ds in relevant:
            score, entities = scored[ds]
            card = cards[ds]
            # Keep only entities truly present in the card (defensive).
            entities = [e for e in entities if card.has_entity(e)]
            if not entities:
                entities = card.expected_probe_labels()[:1]

            if not live_view.is_live(ds):
                reason = "source not live"
                live = live_view.get(ds)
                if live and live.reason:
                    reason = live.reason
                plan.unsupported.append(
                    UnsupportedPart(
                        description=f"Part of the request needs {card.provenance.get('source_name', ds)} ({ds}).",
                        reason=f"{ds} is not live: {reason}",
                    )
                )
                plan.partial = True
                rationale_parts.append(f"{ds} matched but is down (score={score})")
                continue

            sub = SubQuestion(
                id=f"q{len(plan.sub_questions) + 1}",
                source=ds,
                text=f"In {ds}, identify {', '.join(entities)} relevant to: {request}",
                entities=entities,
                limits=Limits(**card.limits()),
                rationale=(
                    f"{ds} card covers {entities} (matched {score} request term(s))"
                ),
            )
            plan.sub_questions.append(sub)
            selected_live.append(ds)
            rationale_parts.append(f"routed to {ds} for {entities}")

        # Cross-source join: only on a resolvable canonical key between two live
        # selected sources.
        if len(selected_live) >= 2:
            for i in range(len(selected_live)):
                for j in range(i + 1, len(selected_live)):
                    a, b = selected_live[i], selected_live[j]
                    key = resolve_join_key(cards[a], cards[b])
                    if key is None:
                        continue
                    plan.joins.append(
                        JoinDeclaration(key=key.name, sources=[a, b], on=key.description)
                    )
                    join_sources = {a, b}
                    plan.sub_questions = [
                        SubQuestion(
                            id=sq.id, source=sq.source, text=sq.text,
                            entities=sq.entities, limits=sq.limits,
                            join_key=key.name if sq.source in join_sources else sq.join_key,
                            rationale=sq.rationale,
                        )
                        for sq in plan.sub_questions
                    ]

        # Nothing matched at all: honestly mark the whole request unsupported.
        if not plan.sub_questions and not plan.unsupported:
            plan.unsupported.append(
                UnsupportedPart(
                    description=request,
                    reason="no live source's schema covers this request",
                )
            )
            plan.partial = True
            rationale_parts.append("no source matched the request terms")

        # Ambiguity signal: a request with no clear entity terms was routed on a
        # best-effort fallback.
        if plan.sub_questions and not request_tokens:
            plan.assumptions.append(
                "request had no specific entity terms; routed to the best-matching live source(s)"
            )

        if feedback:
            plan.assumptions.append(
                "revised after gate feedback: " + "; ".join(feedback[:3])
            )

        plan.rationale = "; ".join(rationale_parts) if rationale_parts else "no routing performed"
        return plan
