#!/usr/bin/env python3
"""Direction resolution: the reverse ask is served, the forward ask is untouched.

The second half is the one that needs proving. Arm-figure comparability rests on
the default cascade emitting exactly what it emitted at ``freeze/holdout-v1``,
so every forward-direction shape here is asserted **byte-identical** to the
string the templates carried before this change. The repair may only reach task
shapes that previously emitted a query no row could satisfy.

``test_generic_only_isolation.py`` makes the same guarantee against the frozen
fixture for ten routing shapes; this file states it in terms of the specific
templates that were changed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from utils.specialists.contracts import SpecialistTask
from utils.specialists.cypher.builder import CypherQueryBuilder
from utils.specialists.direction import AnchorBinding, resolve_anchor
from utils.specialists.resolve import resolve
from utils.specialists.tests._fixtures import fixture_card

pytestmark = pytest.mark.skipif(
    not Path("data/graphs/attack/canonical/nodes.jsonl").is_file(),
    reason="direction is resolved from schemes learned from the snapshot",
)

_LIMITS = {"max_result_rows": 300, "max_traversal_depth": 3, "query_timeout_ms": 5000}

# What each changed template emitted before direction resolution existed. These
# strings are the comparability contract; they are not regenerated from code.
_FROZEN_FORWARD = {
    "group_techniques": (
        "MATCH (g:Group)-[:USES]->(t:Technique) WHERE g.attack_id IN $ids "
        "RETURN g.attack_id AS group_id, g.name AS group_name, "
        "t.attack_id AS technique_id, t.name AS technique_name"
    ),
    "campaign_techniques": (
        "MATCH (c:Campaign)-[:USES]->(t:Technique) WHERE c.attack_id IN $ids "
        "RETURN c.attack_id AS campaign_id, c.name AS campaign_name, "
        "t.attack_id AS technique_id, t.name AS technique_name"
    ),
    "campaign_attribution": (
        "MATCH (c:Campaign)-[:ATTRIBUTED_TO]->(g:Group) WHERE c.attack_id IN $ids "
        "RETURN c.attack_id AS campaign_id, c.name AS campaign_name, "
        "g.attack_id AS group_id, g.name AS group_name"
    ),
    "tactic_techniques": (
        "MATCH (ta:Tactic)-[:HAS_TECHNIQUE]->(t:Technique) WHERE ta.attack_id IN $ids "
        "RETURN ta.attack_id AS tactic_id, ta.name AS tactic_name, "
        "t.attack_id AS technique_id, t.name AS technique_name"
    ),
    "software_techniques": (
        "MATCH (s:Software)-[:USES]->(t) WHERE (t:Technique OR t:SubTechnique) "
        "AND s.attack_id IN $ids "
        "RETURN s.attack_id AS software_id, s.name AS software_name, "
        "t.attack_id AS technique_id, t.name AS technique_name"
    ),
}


def _build(text: str, entities: tuple[str, ...], seeds: tuple[str, ...]):
    task = SpecialistTask(
        sub_question_id="q",
        source="attack",
        text=text,
        entities=entities,
        limits=_LIMITS,
        seed_ids=seeds,
    )
    return CypherQueryBuilder().build(resolve(task, fixture_card("attack")))


# -- the anchor resolver -----------------------------------------------------


def test_the_seed_places_the_anchor() -> None:
    aliases = {"Group": "g", "Technique": "t"}
    assert resolve_anchor(("G0082",), aliases, "attack") == AnchorBinding(
        "Group", "g", "attack_id"
    )
    assert resolve_anchor(("T1047",), aliases, "attack") == AnchorBinding(
        "Technique", "t", "attack_id"
    )


def test_an_anchor_outside_the_template_is_not_resolved() -> None:
    # A software id in a Group/Technique template: no repair is licensed, so the
    # template keeps its default and the gate rejects the draft.
    assert resolve_anchor(("S0154",), {"Group": "g", "Technique": "t"}, "attack") is None


def test_mixed_seeds_resolve_to_nothing() -> None:
    aliases = {"Group": "g", "Technique": "t"}
    assert resolve_anchor(("G0082", "T1047"), aliases, "attack") is None


def test_an_unknown_dataset_resolves_to_nothing() -> None:
    assert resolve_anchor(("T1047",), {"Group": "g"}, "no-such-dataset") is None
    assert resolve_anchor(("T1047",), {"Group": "g"}, "") is None


# -- forward direction: byte-identical ---------------------------------------


@pytest.mark.parametrize(
    "template,text,entities,seeds",
    [
        ("group_techniques", "Which techniques does G0082 use?", ("Group", "Technique"), ("G0082",)),
        ("campaign_techniques", "Which techniques does C0027 use?", ("Campaign", "Technique"), ("C0027",)),
        ("campaign_attribution", "Which group is C0027 attributed to?", ("Campaign", "Group"), ("C0027",)),
        ("tactic_techniques", "Which techniques are in TA0006?", ("Tactic", "Technique"), ("TA0006",)),
        ("software_techniques", "Which techniques does S0154 use?", ("Software", "Technique"), ("S0154",)),
    ],
)
def test_forward_direction_is_unchanged(template, text, entities, seeds) -> None:
    draft = _build(text, entities, seeds)
    assert draft.template == template
    assert draft.query == _FROZEN_FORWARD[template]
    assert draft.params == {"ids": list(seeds)}


# -- reverse direction: now served -------------------------------------------


@pytest.mark.parametrize(
    "template,text,entities,seeds,expected_filter",
    [
        ("group_techniques", "Which groups use T1047?", ("Group", "Technique"), ("T1047",), "t.attack_id IN $ids"),
        ("campaign_techniques", "Which campaigns use T1047?", ("Campaign", "Technique"), ("T1047",), "t.attack_id IN $ids"),
        ("campaign_attribution", "Which campaigns are attributed to G0082?", ("Campaign", "Group"), ("G0082",), "g.attack_id IN $ids"),
        ("software_techniques", "Which software uses T1047?", ("Software", "Technique"), ("T1047",), "t.attack_id IN $ids"),
    ],
)
def test_reverse_direction_binds_the_other_end(
    template, text, entities, seeds, expected_filter
) -> None:
    draft = _build(text, entities, seeds)
    assert draft.template == template
    assert expected_filter in draft.query


def test_a_subtechnique_anchor_widens_the_pinned_target_label() -> None:
    # Groups use sub-techniques, but the template pinned (t:Technique) and no
    # sub-technique id can satisfy Technique.attack_id.
    draft = _build("Which groups use T1021.001?", ("Group", "Technique"), ("T1021.001",))
    assert draft.template == "group_techniques"
    assert "MATCH (g:Group)-[:USES]->(t) " in draft.query
    assert "(t:Technique OR t:SubTechnique) AND t.attack_id IN $ids" in draft.query


def test_the_reverse_ask_used_to_be_unsatisfiable() -> None:
    """State the defect this repairs, so the test explains itself in a year."""
    from utils.specialists.binding import binding_reasons
    from utils.specialists.validation import QueryDraft

    before = QueryDraft(
        query=_FROZEN_FORWARD["group_techniques"],
        params={"ids": ["T1047"]},
        template="group_techniques",
    )
    assert binding_reasons(before, "attack")  # the old query, rejected
    after = _build("Which groups use T1047?", ("Group", "Technique"), ("T1047",))
    assert binding_reasons(after, "attack") == []
