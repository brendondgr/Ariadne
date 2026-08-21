#!/usr/bin/env python3
"""Tests for the synthetic tenant generator.

The generator's whole value is that its output can be trusted without being
inspected, so these tests check the four properties the module docstring commits
to: conformance, determinism, separability of inferred edges, and agreement
between the blueprint and the graph.

Behavioural cases run on a small hand-written catalog. One class runs the real
delivery and skips without it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils.kg_builder.catalog import apply_inferred, catalog_dir, read_catalog
from utils.kg_builder.catalog.declared import DECLARED, INFERRED
from utils.kg_builder.synthetic import generate
from utils.kg_builder.synthetic.spec import TenantSpec

NODE_CSV = """node_type,attribute_name,value_type
USER,user.name,STRING
USER,active_directory__objectsid,STRING
USER,ad__passwordnotreqd,BOOLEAN
GROUP,group.name,STRING
GROUP,group.privileges,BOOLEAN
DOMAIN,ad__minpwdlength,INTEGER
DEVICE,active_directory__dnshostname,STRING
OKTA_GROUP,okta__resource_uid,STRING
AWS_ROLE,aws__resource_uid,STRING
ENTRA_LICENCE,entra__sku,STRING
ENTRA_LICENSE,entra__sku,STRING
"""

EDGE_CSV = """source_node_type,edge_label,target_node_type,attribute_name,value_type
GROUP,GENERIC_ALL,USER,is_inherited,BOOLEAN
GROUP,WRITE_DACL,GROUP,is_inherited,BOOLEAN
GROUP,OWNS,GROUP,is_inherited,BOOLEAN
GROUP,DC_SYNC,DOMAIN,is_inherited,BOOLEAN
GROUP,GET_CHANGES,DOMAIN,is_inherited,BOOLEAN
GROUP,GET_CHANGES_ALL,DOMAIN,is_inherited,BOOLEAN
GROUP,ADD_KEY_CREDENTIAL_LINK,USER,is_inherited,BOOLEAN
GROUP,ALL_EXTENDED_RIGHTS,DOMAIN,is_inherited,BOOLEAN
DOMAIN,TRUSTED_BY,DOMAIN,sid_filtering,BOOLEAN
DOMAIN,SAME_FOREST_TRUST,DOMAIN,sid_filtering,BOOLEAN
DEVICE,RUNS_AS,USER,is_inherited,BOOLEAN
USER,MEMBER_OF,OKTA_GROUP,member_status,STRING
"""


@pytest.fixture()
def catalog(tmp_path: Path):
    (tmp_path / "node_attributes.csv").write_text(NODE_CSV, encoding="utf-8")
    (tmp_path / "relationship_attributes.csv").write_text(EDGE_CSV, encoding="utf-8")
    return apply_inferred(read_catalog(tmp_path, name="fixture"))


@pytest.fixture()
def built(catalog):
    return generate(catalog, seed=1234)


class TestConformance:
    def test_every_edge_matches_a_permitted_triple(self, catalog, built) -> None:
        """The structural guarantee. If this can fail, the generator is not the
        authority the rest of the experiment assumes it is."""
        nodes, edges, spec = built
        label = {n["id"]: n["label"] for n in nodes}
        for edge in edges:
            source = label[edge["source_id"]]
            target = label[edge["target_id"]]
            assert catalog.permits(source, edge["type"], target), (
                f"{source} -{edge['type']}-> {target} is not in the catalog"
            )

    def test_every_property_key_is_declared_for_its_label(self, catalog, built) -> None:
        nodes, _, _ = built
        for node in nodes:
            declared = set(catalog.node_attributes.get(node["label"], {}))
            assert set(node["properties"]) <= declared, node["label"]

    def test_undeclared_properties_are_filtered_not_written(self, catalog, built) -> None:
        """`__id` is passed to the builder and must never survive into output."""
        nodes, _, _ = built
        assert all("__id" not in n["properties"] for n in nodes)

    def test_no_edge_endpoint_dangles(self, built) -> None:
        nodes, edges, _ = built
        ids = {n["id"] for n in nodes}
        for edge in edges:
            assert edge["source_id"] in ids and edge["target_id"] in ids

    def test_an_edge_the_catalog_forbids_raises(self, catalog) -> None:
        """The refusal must be real, not merely documented."""
        from utils.kg_builder.synthetic.generator import _Builder
        import random

        spec = TenantSpec(seed=0, catalog_name="fixture")
        b = _Builder(catalog=catalog, spec=spec, rng=random.Random(0), nodes=[], edges=[])
        user = b.node("USER", "u", {"user.name": "u"})
        domain = b.node("DOMAIN", "d", {"ad__minpwdlength": 8})
        with pytest.raises(ValueError, match="does not permit"):
            b.edge(user, "DC_SYNC", domain)


class TestDeterminism:
    def test_the_same_seed_gives_identical_output(self, catalog) -> None:
        a_nodes, a_edges, a_spec = generate(catalog, seed=99)
        b_nodes, b_edges, b_spec = generate(catalog, seed=99)
        assert json.dumps(a_nodes, sort_keys=True) == json.dumps(b_nodes, sort_keys=True)
        assert json.dumps(a_edges, sort_keys=True) == json.dumps(b_edges, sort_keys=True)
        assert a_spec.to_dict() == b_spec.to_dict()

    def test_a_different_seed_gives_different_output(self, catalog) -> None:
        a_nodes, _, _ = generate(catalog, seed=1)
        b_nodes, _, _ = generate(catalog, seed=2)
        assert json.dumps(a_nodes, sort_keys=True) != json.dumps(b_nodes, sort_keys=True)


class TestInferredEdgesStaySeparable:
    def test_inferred_edges_are_recorded_as_inferred(self, built) -> None:
        _, _, spec = built
        inferred = [e for e in spec.edges if e["origin"] == INFERRED]
        assert inferred
        for record in inferred:
            assert spec.triple_of(record) in {
                ("USER", "MEMBER_OF", "GROUP"),
                ("GROUP", "MEMBER_OF", "GROUP"),
                ("USER", "MEMBER_OF", "ENTRA_GROUP"),
            }

    def test_declared_edges_are_recorded_as_declared(self, built) -> None:
        _, _, spec = built
        for record in spec.edges_of("DC_SYNC"):
            assert record["origin"] == DECLARED

    def test_the_two_populations_partition_the_edge_set(self, built) -> None:
        _, edges, spec = built
        counts = spec.counts()
        assert counts["edges_declared"] + counts["edges_inferred"] == len(edges)


class TestBlueprintAgreesWithTheGraph:
    """The blueprint is upstream of the graph, but they must still describe the
    same thing -- otherwise gold derived from one cannot grade answers from the
    other."""

    def test_node_sets_match(self, built) -> None:
        nodes, _, spec = built
        assert {n["id"] for n in nodes} == set(spec.nodes)

    def test_labels_match_node_for_node(self, built) -> None:
        nodes, _, spec = built
        for node in nodes:
            assert spec.label_of(node["id"]) == node["label"]

    def test_edge_sets_match(self, built) -> None:
        _, edges, spec = built
        from_graph = sorted((e["source_id"], e["type"], e["target_id"]) for e in edges)
        from_spec = sorted((e["source_id"], e["edge"], e["target_id"]) for e in spec.edges)
        assert from_graph == from_spec

    def test_neighbours_agree_with_a_direct_edge_scan(self, built) -> None:
        _, edges, spec = built
        anchor = spec.edges[0]["source_id"]
        direct = sorted(
            {e["target_id"] for e in edges if e["source_id"] == anchor}
        )
        assert spec.neighbours(anchor) == direct


class TestPlantedPaths:
    def test_paths_are_planted_and_recorded(self, built) -> None:
        _, _, spec = built
        assert len(spec.planted_paths) >= 4
        names = {p.name for p in spec.planted_paths}
        assert "dcsync-via-helpdesk" in names

    def test_every_planted_step_exists_in_the_graph(self, built) -> None:
        _, edges, spec = built
        present = {(e["source_id"], e["type"], e["target_id"]) for e in edges}
        for path in spec.planted_paths:
            for step in path.steps:
                assert step in present, f"{path.name}: {step} missing"

    def test_the_dcsync_chain_is_multi_hop_and_ends_at_a_domain(self, built) -> None:
        _, _, spec = built
        path = next(p for p in spec.planted_paths if p.name == "dcsync-via-helpdesk")
        assert path.length == 3
        assert spec.label_of(path.end) == "DOMAIN"
        assert spec.label_of(path.start) == "USER"

    def test_the_owns_chain_traverses_a_homogeneous_edge(self, built) -> None:
        """H3's hard case must be exercised by construction, not by luck."""
        _, _, spec = built
        path = next(p for p in spec.planted_paths if p.name == "owns-chain-to-user")
        source, edge, target = path.steps[0]
        assert edge == "OWNS"
        assert spec.label_of(source) == spec.label_of(target) == "GROUP"

    def test_paths_touching_an_inferred_edge_say_so(self, built) -> None:
        _, _, spec = built
        dcsync = next(p for p in spec.planted_paths if p.name == "dcsync-via-helpdesk")
        assert dcsync.uses_inferred is True  # starts USER -MEMBER_OF-> GROUP
        shadow = next(p for p in spec.planted_paths if p.name == "shadow-credentials")
        assert shadow.uses_inferred is False


class TestSpecRoundTrip:
    def test_write_then_read_preserves_the_blueprint(self, built, tmp_path: Path) -> None:
        _, _, spec = built
        reloaded = TenantSpec.read(spec.write(tmp_path / "spec.json"))
        assert reloaded.counts() == spec.counts()
        assert reloaded.seed == spec.seed
        assert len(reloaded.planted_paths) == len(spec.planted_paths)
        assert reloaded.planted_paths[0].steps == spec.planted_paths[0].steps


class TestTheRealCatalog:
    @pytest.fixture(autouse=True)
    def _require_delivery(self) -> None:
        if not (catalog_dir() / "node_attributes.csv").is_file():
            pytest.skip("ReliaQuest delivery not present")

    @pytest.fixture()
    def real(self):
        cat = apply_inferred(read_catalog(name="identity"))
        return cat, generate(cat, seed=20260821)

    def test_every_declared_label_has_instances(self, real) -> None:
        """58 of 72 labels participate in no declared edge. They are still real
        declared types, and they are the abstention measurement's surface."""
        cat, (nodes, _, spec) = real
        populated = {n["label"] for n in nodes}
        assert populated == set(cat.node_attributes)
        assert len(populated) == 72

    def test_both_licence_spellings_have_instances(self, real) -> None:
        _, (_, _, spec) = real
        assert spec.nodes_of_label("ENTRA_LICENCE")
        assert spec.nodes_of_label("ENTRA_LICENSE")

    def test_the_tenant_is_the_intended_order_of_magnitude(self, real) -> None:
        _, (nodes, edges, _) = real
        assert 1000 <= len(nodes) <= 2000
        assert 3000 <= len(edges) <= 6000

    def test_all_eight_delivered_homogeneous_triples_are_populated(self, real) -> None:
        """H3 cannot be measured on a triple with no instances."""
        cat, (_, _, spec) = real
        homo = cat.homogeneous_triples(DECLARED)
        assert len(homo) == 8
        realised = {spec.triple_of(e) for e in spec.edges}
        for triple in homo:
            assert triple.key() in realised, f"{triple.key()} has no instances"

    def test_identifier_shapes_are_mixed_across_platforms(self, real) -> None:
        """H4 is only meaningful if the data was not built to satisfy it."""
        _, (_, _, spec) = real
        values = [
            v
            for node in spec.nodes.values()
            for v in node["properties"].values()
            if isinstance(v, str)
        ]
        assert any(v.startswith("arn:aws:") for v in values), "no ARNs"
        assert any(v.startswith("S-1-5-21-") for v in values), "no SIDs"
        assert any("@" in v for v in values), "no UPNs"
        assert any(v.startswith("0oa") or v.startswith("00g") for v in values), "no Okta ids"
        assert any(v.startswith("CN=") for v in values), "no DNs"
