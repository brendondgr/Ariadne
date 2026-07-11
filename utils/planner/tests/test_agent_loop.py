#!/usr/bin/env python3

from __future__ import annotations

from typing import Callable

from utils.planner.agent import PlanningAgent
from utils.planner.config import PlannerConfig
from utils.planner.discovery import LiveSourceView
from utils.planner.drafter import DeterministicDrafter
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
GOOD = Limits(3, 1000, 5000)
DEMO = "Which CAPEC patterns map to ATT&CK techniques and their mitigations?"


# -- stubs ------------------------------------------------------------------


class FakeProbe:
    def __init__(self, view: LiveSourceView) -> None:
        self._view = view

    def get_live_sources(self, cards, force: bool = False) -> LiveSourceView:
        return self._view


class ScriptedDrafter:
    """Returns fresh plans from a list of builders; records feedback per call."""

    def __init__(self, builders: list[Callable[[], Plan]]) -> None:
        self._builders = builders
        self.calls = 0
        self.feedback_log: list[list[str] | None] = []

    def draft(self, request, cards, live_view, feedback=None) -> Plan:
        self.feedback_log.append(feedback)
        plan = self._builders[min(self.calls, len(self._builders) - 1)]()
        self.calls += 1
        plan.request = request
        return plan


def _valid_capec() -> Plan:
    return Plan(
        request="",
        sub_questions=[
            SubQuestion("q1", "capec", "patterns", ["AttackPattern", "MAPS_TO"], GOOD)
        ],
    )


def _invalid_label() -> Plan:
    return Plan(
        request="",
        sub_questions=[SubQuestion("q1", "capec", "x", ["GhostLabel"], GOOD)],
    )


def _mixed_valid_invalid() -> Plan:
    return Plan(
        request="",
        sub_questions=[
            SubQuestion("q1", "capec", "good", ["AttackPattern"], GOOD),
            SubQuestion("q2", "capec", "bad", ["GhostLabel"], GOOD),
        ],
    )


def _agent(drafter, *, live=("attack", "capec"), max_iter=3) -> PlanningAgent:
    cfg = PlannerConfig(data_dir="data", max_iterations=max_iter)
    return PlanningAgent(cfg, cards=CARDS, drafter=drafter, probe=FakeProbe(make_live_view(live=live)))


# -- tests ------------------------------------------------------------------


def test_converges_first_iteration_with_deterministic_drafter() -> None:
    agent = _agent(DeterministicDrafter())
    plan = agent.plan(DEMO)
    assert evaluate(plan, CARDS, make_live_view()).ok
    assert len(plan.trace) == 1
    assert plan.trace[0]["gate_ok"] is True


def test_revises_then_converges_and_feeds_feedback() -> None:
    drafter = ScriptedDrafter([_invalid_label, _valid_capec])
    agent = _agent(drafter)
    plan = agent.plan(DEMO)
    assert evaluate(plan, CARDS, make_live_view()).ok
    assert len(plan.trace) == 2
    assert plan.trace[0]["gate_ok"] is False
    assert plan.trace[1]["gate_ok"] is True
    # first call got no feedback; second call got the gate's reasons
    assert drafter.feedback_log[0] is None
    assert drafter.feedback_log[1] and any("capec card" in r for r in drafter.feedback_log[1])


def test_never_converges_degrades_to_partial() -> None:
    drafter = ScriptedDrafter([_invalid_label])  # always invalid
    agent = _agent(drafter, max_iter=3)
    plan = agent.plan(DEMO)
    # bounded: exactly max_iterations drafts happened
    assert drafter.calls == 3
    assert len(plan.trace) == 3
    # degraded plan is honest and gate-valid
    assert plan.partial
    assert evaluate(plan, CARDS, make_live_view()).ok
    assert plan.unsupported  # the unresolvable sub-question surfaced
    assert any("degraded to partial" in a for a in plan.assumptions)


def test_partial_degrade_keeps_valid_drops_invalid() -> None:
    drafter = ScriptedDrafter([_mixed_valid_invalid])  # always mixed
    agent = _agent(drafter, max_iter=2)
    plan = agent.plan(DEMO)
    assert evaluate(plan, CARDS, make_live_view()).ok
    assert plan.target_sources() == {"capec"}
    assert len(plan.sub_questions) == 1  # only the valid one kept
    assert any("GhostLabel" in u.reason or "q2" in u.description for u in plan.unsupported)


def test_degenerate_draft_never_emitted_as_success() -> None:
    drafter = ScriptedDrafter([lambda: Plan(request="")])  # always empty/degenerate
    agent = _agent(drafter, max_iter=2)
    plan = agent.plan(DEMO)
    assert not plan.is_empty()  # degradation added a catch-all unsupported
    assert plan.partial
    assert evaluate(plan, CARDS, make_live_view()).ok


def test_out_of_scope_request_is_honest_partial() -> None:
    agent = _agent(DeterministicDrafter())
    plan = agent.plan("List all Kubernetes pods.")
    assert not plan.sub_questions
    assert plan.unsupported and plan.partial
    assert evaluate(plan, CARDS, make_live_view()).ok


def test_down_source_request_routes_only_live() -> None:
    agent = _agent(DeterministicDrafter(), live=("capec",))  # attack down
    plan = agent.plan(DEMO)
    assert plan.target_sources() == {"capec"}
    assert plan.partial
    assert any("attack" in u.reason for u in plan.unsupported)
    assert evaluate(plan, CARDS, agent.live_sources()).ok


# -- intent classification (planner step one) -------------------------------


def test_converged_plan_carries_classified_intent() -> None:
    agent = _agent(DeterministicDrafter())
    plan = agent.plan(DEMO)  # the flagship cross-source question
    assert plan.intent is not None
    assert plan.intent.label == "correlation"
    assert plan.intent.source == "deterministic"
    # intent survives serialisation and is present only once set.
    assert plan.to_dict()["intent"]["label"] == "correlation"


def test_degraded_plan_still_reports_intent() -> None:
    agent = _agent(DeterministicDrafter())
    plan = agent.plan("List all Kubernetes pods.")  # out of scope -> degrade
    assert plan.intent is not None  # even a partial/degraded plan names its intent


def test_plan_without_intent_serialises_byte_identically() -> None:
    # A plan whose classify step never ran (intent is None) must omit the key,
    # so pre-intent baselines stay byte-identical (mirrors SubQuestion.hop).
    plan = Plan(request="x")
    assert "intent" not in plan.to_dict()
