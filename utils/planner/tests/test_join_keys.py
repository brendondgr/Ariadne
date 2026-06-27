#!/usr/bin/env python3

from __future__ import annotations

from utils.planner.cards import SourceCardView
from utils.planner.join_keys import (
    is_declared,
    get_join_key,
    resolve_join_key,
)
from utils.planner.tests._fixtures import load_fixture_cards


def test_attack_technique_id_is_declared() -> None:
    assert is_declared("attack-technique-id")
    assert not is_declared("made-up-key")
    key = get_join_key("attack-technique-id")
    assert key is not None
    assert key.endpoint_for("capec").via_edge == "MAPS_TO"
    assert key.endpoint_for("attack").property == "attack_id"


def test_resolve_join_key_binds_attack_and_capec_fixtures() -> None:
    cards = load_fixture_cards()
    key = resolve_join_key(cards["attack"], cards["capec"])
    assert key is not None
    assert key.name == "attack-technique-id"
    # order-independent
    key2 = resolve_join_key(cards["capec"], cards["attack"])
    assert key2 is not None and key2.name == "attack-technique-id"


def test_resolve_returns_none_when_capec_lacks_maps_to() -> None:
    cards = load_fixture_cards()
    attack = cards["attack"]
    capec_no_bridge = SourceCardView.from_card_dict(
        {
            "dataset": "capec",
            "runtime_backend": "gremlin",
            "node_labels": ["AttackPattern", "TaxonomyEntry"],
            "relationship_types": ["EXPLOITS_WEAKNESS"],  # no MAPS_TO
        }
    )
    assert resolve_join_key(attack, capec_no_bridge) is None


def test_resolve_returns_none_when_attack_lacks_technique() -> None:
    cards = load_fixture_cards()
    capec = cards["capec"]
    attack_no_tech = SourceCardView.from_card_dict(
        {
            "dataset": "attack",
            "runtime_backend": "neo4j",
            "node_labels": ["Group", "Software"],  # no Technique/SubTechnique
            "relationship_types": ["USES"],
        }
    )
    assert resolve_join_key(attack_no_tech, capec) is None


def test_resolve_returns_none_for_same_dataset() -> None:
    cards = load_fixture_cards()
    assert resolve_join_key(cards["attack"], cards["attack"]) is None
