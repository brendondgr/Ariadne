#!/usr/bin/env python3
"""Merging both catalogues into one dataset (C-015).

The merged graph is a *baseline*, and a baseline that quietly differs from the
system it is compared against measures the difference rather than the question.
Three properties are therefore load-bearing here, and each has a way of failing
that still produces a plausible-looking graph.

**Nothing is lost or duplicated.** A merge is a concatenation; if it silently
drops a catalogue's relationships the merged arm just scores badly and the
conclusion reads "merging is worse".

**CAPEC nodes get the public identifier ATT&CK nodes already carry**, and get
*exactly* the one the federated system reports. Every Cypher query anchors on
``coalesce(n.attack_id, n.id)``, so without it a seed of ``CAPEC-66`` matches
nothing; with a differently-shaped one, gold assertions stop matching and the
arm looks wrong for a formatting reason.

**Nodes with no public form keep their raw id.** Inventing one would give the
merged arm identifiers the federated arms never emit, which is the same defect
in the opposite direction.
"""

from __future__ import annotations

import json

import pytest

from utils.kg_builder.merge import (
    PUBLIC_ID_PROPERTY,
    _merge_constraints,
    _merge_schema,
    build_merged,
    promote_public_id,
)

# -- the public-identifier promotion ----------------------------------------


@pytest.mark.parametrize(
    ("node_id", "expected"),
    [
        ("capec:attack-pattern:66", "CAPEC-66"),
        ("capec:attack-pattern:1", "CAPEC-1"),
        ("cwe:89", "CWE-89"),
    ],
)
def test_a_capec_node_gains_the_public_id_the_federated_path_reports(
    node_id: str, expected: str
) -> None:
    node = {"id": node_id, "label": "AttackPattern", "properties": {}}
    assert promote_public_id(node)["properties"][PUBLIC_ID_PROPERTY] == expected


@pytest.mark.parametrize(
    "node_id",
    [
        "capec:attack-pattern:100:mitigation:1",   # composite child
        "capec:attack-pattern:100:consequence:1",
        "capec:external-reference:REF-1",
    ],
)
def test_a_node_with_no_public_form_keeps_its_raw_id(node_id: str) -> None:
    """The Gremlin path reports these raw; the merged store must not differ."""
    node = {"id": node_id, "label": "Mitigation", "properties": {}}
    assert PUBLIC_ID_PROPERTY not in promote_public_id(node)["properties"]


def test_an_attack_node_is_returned_untouched() -> None:
    node = {
        "id": "attack-pattern--abc",
        "label": "Technique",
        "properties": {"attack_id": "T1047", "stix_type": "attack-pattern"},
    }
    assert promote_public_id(node) is node


def test_promotion_does_not_mutate_its_input() -> None:
    """The ATT&CK half must stay byte-identical to its source."""
    node = {"id": "capec:attack-pattern:66", "label": "AttackPattern", "properties": {}}
    before = json.dumps(node, sort_keys=True)
    promote_public_id(node)
    assert json.dumps(node, sort_keys=True) == before


# -- schema and constraint union --------------------------------------------


def test_the_schema_unions_labels_and_keeps_both_edge_patterns() -> None:
    merged = _merge_schema([
        {
            "node_labels": ["Technique", "Mitigation"],
            "relationship_types": ["MITIGATES"],
            "node_properties": {"Mitigation": ["attack_id"]},
        },
        {
            "node_labels": ["AttackPattern", "Mitigation"],
            "relationship_types": ["HAS_MITIGATION", "ChildOf"],
            "node_properties": {"Mitigation": ["description"]},
            "allowed_edge_patterns": {"HAS_MITIGATION": [["AttackPattern", "Mitigation"]]},
        },
    ])
    assert merged["node_labels"] == ["AttackPattern", "Mitigation", "Technique"]
    assert merged["relationship_types"] == ["ChildOf", "HAS_MITIGATION", "MITIGATES"]
    # The shared label carries both catalogues' properties, not one of them.
    assert merged["node_properties"]["Mitigation"] == ["attack_id", "description"]
    assert merged["allowed_edge_patterns"]["HAS_MITIGATION"] == [
        ["AttackPattern", "Mitigation"]
    ]


def test_constraints_that_require_the_same_thing_are_emitted_once() -> None:
    """Both catalogues ask for a unique Mitigation id under different names."""
    text = _merge_constraints([
        {"constraints": "CREATE CONSTRAINT a IF NOT EXISTS FOR (n:Mitigation) REQUIRE n.id IS UNIQUE;"},
        {"constraints": "CREATE CONSTRAINT b IF NOT EXISTS FOR (n:Mitigation) REQUIRE n.id IS UNIQUE;"},
    ])
    live = [ln for ln in text.splitlines() if ln and not ln.startswith("//")]
    assert len(live) == 1
    assert "CREATE CONSTRAINT a " in live[0]
    assert "dropped as a duplicate" in text   # the drop is recorded, not silent


# -- the whole build against the real catalogues -----------------------------


@pytest.fixture(scope="module")
def built():
    """Compute the merge from the committed canonical artifacts, writing nothing."""
    return build_merged(write=False)


def test_the_merge_is_the_sum_of_its_two_inputs(built) -> None:
    from utils.kg_builder.io import read_jsonl
    from utils.kg_builder.merge import SOURCES, canonical_dir
    from pathlib import Path

    expected_nodes = expected_edges = 0
    for dataset in SOURCES:
        canon = canonical_dir(Path("data"), dataset)
        expected_nodes += sum(1 for _ in read_jsonl(canon / "nodes.jsonl"))
        expected_edges += sum(1 for _ in read_jsonl(canon / "relationships.jsonl"))
    assert built["nodes"] == expected_nodes
    assert built["relationships"] == expected_edges


def test_the_public_id_promotion_covers_every_published_form(built) -> None:
    """558 attack patterns, 336 weaknesses, 261 taxonomy entries, 34 groupings.

    The ATT&CK taxonomy entries are what makes the cross-source join work: CAPEC
    stores the bare `1027.001` where ATT&CK stores `T1027.001`, so without the
    reconciliation the merged store retrieves the right mapping node and then
    cannot follow it.

    The other three groups were excluded while the federated path reported them
    raw, and both paths were wrong together. Categories and views share CAPEC's
    numbering (`capec:category:118` is CAPEC-118) and the other taxonomies
    publish `WASC:27` and `OWASP Attacks:<name>`. Composite children still keep
    their raw ids: the catalogue addresses them only through their parent, and
    giving each the parent's number would make every step claim to be the
    pattern.
    """
    assert built["public_ids_promoted"] == 558 + 336 + (189 + 39 + 33) + (21 + 13)


@pytest.mark.parametrize(
    ("taxonomy", "entry", "expected"),
    [
        ("ATTACK", "1027.001", "T1027.001"),
        ("ATTACK", "1059", "T1059"),
        ("ATTACK", "T1059", "T1059"),   # already prefixed: not double-prefixed
    ],
)
def test_an_attack_taxonomy_entry_is_reconciled_to_the_attack_form(
    taxonomy: str, entry: str, expected: str
) -> None:
    node = {
        "id": f"capec:taxonomy:{taxonomy}:{entry}",
        "label": "TaxonomyEntry",
        "properties": {"taxonomy_name": taxonomy, "entry_id": entry},
    }
    assert promote_public_id(node)["properties"][PUBLIC_ID_PROPERTY] == expected


def test_a_non_attack_taxonomy_entry_gets_its_own_published_form() -> None:
    """CAPEC also maps to WASC, and `WASC:12` is what that catalogue publishes.

    Only the ATT&CK mapping is a join key, but a WASC entry reported as
    `capec:taxonomy:WASC:12` is an identifier no gold assertion and no analyst
    can match — six development questions asked for exactly this and got the
    internal path (`EXP-2026-09-018`, I-12).
    """
    node = {
        "id": "capec:taxonomy:WASC:12",
        "label": "TaxonomyEntry",
        "properties": {"taxonomy_name": "WASC", "entry_id": "12"},
    }
    assert promote_public_id(node)["properties"][PUBLIC_ID_PROPERTY] == "WASC:12"


def test_a_category_and_a_view_share_capecs_published_numbering() -> None:
    """CAPEC-513 is a category and CAPEC-1000 a view: one numbering space."""
    for raw, public in (("capec:category:118", "CAPEC-118"),
                        ("capec:view:1000", "CAPEC-1000")):
        node = {"id": raw, "label": "Category", "properties": {}}
        assert promote_public_id(node)["properties"][PUBLIC_ID_PROPERTY] == public


def test_the_two_catalogues_share_exactly_one_label(built) -> None:
    """11 ATT&CK labels + 15 CAPEC labels, `Mitigation` in both.

    CAPEC went from 10 to 15 on 2026-09-01, when the five sub-element kinds the
    sources declare and the load had been dropping were materialized —
    Prerequisite, Indicator, Example, Resource, AlternateTerm. See
    EXP-2026-09-001 amendment A-3.
    """
    assert built["labels"] == 25


def test_colliding_node_ids_are_a_hard_failure(monkeypatch) -> None:
    """The merge assumes disjoint id spaces. If that ever stops being true, stop."""
    import utils.kg_builder.merge as merge

    def fake_read(data_dir, dataset):
        return {
            "dataset": dataset,
            "nodes": [{"id": "same", "label": "X", "properties": {}}],
            "relationships": [],
            "schema": {"node_labels": ["X"], "relationship_types": []},
            "manifest": {},
            "card": {},
            "constraints": "",
        }

    monkeypatch.setattr(merge, "_read_source", fake_read)
    with pytest.raises(ValueError, match="disjoint identifier spaces"):
        merge.build_merged(write=False)
