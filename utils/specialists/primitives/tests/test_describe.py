#!/usr/bin/env python3
"""Tests for the ``describe`` primitive: full properties + a bounded facet block.

Facet helpers are tested as pure functions; the per-backend normalizers are
tested with fabricated result rows (no live DB) so the suite is hermetic. The
central guarantees the plan rests on are pinned here: **every** property survives
(no allow-list), the facet block is a bounded count (a hub with an 858-neighbour
facet is one row, not 858), inbound edges are visible from the target side (the
Tacos/Lettuce bidirectionality), and a zero-degree node carries no positive
facet.
"""

from __future__ import annotations

import json

from utils.specialists.cypher.normalizer import CypherNormalizer
from utils.specialists.gremlin.normalizer import GremlinNormalizer
from utils.specialists.primitives.describe import (
    Facet,
    facets_from_count_rows,
    fold_facets,
    merge_zero_facets,
)
from utils.specialists.resolve import ResolvedTask
from utils.specialists.schema.registry import PlausibleFacet
from utils.specialists.contracts import SpecialistTask
from utils.specialists.tests._fixtures import fixture_card


# -- pure facet helpers ------------------------------------------------------


def test_fold_facets_counts_per_edge_tuples() -> None:
    facets = fold_facets(
        [
            ("MITIGATES", "in", "Mitigation"),
            ("MITIGATES", "in", "Mitigation"),
            ("HAS_SUBTECHNIQUE", "out", "SubTechnique"),
            ("", "out", "X"),  # missing rel is skipped
        ]
    )
    assert Facet("MITIGATES", "in", "Mitigation", 2) in facets
    assert Facet("HAS_SUBTECHNIQUE", "out", "SubTechnique", 1) in facets
    assert all(f.rel_type for f in facets)
    assert facets == sorted(facets)  # deterministic order


def test_facets_from_count_rows_maps_outgoing_to_direction() -> None:
    rows = [
        {"rel": "MITIGATES", "outgoing": False, "label": "Mitigation", "count": 3},
        {"rel": "HAS_SUBTECHNIQUE", "outgoing": True, "label": "SubTechnique", "count": 13},
        {"rel": "", "outgoing": True, "label": "X", "count": 1},  # skipped
    ]
    facets = facets_from_count_rows(rows)
    assert Facet("MITIGATES", "in", "Mitigation", 3) in facets
    assert Facet("HAS_SUBTECHNIQUE", "out", "SubTechnique", 13) in facets
    assert len(facets) == 2


def test_merge_zero_facets_folds_plausible_as_honest_zeros() -> None:
    observed = [Facet("MITIGATES", "in", "Mitigation", 5)]
    plausible = [
        PlausibleFacet("MITIGATES", "in", "Mitigation"),  # observed -> keeps count 5
        PlausibleFacet("HAS_SUBTECHNIQUE", "out", "SubTechnique"),  # unobserved -> 0
    ]
    merged = merge_zero_facets(observed, plausible)
    by_key = {f.key(): f.count for f in merged}
    assert by_key[("MITIGATES", "in", "Mitigation")] == 5  # observed wins
    assert by_key[("HAS_SUBTECHNIQUE", "out", "SubTechnique")] == 0  # honest zero


# -- Cypher describe normalizer ---------------------------------------------


def _resolved(dataset: str, seed_ids=(), text: str = "describe") -> ResolvedTask:
    task = SpecialistTask(sub_question_id="q", source=dataset, text=text, entities=(), seed_ids=tuple(seed_ids))
    return ResolvedTask(task=task, dataset=dataset, seed_ids=tuple(seed_ids))


def _cypher_row(aid, name, props, facets):
    return {"id": aid, "name": name, "properties_json": json.dumps(props), "facets": facets}


def test_cypher_describe_returns_every_property_and_facets() -> None:
    card = fixture_card("attack")
    props = {
        "attack_id": "T1055",
        "description": "Adversaries may inject code…",
        "external_references": [{"external_id": "T1055"}],
        "x_mitre_platforms": ["Windows"],
    }
    row = _cypher_row(
        "T1055", "Process Injection", props,
        [
            {"rel": "MITIGATES", "outgoing": False, "label": "Mitigation", "count": 3},
            {"rel": "HAS_SUBTECHNIQUE", "outgoing": True, "label": "SubTechnique", "count": 13},
        ],
    )
    [rec] = CypherNormalizer().normalize([row], _resolved("attack", ("T1055",)), "q", card)
    # every property survives — description AND the bulky external_references
    assert rec.properties["description"].startswith("Adversaries")
    assert set(props).issubset(rec.properties)
    # facet block present; describe carries counts, never a neighbour list
    facet_keys = {(f["rel"], f["direction"], f["label"]): f["count"] for f in rec.facets}
    assert facet_keys[("MITIGATES", "in", "Mitigation")] == 3
    assert facet_keys[("HAS_SUBTECHNIQUE", "out", "SubTechnique")] == 13
    assert rec.related == []


def test_cypher_describe_hub_facet_is_bounded_not_expanded() -> None:
    # An 858-neighbour facet is a SINGLE row carrying count 858 — the whole point
    # of the facet block. The record must not materialise 858 neighbours.
    card = fixture_card("attack")
    row = _cypher_row(
        "T1057", "Process Discovery", {"attack_id": "T1057", "description": "d"},
        [{"rel": "USES", "outgoing": False, "label": "Software", "count": 858}],
    )
    [rec] = CypherNormalizer().normalize([row], _resolved("attack", ("T1057",)), "q", card)
    hub = next(f for f in rec.facets if f["rel"] == "USES" and f["label"] == "Software")
    assert hub["count"] == 858 and hub["direction"] == "in"
    assert rec.related == []
    # Facet rows are bounded by distinct facet KINDS, never by degree.
    assert len(rec.facets) < 50


def test_cypher_describe_bidirectionality_tacos_lettuce() -> None:
    # Given A -[CONTAINS]-> B, describe(B) must surface the INBOUND CONTAINS facet
    # (outgoing False). This is the regression the Gremlin dossier lost.
    card = fixture_card("attack")
    row = _cypher_row(
        "B", "Lettuce", {"attack_id": "B"},
        [{"rel": "CONTAINS", "outgoing": False, "label": "Dish", "count": 1}],
    )
    [rec] = CypherNormalizer().normalize([row], _resolved("attack", ("B",)), "q", card)
    inbound = [f for f in rec.facets if f["rel"] == "CONTAINS"]
    assert inbound == [{"rel": "CONTAINS", "direction": "in", "label": "Dish", "count": 1}]


def test_cypher_describe_zero_degree_has_no_positive_facet() -> None:
    card = fixture_card("attack")
    row = _cypher_row("M9999", "Lonely Mitigation", {"attack_id": "M9999"}, [])
    [rec] = CypherNormalizer().normalize([row], _resolved("attack", ("M9999",)), "q", card)
    # May carry plausible zeros (registry-dependent), but never a positive count.
    assert all(f["count"] == 0 for f in rec.facets)
    assert rec.related == []


# -- Gremlin describe normalizer --------------------------------------------


def test_gremlin_describe_folds_edges_into_bidirectional_facets() -> None:
    card = fixture_card("capec")
    row = {
        "node": {"id": "capec:attack-pattern:66", "name": "SQL Injection",
                 "label": "AttackPattern", "Abstraction": "Standard"},
        "out": [
            {"rel": "HAS_MITIGATION", "label": "Mitigation"},
            {"rel": "HAS_MITIGATION", "label": "Mitigation"},
        ],
        "in": [{"rel": "CAN_FOLLOW", "label": "AttackPattern"}],
    }
    [rec] = GremlinNormalizer().normalize([row], _resolved("capec"), "q", card)
    assert rec.primary_id == "CAPEC-66"
    assert rec.properties.get("Abstraction") == "Standard"  # full props, no allow-list
    facet_keys = {(f["rel"], f["direction"], f["label"]): f["count"] for f in rec.facets}
    assert facet_keys[("HAS_MITIGATION", "out", "Mitigation")] == 2
    assert facet_keys[("CAN_FOLLOW", "in", "AttackPattern")] == 1
    assert rec.related == []
