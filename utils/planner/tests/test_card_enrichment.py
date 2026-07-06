#!/usr/bin/env python3

from __future__ import annotations

from utils.planner.card_enrichment import default_safety_for_backend, enrich


def test_attack_enrichment_fills_authored_sections() -> None:
    card = {
        "dataset": "attack",
        "runtime_backend": "neo4j",
        "node_labels": ["Technique"],
        "relationship_types": ["USES"],
        "connection": {},
        "safety": {},
        "provenance": {},
        "entity_descriptions": {},
    }
    out = enrich(card)
    assert out["connection"]["backend"] == "neo4j"
    assert out["provenance"]["id_scheme"] == "attack-id"
    assert out["safety"]["read_only"] is True
    assert "CREATE" in out["safety"]["disallowed_clauses"]
    assert out["entity_descriptions"]["nodes"]["Technique"]


def test_gremlin_enrichment_uses_disallowed_steps() -> None:
    card = {"dataset": "capec", "runtime_backend": "gremlin", "node_labels": ["AttackPattern"], "relationship_types": []}
    out = enrich(card)
    assert "addV" in out["safety"]["disallowed_steps"]
    assert out["connection"]["traversal_source"] == "g"


def test_existing_nonempty_section_wins() -> None:
    card = {
        "dataset": "attack",
        "runtime_backend": "neo4j",
        "node_labels": ["Technique"],
        "relationship_types": [],
        "provenance": {"id_scheme": "custom-scheme"},
    }
    out = enrich(card)
    assert out["provenance"]["id_scheme"] == "custom-scheme"


def test_generated_safety_keys_layer_over_defaults() -> None:
    card = {
        "dataset": "capec",
        "runtime_backend": "gremlin",
        "node_labels": ["AttackPattern", "TaxonomyEntry"],
        "relationship_types": ["MAPS_TO"],
        "safety": {"allowed_edge_patterns": {"MAPS_TO": [["AttackPattern", "TaxonomyEntry"]]}},
    }
    out = enrich(card)
    # generated structural key preserved...
    assert "allowed_edge_patterns" in out["safety"]
    # ...and numeric defaults still present.
    assert out["safety"]["max_result_rows"] == 1000


def test_unknown_dataset_still_gets_backend_safety_defaults() -> None:
    card = {"dataset": "mystery", "runtime_backend": "neo4j", "node_labels": ["X"], "relationship_types": []}
    out = enrich(card)
    assert out["safety"]["max_traversal_depth"] == 3
    assert out["connection"] == {}  # no authored connection for unknown dataset


def test_default_safety_for_backend_distinct_per_backend() -> None:
    assert "disallowed_clauses" in default_safety_for_backend("neo4j")
    assert "disallowed_steps" in default_safety_for_backend("gremlin")
    assert "disallowed_clauses" not in default_safety_for_backend("gremlin")


def test_card_limits_agree_with_specialist_env_defaults() -> None:
    """Integration seam guard: the planner gate and the specialist connectors
    must draw the same bounds — a card/env mismatch is a latent integration bug."""
    from pathlib import Path

    from utils.specialists.config import SpecialistConfig

    spec = SpecialistConfig(data_dir=Path("data"))
    for backend in ("neo4j", "gremlin"):
        safety = default_safety_for_backend(backend)
        assert safety["max_result_rows"] == spec.max_result_rows
        assert safety["query_timeout_ms"] == spec.query_timeout_ms
        assert safety["max_traversal_depth"] > 0
