#!/usr/bin/env python3
"""The Software↔Group and Software↔Campaign edges, and the widened target (EXP-2026-08-012).

Two defects EXP-2026-08-010 found on external questions. Both are about
coverage rather than correctness: the graph held the answer and the builder had
no way to ask for it.

The dispatch tests matter more than the query tests. Adding branches to a long
if-chain is how a question that already worked quietly starts going somewhere
else, so the paths that must NOT change are pinned here alongside the ones that
must.
"""

from __future__ import annotations

import pytest

from utils.specialists.cypher.builder import CypherQueryBuilder
from utils.specialists.resolve import resolve
from utils.specialists.tests._fixtures import fixture_card, make_task


def _draft(text: str, entities: list[str]):
    card = fixture_card("attack")
    task = make_task(entities=tuple(entities), text=text)
    return CypherQueryBuilder().build(resolve(task, card))


# -- the new edge ------------------------------------------------------------


def test_a_group_is_asked_for_its_software_not_its_techniques() -> None:
    """The defect exactly: this used to route to `group_techniques`."""
    draft = _draft("What software are used by attack group 'G0003: Cutting Kitten'?",
                   ["Group", "Software", "USES"])
    assert draft.template == "group_software"
    assert "(g:Group)-[:USES]->(s:Software)" in draft.query


def test_the_same_edge_answers_from_the_software_end() -> None:
    draft = _draft("What attack groups used software 'S0089: BlackEnergy'?",
                   ["Software", "Group", "USES"])
    assert draft.template == "group_software"
    assert "(g:Group)-[:USES]->(s:Software)" in draft.query


def test_a_campaign_is_asked_for_its_software() -> None:
    draft = _draft("What software was used in campaign 'C0028: 2015 Ukraine'?",
                   ["Campaign", "Software", "USES"])
    assert draft.template == "campaign_software"
    assert "(c:Campaign)-[:USES]->(s:Software)" in draft.query


def test_the_campaign_edge_answers_from_the_software_end() -> None:
    draft = _draft("What campaigns used software 'S0089: BlackEnergy'?",
                   ["Software", "Campaign", "USES"])
    assert draft.template == "campaign_software"


# -- the widened target ------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "entities", "template"),
    [
        ("What attack techniques are used by attack group 'G0020: Equation'?",
         ["Group", "Technique", "USES"], "group_techniques"),
        ("What attack techniques were used in campaign 'C0028: 2015 Ukraine'?",
         ["Campaign", "Technique", "USES"], "campaign_techniques"),
    ],
)
def test_an_actor_anchored_technique_ask_still_returns_top_level_only(
    text: str, entities: list[str], template: str
) -> None:
    """Deliberately unchanged, and this test is here to say so.

    EXP-2026-08-010 measured these two families at 0.295 and 0.326 against a
    ~0.99 ceiling, because the pinned `(t:Technique)` target drops every
    sub-technique. Widening it raises both to ~0.98 — but it is not a bug fix.
    `evalset/questions.py::_top_level` filters the gold for exactly these three
    templates to parent techniques, so the narrow answer is a deliberate
    roll-up, and the two external benchmarks disagree with each other about it:
    CTIBench's cti-ate prompt says "excluding any subtechnique IDs" while
    AttackQA lists them.

    Changing it is a product decision that moves recorded query strings and the
    execution-accuracy gold, so it is left to a decision rather than taken here.
    See EXP-2026-08-012 ISSUES.md I1.
    """
    draft = _draft(text, entities)
    assert draft.template == template
    assert "(t:Technique)" in draft.query


# -- what must NOT have moved ------------------------------------------------


@pytest.mark.parametrize(
    ("text", "entities", "template"),
    [
        # The direction this project's own banks actually ask, in every one of
        # the three template families the fix touches. If any of these moves,
        # a recorded figure moves with it.
        ("Which groups use T1012 (Query Registry)?",
         ["Technique", "Group", "USES"], "group_techniques"),
        ("Which groups use T1003.006 (DCSync)?",
         ["Technique", "Group", "USES"], "group_techniques"),
        ("Which software is observed implementing T1134.003 (Make and Impersonate Token)?",
         ["Technique", "Software", "USES"], "software_techniques"),
        ("What attack techniques are used by software 'S0066: 3PARA RAT'?",
         ["Software", "Technique", "USES"], "software_techniques"),
        # Campaign+Group must still be attribution, not either new branch.
        ("Which campaigns were attributed to attack group 'G0034: Sandworm Team'?",
         ["Group", "Campaign", "ATTRIBUTED_TO"], "campaign_attribution"),
        ("What is the parent technique of T1055.002 (Portable Executable Injection)?",
         ["Technique", "SubTechnique", "HAS_SUBTECHNIQUE"], "subtechnique_parent"),
    ],
)
def test_an_existing_route_is_unchanged(text: str, entities: list[str], template: str) -> None:
    assert _draft(text, entities).template == template


def test_all_three_labels_named_still_routes_to_the_technique_path() -> None:
    """The new branches are gated on `not has_technique_entity` precisely so a
    task naming Group, Software and Technique keeps its old destination."""
    draft = _draft("Which groups and software use T1105?",
                   ["Group", "Software", "Technique", "USES"])
    assert draft.template == "group_techniques"
