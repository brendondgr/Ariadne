#!/usr/bin/env python3
"""The intent form and its renderer.

Two properties are under test and they are not the same property. The first is
that a filled form renders to a sentence built entirely from the card's own
words — checked here. The second is that the sentence retrieves what the gold
question retrieves, which no unit test can assert because it needs the graphs;
that is `scripts/rewrite_roundtrip.py`, and its result is recorded in the
experiment.
"""

from __future__ import annotations

import pytest

from utils.planner.canonical import (
    DIR_IN,
    DIR_OUT,
    MODE_COUNT,
    MODE_DESCRIBE,
    MODE_ENUMERATE,
    SLOT_ANCHORS,
    SLOT_RELATION,
    FormError,
    IntentForm,
    _pluralise,
    exclusive_source_words,
    form_from_slot_gold,
    label_phrase,
    relation_gloss,
    relation_phrase,
    render,
    render_for,
    source_phrase,
    verb_for,
)
from utils.planner.tests._fixtures import fixture_card, load_fixture_cards

CARDS = load_fixture_cards()
ATTACK = fixture_card("attack")
CAPEC = fixture_card("capec")


# -- the form itself --------------------------------------------------------


def test_form_roundtrips_through_a_dict() -> None:
    form = IntentForm(
        anchors=("T1047",),
        anchor_labels=("Technique",),
        target_labels=("Mitigation",),
        relation="MITIGATES",
        direction=DIR_IN,
        mode=MODE_ENUMERATE,
        datasets=("attack",),
    )
    assert IntentForm.from_dict(form.to_dict()) == form


def test_unbound_is_deduped_and_slot_ordered() -> None:
    form = IntentForm(anchors=("T1047",)).with_unbound(SLOT_RELATION, SLOT_ANCHORS)
    assert form.unbound == (SLOT_ANCHORS, SLOT_RELATION)
    assert form.with_unbound(SLOT_RELATION).unbound == (SLOT_ANCHORS, SLOT_RELATION)


def test_with_unbound_ignores_a_name_that_is_not_a_slot() -> None:
    assert IntentForm().with_unbound("wishful").unbound == ()


def test_a_form_with_an_outstanding_slot_is_not_bound() -> None:
    assert IntentForm(anchors=("T1047",)).is_bound
    assert not IntentForm(anchors=("T1047",)).with_unbound(SLOT_RELATION).is_bound
    assert not IntentForm().is_bound


# -- card vocabulary --------------------------------------------------------


def test_label_and_relation_phrases_come_from_the_identifier() -> None:
    assert label_phrase(ATTACK, "SubTechnique") == "sub technique"
    assert label_phrase(ATTACK, "SubTechnique", plural=True) == "sub techniques"
    assert relation_phrase(CAPEC, "EXPLOITS_WEAKNESS") == "exploits weakness"


@pytest.mark.parametrize(
    ("word", "expected"),
    [("entry", "entries"), ("technique", "techniques"), ("class", "classes"),
     ("box", "boxes"), ("day", "days")],
)
def test_pluralise(word: str, expected: str) -> None:
    assert _pluralise(word) == expected


def test_relation_gloss_reads_the_card_and_is_absent_when_undeclared() -> None:
    assert relation_gloss(ATTACK, "NOT_A_RELATION") == ""


def test_a_source_is_named_only_in_words_no_other_source_claims() -> None:
    """Two cards both named "MITRE X" must not both score on ``mitre``."""
    cards = {
        "attack": _renamed(ATTACK, "MITRE ATT&CK"),
        "capec": _renamed(CAPEC, "MITRE CAPEC"),
    }
    exclusive = exclusive_source_words(cards)
    assert "mitre" not in exclusive["attack"]
    assert "mitre" not in exclusive["capec"]
    assert source_phrase(cards["attack"], cards) == "ATT&CK"
    assert source_phrase(cards["capec"], cards) == "CAPEC"


def test_a_lone_source_keeps_its_whole_name() -> None:
    only = {"attack": _renamed(ATTACK, "MITRE ATT&CK")}
    assert source_phrase(only["attack"], only) == "MITRE ATT&CK"


def _renamed(card, name: str):
    from dataclasses import replace

    return replace(card, provenance={**(card.provenance or {}), "source_name": name})


# -- rendering, per mode and per relation -----------------------------------


def test_describe_renders_the_anchor_with_its_label() -> None:
    form = IntentForm(
        anchors=("T1047",), anchor_labels=("Technique",), mode=MODE_DESCRIBE,
        datasets=("attack",),
    )
    assert render(form, CARDS) == "In ATT&CK Enterprise, describe technique T1047."


def test_an_unlabelled_anchor_renders_bare() -> None:
    """An invented id must not be dressed up as a Technique by the renderer."""
    form = IntentForm(anchors=("T9999",), mode=MODE_DESCRIBE, datasets=("attack",))
    assert render(form, CARDS) == "In ATT&CK Enterprise, describe T9999."


def test_enumerate_with_an_inbound_relation_puts_the_targets_first() -> None:
    form = IntentForm(
        anchors=("T1047",), anchor_labels=("Technique",), target_labels=("Mitigation",),
        relation="MITIGATES", direction=DIR_IN, mode=MODE_ENUMERATE, datasets=("attack",),
    )
    assert render(form, CARDS) == (
        "In ATT&CK Enterprise, give the mitigations that mitigates technique T1047."
    )


def test_enumerate_with_an_outbound_relation_puts_the_anchor_first() -> None:
    form = IntentForm(
        anchors=("TA0001",), anchor_labels=("Tactic",), target_labels=("Technique",),
        relation="HAS_TECHNIQUE", direction=DIR_OUT, mode=MODE_ENUMERATE,
        datasets=("attack",),
    )
    assert render(form, CARDS) == (
        "In ATT&CK Enterprise, give the techniques that tactic TA0001 has technique."
    )


def test_count_uses_a_counting_verb() -> None:
    form = IntentForm(
        anchors=("T1047",), anchor_labels=("Technique",), target_labels=("Mitigation",),
        relation="MITIGATES", direction=DIR_IN, mode=MODE_COUNT, datasets=("attack",),
    )
    assert render(form, CARDS).startswith(f"In ATT&CK Enterprise, {verb_for(MODE_COUNT, CARDS)} the mitigations")


def test_a_relation_marked_unbound_is_not_emitted() -> None:
    """The gold names HAS_TECHNIQUE for a Group; this catalogue runs it from a
    Tactic. Emitting it widened the question to every technique in ATT&CK."""
    form = IntentForm(
        anchors=("G0016",), anchor_labels=("Group",), target_labels=("Technique",),
        relation="HAS_TECHNIQUE", mode=MODE_ENUMERATE, datasets=("attack",),
    ).with_unbound(SLOT_RELATION)
    rendered = render(form, CARDS)
    assert "has technique" not in rendered
    assert rendered == "In ATT&CK Enterprise, give the techniques for group G0016."


def test_a_relation_the_card_does_not_declare_is_not_emitted() -> None:
    form = IntentForm(
        anchors=("G0016",), anchor_labels=("Group",), target_labels=("Technique",),
        relation="INVENTED", mode=MODE_ENUMERATE, datasets=("attack",),
    )
    assert "invented" not in render(form, CARDS).lower()


def test_a_scan_renders_without_an_anchor() -> None:
    form = IntentForm(target_labels=("Tactic",), mode=MODE_ENUMERATE, datasets=("attack",))
    assert render(form, CARDS) == "In ATT&CK Enterprise, list the tactics."


def test_a_federated_form_renders_one_sentence_per_source_in_order() -> None:
    form = IntentForm(
        anchors=("CAPEC-555",), anchor_labels=("AttackPattern",),
        mode=MODE_DESCRIBE, datasets=("capec", "attack"),
    )
    rendered = render(form, CARDS)
    assert rendered.index("In CAPEC,") < rendered.index("In ATT&CK Enterprise,")


# -- what the renderer refuses to do ----------------------------------------


def test_a_form_with_neither_anchor_nor_target_will_not_render() -> None:
    form = IntentForm(mode=MODE_ENUMERATE, datasets=("attack",))
    with pytest.raises(FormError):
        render(form, CARDS)


def test_an_unbound_dataset_blocks_rendering() -> None:
    form = IntentForm(anchors=("T1047",), datasets=())
    with pytest.raises(FormError):
        render(form, CARDS)


def test_an_unknown_mode_is_an_error_not_a_default() -> None:
    form = IntentForm(anchors=("T1047",), mode="speculate", datasets=("attack",))
    with pytest.raises(FormError):
        render_for(form, ATTACK, CARDS)


# -- the renderer's own vocabulary ------------------------------------------


def test_the_describe_verb_avoids_a_word_that_routes() -> None:
    """A verb that appears in a card's gloss is that catalogue's vocabulary.

    In the live cards, CAPEC's ``AttackPattern`` gloss opens "A CAPEC attack
    pattern ... describing", so the word `describe` scores CAPEC a gloss hit and
    an ATT&CK lookup drags 558 attack patterns in behind it. The fixture cards
    have shorter glosses and do not collide, so the collision is constructed
    here — the point is the mechanism, not which word happens to lose today.
    """
    assert verb_for(MODE_DESCRIBE, None) == "describe"
    assert verb_for(MODE_DESCRIBE, CARDS) == "describe"

    from dataclasses import replace

    wordy = replace(
        CAPEC,
        entity_descriptions={
            **(CAPEC.entity_descriptions or {}),
            "nodes": {"AttackPattern": "A pattern describing an attack."},
        },
    )
    assert verb_for(MODE_DESCRIBE, {"attack": ATTACK, "capec": wordy}) != "describe"


def test_a_single_source_sentence_does_not_read_as_cross_source() -> None:
    from utils.planner.intent import DeterministicIntentClassifier, Intent

    form = IntentForm(
        anchors=("G0016",), anchor_labels=("Group",), target_labels=("Technique",),
        mode=MODE_ENUMERATE, datasets=("attack",),
    )
    reading = DeterministicIntentClassifier().classify(render(form, CARDS), CARDS)
    assert reading.label != Intent.CORRELATION


def test_a_sentence_with_an_anchor_does_not_read_as_a_bulk_scan() -> None:
    from utils.planner.intent import asks_for_bulk_scan

    form = IntentForm(
        anchors=("CAPEC-98",), anchor_labels=("AttackPattern",),
        target_labels=("AttackPattern",), mode=MODE_ENUMERATE, datasets=("capec",),
    )
    assert not asks_for_bulk_scan(render(form, CARDS))


# -- the understanding-gold -------------------------------------------------


def _registry(triples):
    """A minimal stand-in for the schema registry: one dataset, given triples."""

    class _Schema:
        def facet_exists(self, anchor, rel, direction, neighbour=None):
            for source, r, target in triples:
                if r != rel:
                    continue
                if direction == DIR_OUT and source == anchor and neighbour in (None, target):
                    return True
                if direction == DIR_IN and target == anchor and neighbour in (None, source):
                    return True
            return False

        def label_facets(self, label):
            class _F:
                def __init__(self, rel_type, direction, neighbour_label):
                    self.rel_type = rel_type
                    self.direction = direction
                    self.neighbour_label = neighbour_label

            out = []
            for source, rel, target in triples:
                if source == label:
                    out.append(_F(rel, DIR_OUT, target))
                if target == label:
                    out.append(_F(rel, DIR_IN, source))
            return tuple(out)

    class _Registry:
        def dataset(self, name):
            return _Schema()

    return _Registry()


ATTACK_TRIPLES = [
    ("Mitigation", "MITIGATES", "Technique"),
    ("Tactic", "HAS_TECHNIQUE", "Technique"),
    ("Group", "USES", "Technique"),
]


def test_slot_gold_direction_is_read_from_the_declared_endpoints() -> None:
    form = form_from_slot_gold(
        {
            "case_id": "A-MIT-01", "bank": "attack", "anchors": ["T1047"],
            "anchor_labels": ["Technique"], "target_labels": ["Mitigation"],
            "relation": "MITIGATES", "template": "technique_mitigations",
        },
        registry=_registry(ATTACK_TRIPLES),
    )
    assert form.direction == DIR_IN
    assert form.mode == MODE_ENUMERATE
    assert form.datasets == ("attack",)
    assert form.unbound == ()


def test_slot_gold_marks_a_relation_the_anchor_does_not_carry() -> None:
    form = form_from_slot_gold(
        {
            "case_id": "A-GRP-01", "bank": "attack", "anchors": ["G0016"],
            "anchor_labels": ["Group"], "target_labels": ["Technique"],
            "relation": "HAS_TECHNIQUE", "template": "group_techniques",
        },
        registry=_registry(ATTACK_TRIPLES),
    )
    assert form.direction is None
    assert form.unbound == (SLOT_RELATION,)


def test_slot_gold_leaves_an_unknown_anchor_label_unbound() -> None:
    form = form_from_slot_gold(
        {
            "case_id": "A-NEG-01", "bank": "attack", "anchors": ["T9999"],
            "anchor_labels": [], "target_labels": [], "relation": None,
            "template": "describe",
        },
        registry=_registry(ATTACK_TRIPLES),
    )
    assert form.anchor_labels == ()
    assert "anchor_labels" in form.unbound
    assert form.mode == MODE_DESCRIBE


def test_slot_gold_reads_the_federated_bank_as_two_datasets_in_hop_order() -> None:
    form = form_from_slot_gold(
        {
            "case_id": "F-CTM-01", "bank": "federated", "anchors": ["CAPEC-150"],
            "anchor_labels": ["AttackPattern"], "target_labels": [], "relation": None,
            "template": "",
        },
        registry=_registry([]),
    )
    assert form.datasets == ("capec", "attack")


def test_slot_gold_records_where_every_slot_came_from() -> None:
    form = form_from_slot_gold(
        {
            "case_id": "A-MIT-01", "bank": "attack", "anchors": ["T1047"],
            "anchor_labels": ["Technique"], "target_labels": ["Mitigation"],
            "relation": "MITIGATES", "relation_source": "matched from the template name",
            "template": "technique_mitigations",
        },
        registry=_registry(ATTACK_TRIPLES),
    )
    assert form.sources["relation"] == "matched from the template name"
    assert form.sources["mode"] == "template:technique_mitigations"
    assert form.sources["datasets"] == "bank:attack"
