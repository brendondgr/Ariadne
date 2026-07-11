#!/usr/bin/env python3

from __future__ import annotations

from utils.planner.drafter import DeterministicDrafter
from utils.planner.gate import evaluate
from utils.planner.intent import Intent, IntentClassification
from utils.planner.tests._fixtures import load_fixture_cards, make_live_view

CARDS = load_fixture_cards()


def _intent(label: str) -> IntentClassification:
    return IntentClassification(label, 0.9, "test", [], "deterministic")
DEMO = (
    "Which CAPEC patterns related to credential theft map to ATT&CK techniques, "
    "and what mitigations appear for those techniques?"
)


def test_routes_both_sources_and_passes_gate_when_live() -> None:
    drafter = DeterministicDrafter()
    view = make_live_view(live=("attack", "capec"))
    plan = drafter.draft(DEMO, CARDS, view)
    assert plan.target_sources() == {"attack", "capec"}
    # a canonical join binds the two live sources
    assert any(j.key == "attack-technique-id" for j in plan.joins)
    # produced plan is valid by construction
    assert evaluate(plan, CARDS, view).ok, evaluate(plan, CARDS, view).reasons
    assert plan.rationale


def test_marks_down_source_unsupported_and_partial() -> None:
    drafter = DeterministicDrafter()
    view = make_live_view(live=("capec",))  # attack down
    plan = drafter.draft(DEMO, CARDS, view)
    assert plan.target_sources() == {"capec"}
    assert plan.partial
    assert any("attack" in u.reason for u in plan.unsupported)
    # no join (only one live source) and still gate-valid
    assert not plan.joins
    assert evaluate(plan, CARDS, view).ok


def test_out_of_scope_request_marked_unsupported_not_fabricated() -> None:
    drafter = DeterministicDrafter()
    view = make_live_view()
    plan = drafter.draft("List all Kubernetes pods and their CPU usage.", CARDS, view)
    assert not plan.sub_questions  # nothing fabricated
    assert plan.unsupported
    assert plan.partial
    assert evaluate(plan, CARDS, view).ok  # honest, non-degenerate


def test_entities_are_card_valid_and_limits_within_bounds() -> None:
    drafter = DeterministicDrafter()
    view = make_live_view()
    plan = drafter.draft(DEMO, CARDS, view)
    for sq in plan.sub_questions:
        card = CARDS[sq.source]
        assert sq.entities
        assert not card.unknown_entities(sq.entities)
        bounds = card.limits()
        assert sq.limits.max_traversal_depth <= bounds["max_traversal_depth"]
        assert sq.limits.is_present()


def test_single_source_request_routes_one_source() -> None:
    drafter = DeterministicDrafter()
    view = make_live_view()
    plan = drafter.draft("What mitigations exist for ATT&CK techniques?", CARDS, view)
    assert "attack" in plan.target_sources()
    assert evaluate(plan, CARDS, view).ok


def test_gloss_only_match_does_not_select_source() -> None:
    # 'method' hits only CAPEC's AttackPattern *gloss* (no identifier), while the
    # rest hits ATT&CK identifiers. A lone gloss match must not pull CAPEC in or
    # fabricate a cross-source join.
    drafter = DeterministicDrafter()
    view = make_live_view()  # both live
    plan = drafter.draft("Show the method an adversary group uses.", CARDS, view)
    assert plan.target_sources() == {"attack"}
    assert not plan.joins
    assert evaluate(plan, CARDS, view).ok


def test_feedback_recorded_in_assumptions() -> None:
    drafter = DeterministicDrafter()
    view = make_live_view()
    plan = drafter.draft(DEMO, CARDS, view, feedback=["sub-question q1: bad limits"])
    assert any("gate feedback" in a for a in plan.assumptions)


# -- definitional name-lookup bridge ----------------------------------------


def test_definitional_name_question_routes_join_free_name_lookup() -> None:
    # "Phishing" matches no label token, so the keyword router selects nothing;
    # the definitional bridge routes a join-free name lookup to each live source.
    drafter = DeterministicDrafter()
    view = make_live_view(live=("attack", "capec"))
    plan = drafter.draft("What is Phishing?", CARDS, view)
    assert plan.sub_questions  # rescued, not marked unsupported
    assert not plan.joins
    for sq in plan.sub_questions:
        assert sq.join_key is None
        assert "Phishing" in sq.text  # the name reaches the specialist
        assert sq.entities  # gate requires a card entity
    assert evaluate(plan, CARDS, view).ok, evaluate(plan, CARDS, view).reasons


def test_definitional_bridge_only_routes_live_sources() -> None:
    drafter = DeterministicDrafter()
    view = make_live_view(live=("capec",))  # attack down
    plan = drafter.draft("What is Phishing?", CARDS, view)
    assert {sq.source for sq in plan.sub_questions} == {"capec"}
    assert evaluate(plan, CARDS, view).ok


def test_non_definitional_out_of_scope_is_not_bridged() -> None:
    # The bridge must not fire for a non-definitional out-of-scope request.
    drafter = DeterministicDrafter()
    view = make_live_view()
    plan = drafter.draft("List all Kubernetes pods and their CPU usage.", CARDS, view)
    assert not plan.sub_questions
    assert plan.unsupported


# -- intent-driven routing (planner step one changes the plan) --------------


def test_correlation_intent_pulls_in_join_partner() -> None:
    drafter = DeterministicDrafter()
    view = make_live_view()  # both sources live
    request = "attack patterns and their weaknesses"  # capec-only vocabulary

    # Without a correlation intent, keyword routing selects only capec.
    base = drafter.draft(request, CARDS, view)
    assert base.target_sources() == {"capec"}
    assert not base.joins

    # With a correlation intent, the drafter pulls in the live join partner and
    # declares the canonical join — and the result is still gate-valid.
    plan = drafter.draft(request, CARDS, view, intent=_intent(Intent.CORRELATION))
    assert plan.target_sources() == {"capec", "attack"}
    assert any(j.key == "attack-technique-id" for j in plan.joins)
    assert evaluate(plan, CARDS, view).ok, evaluate(plan, CARDS, view).reasons
    assert "intent=correlation" in plan.rationale


def test_correlation_partner_pull_in_respects_liveness() -> None:
    drafter = DeterministicDrafter()
    view = make_live_view(live=("capec",))  # attack is DOWN
    plan = drafter.draft("attack patterns", CARDS, view, intent=_intent(Intent.CORRELATION))
    # The partner is down, so it is not routed and no join is fabricated.
    assert plan.target_sources() == {"capec"}
    assert not plan.joins
    assert evaluate(plan, CARDS, view).ok


def test_definitional_intent_drives_name_lookup() -> None:
    drafter = DeterministicDrafter()
    view = make_live_view()
    request = "Spearphishing"  # a bare name; the heuristic alone would not fire

    base = drafter.draft(request, CARDS, view)  # no intent -> unsupported
    assert not base.sub_questions
    assert base.unsupported

    plan = drafter.draft(request, CARDS, view, intent=_intent(Intent.DEFINITIONAL))
    assert plan.sub_questions  # the classified intent routed a name lookup
    assert evaluate(plan, CARDS, view).ok
