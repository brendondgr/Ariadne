#!/usr/bin/env python3
"""A dataset that arrived with a source card is served by the card's backend.

The Synapse transfer (docs/plans/2026-09-16-synapse-graph-transfer.md) makes a
copied ``export-ariadne`` directory a source. These tests pin the runtime half
of that: the card loads and passes the consistency check with the enrichment
defaults for its backend, ``build_specialist`` dispatches on the card rather
than on a name, the per-dataset endpoint override reaches a hyphenated dataset
name, and the anchor resolver degrades to name-only anchoring for ids it has
no scheme for — it never guesses a MITRE label for an opaque id.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils.planner.cards import SourceCardView, load_source_cards
from utils.specialists import build_specialist
from utils.specialists.config import SpecialistConfig
from utils.specialists.contracts import SpecialistTask
from utils.specialists.cypher.specialist import build_cypher_specialist
from utils.specialists.gremlin.specialist import build_gremlin_specialist
from utils.specialists.resolve.resolver import (
    KIND_TITLE,
    ResolvedAnchor,
    infer_label,
    resolve_anchor,
)

DATASET = "mnp-cs-03000-r2"


def _exported_card(backend: str = "neo4j") -> dict:
    """The shape Synapse's ``export-ariadne`` writes, with nothing authored."""
    return {
        "dataset": DATASET,
        "canonical_manifest": f"data/graphs/{DATASET}/canonical/manifest.json",
        "schema_version": "1.0",
        "runtime_backend": backend,
        "node_labels": ["Condition", "MolecularMarker", "PolymerType"],
        "relationship_types": ["affects_marker", "leads_to"],
        "node_properties": {"PolymerType": {"id": {"type": "string", "optional": False, "example": "node-1"}}},
        "canonical_dir": f"data/graphs/{DATASET}/canonical",
        "exports": {},
        "endpoints": {"neo4j": "", "gremlin": ""},
        "connection": {},
        "safety": {
            "allowed_edge_patterns": {
                "affects_marker": [["PolymerType", "MolecularMarker"]],
                "leads_to": [["MolecularMarker", "Condition"]],
            }
        },
        "provenance": {"source_system": "synapse", "id_scheme": "opaque"},
        "entity_descriptions": {"nodes": {"PolymerType": "A polymer."}, "relationships": {}},
        "identity": {"join_key": ["id"], "unique_backstop": "id", "constraints": []},
    }


def test_exported_card_loads_with_backend_defaults(tmp_path: Path) -> None:
    cards_dir = tmp_path / "source_cards"
    cards_dir.mkdir()
    (cards_dir / f"{DATASET}.json").write_text(json.dumps(_exported_card()), encoding="utf-8")

    cards = load_source_cards(tmp_path)  # runs assert_card_consistency
    assert set(cards) == {DATASET}
    view = cards[DATASET]
    assert view.runtime_backend == "neo4j"
    assert view.has_label("PolymerType") and view.has_relationship("leads_to")
    limits = view.limits()
    assert limits["max_result_rows"] > 0 and limits["max_traversal_depth"] > 0
    assert view.safety["read_only"] is True
    assert view.allowed_edge_patterns["leads_to"] == [["MolecularMarker", "Condition"]]
    assert view.entity_descriptions["nodes"]["PolymerType"] == "A polymer."


def test_specialist_is_chosen_by_the_card_not_the_name(tmp_path: Path) -> None:
    config = SpecialistConfig(data_dir=tmp_path)
    neo4j_card = SourceCardView.from_card_dict(_exported_card("neo4j"))
    gremlin_card = SourceCardView.from_card_dict(_exported_card("gremlin"))

    assert type(build_specialist(DATASET, neo4j_card, config)) is type(
        build_cypher_specialist(neo4j_card, config)
    )
    assert type(build_specialist(DATASET, gremlin_card, config)) is type(
        build_gremlin_specialist(gremlin_card, config)
    )
    with pytest.raises(ValueError, match="runtime_backend='sqlite'"):
        build_specialist(DATASET, SourceCardView.from_card_dict(_exported_card("sqlite")), config)


def test_endpoint_override_reaches_a_hyphenated_dataset(tmp_path: Path, monkeypatch) -> None:
    config = SpecialistConfig(data_dir=tmp_path, neo4j_uri="bolt://attack:5456")
    assert config.endpoint_for("neo4j", DATASET) == "bolt://attack:5456"
    monkeypatch.setenv("ARIADNE_ENDPOINT_MNP_CS_03000_R2", "bolt://localhost:5462")
    assert config.endpoint_for("neo4j", DATASET) == "bolt://localhost:5462"
    # The built-in datasets are unaffected by a foreign override.
    assert config.endpoint_for("neo4j", "attack") == "bolt://attack:5456"


def test_resolver_anchors_by_name_and_never_guesses_a_label() -> None:
    card = SourceCardView.from_card_dict(_exported_card())
    task = SpecialistTask(
        sub_question_id="q1", source=DATASET,
        text="What does Polystyrene lead to?", entities=("PolymerType",),
    )
    anchor = resolve_anchor(task, card)
    assert isinstance(anchor, ResolvedAnchor)
    assert anchor.kind == KIND_TITLE and anchor.value == "Polystyrene"
    assert anchor.dataset == DATASET

    # An opaque Synapse id is not a T-id, a CAPEC id or a CWE id.
    assert infer_label("node-002264710b5bbf6c", DATASET) is None
    nothing = SpecialistTask(sub_question_id="q2", source=DATASET, text="")
    assert resolve_anchor(nothing, card) is None
