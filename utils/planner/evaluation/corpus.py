#!/usr/bin/env python3
"""The expected-plan corpus and its runner.

A small, manually-reviewed set of (request -> expected plan) pairs — including
out-of-scope and partially-answerable requests so the "mark unsupported"
behaviour is tested, not just the happy path (briefing §6.2). Cases carry a
``split`` (``dev`` or ``holdout``) so a portion can be frozen as regression
checks the planner was never tuned on (briefing §6.3).

Each case fixes its own ``live`` source set so scoring is deterministic and
independent of whether the Docker backends happen to be up.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ..agent import PlanningAgent
from ..cards import SourceCardView
from ..config import PlannerConfig
from ..discovery import LiveSourceProbe, LiveSourceView, stub_live_view
from ..drafter import DeterministicDrafter, PlanDrafter
from ..schema import Plan
from .scorer import CaseScore, score_plan

EXPECTED_PLANS_DIR = Path(__file__).parent / "expected_plans"


@dataclass
class ExpectedCase:
    """One manually-reviewed (request -> expected plan) reference."""

    name: str
    request: str
    live: list[str]
    expected_sources: list[str]
    expected_entities: dict[str, list[str]] = field(default_factory=dict)
    expects_join: bool = False
    expects_unsupported: bool = False
    expects_partial: bool = False
    split: str = "dev"

    @classmethod
    def from_dict(cls, data: dict) -> "ExpectedCase":
        return cls(
            name=str(data["name"]),
            request=str(data["request"]),
            live=list(data.get("live", [])),
            expected_sources=list(data.get("expected_sources", [])),
            expected_entities={k: list(v) for k, v in data.get("expected_entities", {}).items()},
            expects_join=bool(data.get("expects_join", False)),
            expects_unsupported=bool(data.get("expects_unsupported", False)),
            expects_partial=bool(data.get("expects_partial", False)),
            split=str(data.get("split", "dev")),
        )


class _FixedProbe(LiveSourceProbe):
    """A probe that returns a fixed view (no backend contact)."""

    def __init__(self, view: LiveSourceView) -> None:
        self._view = view

    def get_live_sources(self, cards, force: bool = False) -> LiveSourceView:
        return self._view


def load_corpus(split: str | None = None) -> list[ExpectedCase]:
    """Load all expected-plan cases, optionally filtered by split."""
    cases: list[ExpectedCase] = []
    for path in sorted(EXPECTED_PLANS_DIR.glob("*.json")):
        with open(path, encoding="utf-8") as f:
            cases.append(ExpectedCase.from_dict(json.load(f)))
    if split is not None:
        cases = [c for c in cases if c.split == split]
    return cases


def run_case(
    case: ExpectedCase,
    cards: dict[str, SourceCardView],
    *,
    drafter: PlanDrafter | None = None,
) -> tuple[Plan, CaseScore]:
    """Run one case through the agent with a fixed live view and score it."""
    live_view = stub_live_view(cards, case.live)
    agent = PlanningAgent(
        PlannerConfig(data_dir="data"),
        cards=cards,
        drafter=drafter or DeterministicDrafter(),
        probe=_FixedProbe(live_view),
    )
    plan = agent.plan(case.request)
    score = score_plan(plan, case, cards, live_view)
    return plan, score


def run_corpus(
    cards: dict[str, SourceCardView],
    *,
    split: str | None = None,
    drafter: PlanDrafter | None = None,
) -> list[tuple[ExpectedCase, Plan, CaseScore]]:
    """Run every (optionally split-filtered) case and return results."""
    results: list[tuple[ExpectedCase, Plan, CaseScore]] = []
    for case in load_corpus(split):
        plan, score = run_case(case, cards, drafter=drafter)
        results.append((case, plan, score))
    return results
