#!/usr/bin/env python3
"""The merged store gets a Cypher specialist, and nothing else notices (C-015).

The merged-graph counterfactual is one Neo4j holding both catalogues, so a
single Cypher specialist answers questions the federated arms split across two
engines and two languages. The specialist itself is unmodified — it reads its
labels, relationships and identifier schemes from the card it is handed, and
the merged card declares the union.

The second half of this file is the part that matters more. A baseline is only
worth running if the system it is compared against is unchanged, so these pin
that adding a third dataset name did not make it visible anywhere by default.
"""

from __future__ import annotations

import pytest

from utils.planner.cards import SourceCardView, load_source_cards
from utils.specialists import build_specialist
from utils.specialists.config import SpecialistConfig
from utils.specialists.cypher.specialist import build_cypher_specialist


def _merged_card() -> SourceCardView:
    return SourceCardView.from_card_dict({
        "dataset": "merged",
        "runtime_backend": "neo4j",
        "node_labels": ["Technique", "Mitigation", "AttackPattern", "Weakness"],
        "relationship_types": ["MITIGATES", "HAS_MITIGATION", "EXPLOITS_WEAKNESS"],
        "node_properties": {},
        "connection": {"backend": "neo4j"},
    })


def _config(tmp_path) -> SpecialistConfig:
    return SpecialistConfig(data_dir=tmp_path)


def test_the_merged_dataset_gets_a_cypher_specialist(tmp_path) -> None:
    specialist = build_specialist("merged", _merged_card(), _config(tmp_path))
    reference = build_cypher_specialist(_merged_card(), _config(tmp_path))
    assert type(specialist) is type(reference)


def test_an_unknown_dataset_is_dispatched_on_its_card(tmp_path) -> None:
    """Since the Synapse transfer (2026-09-16) the name alone does not gate.

    A dataset this file has never heard of gets the specialist its card's
    ``runtime_backend`` names; a card that declares none still raises, so the
    loosening is bounded by what the card says rather than by a name list.
    """
    specialist = build_specialist("sepses", _merged_card(), _config(tmp_path))
    reference = build_cypher_specialist(_merged_card(), _config(tmp_path))
    assert type(specialist) is type(reference)

    backendless = SourceCardView.from_card_dict({
        "dataset": "sepses", "runtime_backend": "", "node_labels": ["X"],
        "relationship_types": [], "node_properties": {},
    })
    with pytest.raises(ValueError, match="No specialist for dataset 'sepses'"):
        build_specialist("sepses", backendless, _config(tmp_path))


# -- the isolation that makes the comparison worth anything ------------------


def test_the_merged_card_is_invisible_to_a_default_configured_run() -> None:
    """`load_source_cards` globs `source_cards/*.json` under the data dir.

    A merged card in the ordinary place would become a third source the planner
    can route to, changing every LLM-planned arm. It lives under `data/merged/`
    instead, and this asserts the ordinary directory stayed clean.
    """
    assert set(load_source_cards("data")) == {"attack", "capec"}


def test_the_merged_dataset_is_invisible_to_the_default_schema_registry() -> None:
    """`discover_datasets` walks `graphs/`, and `binding.py`/`direction.py`
    build on that registry on the DEFAULT path — not only under the generic
    flag. A merged dataset there would be walked by every arm, which costs
    wall clock on the one arm whose 1.6 s is a published figure (C-004).
    """
    from utils.specialists.schema.build import discover_datasets

    assert "merged" not in discover_datasets("data")


def test_the_merged_dataset_is_reachable_when_pointed_at_deliberately() -> None:
    """The other half of the same property: opt-in must actually work."""
    from pathlib import Path

    from utils.specialists.schema.build import discover_datasets

    if not (Path("data-merged/graphs/merged/canonical/nodes.jsonl")).is_file():
        pytest.skip("merged dataset not built — run `python -m utils.kg_builder.merge`")
    assert discover_datasets("data-merged") == ["merged"]


# -- cross-catalogue join values, and why only the merged store gets them -----


def _neighbour_rows():
    """One CAPEC pattern whose MAPS_TO neighbour is an ATT&CK technique id."""
    return [{
        "anchor_id": "CAPEC-572",
        "anchor_name": "Artificially Inflate File Sizes",
        "anchor_label": "AttackPattern",
        "neighbour_id": "T1027.001",
        "neighbour_name": "Binary Padding",
        "neighbour_label": "TaxonomyEntry",
        "rel_type": "MAPS_TO",
    }]


def _normalize(card):
    from utils.specialists.cypher.normalizer import CypherNormalizer

    return CypherNormalizer()._normalize_generic_neighbors(
        _neighbour_rows(), "MATCH (n) ...", card, "capec-id"
    )


def test_a_merged_store_carries_a_neighbours_identifier_as_a_join_value() -> None:
    """In one store the next hop is reachable, so the neighbour is the link."""
    card = SourceCardView.from_card_dict({
        "dataset": "merged",
        "runtime_backend": "neo4j",
        "node_labels": ["AttackPattern", "TaxonomyEntry"],
        "relationship_types": ["MAPS_TO"],
        "identity": {"subsumes": ["attack", "capec"]},
    })
    assert _normalize(card)[0].join_values == ("T1027.001",)


def test_a_single_catalogue_store_does_not() -> None:
    """The federated arms must be untouched by that.

    A CAPEC specialist cannot query ATT&CK, so an ATT&CK id on a neighbour is a
    dead end there rather than a link — and changing what those records carry
    would move `join_index`, the correlation claims built on it, and therefore
    arm figures that are already recorded.
    """
    card = SourceCardView.from_card_dict({
        "dataset": "capec",
        "runtime_backend": "gremlin",
        "node_labels": ["AttackPattern", "TaxonomyEntry"],
        "relationship_types": ["MAPS_TO"],
    })
    assert _normalize(card)[0].join_values == ()


def test_an_anchor_that_is_itself_a_technique_still_joins_everywhere() -> None:
    """The pre-existing rule is unchanged, with or without subsumption."""
    from utils.specialists.cypher.normalizer import CypherNormalizer

    rows = [{
        "anchor_id": "T1047", "anchor_name": "WMI", "anchor_label": "Technique",
        "neighbour_id": "M1040", "neighbour_name": "x", "neighbour_label": "Mitigation",
        "rel_type": "MITIGATES",
    }]
    card = SourceCardView.from_card_dict({
        "dataset": "attack", "runtime_backend": "neo4j",
        "node_labels": ["Technique", "Mitigation"], "relationship_types": ["MITIGATES"],
    })
    out = CypherNormalizer()._normalize_generic_neighbors(rows, "q", card, "technique-id")
    assert out[0].join_values == ("T1047",)
