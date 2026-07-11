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
    # The intent the planner should classify (planner step one). Independent
    # ground truth: curated anchors set it by hand; generated cases derive it
    # from the specialist question's template (never from the classifier itself,
    # which would make the metric circular). ``None`` means "not scored".
    expected_intent: str | None = None
    # Optional decomposition gold. When ``None`` the scorer defaults to one
    # sub-question per expected source; set it when a source needs more than one.
    expected_sub_question_count: int | None = None
    split: str = "dev"
    # Provenance: "curated" (hand-reviewed anchors) or "generated" (derived from
    # the specialist banks by build_corpus.py). Reported separately so the small
    # curated regression set is never conflated with the larger measurement set.
    origin: str = "curated"
    # Difficulty tier of the source question ("easy"/"medium"/""), for tiered
    # reporting. Curated anchors carry "" (mixed / hand-authored).
    tier: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "ExpectedCase":
        raw_count = data.get("expected_sub_question_count")
        return cls(
            name=str(data["name"]),
            request=str(data["request"]),
            live=list(data.get("live", [])),
            expected_sources=list(data.get("expected_sources", [])),
            expected_entities={k: list(v) for k, v in data.get("expected_entities", {}).items()},
            expects_join=bool(data.get("expects_join", False)),
            expects_unsupported=bool(data.get("expects_unsupported", False)),
            expects_partial=bool(data.get("expects_partial", False)),
            expected_intent=data.get("expected_intent"),
            expected_sub_question_count=None if raw_count is None else int(raw_count),
            split=str(data.get("split", "dev")),
            origin=str(data.get("origin", "curated")),
            tier=str(data.get("tier", "")),
        )


class _FixedProbe(LiveSourceProbe):
    """A probe that returns a fixed view (no backend contact)."""

    def __init__(self, view: LiveSourceView) -> None:
        self._view = view

    def get_live_sources(self, cards, force: bool = False) -> LiveSourceView:
        return self._view


def load_corpus(split: str | None = None) -> list[ExpectedCase]:
    """Load all expected-plan cases, optionally filtered by split.

    Curated anchors live in ``expected_plans/*.json``; generated cases live in
    ``expected_plans/generated/*.json`` (see build_corpus.py). Both are globbed
    recursively so the loader picks up either without further wiring.
    """
    cases: list[ExpectedCase] = []
    for path in sorted(EXPECTED_PLANS_DIR.rglob("*.json")):
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
