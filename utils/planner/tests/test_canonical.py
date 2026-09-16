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
    """Both cards own ``Mitigation``, so both have footing and both get a
    sentence, in the form's dataset order — which is the hop order."""
    form = IntentForm(
        anchors=("CAPEC-555",), anchor_labels=("AttackPattern",),
        target_labels=("Mitigation",), mode=MODE_ENUMERATE,
        datasets=("capec", "attack"),
    )
    rendered = render(form, CARDS)
    assert rendered.index("In CAPEC,") < rendered.index("In ATT&CK Enterprise,")


def test_a_source_with_no_footing_in_the_form_gets_no_sentence() -> None:
    """"In ATT&CK, summarise CAPEC-555" is not a question about anything."""
    form = IntentForm(
        anchors=("CAPEC-555",), anchor_labels=("AttackPattern",),
        mode=MODE_DESCRIBE, datasets=("capec", "attack"),
    )
    rendered = render(form, CARDS)
    assert rendered == "In CAPEC, describe attack pattern CAPEC-555."


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


# -- deterministic fill -----------------------------------------------------
#
# These exercise the real name index and schema registry against the canonical
# snapshot, so they are skipped where that snapshot is absent (a fresh clone
# before `--build`). The alternative — a fake index — would test the fake.

import os  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest as _pytest  # noqa: E402

from utils.planner.canonical import deterministic_fill  # noqa: E402
from utils.planner.cards import SourceCardView, load_source_cards  # noqa: E402

_REPO = Path(__file__).resolve().parents[3]
_HAS_SNAPSHOT = (_REPO / "data" / "graphs" / "attack" / "canonical" / "nodes.jsonl").exists()
needs_snapshot = _pytest.mark.skipif(
    not _HAS_SNAPSHOT, reason="needs the canonical snapshot (run main.py --build)"
)


@_pytest.fixture(scope="module")
def live_cards():
    return load_source_cards()


@needs_snapshot
def test_tier0_wording_binds_every_slot(live_cards) -> None:
    form = deterministic_fill(
        "What mitigations does ATT&CK list for T1047 (Windows Management Instrumentation)?",
        live_cards,
    )
    assert form.unbound == ()
    assert form.anchors == ("T1047",)
    assert form.anchor_labels == ("Technique",)
    assert form.target_labels == ("Mitigation",)
    assert form.relation == "MITIGATES"
    assert form.direction == DIR_IN
    assert form.mode == MODE_ENUMERATE
    assert form.datasets == ("attack",)


@needs_snapshot
def test_a_synonym_verb_still_binds_the_relation_through_the_lexicon(live_cards) -> None:
    """"defend against" is not a card word; the gloss stem reaches MITIGATES."""
    form = deterministic_fill("Which ATT&CK mitigations defend against T1047?", live_cards)
    assert form.relation == "MITIGATES"
    assert form.anchors == ("T1047",)


@needs_snapshot
def test_an_exact_name_binds_the_anchor_to_its_identifier(live_cards) -> None:
    """The analyst gave a name; the canonical form cites the id it resolves to.

    That is the point of rewriting into tier-0 form — the resolver's
    highest-authority rung wants an identifier, and a complete-name match is a
    lookup that supplies one. The name is kept for provenance only.
    """
    form = deterministic_fill("What is Phishing?", live_cards)
    assert form.anchors and form.anchors[0].startswith("CAPEC-")
    assert form.anchor_titles == ("Phishing",)
    assert form.sources["anchors"] == "exact-name"


@needs_snapshot
def test_the_anchor_is_bound_by_whichever_source_owns_the_identifier(live_cards) -> None:
    """The question leads with ATT&CK; the anchor it names is CAPEC's."""
    form = deterministic_fill(
        "Which ATT&CK techniques correspond to CAPEC-555?", live_cards
    )
    assert form.anchors == ("CAPEC-555",)
    assert form.datasets[0] == "capec"


@needs_snapshot
def test_a_paraphrased_name_leaves_the_anchor_unbound(live_cards) -> None:
    """The ranked index would answer this. It is deliberately not consulted."""
    form = deterministic_fill(
        "What countermeasures exist against abuse of Windows' built-in "
        "management scripting interface?",
        live_cards,
    )
    assert SLOT_ANCHORS in form.unbound
    assert form.anchors == ()
    assert form.anchor_titles == ()


@needs_snapshot
def test_how_many_reads_as_count(live_cards) -> None:
    assert deterministic_fill("How many mitigations does T1047 have?", live_cards).mode == (
        MODE_COUNT
    )


@needs_snapshot
def test_a_schema_word_is_not_an_exact_name_anchor(live_cards) -> None:
    """"Software" is a complete node name AND a label. It anchors nothing."""
    form = deterministic_fill("List ATT&CK software entries (bounded scan).", live_cards)
    assert form.anchor_titles == ()
    assert form.target_labels == ("Software",)
    assert SLOT_ANCHORS not in form.unbound  # a real scan may have no anchor


@needs_snapshot
def test_an_anchorless_non_scan_is_unbound_not_a_catalogue_dump(live_cards) -> None:
    form = deterministic_fill("What are the mitigations for phishing attacks?", live_cards)
    if not (form.anchors or form.anchor_titles):
        assert SLOT_ANCHORS in form.unbound


@needs_snapshot
def test_source_naming_words_do_not_leak_into_the_target_labels(live_cards) -> None:
    """`att` reaches ATT&CK's `Matrix` gloss; it must not become a target."""
    form = deterministic_fill("What mitigations does ATT&CK list for T1047?", live_cards)
    assert "Matrix" not in form.target_labels


@needs_snapshot
def test_a_relation_the_anchor_does_not_carry_is_reported_unbound(live_cards) -> None:
    form = deterministic_fill("Which techniques does group G0016 use?", live_cards)
    assert SLOT_RELATION in form.unbound
    assert "has technique" not in render(form, live_cards)


@needs_snapshot
def test_the_flags_are_off_by_default() -> None:
    from utils.planner.config import PlannerConfig

    for var in ("ARIADNE_REWRITE", "ARIADNE_REWRITE_MODEL"):
        os.environ.pop(var, None)
    config = PlannerConfig.from_env()
    assert config.rewrite_enabled is False
    assert config.rewrite_model_enabled is False


@needs_snapshot
def test_the_flags_read_the_environment() -> None:
    from utils.planner.config import PlannerConfig

    os.environ["ARIADNE_REWRITE"] = "1"
    os.environ["ARIADNE_REWRITE_MODEL"] = "true"
    try:
        config = PlannerConfig.from_env()
        assert config.rewrite_enabled is True
        assert config.rewrite_model_enabled is True
    finally:
        os.environ.pop("ARIADNE_REWRITE", None)
        os.environ.pop("ARIADNE_REWRITE_MODEL", None)


# -- candidate lists --------------------------------------------------------


def test_relation_and_label_candidates_are_the_whole_card_with_its_glosses() -> None:
    from utils.planner.canonical import candidate_lists

    form = IntentForm(datasets=("attack",)).with_unbound(SLOT_RELATION)
    lists = candidate_lists("anything", form, CARDS, dataset="attack")
    assert [c.value for c in lists.relations] == sorted(ATTACK.relationship_types)
    assert [c.value for c in lists.labels] == sorted(ATTACK.node_labels)
    assert [c.index for c in lists.relations] == list(range(len(lists.relations)))
    assert any(c.gloss for c in lists.relations)


def test_an_index_out_of_range_or_of_the_wrong_type_is_not_a_choice() -> None:
    """A model that returns a *name* has not chosen from the list."""
    from utils.planner.canonical import candidate_lists

    form = IntentForm(datasets=("attack",)).with_unbound(SLOT_RELATION)
    lists = candidate_lists("anything", form, CARDS, dataset="attack")
    assert lists.relation_at(0) is not None
    assert lists.relation_at(len(lists.relations)) is None
    assert lists.relation_at(-1) is None
    assert lists.relation_at("MITIGATES") is None
    assert lists.relation_at(True) is None
    assert lists.relation_at(None) is None


def test_no_anchor_candidates_are_produced_when_the_anchor_is_already_bound() -> None:
    from utils.planner.canonical import candidate_lists

    form = IntentForm(anchors=("T1047",), datasets=("attack",))
    assert candidate_lists("T1047", form, CARDS, dataset="attack").anchors == ()


def test_candidate_lists_for_an_unrouted_form_cover_every_live_source() -> None:
    from utils.planner.canonical import candidate_lists_all

    form = IntentForm().with_unbound(SLOT_ANCHORS, "datasets")
    assert sorted(candidate_lists_all("anything", form, CARDS)) == ["attack", "capec"]


def test_candidate_lists_for_a_routed_form_cover_only_its_sources() -> None:
    from utils.planner.canonical import candidate_lists_all

    form = IntentForm(datasets=("attack",)).with_unbound(SLOT_ANCHORS)
    assert sorted(candidate_lists_all("anything", form, CARDS)) == ["attack"]


@needs_snapshot
def test_anchor_candidates_are_scoped_by_the_anchor_label_not_the_target(live_cards) -> None:
    """Scoping by the target guaranteed the gold anchor could never appear."""
    from utils.planner.canonical import candidate_lists

    form = IntentForm(
        target_labels=("Mitigation",), datasets=("attack",), mode=MODE_ENUMERATE
    ).with_unbound(SLOT_ANCHORS)
    lists = candidate_lists("browser extension persistence", form, live_cards)
    assert lists.anchors
    assert {c.label for c in lists.anchors} != {"Mitigation"}


@needs_snapshot
def test_an_anchor_candidate_carries_enough_to_tell_it_apart(live_cards) -> None:
    from utils.planner.canonical import candidate_lists

    form = IntentForm(datasets=("attack",)).with_unbound(SLOT_ANCHORS)
    lists = candidate_lists(
        "abuse of Windows management instrumentation", form, live_cards
    )
    top = lists.anchors[0]
    assert top.value and top.name and top.label
    assert top.gloss and top.gloss.endswith((".", "!", "?"))


# -- relation derivation from the label pair (EXP-2026-09-015) ---------------


def test_relations_between_pins_a_declared_pair():
    from utils.planner.canonical import relations_between

    rels = relations_between("AttackPattern", "Prerequisite", "capec")
    assert rels == ("HAS_PREREQUISITE",)


def test_relations_between_is_empty_for_an_undeclared_pair():
    from utils.planner.canonical import relations_between

    assert relations_between("AttackPattern", "NoSuchLabel", "capec") == ()


def test_relations_between_needs_both_labels():
    from utils.planner.canonical import relations_between

    assert relations_between("AttackPattern", None, "capec") == ()
    assert relations_between("", "Prerequisite", "capec") == ()


def test_relations_between_is_unknown_dataset_safe():
    from utils.planner.canonical import relations_between

    assert relations_between("AttackPattern", "Prerequisite", "nope") == ()


def test_relations_between_reads_both_directions():
    """The mirror pair resolves to the same relation, read from the other end."""
    from utils.planner.canonical import relations_between

    assert relations_between("Prerequisite", "AttackPattern", "capec") == (
        "HAS_PREREQUISITE",
    )


# -- the requested slots (EXP-2026-09-018 Step 4) ----------------------------
#
# What the plan does not carry: which property the answer must state, and which
# filter it must apply. Both are read from the question's own words against the
# card's declared vocabulary, so the benchmark and the shipped path derive them
# the same way. Extending the plan schema instead would hand the system a
# perfectly-filled slot the live planner does not produce, and the measured gain
# would not transfer (operator decision, 2026-09-11).


def _capec_card():
    from utils.planner.cards import load_source_cards

    cards = load_source_cards("data")
    if "capec" not in cards:
        pytest.skip("generated source cards not built in this checkout")
    return cards


def _live_registry():
    from utils.specialists.schema import get_registry

    return get_registry()


def test_a_property_is_bound_from_the_question_s_own_words() -> None:
    from utils.planner.canonical import requested_slots

    cards = _capec_card()
    slots = requested_slots(
        "Which platforms does the detection analytic AN0307 apply to?",
        ["Analytic"],
        cards["attack"],
        _live_registry(),
    )
    assert slots.property == "x_mitre_platforms"


def test_a_property_word_matches_across_ordinary_inflection() -> None:
    """"describe" is the question's word and ``description`` is the card's."""
    from utils.planner.canonical import requested_slots

    cards = _capec_card()
    slots = requested_slots(
        "What does C0005 describe?", ["Campaign"], cards["attack"], _live_registry()
    )
    assert slots.property == "description"


def test_a_filter_is_bound_from_a_value_the_data_carries() -> None:
    """The question names the value and usually not the field.

    "Which techniques used by APT1 apply to macOS" says ``macOS`` and never says
    ``platform``; 26 of the 27 platform-filtered development questions are that
    shape. So the binding is on the value, and what keeps it from guessing is
    that the value must be one the registry has *observed* on that property.
    """
    from utils.planner.canonical import requested_slots

    cards = _capec_card()
    slots = requested_slots(
        "Which attack patterns at the Meta abstraction level can precede CAPEC-234?",
        ["AttackPattern", "CanFollow", "AttackPattern"],
        cards["capec"],
        _live_registry(),
    )
    assert slots.filter == ("AttackPattern", "Abstraction", "Meta")


def test_a_value_inside_a_hyphenated_name_is_not_a_filter() -> None:
    """``Meta`` inside "Using Meta-characters in E-mail Headers" is a name.

    The default word boundary treats a hyphen as a break, so this bound an
    abstraction-level filter to a question about severity — the only wrong
    binding either bank produced, and it is now zero on both.
    """
    from utils.planner.canonical import requested_slots

    cards = _capec_card()
    slots = requested_slots(
        "Which attack patterns with a typical severity of High is Using "
        "Meta-characters in E-mail Headers to Inject Malicious Payloads, "
        "CAPEC-41, a more specific case of?",
        ["AttackPattern", "ChildOf", "AttackPattern"],
        cards["capec"],
        _live_registry(),
    )
    assert slots.filter is None


def test_a_property_that_restates_the_record_s_kind_is_not_a_filter() -> None:
    """``stix_type`` duplicates the label, so every question matches it.

    31 of the development half's 39 spurious bindings were exactly that, and the
    noise then tripped the ambiguity guard and suppressed 12 real filters too.
    """
    from utils.planner.canonical import requested_slots

    cards = _capec_card()
    slots = requested_slots(
        "Which malware and tools used in campaign C0026 run on Windows?",
        ["Campaign", "USES", "Software"],
        cards["attack"],
        _live_registry(),
    )
    assert slots.filter == ("Software", "x_mitre_platforms", "Windows")


def test_an_unreadable_question_binds_nothing() -> None:
    from utils.planner.canonical import RequestedSlots, requested_slots

    cards = _capec_card()
    slots = requested_slots(
        "Tell me about CAPEC-66.", ["AttackPattern"], cards["capec"], _live_registry()
    )
    assert slots.property is None and slots.filter is None
    assert not RequestedSlots().any_bound()


def test_an_opaque_identifier_is_not_cited_the_name_is(monkeypatch) -> None:
    """A card-backed graph whose ids the resolver cannot read keeps its name.

    Synapse ids are ``node-<hash>``: no rung of the resolver's ladder matches
    them, so a canonical form that cited one would send the specialist a
    string it can only treat as a (non-matching) name. The exact-name lookup
    still binds the anchor — as the title it matched on.
    """
    from utils.planner import canonical
    from utils.specialists.schema import namesearch
    from utils.specialists.schema.namesearch import Candidate

    card = SourceCardView.from_card_dict({
        "dataset": "mnp-cs-03000-r2",
        "runtime_backend": "neo4j",
        "node_labels": ["PolymerType", "MolecularMarker", "Condition"],
        "relationship_types": ["affects_marker", "leads_to"],
        "node_properties": {},
        "safety": {"allowed_edge_patterns": {
            "affects_marker": [["PolymerType", "MolecularMarker"]],
            "leads_to": [["MolecularMarker", "Condition"]],
        }},
        "provenance": {"source_name": "Synapse graph mnp-cs-03000-r2", "id_scheme": "opaque"},
        "entity_descriptions": {"nodes": {}, "relationships": {}},
    })
    cards = {"mnp-cs-03000-r2": card}
    # deterministic_fill imports the lookup locally, so patch its home module.
    monkeypatch.setattr(
        namesearch, "exact_name_matches",
        lambda dataset, question, **_: [
            Candidate(entity_id="node-64deb8c7c15d77a4", label="PolymerType",
                      name="Polystyrene", score=1.0)
        ] if "polystyrene" in question.lower() else [],
    )
    form = deterministic_fill("What molecular markers does Polystyrene affect?", cards)
    assert form.anchors == ()
    assert form.anchor_titles == ("Polystyrene",)
    assert form.anchor_labels == ("PolymerType",)
    assert form.sources["anchors"] == "exact-name"
    # The anchor slot is bound (by title); other slots depend on the schema
    # registry, which has no canonical files for this graph in a unit test.
    assert "anchors" not in form.unbound
    rendered = canonical.render(form, cards)
    assert "Polystyrene" in rendered and "node-64deb8c7c15d77a4" not in rendered
