#!/usr/bin/env python3
"""Tests for building a :class:`DatasetSchema` from a declared catalog.

The behavioural cases run on a small hand-written catalog so they do not need
ReliaQuest's delivery, which is not redistributable and is not committed. One
class pins the real delivery and skips without it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from utils.kg_builder.catalog import apply_inferred, catalog_dir, read_catalog
from utils.specialists.schema.build import (
    build_dataset_schema,
    build_declared_schema,
    build_registry,
    discover_datasets,
)
from utils.specialists.schema.idscheme import UNDETERMINED
from utils.specialists.schema.registry import DECLARED, IN, OBSERVED, OUT

NODE_CSV = """node_type,attribute_name,value_type
USER,user.name,STRING
USER,ad__enabled,BOOLEAN
GROUP,group.name,STRING
DOMAIN,ad__minpwdlength,INTEGER
"""

EDGE_CSV = """source_node_type,edge_label,target_node_type,attribute_name,value_type
GROUP,GENERIC_ALL,USER,is_inherited,BOOLEAN
GROUP,OWNS,GROUP,is_inherited,BOOLEAN
GROUP,DC_SYNC,DOMAIN,is_inherited,BOOLEAN
USER,MEMBER_OF,OKTA_GROUP,member_status,STRING
"""


@pytest.fixture()
def catalog(tmp_path: Path):
    (tmp_path / "node_attributes.csv").write_text(NODE_CSV, encoding="utf-8")
    (tmp_path / "relationship_attributes.csv").write_text(EDGE_CSV, encoding="utf-8")
    return read_catalog(tmp_path, name="fixture")


class TestDeclaredSchema:
    def test_labels_and_properties_come_from_the_catalog(self, catalog) -> None:
        schema = build_declared_schema(catalog)
        assert "USER" in schema.labels()
        assert schema.label_properties("USER") == frozenset({"user.name", "ad__enabled"})

    def test_triples_come_from_the_catalog(self, catalog) -> None:
        schema = build_declared_schema(catalog)
        assert ("GROUP", "DC_SYNC", "DOMAIN") in schema.triples

    def test_provenance_is_declared_not_observed(self, catalog) -> None:
        schema = build_declared_schema(catalog)
        assert schema.provenance == DECLARED
        assert schema.is_declared is True

    def test_facets_resolve_in_both_directions(self, catalog) -> None:
        """The direction machinery must work off declared triples exactly as it
        does off observed ones -- that is the whole premise of the transfer."""
        schema = build_declared_schema(catalog)
        assert schema.facet_exists("GROUP", "DC_SYNC", OUT, "DOMAIN")
        assert schema.facet_exists("DOMAIN", "DC_SYNC", IN, "GROUP")
        assert not schema.facet_exists("DOMAIN", "DC_SYNC", OUT, "GROUP")

    def test_a_homogeneous_triple_yields_two_facets_differing_only_in_direction(
        self, catalog
    ) -> None:
        """EXP-2026-08-011 H3's mechanism, pinned as a fact about the data model.

        GROUP -OWNS-> GROUP produces (OWNS, out, GROUP) and (OWNS, in, GROUP).
        The neighbour label is identical in both, so nothing but the direction
        field distinguishes them -- which is why a question phrased in either
        direction cannot be disambiguated by the neighbour label alone.
        """
        schema = build_declared_schema(catalog)
        owns = [f for f in schema.label_facets("GROUP") if f.rel_type == "OWNS"]
        assert {f.direction for f in owns} == {OUT, IN}
        assert {f.neighbour_label for f in owns} == {"GROUP"}

    def test_id_schemes_are_empty_and_every_verdict_is_undetermined(self, catalog) -> None:
        """A catalog has no values, so nothing can be learned -- and the honest
        answer to 'could this value inhabit this property' is `undetermined`,
        never a mismatch. This is EXP-2026-08-011 H4's safety half."""
        schema = build_declared_schema(catalog)
        assert schema.label_id_schemes == {}
        for value in ["S-1-5-21-1004336348", "jsmith@corp.example", "not-an-id-at-all", ""]:
            assert schema.value_verdict("USER", "id", value) == UNDETERMINED
        assert schema.labels_for_id("anything") == frozenset()

    def test_inferred_triples_are_flagged_and_declared_ones_are_not(self, catalog) -> None:
        schema = build_declared_schema(apply_inferred(catalog))
        assert schema.is_inferred_triple("USER", "MEMBER_OF", "GROUP")
        assert not schema.is_inferred_triple("GROUP", "DC_SYNC", "DOMAIN")
        assert schema.inferred_triples <= schema.triples

    def test_a_catalog_without_inferred_edges_has_none_flagged(self, catalog) -> None:
        schema = build_declared_schema(catalog)
        assert schema.inferred_triples == frozenset()


class TestTheScanPathIsUnchanged:
    """The declared path is additive. If any of these move, arms already
    measured have moved with them."""

    def test_a_scanned_schema_still_defaults_to_observed(self, tmp_path: Path) -> None:
        nodes = tmp_path / "nodes.jsonl"
        rels = tmp_path / "relationships.jsonl"
        nodes.write_text(
            '{"id":"a","label":"Technique","properties":{"attack_id":"T1055"}}\n'
            '{"id":"b","label":"Group","properties":{"attack_id":"G0007"}}\n',
            encoding="utf-8",
        )
        rels.write_text('{"type":"USES","source_id":"b","target_id":"a"}\n', encoding="utf-8")
        schema = build_dataset_schema("fixture", nodes, rels)
        assert schema.provenance == OBSERVED
        assert schema.is_declared is False
        assert schema.inferred_triples == frozenset()

    def test_a_scanned_schema_still_learns_id_schemes(self, tmp_path: Path) -> None:
        """The declared path leaves schemes empty; the scan path must not."""
        nodes = tmp_path / "nodes.jsonl"
        rels = tmp_path / "relationships.jsonl"
        nodes.write_text(
            '{"id":"a","label":"Technique","properties":{"attack_id":"T1055"}}\n',
            encoding="utf-8",
        )
        rels.write_text("", encoding="utf-8")
        schema = build_dataset_schema("fixture", nodes, rels)
        assert schema.label_id_schemes != {}


class TestTheRealCatalog:
    @pytest.fixture(autouse=True)
    def _require_delivery(self) -> None:
        if not (catalog_dir() / "node_attributes.csv").is_file():
            pytest.skip("ReliaQuest delivery not present")

    def test_the_whole_catalog_becomes_a_schema(self) -> None:
        schema = build_declared_schema(apply_inferred(read_catalog()), "identity")
        assert len(schema.labels()) == 72
        assert len(schema.triples) == 63
        assert len(schema.inferred_triples) == 3
        assert len(schema.label_properties("USER")) == 131

    def test_every_delivered_homogeneous_triple_is_a_two_direction_facet(self) -> None:
        """H3's population, reached through the registry rather than the catalog."""
        cat = read_catalog()
        schema = build_declared_schema(cat, "identity")
        homo = cat.homogeneous_triples(DECLARED)
        assert len(homo) == 8
        for triple in homo:
            assert schema.facet_exists(triple.source, triple.edge, OUT, triple.target)
            assert schema.facet_exists(triple.target, triple.edge, IN, triple.source)

    def test_no_property_of_the_real_catalog_produces_a_false_mismatch(self) -> None:
        """H4's safety half over the real label set: 72 labels, zero mismatches."""
        schema = build_declared_schema(read_catalog(), "identity")
        for label in schema.labels():
            for prop in list(schema.label_properties(label))[:5]:
                assert schema.value_verdict(label, prop, "S-1-5-21-99") == UNDETERMINED


class TestIsolationFromMeasuredArms:
    """The identity source must not become routable or discoverable by default.

    ``load_source_cards()`` globs ``source_cards/*.json`` and
    ``discover_datasets()`` walks ``graphs/`` -- either would silently add a
    source to arms that are already measured. EXP-2026-08-009 pinned the same
    property for ``merged``; this pins it for ``identity``.
    """

    def test_discover_datasets_on_the_default_dir_excludes_identity(self) -> None:
        assert "identity" not in discover_datasets("data")

    def test_the_default_registry_has_only_the_measured_datasets(self) -> None:
        registry = build_registry("data")
        assert "identity" not in registry.dataset_names()

    def test_load_source_cards_on_the_default_dir_is_unchanged(self) -> None:
        from utils.planner.cards import load_source_cards

        assert set(load_source_cards("data")) == {"attack", "capec"}

    def test_every_default_schema_is_observed(self) -> None:
        """No declared schema may leak into the default registry."""
        registry = build_registry("data")
        for name in registry.dataset_names():
            assert registry.dataset(name).provenance == OBSERVED
