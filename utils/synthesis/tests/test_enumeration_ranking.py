#!/usr/bin/env python3
"""The enumeration ranks before it lists, and says what it withheld.

`EXP-2026-09-020` A-5: every retrieval widening on record raises coverage --
a recall measure that cannot fall when evidence is added -- and raises
`catalogue_dump` with it, because the enumeration listed whatever it was handed
in arrival order and stopped at the bound without saying so. These tests pin the
two halves of the fix.
"""

from __future__ import annotations

import os

from utils.synthesis.composer import _enumeration_claim

from ._fixtures import make_record, make_result


def _claim(related, *, entities=(), text="which tactics?", **kw):
    anchor = make_record("T1059", name="Command Interpreter", related=related, **kw)
    return _enumeration_claim(
        make_result(records=[anchor], entities=entities, text=text), anchor
    )


def test_the_label_the_plan_asked_for_is_listed_first() -> None:
    """A Tactic ranks above a Mitigation when the plan named Tactic."""
    related = [
        {"id": "M1040", "name": "Behavior Prevention", "label": "Mitigation",
         "type": "MITIGATES"},
        {"id": "TA0002", "name": "Execution", "label": "Tactic",
         "type": "HAS_TACTIC"},
    ]
    text = _claim(related, entities=("Technique", "HAS_TACTIC", "Tactic")).text
    assert text.index("TA0002") < text.index("M1040")


def test_a_neighbour_reached_through_a_named_relation_outranks_one_that_is_not() -> None:
    related = [
        {"id": "M1040", "name": "Alpha", "label": "Mitigation", "type": "DETECTS"},
        {"id": "M1041", "name": "Beta", "label": "Mitigation", "type": "MITIGATES"},
    ]
    text = _claim(related, entities=("MITIGATES",)).text
    assert text.index("M1041") < text.index("M1040")


def test_ranking_never_changes_which_ids_are_claimed() -> None:
    """Ordering is presentation. The set must be identical either way."""
    related = [
        {"id": f"M10{n}", "name": f"n{n}", "label": "Mitigation", "type": "MITIGATES"}
        for n in range(40, 46)
    ]
    on = _claim(related, entities=("Tactic",))
    os.environ["SYNTHESIS_RANK_ENUMERATION"] = "0"
    try:
        off = _claim(related, entities=("Tactic",))
    finally:
        os.environ.pop("SYNTHESIS_RANK_ENUMERATION", None)
    assert set(on.entity_ids) == set(off.entity_ids)


def test_a_bounded_list_says_how_many_it_withheld() -> None:
    """A bounded list that does not say it is bounded reads as a complete one."""
    related = [
        {"id": f"M{1000 + n}", "name": f"n{n}", "label": "Mitigation",
         "type": "MITIGATES"}
        for n in range(30)
    ]
    os.environ["SYNTHESIS_MAX_ENUMERATION_IDS"] = "5"
    try:
        text = _claim(related).text
    finally:
        os.environ.pop("SYNTHESIS_MAX_ENUMERATION_IDS", None)
    assert "withheld" in text
    assert "has 30 " in text, text


def test_a_complete_list_never_claims_to_have_withheld_anything() -> None:
    related = [
        {"id": "M1040", "name": "a", "label": "Mitigation", "type": "MITIGATES"},
        {"id": "M1041", "name": "b", "label": "Mitigation", "type": "MITIGATES"},
    ]
    assert "withheld" not in _claim(related).text


def test_narrative_source_says_who_wrote_the_prose() -> None:
    """`composer` names who wrote the CLAIMS; this names who wrote the sentence.

    They are different seams. A workbench that cites the record and the query
    behind every claim should not leave the prose layer's provenance invisible.
    """
    from utils.synthesis.contracts import SynthesizedAnswer

    answer = SynthesizedAnswer(request="q")
    assert answer.narrative_source == "deterministic"
    assert answer.to_dict()["narrative_source"] == "deterministic"


def test_a_failed_narrator_does_not_claim_to_have_written_the_prose() -> None:
    """The stamp lands after the call returns, never before it."""
    from utils.synthesis.config import SynthesisConfig
    from utils.synthesis.contracts import Claim, SynthesizedAnswer
    from utils.synthesis import factory
    from utils.synthesis.llm_composer import ComposerUnavailable

    answer = SynthesizedAnswer(request="q", narrative="deterministic prose")
    answer.claims = [Claim(text="x", kind="fact")]

    def _boom(*a, **kw):
        raise ComposerUnavailable("endpoint down")

    original = factory.compose_narrative
    factory.compose_narrative = _boom
    try:
        factory.apply_llm_narrative(
            answer, object(), SynthesisConfig(llm_enabled=True)
        )
    finally:
        factory.compose_narrative = original

    assert answer.narrative == "deterministic prose"
    assert answer.narrative_source == "deterministic"
    assert "narrator unavailable" in (answer.fallback_reason or "").lower()
