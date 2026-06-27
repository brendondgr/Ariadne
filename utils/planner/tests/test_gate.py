#!/usr/bin/env python3

from __future__ import annotations

from utils.planner.gate import evaluate
from utils.planner.schema import (
    JoinDeclaration,
    Limits,
    Plan,
    SubQuestion,
    UnsupportedPart,
)
from utils.planner.tests._fixtures import load_fixture_cards, make_live_view

CARDS = load_fixture_cards()
GOOD_LIMITS = Limits(3, 1000, 5000)


def _capec_sq(**over) -> SubQuestion:
    base = dict(
        id="q1", source="capec", text="credential-theft patterns",
        entities=["AttackPattern", "MAPS_TO", "TaxonomyEntry"], limits=GOOD_LIMITS,
        join_key="attack-technique-id",
    )
    base.update(over)
    return SubQuestion(**base)  # type: ignore[arg-type]


def _attack_sq(**over) -> SubQuestion:
    base = dict(
        id="q2", source="attack", text="mitigations for techniques",
        entities=["Technique", "MITIGATES", "Mitigation"], limits=GOOD_LIMITS,
        join_key="attack-technique-id",
    )
    base.update(over)
    return SubQuestion(**base)  # type: ignore[arg-type]


def _good_plan() -> Plan:
    return Plan(
        request="Which CAPEC credential-theft patterns map to ATT&CK techniques and their mitigations?",
        sub_questions=[_capec_sq(), _attack_sq()],
        joins=[JoinDeclaration(key="attack-technique-id", sources=["capec", "attack"])],
        rationale="CAPEC holds attack patterns; ATT&CK holds techniques+mitigations",
    )


# -- accept -----------------------------------------------------------------


def test_good_plan_passes_when_both_live() -> None:
    result = evaluate(_good_plan(), CARDS, make_live_view(live=("attack", "capec")))
    assert result.ok, result.reasons


def test_loose_but_valid_plan_still_passes() -> None:
    # extra assumptions / verbose rationale must not be penalised (not too strict).
    plan = _good_plan()
    plan.assumptions = ["assumed 'credential theft' is a description keyword"]
    plan.rationale = "a long-winded but structurally valid rationale " * 5
    assert evaluate(plan, CARDS, make_live_view()).ok


def test_partial_unsupported_only_plan_passes() -> None:
    # honest "I can't answer" — not degenerate because unsupported is named.
    plan = Plan(
        request="pull from a threat-intel feed",
        unsupported=[UnsupportedPart("threat-intel feed lookup", "no live source holds this")],
        partial=True,
    )
    assert evaluate(plan, CARDS, make_live_view()).ok


# -- reject -----------------------------------------------------------------


def test_dead_source_rejected() -> None:
    plan = _good_plan()
    result = evaluate(plan, CARDS, make_live_view(live=("capec",)))  # attack down
    assert not result.ok
    assert any("attack" in r and "not live" in r for r in result.reasons)


def test_nonexistent_label_rejected() -> None:
    plan = Plan(request="x", sub_questions=[_capec_sq(entities=["GhostLabel"])])
    result = evaluate(plan, CARDS, make_live_view())
    assert not result.ok
    assert any("not in capec card" in r for r in result.reasons)


def test_missing_limits_rejected() -> None:
    plan = Plan(request="x", sub_questions=[_capec_sq(limits=Limits())])
    result = evaluate(plan, CARDS, make_live_view())
    assert not result.ok
    assert any("missing required traversal limits" in r for r in result.reasons)


def test_out_of_bounds_limits_rejected() -> None:
    plan = Plan(request="x", sub_questions=[_capec_sq(limits=Limits(99, 1000, 5000))])
    result = evaluate(plan, CARDS, make_live_view())
    assert not result.ok
    assert any("max_traversal_depth" in r and "exceeds" in r for r in result.reasons)


def test_unknown_source_rejected() -> None:
    plan = Plan(request="x", sub_questions=[_capec_sq(source="mitre_d3fend")])
    result = evaluate(plan, CARDS, make_live_view())
    assert not result.ok
    assert any("unknown source" in r for r in result.reasons)


def test_undeclared_join_key_rejected() -> None:
    plan = Plan(
        request="x",
        sub_questions=[_capec_sq(), _attack_sq()],
        joins=[JoinDeclaration(key="made-up-key", sources=["capec", "attack"])],
    )
    result = evaluate(plan, CARDS, make_live_view())
    assert not result.ok
    assert any("not the canonical bridge" in r or "no declared canonical" in r for r in result.reasons)


def test_join_with_down_source_rejected() -> None:
    plan = Plan(
        request="x",
        sub_questions=[_capec_sq()],
        joins=[JoinDeclaration(key="attack-technique-id", sources=["capec", "attack"])],
    )
    result = evaluate(plan, CARDS, make_live_view(live=("capec",)))
    assert not result.ok
    assert any("join" in r and "attack" in r for r in result.reasons)


def test_empty_entities_rejected() -> None:
    plan = Plan(request="x", sub_questions=[_capec_sq(entities=[])])
    result = evaluate(plan, CARDS, make_live_view())
    assert not result.ok
    assert any("names no graph entity" in r for r in result.reasons)


def test_degenerate_plan_rejected() -> None:
    result = evaluate(Plan(request="x"), CARDS, make_live_view())
    assert not result.ok
    assert any("degenerate" in r for r in result.reasons)


def test_duplicate_sub_question_id_rejected() -> None:
    plan = Plan(request="x", sub_questions=[_capec_sq(id="dup"), _attack_sq(id="dup")])
    result = evaluate(plan, CARDS, make_live_view())
    assert not result.ok
    assert any("duplicate sub-question id" in r for r in result.reasons)
