#!/usr/bin/env python3
"""Anchor-resolver tests: the deterministic id/title ladder + honest ambiguity."""

from __future__ import annotations

from utils.specialists.contracts import SpecialistTask
from utils.specialists.resolve.resolver import (
    AmbiguousAnchor,
    ResolvedAnchor,
    infer_label,
    resolve_anchor,
)
from utils.specialists.tests._fixtures import fixture_card


def _task(text: str, *, source: str = "attack", seed_ids=()) -> SpecialistTask:
    return SpecialistTask(
        sub_question_id="q",
        source=source,
        text=text,
        entities=(),
        seed_ids=tuple(seed_ids),
    )


# -- exact id ----------------------------------------------------------------


def test_exact_id_in_text_resolves_with_inferred_label() -> None:
    anchor = resolve_anchor(_task("What is T1055?"), fixture_card("attack"))
    assert isinstance(anchor, ResolvedAnchor)
    assert (anchor.kind, anchor.value, anchor.label, anchor.via) == (
        "id", "T1055", "Technique", "exact-id",
    )


def test_id_label_inference_covers_the_prefixes() -> None:
    assert infer_label("TA0006", "attack") == "Tactic"
    assert infer_label("M1049", "attack") == "Mitigation"
    assert infer_label("G0016", "attack") == "Group"
    assert infer_label("S0002", "attack") == "Software"
    assert infer_label("T1055.011", "attack") == "Technique"
    assert infer_label("CAPEC-66", "capec") == "AttackPattern"
    assert infer_label("CWE-79", "capec") == "Weakness"
    assert infer_label("not-an-id", "attack") is None


def test_planner_seed_id_wins_over_text() -> None:
    anchor = resolve_anchor(_task("some prose", seed_ids=("M1049",)), fixture_card("attack"))
    assert isinstance(anchor, ResolvedAnchor)
    assert anchor.value == "M1049"
    assert anchor.via == "seed"
    assert anchor.label == "Mitigation"


# -- exact / fuzzy title -----------------------------------------------------


def test_named_entity_resolves_to_a_fuzzy_title_anchor() -> None:
    anchor = resolve_anchor(_task("Tell me about User Training"), fixture_card("attack"))
    assert isinstance(anchor, ResolvedAnchor)
    assert anchor.kind == "title"
    assert anchor.value == "User Training"
    assert anchor.via == "fuzzy"


def test_alias_hit_normalises_to_the_canonical_title() -> None:
    # G0016's aliases include "Cozy Bear"; an injected alias index maps it to the
    # canonical group name, so the anchor is unambiguous even though the text
    # never says "APT29".
    alias_index = {"cozy bear": "APT29", "the dukes": "APT29"}
    anchor = resolve_anchor(
        _task("What does Cozy Bear do?"), fixture_card("attack"), alias_index=alias_index
    )
    assert isinstance(anchor, ResolvedAnchor)
    assert anchor.kind == "title"
    assert anchor.value == "APT29"
    assert anchor.via == "alias"


def test_two_aliases_of_one_entity_collapse_to_one_anchor() -> None:
    # "Cozy Bear" and "The Dukes" both resolve to APT29 -> a single anchor, not
    # ambiguity (dedupe is on the canonical value).
    alias_index = {"cozy bear": "APT29", "the dukes": "APT29"}
    anchor = resolve_anchor(
        _task("Is Cozy Bear the same as The Dukes?"),
        fixture_card("attack"),
        alias_index=alias_index,
    )
    assert isinstance(anchor, ResolvedAnchor)
    assert anchor.value == "APT29"


# -- ambiguity ---------------------------------------------------------------


def test_two_ids_return_ambiguous_not_a_guess() -> None:
    anchor = resolve_anchor(_task("Compare T1055 and T1027"), fixture_card("attack"))
    assert isinstance(anchor, AmbiguousAnchor)
    values = {c.value for c in anchor.candidates}
    assert values == {"T1055", "T1027"}
    assert anchor.reason


def test_two_named_entities_return_ambiguous() -> None:
    anchor = resolve_anchor(
        _task('Compare "User Training" and "Data Backup"'), fixture_card("attack")
    )
    assert isinstance(anchor, AmbiguousAnchor)
    assert {c.value for c in anchor.candidates} == {"User Training", "Data Backup"}


def test_id_tier_beats_title_tier() -> None:
    # A text with both an id and a Title-Case name anchors on the id (higher tier).
    anchor = resolve_anchor(_task("Describe Spearphishing T1566"), fixture_card("attack"))
    assert isinstance(anchor, ResolvedAnchor)
    assert anchor.kind == "id" and anchor.value == "T1566"


# -- miss + capec priority ---------------------------------------------------


def test_no_id_no_name_is_a_miss() -> None:
    # Pure function words: no id, no Title-Case run, no 4+ char content token —
    # the name extractor lifts nothing, so the ladder bottoms out at a miss.
    assert resolve_anchor(_task("can you do it for me"), fixture_card("attack")) is None


def test_capec_native_priority_prefers_capec_over_technique() -> None:
    anchor = resolve_anchor(
        _task("Does CAPEC-66 map to T1055?", source="capec"), fixture_card("capec")
    )
    assert isinstance(anchor, ResolvedAnchor)
    assert anchor.value == "CAPEC-66"
    assert anchor.label == "AttackPattern"


def test_to_dict_round_trips_for_tracing() -> None:
    anchor = resolve_anchor(_task("What is T1055?"), fixture_card("attack"))
    assert resolve_anchor(_task("x and y T1055 T1027"), fixture_card("attack")).to_dict()["candidates"]
    assert anchor.to_dict() == {
        "kind": "id", "value": "T1055", "dataset": "attack",
        "label": "Technique", "via": "exact-id",
    }
