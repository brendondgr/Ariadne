#!/usr/bin/env python3

from __future__ import annotations

from utils.planner.drafter import DeterministicDrafter
from utils.planner.gate import evaluate
from utils.planner.tests._fixtures import load_fixture_cards, make_live_view

CARDS = load_fixture_cards()
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


def test_feedback_recorded_in_assumptions() -> None:
    drafter = DeterministicDrafter()
    view = make_live_view()
    plan = drafter.draft(DEMO, CARDS, view, feedback=["sub-question q1: bad limits"])
    assert any("gate feedback" in a for a in plan.assumptions)
