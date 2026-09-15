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


# -- the anchor gate: the model may never choose the entity ------------------


def test_stands_down_when_the_anchor_is_not_an_exact_bind() -> None:
    """T5's shape: a description with no name the resolver can look up."""
    from utils.orchestration.agents.planner.nodes import RUNG_SKIPPED_ANCHOR

    out = _canonicalize(
        "Which countermeasures stop an adversary abusing a scripting interpreter?",
        rewrite_enabled=True,
        rewrite_model_enabled=True,
        rewrite_only_without_identifier=True,
        rewrite_require_resolved_anchor=True,
    )
    assert out["rewrite_trace"]["rung"] == RUNG_SKIPPED_ANCHOR
    assert "request" not in out  # the analyst's own words go forward


def test_an_exact_bind_still_reaches_the_stage(monkeypatch) -> None:
    """T3's shape: the complete name is in the text, so the anchor is a lookup.

    The provenance is what the gate reads, so the provenance is what this test
    supplies. Exercising the real `exact_name_matches` here would test the
    fixture cards' name index rather than the decision, and the fixtures carry
    no index -- which is exactly why the first version of this test failed.
    """
    import utils.planner.canonical as canonical
    from utils.orchestration.agents.planner.nodes import RUNG_SKIPPED_ANCHOR
    from utils.planner.canonical import IntentForm, MODE_ENUMERATE, SLOT_ANCHORS

    bound = IntentForm(
        anchors=("T1047",), anchor_labels=("Technique",), target_labels=("Mitigation",),
        relation="MITIGATES", direction="in", mode=MODE_ENUMERATE, datasets=("attack",),
        sources={SLOT_ANCHORS: "exact-name"},
    )
    monkeypatch.setattr(canonical, "deterministic_fill", lambda *a, **k: bound)
    out = _canonicalize(
        "What mitigations are listed for Windows Management Instrumentation?",
        rewrite_enabled=True,
        rewrite_model_enabled=True,
        rewrite_only_without_identifier=True,
        rewrite_require_resolved_anchor=True,
    )
    assert out["rewrite_trace"]["rung"] != RUNG_SKIPPED_ANCHOR


def test_a_model_chosen_anchor_is_refused(monkeypatch) -> None:
    """The case the amendment exists for: the model picked who it is about."""
    import utils.planner.canonical as canonical
    from utils.orchestration.agents.planner.nodes import RUNG_SKIPPED_ANCHOR
    from utils.planner.canonical import IntentForm, MODE_ENUMERATE, SLOT_ANCHORS

    guessed = IntentForm(
        anchors=("T1059",), anchor_labels=("Technique",), mode=MODE_ENUMERATE,
        datasets=("attack",), sources={SLOT_ANCHORS: "ambiguous: 2 complete names in the text"},
    )
    monkeypatch.setattr(canonical, "deterministic_fill", lambda *a, **k: guessed)
    out = _canonicalize(
        "What stops an adversary abusing a scripting interpreter?",
        rewrite_enabled=True,
        rewrite_model_enabled=True,
        rewrite_only_without_identifier=True,
        rewrite_require_resolved_anchor=True,
    )
    assert out["rewrite_trace"]["rung"] == RUNG_SKIPPED_ANCHOR


def test_anchor_gate_defaults_off() -> None:
    from utils.orchestration.agents.planner.nodes import RUNG_SKIPPED_ANCHOR

    out = _canonicalize(
        "Which countermeasures stop an adversary abusing a scripting interpreter?",
        rewrite_enabled=True,
        rewrite_model_enabled=False,
        rewrite_only_without_identifier=True,
    )
    assert out["rewrite_trace"]["rung"] != RUNG_SKIPPED_ANCHOR


def test_anchor_gate_reads_its_environment_flag(monkeypatch) -> None:
    monkeypatch.delenv("ARIADNE_REWRITE_REQUIRE_RESOLVED_ANCHOR", raising=False)
    assert PlannerConfig.from_env().rewrite_require_resolved_anchor is False
    monkeypatch.setenv("ARIADNE_REWRITE_REQUIRE_RESOLVED_ANCHOR", "1")
    assert PlannerConfig.from_env().rewrite_require_resolved_anchor is True
