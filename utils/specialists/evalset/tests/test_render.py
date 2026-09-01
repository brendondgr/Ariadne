#!/usr/bin/env python3
"""Renderer prompt construction and validation — no model, no network.

The renderer is the one place a model touches question generation, so the tests
here are about containment: what the prompt is allowed to contain, and what a
returned question must survive before it is kept.

The gloss tables are the only hand-authored artifact in the pipeline. Two tests
hold them to the property that makes them safe — no gloss may name a label, and
every gloss the current spec pool needs must exist — because a missing gloss
would otherwise be filled from the raw predicate, which is exactly the schema
leak the whole design avoids.
"""

from __future__ import annotations

import pytest

from utils.specialists.evalset import composition as comp
from utils.specialists.evalset import raw_graph as rg
from utils.specialists.evalset import render as rd
from utils.specialists.evalset.schema_census import build_census


@pytest.fixture(scope="module")
def graph() -> rg.RawGraph:
    return rg.build()


@pytest.fixture(scope="module")
def specs(graph: rg.RawGraph) -> list[comp.Spec]:
    return comp.enumerate_specs(graph, build_census(), per_shape_limit=2)


def _spec(**kwargs) -> comp.Spec:
    base = dict(
        id="X", tier="D2", kind="traverse", source="attack",
        anchor_id="a", anchor_key="T1055", anchor_label="Technique", anchor_name="Process Injection",
        steps=(comp.Step(predicate="mitigates", reverse=True, label="Mitigation"),),
        filters=(), return_label="Mitigation", return_field="key",
        gold=("M1040",), gold_width=1, gold_kind="set", dangling=(), shapes=(), query={},
    )
    base.update(kwargs)
    return comp.Spec(**base)


# --- containment: what may reach a prompt ------------------------------------


def test_the_prompt_never_contains_the_gold(specs: list[comp.Spec]) -> None:
    """A prompt carrying the answer would make every score circular.

    Matched on word boundaries, the way the real validator does: `CAPEC-700`
    contains `CAPEC-70` as a substring and is a different pattern.
    """
    for spec in specs[:400]:
        prompt = rd.prompt_for(rd.brief_for(spec), "analyst")
        in_prompt = rd.identifiers_in(prompt)
        for answer in spec.gold:
            if rd.identifiers_in(answer):
                assert answer.upper() not in in_prompt, (spec.id, answer)
            else:
                assert answer not in prompt, (spec.id, answer)


def test_the_prompt_never_contains_schema_vocabulary(specs: list[comp.Spec]) -> None:
    """Predicates are the schema's own words; handing them over guarantees leakage."""
    for spec in specs[:300]:
        for register in rd.REGISTERS:
            prompt = rd.prompt_for(rd.brief_for(spec), register)
            assert not rd.schema_leakage(prompt), (spec.id, rd.schema_leakage(prompt))


def test_the_prompt_never_reveals_the_tier(specs: list[comp.Spec]) -> None:
    """A D0 question that telegraphs its own unanswerability tests nothing."""
    d0 = [s for s in specs if s.tier == "D0"][:40]
    assert d0
    for spec in d0:
        prompt = rd.prompt_for(rd.brief_for(spec), "analyst").lower()
        for tell in ("unanswerable", "no answer", "d0", "trick", "does not exist"):
            assert tell not in prompt, spec.id


def test_a_D0_brief_is_shaped_like_a_D2_brief(graph: rg.RawGraph, specs: list[comp.Spec]) -> None:
    d0 = next(s for s in specs if s.tier == "D0" and s.steps)
    d2 = next(s for s in specs if s.tier == "D2")
    a, b = rd.brief_for(d0), rd.brief_for(d2)
    assert {f for f in a.__dataclass_fields__} == {f for f in b.__dataclass_fields__}
    assert a.constraint is None and b.constraint is None


# --- the gloss tables --------------------------------------------------------


def test_no_relation_gloss_ends_with_a_label() -> None:
    """The frame appends the label, so a gloss that ends with one doubles it.

    Checked on the *ending* rather than on any mention: "is a step in" names a
    label and composes correctly ("the CAPEC attack patterns each of those is a
    step in"), while "corresponds to the ATT&CK technique" does not.
    """
    endings = {w.lower() for pair in rd.LABEL_GLOSS.values() for w in pair}
    for predicate, glosses in rd.RELATION_GLOSS.items():
        for gloss in glosses:
            for ending in endings:
                assert not gloss.lower().endswith(ending), f"{predicate}: {gloss!r}"


def test_no_rendered_ask_names_a_label_twice_running(specs: list[comp.Spec]) -> None:
    """The composition failure this guards, stated over real specs."""
    singulars = [pair[0].lower() for pair in rd.LABEL_GLOSS.values()]
    for spec in specs[:400]:
        ask = rd.brief_for(spec).ask.lower()
        for singular in singulars:
            assert f"{singular} {singular}" not in ask, spec.id
            assert f"{singular}s the {singular}" not in ask, spec.id


def test_every_spec_the_pool_produces_is_renderable(specs: list[comp.Spec]) -> None:
    coverage = rd.coverage(specs)
    assert coverage["rate"] == 1.0, coverage["missing"]


def test_a_missing_gloss_raises_rather_than_falling_back(graph: rg.RawGraph) -> None:
    """Falling back to the raw predicate is the leak, so it must be impossible."""
    spec = _spec(steps=(comp.Step(predicate="no-such-predicate", reverse=False, label="Mitigation"),))
    assert not rd.renderable(spec)
    with pytest.raises(KeyError, match="no gloss"):
        rd.brief_for(spec)


def test_constraints_use_their_own_gloss_frame(specs: list[comp.Spec]) -> None:
    """"only those where how general or specific it is is Meta" is not English."""
    d5 = [s for s in specs if s.tier == "D5"][:40]
    assert d5
    for spec in d5:
        constraint = rd.brief_for(spec).constraint
        assert constraint and " is is " not in constraint, spec.id


# --- validation of what comes back -------------------------------------------


def test_a_question_naming_the_answer_is_rejected() -> None:
    spec = _spec()
    assert "names the answer" in rd.rejection_reason(
        "Which mitigations apply to T1055, such as M1040?", spec
    )


def test_a_question_not_naming_its_anchor_is_rejected() -> None:
    assert "does not name its anchor" in rd.rejection_reason(
        "Which mitigations apply to process injection?", _spec()
    )


def test_a_question_naming_a_stray_identifier_is_rejected() -> None:
    reason = rd.rejection_reason("How do T1055 and T1027 differ in mitigation?", _spec())
    assert "names other identifiers" in reason and "T1027" in reason


def test_a_sub_techniques_parent_is_not_a_stray() -> None:
    spec = _spec(anchor_key="T1055.011", gold=("M1040",))
    assert rd.rejection_reason("What mitigates T1055.011?", spec) is None


def test_schema_leakage_is_a_hard_rejection() -> None:
    spec = _spec()
    for leaked in (
        "What is the kill_chain_phase of T1055?",
        "Which x_mitre_platforms does T1055 list?",
        "Which AttackPattern maps to T1055?",
    ):
        assert "leaks schema vocabulary" in rd.rejection_reason(leaked, spec), leaked


def test_a_clean_question_passes() -> None:
    assert rd.rejection_reason("What mitigations are recommended for T1055?", _spec()) is None


def test_an_explanation_instead_of_a_question_is_rejected() -> None:
    assert "too long" in rd.rejection_reason("T1055 " + "x" * 700, _spec())
    assert "more than one question" in rd.rejection_reason(
        "What mitigates T1055? And what detects it?", _spec()
    )


# --- the reported metric -----------------------------------------------------


def test_schema_overlap_separates_an_echo_from_a_paraphrase() -> None:
    spec = _spec()
    echo = rd.schema_overlap("Which Mitigation mitigates Technique T1055?", spec)
    para = rd.schema_overlap("How would a defender stop T1055 from working?", spec)
    assert echo > para
    assert 0.0 <= para < 0.2
