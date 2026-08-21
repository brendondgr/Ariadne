#!/usr/bin/env python3
"""Tests for assembling the identity source card.

The card is what the planner and the specialists actually read, so the things
worth pinning are the ones a downstream reader would silently get wrong: that
the authored overlay wins over generated values, that every label and edge has a
gloss, and that the declared/inferred split survives into the card.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from utils.kg_builder.catalog import apply_inferred, catalog_dir, read_catalog
from utils.kg_builder.catalog.card import (
    build_card,
    examples_from_nodes,
    load_overlay,
    write_card,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
OVERLAY = REPO_ROOT / "data-identity/source_cards/overlays/identity.overlay.json"

NODE_CSV = """node_type,attribute_name,value_type
USER,user.name,STRING
GROUP,group.name,STRING
DOMAIN,ad__minpwdlength,INTEGER
"""
EDGE_CSV = """source_node_type,edge_label,target_node_type,attribute_name,value_type
GROUP,DC_SYNC,DOMAIN,is_inherited,BOOLEAN
USER,MEMBER_OF,OKTA_GROUP,member_status,STRING
"""


@pytest.fixture()
def catalog(tmp_path: Path):
    (tmp_path / "node_attributes.csv").write_text(NODE_CSV, encoding="utf-8")
    (tmp_path / "relationship_attributes.csv").write_text(EDGE_CSV, encoding="utf-8")
    return apply_inferred(read_catalog(tmp_path, name="identity"))


class TestCardAssembly:
    def test_generated_half_comes_from_the_catalog(self, catalog) -> None:
        card = build_card(catalog, {}, out_dir="data-identity")
        assert "USER" in card["node_labels"]
        assert "DC_SYNC" in card["relationship_types"]
        assert card["dataset"] == "identity"

    def test_the_overlay_wins_over_a_generated_value(self, catalog) -> None:
        """The authored half must be able to correct the generated half, not be
        silently overridden by it."""
        card = build_card(
            catalog, {"runtime_backend": "authored-wins"}, out_dir="data-identity"
        )
        assert card["runtime_backend"] == "authored-wins"

    def test_underscore_keys_in_the_overlay_are_not_copied(self, catalog) -> None:
        """`_comment` documents the overlay; it is not card content."""
        card = build_card(catalog, {"_comment": ["notes"]}, out_dir="data-identity")
        assert "_comment" not in card

    def test_declared_endpoints_carry_origin_and_homogeneity(self, catalog) -> None:
        card = build_card(catalog, {}, out_dir="data-identity")
        endpoints = card["identity"]["declared_endpoints"]
        origins = {e["origin"] for e in endpoints}
        assert origins == {"declared", "inferred"}
        assert all("homogeneous" in e for e in endpoints)

    def test_labels_with_no_edges_are_marked_not_traversable(self, catalog) -> None:
        """A label that exists but cannot be walked must say so, or a planner
        will route a multi-hop question into a dead end."""
        card = build_card(catalog, {}, out_dir="data-identity")
        assert "DOMAIN" not in card["identity"]["not_traversable"]

    def test_examples_come_from_real_instances(self, catalog) -> None:
        """`STRING` conveys no shape. An example is the only way the card tells a
        reader that this source keys AD objects by SID and AWS ones by ARN."""
        nodes = [
            {"label": "USER", "properties": {"user.name": "jsmith0"}},
            {"label": "USER", "properties": {"user.name": "ignored-second"}},
        ]
        card = build_card(
            catalog, {}, out_dir="data-identity", examples=examples_from_nodes(nodes)
        )
        assert card["node_properties"]["USER"]["user.name"]["example"] == "jsmith0"

    def test_the_card_records_that_the_catalog_was_truncated(self, catalog) -> None:
        card = build_card(catalog, {}, out_dir="data-identity")
        assert card["catalog"]["truncated"] is True
        assert card["catalog"]["inferred_triples"] == 3

    def test_round_trip_through_disk(self, catalog, tmp_path: Path) -> None:
        import json

        card = build_card(catalog, {}, out_dir="data-identity")
        path = write_card(card, tmp_path / "identity.json")
        assert json.loads(path.read_text(encoding="utf-8")) == card


class TestTheAuthoredOverlay:
    """The overlay is committed source. These tests are what stop a gloss going
    missing when the catalog grows."""

    @pytest.fixture(autouse=True)
    def _require_delivery(self) -> None:
        if not (catalog_dir() / "node_attributes.csv").is_file():
            pytest.skip("ReliaQuest delivery not present")

    @pytest.fixture()
    def real_card(self):
        cat = apply_inferred(read_catalog(name="identity"))
        return build_card(cat, load_overlay(OVERLAY), out_dir="data-identity")

    def test_every_label_has_a_gloss(self, real_card) -> None:
        missing = set(real_card["node_labels"]) - set(
            real_card["entity_descriptions"]["nodes"]
        )
        assert not missing, f"labels without a description: {sorted(missing)}"

    def test_every_relationship_has_a_gloss(self, real_card) -> None:
        missing = set(real_card["relationship_types"]) - set(
            real_card["entity_descriptions"]["relationships"]
        )
        assert not missing, f"relationships without a description: {sorted(missing)}"

    def test_the_group_family_is_disambiguated(self, real_card) -> None:
        """Six labels contain the word 'group' and one of them is a firewall
        rule set. If the glosses do not distinguish them, the planner has no
        signal at all when a question says 'group'."""
        nodes = real_card["entity_descriptions"]["nodes"]
        assert "Distinct from" in nodes["ENTRA_GROUP"]
        assert "Distinct from" in nodes["OKTA_GROUP"]
        assert "Distinct from" in nodes["GCP_GROUP"]
        assert "network" in nodes["AWS_EC2_SECURITY_GROUP"].lower()
        assert "Distinct from" in nodes["GROUP"]

    def test_the_licence_collision_is_described_rather_than_hidden(
        self, real_card
    ) -> None:
        nodes = real_card["entity_descriptions"]["nodes"]
        assert "ENTRA_LICENSE" in nodes["ENTRA_LICENCE"]
        assert "ENTRA_LICENCE" in nodes["ENTRA_LICENSE"]

    def test_the_member_of_gloss_declares_which_forms_are_inferred(
        self, real_card
    ) -> None:
        """A reader of the card must be able to see that three MEMBER_OF forms
        are this project's reconstruction without consulting anything else."""
        gloss = real_card["entity_descriptions"]["relationships"]["MEMBER_OF"]
        assert "INFERRED" in gloss

    def test_provenance_states_both_halves_of_what_this_source_is(
        self, real_card
    ) -> None:
        provenance = real_card["provenance"]
        assert provenance["schema_provenance"] == "declared"
        assert provenance["instance_provenance"] == "synthetic"
        assert "schema navigation" in provenance["caveat"]

    def test_the_isolated_store_is_not_the_attack_store(self, real_card) -> None:
        """A card pointing at :5456 would load 72 foreign labels into the graph
        every measured arm queries."""
        assert real_card["connection"]["uri"] == "bolt://localhost:5459"
        assert real_card["safety"]["read_only"] is True

    def test_fifty_seven_labels_are_declared_but_unwalkable(self, real_card) -> None:
        assert len(real_card["identity"]["not_traversable"]) == 57
