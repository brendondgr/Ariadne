#!/usr/bin/env python3

from __future__ import annotations

import json

from utils.planner.agent import PlanningAgent
from utils.planner.cli import run_plan_command
from utils.planner.config import PlannerConfig
from utils.planner.discovery import LiveSourceView
from utils.planner.drafter import DeterministicDrafter
from utils.planner.tests._fixtures import load_fixture_cards, make_live_view

CARDS = load_fixture_cards()
DEMO = "Which CAPEC patterns map to ATT&CK techniques and their mitigations?"


class FixedProbe:
    def __init__(self, view: LiveSourceView) -> None:
        self._view = view

    def get_live_sources(self, cards, force: bool = False) -> LiveSourceView:
        return self._view


def _agent(live=("attack", "capec")) -> PlanningAgent:
    return PlanningAgent(
        PlannerConfig(data_dir="data"),
        cards=CARDS,
        drafter=DeterministicDrafter(),
        probe=FixedProbe(make_live_view(live=live)),
    )


def test_cli_prints_live_sources_and_plan(capsys) -> None:
    code = run_plan_command(DEMO, agent=_agent())
    out = capsys.readouterr().out
    assert "Live sources" in out
    assert "[LIVE] attack" in out and "[LIVE] capec" in out
    assert "=== Plan ===" in out
    # the printed plan is valid JSON
    blob = out.split("=== Plan ===", 1)[1].split("=== Summary ===", 1)[0].strip()
    parsed = json.loads(blob)
    assert parsed["request"] == DEMO
    assert code == 0  # both live ⇒ not partial


def test_cli_reports_partial_when_source_down(capsys) -> None:
    code = run_plan_command(DEMO, agent=_agent(live=("capec",)))
    out = capsys.readouterr().out
    assert "[DOWN] attack" in out
    assert "unsupported" in out
    assert code == 1  # partial plan


def test_cli_handles_no_cards(capsys) -> None:
    agent = PlanningAgent(PlannerConfig(data_dir="data"), cards={},
                          drafter=DeterministicDrafter(), probe=FixedProbe(LiveSourceView({})))
    code = run_plan_command(DEMO, agent=agent)
    out = capsys.readouterr().out
    assert "No source cards" in out
    assert code == 2
