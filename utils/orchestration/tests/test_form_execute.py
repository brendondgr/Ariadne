"""Under ARIADNE_FORM_EXECUTE the bound form is executed as a plan, not re-parsed (EXP-2026-09-025).

Pins: the canonicalize node emits ``form_plan`` from a bound form only under the
flag; the draft node uses it on its first iteration and drafts normally after a
gate rejection; the flag defaults off so every recorded arm is unchanged.
"""

from __future__ import annotations

import dataclasses

from utils.orchestration.agents.planner.nodes import build_nodes
from utils.planner import canonical
from utils.planner.config import PlannerConfig
from utils.planner.intent import DeterministicIntentClassifier
from utils.planner.schema import Limits, Plan, SubQuestion
from utils.planner.tests._fixtures import load_fixture_cards

CARDS = load_fixture_cards()
GOOD = Limits(3, 1000, 5000)


class _Drafter:
    calls = 0

    def draft(self, request, cards, live_view, feedback=None, intent=None) -> Plan:
        _Drafter.calls += 1
        return Plan(request=request, sub_questions=[SubQuestion("q1", "attack", request, ["Technique"], GOOD)])


def _nodes(**config_kwargs):
    config = dataclasses.replace(PlannerConfig(data_dir="."), **config_kwargs)
    return build_nodes(_Drafter(), CARDS, 3, DeterministicIntentClassifier(), config)


BOUND = canonical.IntentForm(
    anchors=("T1047",), anchor_labels=("Technique",), target_labels=("Mitigation",),
    relation="MITIGATES", direction="in", mode=canonical.MODE_ENUMERATE, datasets=("attack",),
    sources={canonical.SLOT_ANCHORS: "exact-id"},
)


def test_a_bound_form_becomes_a_plan_under_the_flag(monkeypatch):
    monkeypatch.setattr(canonical, "deterministic_fill", lambda *a, **k: BOUND)
    nodes = _nodes(rewrite_enabled=True, form_execute=True)
    out = nodes["canonicalize"]({"request": "What stops T1047?", "original_request": "What stops T1047?"})
    assert out["rewrite_trace"]["executed"] == "form"
    plan = out["form_plan"]
    assert plan.sub_questions[0].entities == ["Technique", "MITIGATES", "Mitigation"]
    assert out["canonical_question"], "the rendered sentence is still recorded"


def test_the_flag_off_emits_no_plan(monkeypatch):
    monkeypatch.setattr(canonical, "deterministic_fill", lambda *a, **k: BOUND)
    nodes = _nodes(rewrite_enabled=True, form_execute=False)
    out = nodes["canonicalize"]({"request": "What stops T1047?", "original_request": "What stops T1047?"})
    assert "form_plan" not in out and "executed" not in out["rewrite_trace"]


def test_the_draft_node_uses_the_form_plan_first_and_drafts_after_a_rejection():
    nodes = _nodes(rewrite_enabled=True, form_execute=True)
    plan = Plan(request="q", sub_questions=[SubQuestion("q1", "attack", "q", ["Technique"], GOOD)])
    before = _Drafter.calls
    first = nodes["draft"]({"request": "q", "form_plan": plan, "iteration": 0, "live_view": None})
    assert first["last_plan"] is plan and first["drafter_used"] == "form"
    assert _Drafter.calls == before, "the drafter was not consulted"
    second = nodes["draft"]({"request": "q", "form_plan": plan, "iteration": 1, "live_view": None})
    assert second["drafter_used"] != "form" and _Drafter.calls == before + 1


def test_config_reads_the_environment_flag(monkeypatch):
    monkeypatch.delenv("ARIADNE_FORM_EXECUTE", raising=False)
    assert PlannerConfig.from_env().form_execute is False
    monkeypatch.setenv("ARIADNE_FORM_EXECUTE", "1")
    assert PlannerConfig.from_env().form_execute is True
