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


def test_an_unknown_dataset_still_raises(tmp_path) -> None:
    """The branch is an addition, not a loosening."""
    with pytest.raises(ValueError, match="No specialist for dataset"):
        build_specialist("sepses", _merged_card(), _config(tmp_path))


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

    if not (Path("data/merged/graphs/merged/canonical/nodes.jsonl")).is_file():
        pytest.skip("merged dataset not built — run `python -m utils.kg_builder.merge`")
    assert discover_datasets("data/merged") == ["merged"]
