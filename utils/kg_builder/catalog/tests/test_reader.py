#!/usr/bin/env python3
"""Tests for the declared-catalog reader.

Two populations deliberately. Hand-written fixtures carry the behavioural tests,
because the delivered CSVs are funder-supplied and not redistributable and must
never be committed. One class pins the *real* delivery's counts and skips when it
is not present, so a machine with the delivery checks that the parser still sees
what the dataset card records, and CI without it still runs everything else.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils.kg_builder.catalog import (
    DECLARED,
    INFERRED,
    DeclaredCatalog,
    DeclaredTriple,
    add_triples,
    apply_inferred,
    catalog_dir,
    inferred_triples,
    read_catalog,
)

NODE_CSV = """node_type,attribute_name,value_type
USER,user.name,STRING
USER,ad__enabled,BOOLEAN
GROUP,group.privileges,BOOLEAN
DOMAIN,ad__minpwdlength,INTEGER
ENTRA_GROUP,entra__group_type,LIST_STRING
ENTRA_LICENCE,entra__sku,STRING
ENTRA_LICENSE,entra__sku,STRING
"""

EDGE_CSV = """source_node_type,edge_label,target_node_type,attribute_name,value_type
GROUP,GENERIC_ALL,USER,is_inherited,BOOLEAN
GROUP,GENERIC_ALL,USER,principal_type,STRING
GROUP,OWNS,GROUP,is_inherited,BOOLEAN
GROUP,DC_SYNC,DOMAIN,is_inherited,BOOLEAN
USER,MEMBER_OF,OKTA_GROUP,member_status,STRING
"""


@pytest.fixture()
def delivery(tmp_path: Path) -> Path:
    (tmp_path / "node_attributes.csv").write_text(NODE_CSV, encoding="utf-8")
    (tmp_path / "relationship_attributes.csv").write_text(EDGE_CSV, encoding="utf-8")
    return tmp_path


class TestParsing:
    def test_reads_node_attributes_with_declared_types(self, delivery: Path) -> None:
        catalog = read_catalog(delivery)
        assert catalog.node_attributes["USER"]["ad__enabled"].value_type == "BOOLEAN"
        assert catalog.node_attributes["DOMAIN"]["ad__minpwdlength"].value_type == "INTEGER"
        assert catalog.node_attributes["ENTRA_GROUP"]["entra__group_type"].value_type == "LIST_STRING"

    def test_triples_are_deduplicated_across_attribute_rows(self, delivery: Path) -> None:
        """GENERIC_ALL appears on two rows; it is one triple with two attributes."""
        catalog = read_catalog(delivery)
        keys = [t.key() for t in catalog.triples]
        assert keys.count(("GROUP", "GENERIC_ALL", "USER")) == 1
        assert set(catalog.edge_attributes[("GROUP", "GENERIC_ALL", "USER")]) == {
            "is_inherited",
            "principal_type",
        }

    def test_endpoint_labels_absent_from_the_node_csv_are_registered(self, delivery: Path) -> None:
        """OKTA_GROUP is only ever a triple endpoint. Keep the edge, register the label."""
        catalog = read_catalog(delivery)
        assert "OKTA_GROUP" in catalog.node_attributes
        assert catalog.node_attributes["OKTA_GROUP"] == {}
        assert catalog.permits("USER", "MEMBER_OF", "OKTA_GROUP")

    def test_the_licence_license_collision_survives_verbatim(self, delivery: Path) -> None:
        """Both spellings are real production node types. Merging them would mean
        evaluating against a tidier schema than the customer has."""
        catalog = read_catalog(delivery)
        assert "ENTRA_LICENCE" in catalog.node_attributes
        assert "ENTRA_LICENSE" in catalog.node_attributes

    def test_homogeneous_triples_are_identified(self, delivery: Path) -> None:
        catalog = read_catalog(delivery)
        homo = catalog.homogeneous_triples()
        assert [t.key() for t in homo] == [("GROUP", "OWNS", "GROUP")]

    def test_source_files_are_recorded_by_checksum(self, delivery: Path) -> None:
        catalog = read_catalog(delivery)
        assert set(catalog.source_files) == {
            "node_attributes.csv",
            "relationship_attributes.csv",
        }
        assert all(v.startswith("sha256:") for v in catalog.source_files.values())

    def test_a_wrong_header_is_refused(self, tmp_path: Path) -> None:
        (tmp_path / "node_attributes.csv").write_text("a,b,c\n1,2,3\n", encoding="utf-8")
        (tmp_path / "relationship_attributes.csv").write_text(EDGE_CSV, encoding="utf-8")
        with pytest.raises(ValueError, match="expected header"):
            read_catalog(tmp_path)

    def test_a_missing_file_names_the_env_var(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="ARIADNE_IDENTITY_CATALOG_DIR"):
            read_catalog(tmp_path)


class TestTruncationDetection:
    def test_truncation_is_flagged_when_member_of_never_reaches_group(
        self, delivery: Path
    ) -> None:
        catalog = read_catalog(delivery)
        assert catalog.truncation is not None
        assert catalog.truncation.suspected is True
        assert any("MEMBER_OF" in line for line in catalog.truncation.evidence)
        assert "customer_edge_catalog" in catalog.truncation.corrected_query

    def test_a_complete_delivery_is_not_flagged(self, tmp_path: Path) -> None:
        """The detector must be able to say no, or it is not a detector."""
        (tmp_path / "node_attributes.csv").write_text(NODE_CSV, encoding="utf-8")
        (tmp_path / "relationship_attributes.csv").write_text(
            "source_node_type,edge_label,target_node_type,attribute_name,value_type\n"
            "USER,MEMBER_OF,GROUP,member_status,STRING\n"
            "GROUP,GENERIC_ALL,USER,is_inherited,BOOLEAN\n"
            "DEVICE,RUNS_AS,USER,is_inherited,BOOLEAN\n"
            "GPO,GP_LINK,DOMAIN,enforced,BOOLEAN\n",
            encoding="utf-8",
        )
        catalog = read_catalog(tmp_path)
        assert catalog.truncation is not None
        assert catalog.truncation.suspected is False
        assert catalog.truncation.evidence == ()


class TestInferredEdges:
    def test_inferred_edges_are_tagged_and_separable(self, delivery: Path) -> None:
        catalog = apply_inferred(read_catalog(delivery))
        assert all(t.origin == INFERRED for t in catalog.inferred_triples())
        assert all(t.origin == DECLARED for t in catalog.declared_triples())
        assert len(catalog.triples) == len(catalog.declared_triples()) + len(
            catalog.inferred_triples()
        )

    def test_every_inferred_edge_carries_a_justification(self) -> None:
        from utils.kg_builder.catalog.inferred import INFERRED_EDGES

        assert INFERRED_EDGES
        for key, reason in INFERRED_EDGES.items():
            assert len(reason) > 80, f"{key} needs a real justification, not a label"

    def test_a_collision_with_a_declared_triple_raises(self, tmp_path: Path) -> None:
        """If an inferred edge is already declared, the inference was unnecessary
        -- shrink the list rather than shadowing the delivery."""
        (tmp_path / "node_attributes.csv").write_text(NODE_CSV, encoding="utf-8")
        (tmp_path / "relationship_attributes.csv").write_text(
            "source_node_type,edge_label,target_node_type,attribute_name,value_type\n"
            "USER,MEMBER_OF,GROUP,member_status,STRING\n",
            encoding="utf-8",
        )
        catalog = read_catalog(tmp_path)
        with pytest.raises(ValueError, match="already present"):
            apply_inferred(catalog)

    def test_add_triples_refuses_duplicates(self, delivery: Path) -> None:
        catalog = read_catalog(delivery)
        with pytest.raises(ValueError, match="already present"):
            add_triples(catalog, [DeclaredTriple("GROUP", "OWNS", "GROUP", INFERRED)])


class TestArtifactRoundTrip:
    def test_write_then_read_preserves_everything_that_matters(
        self, delivery: Path, tmp_path: Path
    ) -> None:
        original = apply_inferred(read_catalog(delivery))
        path = original.write(tmp_path / "declared.json")
        reloaded = DeclaredCatalog.read(path)

        assert reloaded.counts() == original.counts()
        assert reloaded.node_labels == original.node_labels
        assert [t.key() for t in reloaded.declared_triples()] == [
            t.key() for t in original.declared_triples()
        ]
        assert [t.key() for t in reloaded.inferred_triples()] == [
            t.key() for t in original.inferred_triples()
        ]
        assert reloaded.truncation is not None
        assert reloaded.truncation.suspected is original.truncation.suspected

    def test_the_artifact_records_the_truncation_for_downstream_readers(
        self, delivery: Path, tmp_path: Path
    ) -> None:
        catalog = apply_inferred(read_catalog(delivery))
        payload = json.loads(catalog.write(tmp_path / "d.json").read_text(encoding="utf-8"))
        assert payload["truncation"]["suspected"] is True
        assert payload["counts"]["triples_inferred"] == len(inferred_triples())
        origins = {entry["origin"] for entry in payload["triples"]}
        assert origins == {DECLARED, INFERRED}


class TestTheRealDelivery:
    """Pins the counts the dataset card records. Skips without the delivery."""

    @pytest.fixture(autouse=True)
    def _require_delivery(self) -> None:
        base = catalog_dir()
        if not (base / "node_attributes.csv").is_file():
            pytest.skip(f"ReliaQuest delivery not present at {base}")

    def test_delivered_counts_match_the_dataset_card(self) -> None:
        catalog = read_catalog()
        counts = catalog.counts()
        assert counts["node_types"] == 72
        assert counts["edge_labels"] == 21
        assert counts["triples"] == 60
        assert counts["node_attributes"] == 779
        assert counts["edge_attributes"] == 118

    def test_the_delivery_has_eight_homogeneous_triples(self) -> None:
        """H3's population. If this number moves, H3's threshold must be re-derived."""
        catalog = read_catalog()
        assert len(catalog.homogeneous_triples()) == 8

    def test_inferring_edges_does_not_enlarge_h3s_population(self) -> None:
        """GROUP -MEMBER_OF-> GROUP is inferred AND homogeneous. H3 is a claim
        about ReliaQuest's schema, so it must be measured over the delivered
        eight -- never over all nine."""
        catalog = apply_inferred(read_catalog())
        assert len(catalog.homogeneous_triples()) == 9
        assert len(catalog.homogeneous_triples(DECLARED)) == 8
        assert catalog.counts()["triples_homogeneous_declared"] == 8

    def test_the_delivery_is_detected_as_truncated(self) -> None:
        catalog = read_catalog()
        assert catalog.truncation is not None and catalog.truncation.suspected

    def test_both_licence_spellings_are_present_in_the_real_delivery(self) -> None:
        catalog = read_catalog()
        assert "ENTRA_LICENCE" in catalog.node_attributes
        assert "ENTRA_LICENSE" in catalog.node_attributes
