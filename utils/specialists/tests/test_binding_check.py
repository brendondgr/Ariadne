#!/usr/bin/env python3
"""The pre-run gate's binding check: what it rejects, and what it must not.

The check exists to stop one silent failure — a query filtering a property
against values that property can never hold, which returns nothing and reads as
"there are none". Most of this file is about the *other* direction, because a
guard that fires when it should not is worse than no guard: it would drop real
answers, and on a source whose identifiers nobody has learned it would drop all
of them.

Three refusals to fire are pinned here: on a disjunction where another branch
can match, on an unlearnable (opaque) property, and on a dataset the registry
has never seen.
"""

from __future__ import annotations

import pytest

from utils.specialists.binding import (
    Binding,
    binding_reasons,
    extract_bindings,
    unsatisfiable_bindings,
)
from utils.specialists.contracts import SpecialistTask
from utils.specialists.cypher.builder import CypherQueryBuilder
from utils.specialists.cypher.validator import CypherValidator
from utils.specialists.resolve import resolve
from utils.specialists.schema import get_registry
from utils.specialists.tests._fixtures import fixture_card

_LIMITS = {"max_result_rows": 300, "max_traversal_depth": 3, "query_timeout_ms": 5000}


def _real_data_present() -> bool:
    from pathlib import Path

    return Path("data/graphs/attack/canonical/nodes.jsonl").is_file()


pytestmark = pytest.mark.skipif(
    not _real_data_present(), reason="the check reads schemes learned from the snapshot"
)


def _draft(query: str, params: dict, template: str = "t", meta: dict | None = None):
    from utils.specialists.validation import QueryDraft

    return QueryDraft(query=query, params=params, template=template, meta=meta or {})


# -- it fires on the defect --------------------------------------------------


def test_the_holdout_query_is_rejected() -> None:
    draft = _draft(
        "MATCH (g:Group)-[:USES]->(t:Technique) WHERE g.attack_id IN $ids "
        "RETURN g.attack_id AS group_id",
        {"ids": ["T1550.002"]},
        "group_techniques",
    )
    reasons = binding_reasons(draft, "attack")
    assert len(reasons) == 1
    # The reason is repair feedback as well as a trace line, so it must say what
    # the property looks like and what the values actually identify.
    assert "Group.attack_id" in reasons[0]
    assert "g#" in reasons[0]
    assert "SubTechnique" in reasons[0]


def test_the_group_software_edge_is_answered_rather_than_refused() -> None:
    """This test used to assert the opposite, and the reason it changed matters.

    Its original comment read: "the router picks the Group template because
    Group was named, and no direction flip repairs it because the template does
    not walk that edge. The gate is what stops it executing." That was an
    accurate description of a gap — the gate was doing the only thing left to
    do with a question the builder could not express, which is refuse it.

    EXP-2026-08-010 measured what that cost on outside questions: four families
    at 0.000 against a 1.000 ceiling. `group_software` now walks the edge, so
    there is no misroute for the gate to catch and the question is answered.

    The gate itself is unchanged and is still exercised by
    `test_the_binding_gate_rejects_a_seed_bound_to_the_wrong_end` and the
    audit in test_binding_audit.py.
    """
    task = SpecialistTask(
        sub_question_id="q1",
        source="attack",
        text="Which groups relate to S0154?",
        entities=("Group", "Software"),
        limits=_LIMITS,
        seed_ids=("S0154",),
    )
    card = fixture_card("attack")
    draft = CypherQueryBuilder().build(resolve(task, card))
    result = CypherValidator().validate(draft, card, _LIMITS)
    assert draft.template == "group_software"
    assert result.ok, result.reasons
    assert "(g:Group)-[:USES]->(s:Software)" in result.query
    assert "s.attack_id IN $ids" in result.query


def test_the_repaired_reverse_direction_passes_the_gate() -> None:
    task = SpecialistTask(
        sub_question_id="q2",
        source="attack",
        text="Which groups use T1047?",
        entities=("Group", "Technique"),
        limits=_LIMITS,
        seed_ids=("T1047",),
    )
    card = fixture_card("attack")
    draft = CypherQueryBuilder().build(resolve(task, card))
    assert "t.attack_id IN $ids" in draft.query
    assert CypherValidator().validate(draft, card, _LIMITS).ok


# -- it stays silent when it should ------------------------------------------


def test_a_disjunction_survives_if_either_branch_can_match() -> None:
    # subtechnique_parent: seeded with a sub-technique id, the Technique branch
    # matches nothing and the SubTechnique branch matches exactly the right row.
    draft = _draft(
        "MATCH (t:Technique)-[:HAS_SUBTECHNIQUE]->(st:SubTechnique) "
        "WHERE t.attack_id IN $ids OR st.attack_id IN $ids RETURN t.attack_id",
        {"ids": ["T1059.001"]},
        "subtechnique_parent",
    )
    assert unsatisfiable_bindings(draft, "attack") == ()
    assert binding_reasons(draft, "attack") == []


def test_a_correct_query_is_untouched() -> None:
    draft = _draft(
        "MATCH (g:Group)-[:USES]->(t:Technique) WHERE g.attack_id IN $ids RETURN g",
        {"ids": ["G0082"]},
        "group_techniques",
    )
    assert binding_reasons(draft, "attack") == []


def test_a_mixed_parameter_is_not_rejected() -> None:
    # One seed fits, one does not: the query still returns real rows.
    draft = _draft(
        "MATCH (g:Group)-[:USES]->(t:Technique) WHERE g.attack_id IN $ids RETURN g",
        {"ids": ["G0082", "T1047"]},
        "group_techniques",
    )
    assert binding_reasons(draft, "attack") == []


def test_an_opaque_property_is_never_a_mismatch() -> None:
    # ATT&CK node ids are STIX UUIDs: unlearnable, so unjudgeable.
    draft = _draft(
        "MATCH (g:Group) WHERE g.id IN $ids RETURN g",
        {"ids": ["definitely-not-a-stix-id"]},
        "x",
    )
    assert binding_reasons(draft, "attack") == []


def test_an_unknown_dataset_is_never_a_mismatch() -> None:
    draft = _draft(
        "MATCH (g:Group) WHERE g.attack_id IN $ids RETURN g", {"ids": ["T1047"]}, "x"
    )
    assert binding_reasons(draft, "") == []
    assert binding_reasons(draft, "no-such-dataset") == []


def test_a_query_without_parameters_is_never_a_mismatch() -> None:
    draft = _draft("MATCH (g:Group)-[:USES]->(t:Technique) RETURN g", {}, "x")
    assert binding_reasons(draft, "attack") == []


# -- extraction paths --------------------------------------------------------


def test_gremlin_bindings_are_checked_too() -> None:
    draft = _draft(
        'g.V().hasLabel("Weakness").has("id", within(cweIds)).as("w")',
        {"cweIds": ["capec:attack-pattern:116"]},
        "cwe_chain",
    )
    assert binding_reasons(draft, "capec")


def test_a_declared_binding_is_honoured_over_the_query_text() -> None:
    draft = _draft(
        "OPAQUE LANGUAGE :: whatever",
        {"ids": ["T1047"]},
        "x",
        {"bindings": [{"label": "Group", "property": "attack_id", "param": "ids"}]},
    )
    assert extract_bindings(draft) == (Binding("Group", "attack_id", "ids", ("T1047",)),)
    assert binding_reasons(draft, "attack")


def test_the_registry_is_the_only_source_of_truth() -> None:
    # No MITRE knowledge is compiled in: the verdict comes from learned schemes.
    registry = get_registry()
    assert registry.value_verdict("Group", "attack_id", "T1047", dataset="attack") == "mismatch"
    assert registry.value_verdict("Group", "attack_id", "G0082", dataset="attack") == "consistent"
