"""The planner subgraph in isolation: converge, revise, degrade.

The ``PlanningAgent`` facade tests (``utils/planner/tests/test_agent_loop.py``)
already pin the end-to-end contract; these exercise the graph directly so a
wiring regression is caught at the subgraph boundary.
"""

from __future__ import annotations

from typing import Callable

from utils.orchestration.agents.planner.graph import build_planning_graph
from utils.planner.schema import Limits, Plan, SubQuestion
from utils.planner.tests._fixtures import load_fixture_cards, make_live_view

CARDS = load_fixture_cards()
GOOD = Limits(3, 1000, 5000)
LIVE = make_live_view(live=("attack", "capec"))


class ScriptedDrafter:
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


def _valid() -> Plan:
    return Plan(request="", sub_questions=[
        SubQuestion("q1", "capec", "patterns", ["AttackPattern", "MAPS_TO"], GOOD)])


def _invalid() -> Plan:
    return Plan(request="", sub_questions=[
        SubQuestion("q1", "capec", "x", ["GhostLabel"], GOOD)])


def _run(drafter, *, max_iterations=3) -> Plan:
    graph = build_planning_graph(drafter, CARDS, max_iterations)
    out = graph.invoke(
        {"request": "demo", "live_view": LIVE, "iteration": 0, "feedback": None},
        config={"recursion_limit": 50},
    )
    return out["plan"]


def test_converges_first_iteration():
    plan = _run(ScriptedDrafter([_valid]))
    assert not plan.partial
    assert len(plan.trace) == 1
    assert plan.trace[0]["gate_ok"] is True
    assert plan.trace[0]["iteration"] == 1
    assert plan.trace[0]["drafter"] == "ScriptedDrafter"


def test_revises_with_gate_feedback_then_converges():
    drafter = ScriptedDrafter([_invalid, _valid])
    plan = _run(drafter)
    assert [t["gate_ok"] for t in plan.trace] == [False, True]
    assert drafter.feedback_log[0] is None
    assert drafter.feedback_log[1], "second draft must receive the gate's reasons"


def test_degrades_at_iteration_cap():
    drafter = ScriptedDrafter([_invalid])
    plan = _run(drafter, max_iterations=3)
    assert drafter.calls == 3, "bounded: exactly max_iterations drafts"
    assert len(plan.trace) == 3
    assert plan.partial
    assert any("degraded to partial" in a for a in plan.assumptions)
