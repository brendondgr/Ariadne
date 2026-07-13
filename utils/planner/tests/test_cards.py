#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils.planner.cards import (
    CardConsistencyError,
    SourceCardView,
    assert_card_consistency,
    load_source_cards,
)
from utils.planner.tests._fixtures import FIXTURE_DATA_DIR, load_fixture_cards


def test_load_fixture_cards_returns_both_datasets() -> None:
    cards = load_fixture_cards()
    assert set(cards) == {"attack", "capec"}
    assert cards["attack"].runtime_backend == "neo4j"
    assert cards["capec"].runtime_backend == "gremlin"


def test_structural_membership_is_routing_truth() -> None:
    attack = load_fixture_cards()["attack"]
    assert attack.has_label("Technique")
    assert attack.has_relationship("MITIGATES")
    assert attack.has_entity("USES")
    assert not attack.has_label("AttackPattern")  # that's CAPEC's
    assert attack.unknown_entities(["Technique", "Bogus", "USES"]) == ["Bogus"]


def test_enrichment_fills_limits_for_both_backends() -> None:
    cards = load_fixture_cards()
    for view in cards.values():
        limits = view.limits()
        assert limits["max_traversal_depth"] > 0
        assert limits["max_result_rows"] > 0
        assert limits["query_timeout_ms"] > 0


def test_card_view_exposes_canonical_derived_facets(tmp_path: Path) -> None:
    """The card view reaches the registry so the resolver/validators can consult
    real structure through the same handle the planner routes over."""
    from utils.specialists.schema import PlausibleFacet, get_registry

    canonical = tmp_path / "graphs" / "mini" / "canonical"
    canonical.mkdir(parents=True)
    (canonical / "nodes.jsonl").write_text(
        json.dumps({"id": "t1", "label": "Technique", "properties": {"attack_id": "T1", "name": "n"}}) + "\n"
        + json.dumps({"id": "m1", "label": "Mitigation", "properties": {"attack_id": "M1"}}) + "\n",
        encoding="utf-8",
    )
    (canonical / "relationships.jsonl").write_text(
        json.dumps({"id": "r1", "type": "MITIGATES", "source_id": "m1", "target_id": "t1"}) + "\n",
        encoding="utf-8",
    )
    get_registry.cache_clear()

    view = SourceCardView(
        dataset="mini",
        runtime_backend="neo4j",
        node_labels=frozenset({"Technique", "Mitigation"}),
        relationship_types=frozenset({"MITIGATES"}),
        node_properties={},
        allowed_edge_patterns={},
        safety={},
        provenance={},
        entity_descriptions={},
        connection={},
    )
    assert PlausibleFacet("MITIGATES", "in", "Mitigation") in view.label_facets("Technique", data_dir=tmp_path)
    assert view.label_property_keys("Technique", data_dir=tmp_path) == frozenset({"attack_id", "name"})
    get_registry.cache_clear()


def test_capec_allowed_edge_patterns_survive_enrichment() -> None:
    capec = load_fixture_cards()["capec"]
    assert "MAPS_TO" in capec.allowed_edge_patterns
    assert capec.allowed_edge_patterns["MAPS_TO"] == [["AttackPattern", "TaxonomyEntry"]]
    # numeric limits were layered on top of the generated structural keys.
    assert capec.safety["max_traversal_depth"] > 0


def test_consistency_passes_for_fixtures() -> None:
    for view in load_fixture_cards().values():
        assert_card_consistency(view)  # should not raise


def test_consistency_rejects_edge_pattern_with_unknown_label() -> None:
    bad = {
        "dataset": "capec",
        "runtime_backend": "gremlin",
        "node_labels": ["AttackPattern", "TaxonomyEntry"],
        "relationship_types": ["MAPS_TO"],
        "safety": {"allowed_edge_patterns": {"MAPS_TO": [["AttackPattern", "Ghost"]]}},
    }
    view = SourceCardView.from_card_dict(bad)
    with pytest.raises(CardConsistencyError):
        assert_card_consistency(view)


def test_consistency_rejects_edge_pattern_with_undeclared_relationship() -> None:
    bad = {
        "dataset": "capec",
        "runtime_backend": "gremlin",
        "node_labels": ["AttackPattern", "TaxonomyEntry"],
        "relationship_types": ["MAPS_TO"],
        "safety": {"allowed_edge_patterns": {"PHANTOM": [["AttackPattern", "TaxonomyEntry"]]}},
    }
    view = SourceCardView.from_card_dict(bad)
    with pytest.raises(CardConsistencyError):
        assert_card_consistency(view)


def test_load_missing_dir_returns_empty(tmp_path) -> None:
    assert load_source_cards(tmp_path) == {}


def test_real_generated_cards_enrich_when_present() -> None:
    """If the repo has been built, the real cards should enrich cleanly."""
    cards = load_source_cards("data")
    if not cards:
        pytest.skip("real source cards not built in this environment")
    for view in cards.values():
        assert_card_consistency(view)
        assert view.limits()["max_traversal_depth"] > 0
        assert view.provenance.get("id_scheme")
