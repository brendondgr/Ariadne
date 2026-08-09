#!/usr/bin/env python3
"""Prove the generic-primitive work changed nothing outside its own branch.

``freeze/holdout-v1`` pins the tree the blind holdout is measured against and
forbids behavioural change under ``utils/specialists/`` until it reports. The
Arm H primitives live under that path, so the freeze holds only if every one of
them is unreachable unless ``SPECIALIST_GENERIC_ONLY`` is set.

That is a claim about behaviour, not about intent, so it is tested rather than
asserted in a comment: with the flag unset, the builders must emit exactly the
query string the frozen tree emitted, for a spread of task shapes covering every
routing branch of the default cascade.

``fixtures/frozen_default_queries.json`` was captured by checking the tag out
into a scratch tree (``git archive freeze/holdout-v1``) and running its builders.
It must never be regenerated from the working tree — that would make this test
tautological. Regenerate it only from the tag, and only if the tag moves.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils.specialists.contracts import SpecialistTask
from utils.specialists.cypher.builder import CypherQueryBuilder
from utils.specialists.gremlin.builder import GremlinQueryBuilder
from utils.specialists.resolve import resolve
from utils.specialists.tests._fixtures import FIXTURES_DIR, fixture_card

FROZEN = json.loads((FIXTURES_DIR / "frozen_default_queries.json").read_text())

ARM_H_TEMPLATES = {
    "generic_bridge",
    "generic_chain",
    "generic_intersect",
    "generic_walk",
}


@pytest.fixture(autouse=True)
def templates_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """The default posture: hand-written templates on, generic branch off."""
    monkeypatch.delenv("SPECIALIST_GENERIC_ONLY", raising=False)


def _build(case: dict):
    source = case["source"]
    task = SpecialistTask(
        sub_question_id="q1",
        source=source,
        text=case["text"],
        entities=tuple(case["entities"]),
        **case["kw"],
    )
    resolved = resolve(task, fixture_card(source))
    builder = CypherQueryBuilder() if source == "attack" else GremlinQueryBuilder()
    return builder.build(resolved)


@pytest.mark.parametrize("case", FROZEN, ids=[c["template"] for c in FROZEN])
def test_default_query_is_identical_to_the_frozen_tree(case: dict) -> None:
    """Byte-for-byte, the frozen tree's query — template, string and params.

    A difference here means the generic branch leaked into the default path and
    every arm figure produced after ``freeze/holdout-v1`` is invalid.
    """
    draft = _build(case)

    assert draft.template == case["template"]
    assert draft.query == case["query"]
    assert draft.params == case["params"]


def test_no_arm_h_primitive_is_reachable_with_templates_enabled() -> None:
    """Sweep every case: not one Arm H template may be emitted by default."""
    emitted = {_build(case).template for case in FROZEN}

    assert not (emitted & ARM_H_TEMPLATES)


def test_the_flag_actually_changes_routing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Guard against the isolation test passing because the flag does nothing.

    If ``SPECIALIST_GENERIC_ONLY`` stopped being read, every assertion above
    would still pass while proving nothing at all.
    """
    monkeypatch.setenv("SPECIALIST_GENERIC_ONLY", "true")
    emitted = {_build(case).template for case in FROZEN}

    assert emitted & ARM_H_TEMPLATES


def test_the_frozen_baseline_covers_every_default_branch() -> None:
    """The fixture must exercise the cascade, not one lucky branch."""
    templates = {case["template"] for case in FROZEN}

    assert templates >= {
        "technique_mitigations",
        "technique_tactics",
        "technique_detection",
        "group_techniques",
        "capec_maps_to",
        "cwe_chain",
        "capec_reverse_maps",
        "capec_neighbors",
        "describe",
    }
