#!/usr/bin/env python3
"""Execute an ``IntentForm`` as a plan, instead of rendering it and parsing it back.

EXP-2026-09-025 (plan Step 6). The rewrite stage fills a form — anchor,
anchor label, relation, direction, target labels, mode, datasets — and until
now handed the *drafter* an English sentence rendered from it, which the
drafter's word-router then parsed into sub-questions again. EXP-2026-09-021
Step 4 measured that round trip breaking 13 T1 answers whose form held the
right identifier and the schema-resolved relation; EXP-2026-09-023 measured
three more on the sealed bank ("attributed to Tonto Team" → ATTRIBUTED_TO).

A form is already what a sub-question needs. This module turns it into one
directly: the anchor's identifier in the text (the specialists' resolve step
reads identifiers off the text, as it does for any hop), the anchor label,
relation and target labels in ``entities`` (which the query builders' ladder
routes on, and which the deterministic gate validates against the card), and
the card's own limits. A second source named by the form is added through the
declared join key exactly as the drafter adds one — never by dataset order.

Nothing here reads a catalogue: labels, relations and join keys come from the
form, the card and the join-key registry. A form the stage could not bind
returns ``None`` and the caller keeps today's path.
"""

from __future__ import annotations

from typing import Any

from .canonical import (
    MODE_DESCRIBE,
    SLOT_ANCHORS,
    SLOT_DATASETS,
    SLOT_RELATION,
    SLOT_TARGET_LABELS,
    IntentForm,
    render_for,
)
from .cards import SourceCardView
from .join_keys import resolve_join_key
from .schema import JoinDeclaration, Limits, Plan, SubQuestion


def _describe_text(form: IntentForm, card: SourceCardView) -> str:
    cited = ", ".join(form.anchors or form.anchor_titles)
    label = form.anchor_labels[0] if form.anchor_labels else ""
    return f"In {card.dataset}, describe {label} {cited}".replace("  ", " ").strip()


def plan_from_form(
    form: IntentForm,
    cards: dict[str, SourceCardView],
    request: str,
) -> Plan | None:
    """The plan a bound form denotes, or ``None`` when the form cannot be executed.

    ``None`` — not a partial plan — whenever a slot the execution needs is
    unbound: the datasets, the anchor, and for a relation question the
    relation and a target label. The caller's fallback is the existing
    render-and-draft path, so a form this refuses is answered exactly as today.
    """
    blocking = {SLOT_DATASETS, SLOT_ANCHORS}
    if form.mode != MODE_DESCRIBE:
        blocking |= {SLOT_RELATION, SLOT_TARGET_LABELS}
    if any(slot in form.unbound for slot in blocking):
        return None
    if not (form.anchors or form.anchor_titles):
        return None
    datasets = [d for d in form.datasets if d in cards]
    if not datasets:
        return None
    primary = datasets[0]
    card = cards[primary]

    anchor_label = next((l for l in form.anchor_labels if card.has_label(l)), None)
    if form.mode == MODE_DESCRIBE or not form.relation:
        entities = [anchor_label] if anchor_label else [e for e in card.expected_probe_labels()[:1] if e]
        text = _describe_text(form, card)
        rationale = "form: describe the bound anchor"
    else:
        if not card.has_relationship(form.relation):
            return None
        targets = [l for l in form.target_labels if card.has_label(l) and l != anchor_label]
        if not targets:
            return None
        entities = ([anchor_label] if anchor_label else []) + [form.relation] + targets
        # The rendered sentence is kept as the sub-question's text: it carries
        # the identifier the specialists resolve on and reads as the record's
        # canonical question. It is no longer *parsed* by anything.
        text = render_for(form, card, cards)
        rationale = f"form: {form.relation} {form.direction or ''} from the bound anchor".strip()

    plan = Plan(request=request)
    plan.sub_questions.append(
        SubQuestion(
            id="q1", source=primary, text=text, entities=entities,
            limits=Limits(**card.limits()), rationale=rationale,
        )
    )
    plan.assumptions.append("planned directly from the rewrite stage's bound form")

    # A second source the form names is reached through the declared join key,
    # the way the drafter reaches it — and not at all when no key binds.
    for partner in datasets[1:]:
        partner_card = cards[partner]
        key = resolve_join_key(card, partner_card)
        if key is None:
            plan.assumptions.append(f"{partner} named by the form but no join key binds it to {primary}; not planned")
            continue
        endpoint = key.endpoint_for(partner)
        partner_entities = [l for l in (endpoint.labels if endpoint else ()) if partner_card.has_label(l)]
        if not partner_entities:
            continue
        plan.sub_questions[0] = SubQuestion(
            **{**_fields(plan.sub_questions[0]), "join_key": key.name}
        )
        plan.sub_questions.append(
            SubQuestion(
                id=f"q{len(plan.sub_questions) + 1}", source=partner,
                text=f"In {partner}, identify {', '.join(partner_entities)} relevant to: {request}",
                entities=partner_entities, limits=Limits(**partner_card.limits()),
                join_key=key.name,
                rationale=f"form: {partner} joined to {primary} on {key.name}",
            )
        )
        plan.joins.append(JoinDeclaration(key=key.name, sources=[primary, partner], on=key.description))
    return plan


def _fields(sq: SubQuestion) -> dict[str, Any]:
    return {
        "id": sq.id, "source": sq.source, "text": sq.text, "entities": list(sq.entities),
        "limits": sq.limits, "join_key": sq.join_key, "rationale": sq.rationale, "hop": sq.hop,
    }
