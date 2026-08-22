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
from .intent import Intent, IntentClassification, mentions_entity_id
from .join_keys import CANONICAL_JOIN_KEYS, resolve_join_key
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
        intent: IntentClassification | None = None,
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


# A gloss token shared by more than this many entities is too generic to route
# on (e.g. "attack"/"pattern" appear in most CAPEC glosses), so it is ignored.
_MAX_GLOSS_FANOUT = 2


def _concept_indexes(card: SourceCardView) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Build (identifier_index, gloss_index) mapping token -> card entities.

    The identifier index comes from label/relationship names and is the precise
    routing signal; the gloss index comes from human descriptions and is only a
    weak hint used for distinctive tokens.
    """
    id_index: dict[str, set[str]] = {}
    gloss_index: dict[str, set[str]] = {}

    def add(index: dict[str, set[str]], token: str, entity: str) -> None:
        if token in _STOPWORDS or len(token) < 3:
            return
        index.setdefault(token, set()).add(entity)
        if token.endswith("s") and len(token) > 3:
            index.setdefault(token[:-1], set()).add(entity)

    for label in card.node_labels:
        for tok in _split_identifier(label):
            add(id_index, tok, label)
    for rel in card.relationship_types:
        for tok in _split_identifier(rel):
            add(id_index, tok, rel)

    glosses = card.entity_descriptions or {}
    for kind in ("nodes", "relationships"):
        for entity, text in (glosses.get(kind) or {}).items():
            if entity not in card.node_labels and entity not in card.relationship_types:
                continue
            for tok in _tokens(text):
                add(gloss_index, tok, entity)
    return id_index, gloss_index


def _source_name_tokens(dataset: str, card: SourceCardView) -> set[str]:
    """Tokens that *name* this source: its dataset key and its source_name words.

    A source's own name is the strongest routing signal a request can carry, and
    it must not count for anybody else. "What mitigations does ATT&CK list for
    T1047?" contributes ``att`` (the ampersand splits the token), which no label
    in either catalogue contains — so before this the word ATT&CK was worth
    nothing to ATT&CK, the question scored 1 to CAPEC's 2, and a purely ATT&CK
    question pulled in CAPEC.
    """
    words = {dataset.lower()}
    name = str((card.provenance or {}).get("source_name") or "")
    for word in _split_identifier(name.replace("&", " ")):
        if len(word) >= 3:
            words.add(word)
    return words


def _distinctive_name_tokens(
    cards: dict[str, SourceCardView],
) -> dict[str, set[str]]:
    """Per-source name tokens, minus any that another live card uses as a label.

    ``attack`` is the dataset key for ATT&CK *and* a word inside CAPEC's
    ``AttackPattern`` label, so it names neither: "attack patterns and their
    weaknesses" is CAPEC vocabulary and must not be read as a reference to
    ATT&CK. ``att`` and ``capec`` appear in no label anywhere and do name their
    sources. The test is structural -- does another live card use this word in
    an identifier -- rather than a list of words to distrust.
    """
    indexes = {ds: _concept_indexes(card)[0] for ds, card in cards.items()}
    out: dict[str, set[str]] = {}
    for ds, card in cards.items():
        elsewhere: set[str] = set()
        for other, index in indexes.items():
            if other != ds:
                elsewhere |= set(index)
        out[ds] = {
            w for w in _source_name_tokens(ds, card) - elsewhere
            if w not in _STOPWORDS
        }
    return out


def _match_card(
    request_tokens: set[str],
    card: SourceCardView,
    *,
    claimed: dict[str, set[str]] | None = None,
    dataset: str | None = None,
) -> tuple[int, int, list[str], set[str]]:
    """Return (id_hits, gloss_hits, matched_entities, matched_tokens) for a card.

    ``id_hits`` counts request tokens that match an actual node-label or
    relationship-type **name**; ``gloss_hits`` counts tokens that only match a
    human description (and map to a small, specific entity set).

    ``claimed`` maps each live dataset to the tokens that name it. A token
    naming some *other* live source is discarded here rather than counted: it is
    that source's evidence, not this one's.

    ``matched_tokens`` is returned so the caller can compare sources by *which*
    tokens they matched and not merely how many, which is what
    :func:`_select_sources` needs.
    """
    id_index, gloss_index = _concept_indexes(card)
    matched: set[str] = set()
    tokens: set[str] = set()

    def belongs_elsewhere(tok: str) -> bool:
        if not claimed:
            return False
        owners = {ds for ds, words in claimed.items() if tok in words}
        return bool(owners) and dataset not in owners

    id_hits = 0
    for tok in request_tokens:
        if belongs_elsewhere(tok):
            continue
        entities = id_index.get(tok)
        if entities:
            id_hits += 1
            tokens.add(tok)
            matched.update(entities)
    gloss_hits = 0
    for tok in request_tokens:
        if tok in id_index or belongs_elsewhere(tok):
            continue
        entities = gloss_index.get(tok)
        if entities and len(entities) <= _MAX_GLOSS_FANOUT:
            gloss_hits += 1
            tokens.add(tok)
            matched.update(entities)
    # Naming the source is itself an identifier-strength hit, even when no label
    # happens to contain the word.
    if claimed and dataset:
        for tok in request_tokens & claimed.get(dataset, set()):
            if tok not in tokens:
                id_hits += 1
                tokens.add(tok)
    return id_hits, gloss_hits, sorted(matched), tokens


def _select_sources(scored: dict[str, tuple[int, int, list[str], set[str]]]) -> set[str]:
    """Which sources a request is actually about.

    The rule until 2026-08-22 was ``id_hits > 0`` for every card independently:
    an absolute threshold with no comparison between sources. With one Neo4j
    source and one Gremlin source that was adequate, because their vocabularies
    barely overlap. Add a customer graph -- 72 labels and 779 property names of
    ordinary IT English -- and a single shared, generic word drags in an entire
    catalogue: **80 of 117 identity questions routed to ATT&CK, almost always on
    the word "group"** matching ATT&CK's ``Group`` label. The catalogue then
    contributed nothing but volume, and turned abstentions into false answers
    (EXP-2026-08-013: unanswerable 1.000 -> 0.167, one question returning 558
    CAPEC records beside the single identity record that was the whole answer).

    So a secondary source must bring evidence the leader does not already have.
    The leader is whichever source matched the most request tokens; any other
    source is selected only if it matched a token the leader did not. A source
    whose entire case is a word the leader also matches has said nothing to
    distinguish itself and is not selected.

    This is strictly better on the two-catalogue configuration too: it drops
    CAPEC from the eight "What mitigations does ATT&CK list for T1047?"
    questions and from ``A-CMP-ATT-02``, which are ATT&CK questions that were
    pulling in CAPEC on the shared word "mitigation". Across the 120 golden
    entries no question loses the source it is about.
    """
    live = {ds: tokens for ds, (id_hits, _g, _e, tokens) in scored.items() if id_hits > 0}
    if not live:
        return set()
    # Ties broken by name so the selection is deterministic, never by dict order.
    leader = max(live, key=lambda ds: (len(live[ds]), ds))
    keep = {leader}
    for ds, tokens in live.items():
        if ds != leader and (tokens - live[leader]):
            keep.add(ds)
    return keep


class DeterministicDrafter:
    """Card-grounded, rule-based drafter that produces gate-valid plans."""

    def draft(
        self,
        request: str,
        cards: dict[str, SourceCardView],
        live_view: LiveSourceView,
        feedback: list[str] | None = None,
        intent: IntentClassification | None = None,
    ) -> Plan:
        request_tokens = _tokens(request)
        plan = Plan(request=request)
        rationale_parts: list[str] = []
        selected_live: list[str] = []
        if intent is not None:
            rationale_parts.append(f"intent={intent.label}")

        # Score every source, then select comparatively. A lone gloss match is
        # still too weak on its own; on top of that, a source must now bring a
        # token the best-matching source did not (see `_select_sources`).
        claimed = _distinctive_name_tokens(cards)
        scored = {
            ds: _match_card(request_tokens, card, claimed=claimed, dataset=ds)
            for ds, card in cards.items()
        }
        selected = _select_sources(scored)
        relevant = sorted(
            selected, key=lambda ds: (-scored[ds][0], -scored[ds][1], ds)
        )
        shed = sorted(
            ds for ds, (id_hits, _g, _e, _t) in scored.items()
            if id_hits > 0 and ds not in selected
        )
        if shed:
            rationale_parts.append(
                "not selected (no evidence beyond the leading source): " + ", ".join(shed)
            )

        for ds in relevant:
            id_hits, gloss_hits, entities, _tokens_matched = scored[ds]
            score = id_hits + gloss_hits
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

        # Correlation intent: the analyst wants a cross-source answer but keyword
        # routing selected only one side. Pull in the declared join partner (when
        # live and card-valid) so the join below can close, instead of shipping a
        # cross-source question single-sourced. The gate still validates the added
        # sub-question, so this only ever proposes a partner it could route anyway.
        if (
            intent is not None
            and intent.label == Intent.CORRELATION
            and len(selected_live) == 1
        ):
            selected = selected_live[0]
            for key in CANONICAL_JOIN_KEYS:
                if key.endpoint_for(selected) is None:
                    continue
                partner_ep = next(e for e in key.endpoints if e.dataset != selected)
                partner = partner_ep.dataset
                partner_card = cards.get(partner)
                if (
                    partner in selected_live
                    or not live_view.is_live(partner)
                    or partner_card is None
                    or resolve_join_key(cards[selected], partner_card) is None
                ):
                    continue
                entities = [lbl for lbl in partner_ep.labels if partner_card.has_label(lbl)]
                if not entities:
                    continue
                plan.sub_questions.append(
                    SubQuestion(
                        id=f"q{len(plan.sub_questions) + 1}",
                        source=partner,
                        text=f"In {partner}, identify {', '.join(entities)} relevant to: {request}",
                        entities=entities,
                        limits=Limits(**partner_card.limits()),
                        rationale=f"{partner} pulled in to close the {key.name} join (correlation intent)",
                    )
                )
                selected_live.append(partner)
                rationale_parts.append(f"correlation intent pulled in {partner} to close {key.name}")
                plan.assumptions.append(
                    f"correlation intent: added {partner} to close the {key.name} join"
                )

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

        # Definitional rescue: a "what is X" / "define X" question names an
        # entity by its human name, which is not a label token, so the keyword
        # router above selected nothing. Route a join-free name-lookup
        # sub-question to every live source so the specialist's name-dossier can
        # resolve the entity by name (the id-less analogue of a seeded lookup).
        # It fires only on this dead end, so it never changes a plan the keyword
        # router could already build.
        # Prefer the classified intent when the planner supplied one, so the
        # classifier and this path agree; fall back to the specialists' heuristic
        # when drafting standalone (no intent passed). The rescue fires for a
        # definitional (by-name) question OR any in-scope intent that names a
        # concrete entity id (e.g. a traversal "up from CAPEC-16") — routing a
        # resolve-by-name/id lookup the keyword router missed. An off-domain
        # request (unsupported, no id) is left honestly unrouted.
        if intent is not None:
            should_rescue = intent.label == Intent.DEFINITIONAL or (
                intent.label != Intent.UNSUPPORTED and mentions_entity_id(request)
            )
        else:
            # Standalone (no intent supplied): the local definitional heuristic.
            # Lazy import keeps drafter import-light and avoids any planner
            # submodule import-order surprises.
            from utils.planner.intent import is_definitional_request

            should_rescue = is_definitional_request(request)

        if not plan.sub_questions and should_rescue:
            for ds in sorted(cards):
                if not live_view.is_live(ds):
                    continue
                card = cards[ds]
                probe = [e for e in card.expected_probe_labels()[:1] if e]
                if not probe:
                    continue
                plan.sub_questions.append(
                    SubQuestion(
                        id=f"q{len(plan.sub_questions) + 1}",
                        source=ds,
                        text=request,
                        entities=probe,
                        limits=Limits(**card.limits()),
                        rationale=(
                            f"{ds} name lookup for a definitional question "
                            "(no id/label term matched; resolve by entity name)"
                        ),
                    )
                )
                selected_live.append(ds)
                rationale_parts.append(f"definitional name lookup routed to {ds}")
            if plan.sub_questions:
                plan.assumptions.append(
                    "no schema term matched; routed a name lookup for the named "
                    "entity to each live source"
                )

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
