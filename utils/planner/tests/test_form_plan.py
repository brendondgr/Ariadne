"""A bound form executes as a plan; an unbound one returns None (EXP-2026-09-025, plan Step 6).

Runs on the committed fixture cards (attack + capec) and on a made-up card,
so the mapping is shown to read only the form, the card and the join-key
registry.
"""

from __future__ import annotations

from utils.planner import canonical as c
from utils.planner.cards import SourceCardView
from utils.planner.form_plan import plan_from_form
from utils.planner.gate import evaluate
from utils.planner.tests._fixtures import load_fixture_cards, make_live_view

CARDS = load_fixture_cards()


def _form(**kw) -> c.IntentForm:
    base = dict(anchors=("T1047",), anchor_labels=("Technique",), target_labels=("Mitigation",),
                relation="MITIGATES", direction="in", mode=c.MODE_ENUMERATE, datasets=("attack",))
    base.update(kw)
    return c.IntentForm(**base)


def test_a_relation_form_becomes_one_anchored_relation_sub_question():
    plan = plan_from_form(_form(), CARDS, "How do I defend against T1047?")
    assert plan is not None and len(plan.sub_questions) == 1
    sq = plan.sub_questions[0]
    assert sq.source == "attack"
    assert sq.entities == ["Technique", "MITIGATES", "Mitigation"]
    assert "T1047" in sq.text, "the identifier rides in the text for the resolver"
    assert evaluate(plan, CARDS, make_live_view()).ok


def test_a_describe_form_names_only_the_anchor_label():
    plan = plan_from_form(_form(mode=c.MODE_DESCRIBE, relation=None, target_labels=()), CARDS, "What is T1047?")
    assert plan.sub_questions[0].entities == ["Technique"]
    assert "T1047" in plan.sub_questions[0].text
    assert evaluate(plan, CARDS, make_live_view()).ok


def test_an_unbound_anchor_returns_none():
    assert plan_from_form(_form(anchors=()).with_unbound(c.SLOT_ANCHORS), CARDS, "q") is None


def test_an_unbound_relation_on_an_enumerate_form_returns_none():
    assert plan_from_form(_form(relation=None).with_unbound(c.SLOT_RELATION), CARDS, "q") is None


def test_a_relation_the_card_does_not_declare_returns_none():
    assert plan_from_form(_form(relation="DEFENDS"), CARDS, "q") is None


def test_the_anchor_label_is_not_also_a_target():
    plan = plan_from_form(_form(target_labels=("Technique", "Mitigation")), CARDS, "q")
    assert plan.sub_questions[0].entities == ["Technique", "MITIGATES", "Mitigation"]


def test_a_second_source_is_reached_through_the_declared_join_key():
    form = _form(anchors=("CAPEC-98",), anchor_labels=("AttackPattern",), target_labels=("TaxonomyEntry",),
                 relation="MAPS_TO", direction="out", datasets=("capec", "attack"))
    plan = plan_from_form(form, CARDS, "Which ATT&CK techniques does CAPEC-98 map to?")
    assert [sq.source for sq in plan.sub_questions] == ["capec", "attack"]
    assert plan.joins and plan.joins[0].key == "attack-technique-id"
    assert all(sq.join_key == "attack-technique-id" for sq in plan.sub_questions)
    assert evaluate(plan, CARDS, make_live_view()).ok


def test_a_partner_with_no_join_key_is_named_in_assumptions_not_planned():
    library = SourceCardView.from_card_dict({
        "dataset": "library", "runtime_backend": "neo4j",
        "node_labels": ["Book"], "relationship_types": ["CITES"],
        "node_properties": {"Book": {"title": {}}},
    })
    cards = {**CARDS, "library": library}
    form = _form(datasets=("attack", "library"))
    plan = plan_from_form(form, cards, "q")
    assert [sq.source for sq in plan.sub_questions] == ["attack"]
    assert any("no join key" in a for a in plan.assumptions)


def test_a_form_on_a_card_it_has_never_seen_still_plans():
    library = SourceCardView.from_card_dict({
        "dataset": "library", "runtime_backend": "neo4j",
        "node_labels": ["Book", "Topic"], "relationship_types": ["COVERS"],
        "node_properties": {"Book": {"title": {}}, "Topic": {"name": {}}},
    })
    form = c.IntentForm(anchors=("b1",), anchor_labels=("Book",), target_labels=("Topic",),
                        relation="COVERS", direction="out", mode=c.MODE_ENUMERATE, datasets=("library",))
    plan = plan_from_form(form, {"library": library}, "what does b1 cover")
    assert plan.sub_questions[0].entities == ["Book", "COVERS", "Topic"]
