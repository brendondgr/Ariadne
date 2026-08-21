#!/usr/bin/env python3
"""The binding audit: extraction fidelity, and the inventory it currently finds.

Two things are tested here and they have different lifetimes.

The **extraction** tests are permanent: they pin the parsers that turn a query
string back into ``(label, property, bound values)``, in both languages, and the
declaration path that will supersede them.

The **inventory** tests are characterisation tests — they record the defect as
it stands *before* the repair, so that the repair has something to move. They are
expected to be rewritten by the step that fixes the cascade, and the rewrite is
the point: an inventory assertion that never changes is an inventory nobody
fixed.

The audit executes nothing, so none of this needs a database.
"""

from __future__ import annotations

import pytest

from utils.specialists.audit.binding_audit import (
    KIND_MISMATCH,
    KIND_UNCHECKED,
    AuditCase,
    Binding,
    audit_bindings,
    enumerate_cases,
    extract_bindings,
    seed_vocabulary,
)
from utils.specialists.contracts import SpecialistTask
from utils.specialists.cypher.builder import CypherQueryBuilder
from utils.specialists.resolve import resolve
from utils.specialists.schema import get_registry
from utils.specialists.tests._fixtures import fixture_card
from utils.specialists.validation import QueryDraft

# Extra CAPEC anchors: the committed CAPEC bank only ever seeds CAPEC ids, so
# without these the Gremlin side of the audit never sees a CWE or ATT&CK anchor.
_CAPEC_EXTRA = ("CWE-1243", "T1003")


@pytest.fixture(scope="module")
def report():
    return audit_bindings(extra_seeds={"capec": _CAPEC_EXTRA})


# -- extraction --------------------------------------------------------------


def test_cypher_binding_is_recovered_with_its_label() -> None:
    draft = QueryDraft(
        query=(
            "MATCH (g:Group)-[:USES]->(t:Technique) WHERE g.attack_id IN $ids "
            "RETURN g.attack_id AS group_id"
        ),
        params={"ids": ["T1047"]},
        template="group_techniques",
    )
    assert extract_bindings(draft) == (Binding("Group", "attack_id", "ids", ("T1047",)),)


def test_cypher_equality_binding_is_recovered() -> None:
    draft = QueryDraft(
        query="MATCH (m:Mitigation) WHERE m.attack_id = $mid RETURN m",
        params={"mid": "M1038"},
        template="x",
    )
    assert extract_bindings(draft) == (Binding("Mitigation", "attack_id", "mid", ("M1038",)),)


def test_gremlin_binding_carries_the_nearest_haslabel() -> None:
    draft = QueryDraft(
        query=(
            'g.V().hasLabel("AttackPattern").has("id", within(ids)).as("ap")'
            '.out("MAPS_TO").hasLabel("TaxonomyEntry").has("taxonomy_name","ATTACK")'
        ),
        params={"ids": ["capec:attack-pattern:1"]},
        template="capec_maps_to",
    )
    assert extract_bindings(draft) == (
        Binding("AttackPattern", "id", "ids", ("capec:attack-pattern:1",)),
    )


def test_a_declared_binding_wins_over_parsing() -> None:
    # The durable mechanism: a builder states its own bindings, so a query
    # language these parsers have never seen is still checkable.
    draft = QueryDraft(
        query="SOME OTHER LANGUAGE :: filter(node.uid, $ids)",
        params={"ids": ["dev-1001"]},
        template="whatever",
        meta={"bindings": [{"label": "Device", "property": "uid", "param": "ids"}]},
    )
    assert extract_bindings(draft) == (Binding("Device", "uid", "ids", ("dev-1001",)),)


def test_a_query_with_no_parameters_binds_nothing() -> None:
    draft = QueryDraft(
        query="MATCH (g:Group)-[:USES]->(t:Technique) RETURN g.attack_id",
        params={},
        template="group_techniques",
    )
    assert extract_bindings(draft) == ()


# -- fidelity: the audit's synthetic case reproduces the real path -----------


def test_the_audit_case_matches_what_the_resolver_produces() -> None:
    """The audit builds ``ResolvedTask`` directly; prove that is not a shortcut.

    If the synthetic case emitted a different query than a real question does,
    every finding would be an artefact of the harness.
    """
    task = SpecialistTask(
        sub_question_id="q1",
        source="attack",
        text="Which groups use T1047?",
        entities=("Group", "Technique"),
        seed_ids=("T1047",),
    )
    real = CypherQueryBuilder().build(resolve(task, fixture_card("attack")))
    synthetic = CypherQueryBuilder().build(
        AuditCase("attack", ("Group", "Technique"), (), ("T1047",)).resolved()
    )
    assert synthetic.template == real.template
    assert synthetic.query == real.query
    assert synthetic.params == real.params


# -- the case space ----------------------------------------------------------


def test_seed_vocabulary_keeps_one_exemplar_per_family() -> None:
    seeds = seed_vocabulary("attack")
    # Technique and sub-technique are different families; two T-ids of the same
    # family are not.
    assert any(s.startswith("T") and "." not in s for s in seeds)
    assert any("." in s for s in seeds)
    assert len(seeds) == len(set(seeds))
    # The catalogue mentions dozens of technique ids; the vocabulary must not.
    assert len(seeds) < 15


def test_extra_seeds_widen_a_thin_catalogue() -> None:
    base = seed_vocabulary("capec")
    widened = seed_vocabulary("capec", _CAPEC_EXTRA)
    assert set(base) < set(widened)


def test_the_case_space_covers_scopes_the_catalogue_never_asks() -> None:
    registry = get_registry()
    scopes = {case.labels for case in enumerate_cases("attack", registry)}
    # A schema triple in both label orders — the reverse-direction shapes a
    # co-authored catalogue is blind to by construction.
    assert ("Group", "Technique") in scopes
    assert ("Technique", "Group") in scopes


# -- coverage ----------------------------------------------------------------


def test_every_parameterised_draft_is_actually_checked(report) -> None:
    # The guard on the guard: an unchecked draft means a query bound values that
    # nothing verified, which would make a clean report meaningless.
    assert report.of_kind(KIND_UNCHECKED) == []
    assert report.bindings >= report.drafts


# -- inventory ---------------------------------------------------------------


def test_the_holdout_defect_is_gone(report) -> None:
    """`group_techniques` seeded with a technique id no longer filters Group ids."""
    hits = [
        f
        for f in report.of_kind(KIND_MISMATCH)
        if f.template == "group_techniques" and f.seed_ids in (("T1047",), ("T1021.001",))
    ]
    assert hits == []


def test_no_reverse_direction_ask_is_left_unserved(report) -> None:
    """What survives is misrouting, not direction.

    A finding whose seed label is in scope but whose template walks a different
    edge entirely — Group+Software seeded with a Software id — is not a
    direction defect and no flip can repair it. The gate rejects those, so they
    surface as an honest refusal rather than an empty answer, and they are
    listed here so the residue stays visible.
    """
    residue = {(f.template, f.seed_ids[0]) for f in report.in_scope()}
    assert residue == {
        ("tactic_techniques", "M1038"),
    }
