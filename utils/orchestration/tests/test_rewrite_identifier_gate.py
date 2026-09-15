"""The identifier gate: the rewrite stage stands down when the question names an id.

`EXP-2026-09-021` Step 4 measured the rewrite stage separately on the two
populations it acts on. Where the question still cites an identifier it broke 32
answers and fixed 10; where it cites none it fixed 44 and broke 7. The stage
canonicalises a question into the source card's vocabulary, and an identifier is
the strongest routing signal the template ladder has, so rendering it away costs
more than the canonical form returns.

So there are four things to pin: the gate fires on a question that cites an
identifier, it does *not* fire on one that does not, the flag defaults off so the
stage behaves exactly as `EXP-2026-09-014` measured it, and the rung it records
is distinguishable from "the flag was never set" -- which is the difference
between a stage that declined and a stage that was not asked.
"""

from __future__ import annotations

import dataclasses

from utils.orchestration.agents.planner.nodes import (
    RUNG_OFF,
    RUNG_SKIPPED_ID,
    build_nodes,
)
from utils.planner.config import PlannerConfig
from utils.planner.intent import DeterministicIntentClassifier
from utils.planner.schema import Limits, Plan, SubQuestion
from utils.planner.tests._fixtures import load_fixture_cards

CARDS = load_fixture_cards()
GOOD = Limits(3, 1000, 5000)


class _Drafter:
    def draft(self, request, cards, live_view, feedback=None, intent=None) -> Plan:
        return Plan(
            request=request,
            sub_questions=[SubQuestion("q1", "attack", request, ["Technique"], GOOD)],
        )


def _canonicalize(request: str, **config_kwargs):
    config = dataclasses.replace(PlannerConfig(data_dir="."), **config_kwargs)
    nodes = build_nodes(_Drafter(), CARDS, 3, DeterministicIntentClassifier(), config)
    return nodes["canonicalize"]({"request": request, "original_request": request})


# -- the gate fires, and only where it should -------------------------------


def test_stands_down_when_the_question_cites_an_identifier() -> None:
    """T1's shape: the verb changed but the identifier survived."""
    out = _canonicalize(
        "How do I defend against T1047?",
        rewrite_enabled=True,
        rewrite_model_enabled=True,
        rewrite_only_without_identifier=True,
    )
    assert out["rewrite_trace"]["rung"] == RUNG_SKIPPED_ID
    assert "T1047" in out["rewrite_trace"]["identifiers"]
    # The analyst's own words go forward untouched -- no canonical question.
    assert "request" not in out
    assert out["original_request"] == "How do I defend against T1047?"


def test_runs_when_the_question_cites_no_identifier() -> None:
    """T3's shape: the entity is named, the identifier is gone."""
    out = _canonicalize(
        "What mitigations are listed for Windows Management Instrumentation?",
        rewrite_enabled=True,
        rewrite_model_enabled=False,
        rewrite_only_without_identifier=True,
    )
    assert out["rewrite_trace"]["rung"] != RUNG_SKIPPED_ID


def test_capec_identifiers_also_trip_the_gate() -> None:
    """The predicate is the resolver's per-dataset ladder, not an ATT&CK regex."""
    out = _canonicalize(
        "How would you stop CAPEC-66 from working?",
        rewrite_enabled=True,
        rewrite_model_enabled=True,
        rewrite_only_without_identifier=True,
    )
    assert out["rewrite_trace"]["rung"] == RUNG_SKIPPED_ID


# -- the flag ships off -----------------------------------------------------


def test_defaults_off_so_the_stage_is_unchanged() -> None:
    """With the gate flag unset, an id-bearing question still reaches the stage."""
    out = _canonicalize(
        "How do I defend against T1047?",
        rewrite_enabled=True,
        rewrite_model_enabled=False,
    )
    assert out["rewrite_trace"]["rung"] != RUNG_SKIPPED_ID


def test_gate_is_inert_when_the_whole_stage_is_off() -> None:
    """`off` and `skipped_identifier` are different facts and stay different."""
    out = _canonicalize(
        "How do I defend against T1047?",
        rewrite_only_without_identifier=True,
    )
    assert out["rewrite_trace"]["rung"] == RUNG_OFF


def test_config_reads_the_environment_flag(monkeypatch) -> None:
    monkeypatch.delenv("ARIADNE_REWRITE_ONLY_WITHOUT_ID", raising=False)
    assert PlannerConfig.from_env().rewrite_only_without_identifier is False
    monkeypatch.setenv("ARIADNE_REWRITE_ONLY_WITHOUT_ID", "1")
    assert PlannerConfig.from_env().rewrite_only_without_identifier is True
