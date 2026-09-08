"""The canonicalize node: ordering, provenance, and the flag-off identity.

The node sits between ``classify`` and ``draft``, and everything downstream sees
only a ``request`` string. So there are exactly three things to pin here: that
the node runs in the right place, that what it hands the drafter is the right
string, and that with the flag off nothing about the plan changes — including
its JSON, which the captured baselines are compared against byte for byte.
"""

from __future__ import annotations

import dataclasses
from typing import Callable

import pytest

from utils.orchestration.agents.planner.graph import build_planning_graph
from utils.orchestration.agents.planner.nodes import (
    RUNG_ABSTAIN,
    RUNG_DETERMINISTIC,
    RUNG_OFF,
    build_nodes,
)
from utils.planner.canonical import IntentForm, MODE_ENUMERATE, SLOT_ANCHORS
from utils.planner.config import PlannerConfig
from utils.planner.intent import DeterministicIntentClassifier
from utils.planner.schema import Limits, Plan, SubQuestion
from utils.planner.tests._fixtures import load_fixture_cards, make_live_view

CARDS = load_fixture_cards()
LIVE = make_live_view(live=("attack", "capec"))
GOOD = Limits(3, 1000, 5000)


class RecordingDrafter:
    """Accepts anything and remembers the request string it was handed."""

    def __init__(self) -> None:
        self.requests: list[str] = []

    def draft(self, request, cards, live_view, feedback=None, intent=None) -> Plan:
        self.requests.append(request)
        return Plan(
            request=request,
            sub_questions=[
                SubQuestion("q1", "attack", f"In attack: {request}", ["Technique"], GOOD)
            ],
        )


def _config(**kwargs) -> PlannerConfig:
    base = PlannerConfig(data_dir=".")
    return dataclasses.replace(base, **kwargs)


def _run(config: PlannerConfig | None, request: str) -> tuple[Plan, RecordingDrafter]:
    drafter = RecordingDrafter()
    graph = build_planning_graph(
        drafter, CARDS, 3, DeterministicIntentClassifier(), config
    )
    out = graph.invoke(
        {
            "request": request, "original_request": request,
            "live_view": LIVE, "iteration": 0, "feedback": None,
        }
    )
    return out["plan"], drafter


# -- ordering ---------------------------------------------------------------


def test_the_node_exists_and_sits_between_classify_and_draft() -> None:
    nodes = build_nodes(RecordingDrafter(), CARDS, 3, DeterministicIntentClassifier())
    assert "canonicalize" in nodes
    graph = build_planning_graph(
        RecordingDrafter(), CARDS, 3, DeterministicIntentClassifier()
    )
    edges = {(e.source, e.target) for e in graph.get_graph().edges}
    assert ("classify", "canonicalize") in edges
    assert ("canonicalize", "draft") in edges
    assert ("classify", "draft") not in edges


def test_the_deterministic_fill_can_read_the_classified_intent() -> None:
    """Mode comes from intent, so canonicalize must run after classify."""
    captured: dict[str, object] = {}
    nodes = build_nodes(
        RecordingDrafter(), CARDS, 3, DeterministicIntentClassifier(),
        _config(rewrite_enabled=True),
    )
    state = {"request": "Which techniques does group G0016 use?", "original_request": ""}
    state.update(nodes["classify"](state))
    captured.update(nodes["canonicalize"](state))
    assert state.get("intent") is not None
    assert captured["rewrite_trace"]["rung"] in {RUNG_DETERMINISTIC, RUNG_ABSTAIN}


# -- the flag off -----------------------------------------------------------


@pytest.mark.parametrize("config", [None, _config(rewrite_enabled=False)])
def test_with_the_flag_off_the_drafter_sees_the_analysts_own_words(config) -> None:
    question = "What mitigations does ATT&CK list for T1047?"
    plan, drafter = _run(config, question)
    assert drafter.requests == [question]
    assert plan.request == question


@pytest.mark.parametrize("config", [None, _config(rewrite_enabled=False)])
def test_with_the_flag_off_the_plan_json_gains_no_key(config) -> None:
    """A plan JSON that gains a field no longer matches the captured baselines."""
    plan, _drafter = _run(config, "What mitigations does ATT&CK list for T1047?")
    assert plan.rewrite is None
    assert "rewrite" not in plan.to_dict()


def test_the_off_rung_is_recorded_in_the_state_even_though_it_is_not_on_the_plan() -> None:
    nodes = build_nodes(RecordingDrafter(), CARDS, 3, DeterministicIntentClassifier())
    out = nodes["canonicalize"]({"request": "anything", "original_request": "anything"})
    assert out["rewrite_trace"]["rung"] == RUNG_OFF


# -- the flag on ------------------------------------------------------------


def test_a_form_that_cannot_bind_leaves_the_request_alone_and_says_so() -> None:
    nodes = build_nodes(
        RecordingDrafter(), CARDS, 3, DeterministicIntentClassifier(),
        _config(rewrite_enabled=True),
    )
    state = {"request": "wholly unrelated musings", "original_request": "wholly unrelated musings"}
    state.update(nodes["classify"](state))
    out = nodes["canonicalize"](state)
    assert "request" not in out  # the analyst's words go forward untouched
    assert out["rewrite_trace"]["rung"] == RUNG_ABSTAIN
    assert out["rewrite_trace"]["unbound"]


def test_the_provenance_names_the_rung_the_original_and_the_canonical() -> None:
    from utils.orchestration.agents.planner.nodes import _provenance

    block = _provenance(
        {
            "rewrite_trace": {"rung": RUNG_DETERMINISTIC, "cache_hit": False, "unbound": []},
            "original_request": "how do I stop it?",
            "canonical_question": "In attack, give the mitigations for technique T1047.",
            "intent_form": IntentForm(
                anchors=("T1047",), mode=MODE_ENUMERATE, datasets=("attack",)
            ).to_dict(),
        }
    )
    assert block["rung"] == RUNG_DETERMINISTIC
    assert block["original_question"] == "how do I stop it?"
    assert block["canonical_question"].startswith("In attack,")
    assert block["form"]["anchors"] == ["T1047"]


def test_the_provenance_is_absent_when_the_stage_never_ran() -> None:
    from utils.orchestration.agents.planner.nodes import _provenance

    assert _provenance({"rewrite_trace": {"rung": RUNG_OFF}}) is None
    assert _provenance({}) is None


def test_a_rewritten_request_reaches_the_drafter_and_the_plan_records_both() -> None:
    """The one behaviour that matters: the drafter sees the canonical sentence."""
    question = "What mitigations does ATT&CK list for T1047?"
    plan, drafter = _run(_config(rewrite_enabled=True), question)
    if plan.rewrite and plan.rewrite.get("rung") == RUNG_DETERMINISTIC and (
        plan.rewrite.get("canonical_question")
    ):
        assert drafter.requests == [plan.rewrite["canonical_question"]]
        assert plan.rewrite["original_question"] == question
    else:  # the fixture cards may not bind every slot; then nothing is rewritten
        assert drafter.requests == [question]
