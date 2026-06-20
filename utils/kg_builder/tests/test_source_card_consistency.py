#!/usr/bin/env python3

"""Contract tests guarding source-card / overlay agreement with the structural schema.

The ATT&CK card once drifted because the authored overlay (`entity_descriptions`)
and the introspected structural lists (`node_labels` / `relationship_types`, derived
from the schema frozensets) were maintained in separate files with nothing asserting
they agree. A specialist that trusts a description for a label or edge that does not
exist in the graph will generate queries that silently return nothing. These tests
pin every authored description to a real label/edge and vice versa, for both cards.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils.kg_builder.schema.attack import (
    ATTACK_NODE_LABELS,
    ATTACK_RELATIONSHIP_TYPES,
)
from utils.kg_builder.schema.capec import (
    CAPEC_NODE_LABELS,
    CAPEC_RELATIONSHIP_TYPES,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SOURCE_CARDS = _REPO_ROOT / "data" / "source_cards"


def _load(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# (dataset, overlay file, card file, node labels, relationship types)
_CARDS = [
    (
        "attack",
        _SOURCE_CARDS / "overlays" / "attack.overlay.json",
        _SOURCE_CARDS / "attack.json",
        ATTACK_NODE_LABELS,
        ATTACK_RELATIONSHIP_TYPES,
    ),
    (
        "capec",
        _SOURCE_CARDS / "overlays" / "capec.overlay.json",
        _SOURCE_CARDS / "capec.json",
        CAPEC_NODE_LABELS,
        CAPEC_RELATIONSHIP_TYPES,
    ),
]


@pytest.mark.parametrize("dataset,overlay_path,_card,node_labels,rel_types", _CARDS)
def test_overlay_descriptions_match_schema(
    dataset, overlay_path, _card, node_labels, rel_types
) -> None:
    """Authored overlay descriptions must cover exactly the schema's labels/edges.

    This is the source-level contract: prose is authored in the overlay, structure
    is owned by the schema frozensets. If they diverge, the build is wrong.
    """
    overlay = _load(overlay_path)
    descriptions = overlay.get("entity_descriptions", {})

    described_nodes = set(descriptions.get("nodes", {}))
    described_rels = set(descriptions.get("relationships", {}))

    assert described_nodes == set(node_labels), (
        f"{dataset}: overlay node descriptions disagree with schema node_labels; "
        f"undescribed={set(node_labels) - described_nodes}, "
        f"phantom={described_nodes - set(node_labels)}"
    )
    assert described_rels == set(rel_types), (
        f"{dataset}: overlay relationship descriptions disagree with schema "
        f"relationship_types; undescribed={set(rel_types) - described_rels}, "
        f"phantom={described_rels - set(rel_types)}"
    )


@pytest.mark.parametrize("dataset,_overlay,card_path,node_labels,rel_types", _CARDS)
def test_generated_card_is_self_consistent(
    dataset, _overlay, card_path, node_labels, rel_types
) -> None:
    """The committed card artifact must agree with itself and be freshly generated.

    Guards against a stale card: a structural change that was not followed by a
    rebuild would surface here as the card's introspected lists or descriptions
    drifting from the schema frozensets.
    """
    if not card_path.exists():
        pytest.skip(f"{dataset} source card not built")

    card = _load(card_path)
    described_nodes = set(card.get("entity_descriptions", {}).get("nodes", {}))
    described_rels = set(card.get("entity_descriptions", {}).get("relationships", {}))

    assert set(card.get("node_labels", [])) == set(node_labels), (
        f"{dataset}: card node_labels are stale relative to the schema frozenset"
    )
    assert set(card.get("relationship_types", [])) == set(rel_types), (
        f"{dataset}: card relationship_types are stale relative to the schema frozenset"
    )
    assert described_nodes == set(card.get("node_labels", [])), (
        f"{dataset}: card descriptions disagree with its own node_labels"
    )
    assert described_rels == set(card.get("relationship_types", [])), (
        f"{dataset}: card descriptions disagree with its own relationship_types"
    )
