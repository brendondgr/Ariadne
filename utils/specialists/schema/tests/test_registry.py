#!/usr/bin/env python3
"""Registry derivation tests, against a small committed-shape canonical fixture.

Every assertion here runs on a fixture written into ``tmp_path`` so the suite is
hermetic — it does not depend on the gitignored ``data/graphs`` artifacts. A
final opt-in test cross-checks the derivation against the real ATT&CK canonical
when it happens to be present locally, and skips otherwise.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils.specialists.schema import (
    build_dataset_schema,
    build_registry,
    discover_datasets,
    get_registry,
)
from utils.specialists.schema.degree_stats import degree_stats
from utils.specialists.schema.registry import PlausibleFacet


# -- fixture -----------------------------------------------------------------

# A miniature ATT&CK-shaped graph plus a self-referential bidirectional edge.
_NODES = [
    {"id": "t1", "label": "Technique", "properties": {"attack_id": "T1000", "name": "Tech One", "description": "d"}},
    {"id": "t1a", "label": "SubTechnique", "properties": {"attack_id": "T1000.001", "name": "Sub One", "description": "d"}},
    {"id": "m1", "label": "Mitigation", "properties": {"attack_id": "M1000", "name": "Mit One"}},
    {"id": "ta1", "label": "Tactic", "properties": {"name": "Tactic One"}},
    {"id": "p1", "label": "Pattern", "properties": {"name": "P1"}},
    {"id": "p2", "label": "Pattern", "properties": {"name": "P2"}},
]
_RELS = [
    {"id": "r1", "type": "HAS_SUBTECHNIQUE", "source_id": "t1", "target_id": "t1a"},
    {"id": "r2", "type": "MITIGATES", "source_id": "m1", "target_id": "t1"},
    {"id": "r3", "type": "HAS_TECHNIQUE", "source_id": "ta1", "target_id": "t1"},
    # Bidirectional, self-referential: both P1->P2 and P2->P1 exist.
    {"id": "r4", "type": "CanFollow", "source_id": "p1", "target_id": "p2"},
    {"id": "r5", "type": "CanFollow", "source_id": "p2", "target_id": "p1"},
    # An edge with a dangling endpoint contributes no triple.
    {"id": "r6", "type": "USES", "source_id": "ghost", "target_id": "t1"},
]


def _write_canonical(data_dir: Path, dataset: str, nodes, rels) -> None:
    canonical = data_dir / "graphs" / dataset / "canonical"
    canonical.mkdir(parents=True, exist_ok=True)
    (canonical / "nodes.jsonl").write_text(
        "\n".join(json.dumps(n) for n in nodes) + "\n", encoding="utf-8"
    )
    (canonical / "relationships.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rels) + "\n", encoding="utf-8"
    )


@pytest.fixture()
def mini_data_dir(tmp_path: Path) -> Path:
    _write_canonical(tmp_path, "mini", _NODES, _RELS)
    return tmp_path


# -- label & property derivation --------------------------------------------


def test_all_labels_are_derived(mini_data_dir: Path) -> None:
    schema = build_registry(mini_data_dir).dataset("mini")
    assert schema is not None
    assert schema.labels() == frozenset(
        {"Technique", "SubTechnique", "Mitigation", "Tactic", "Pattern"}
    )


def test_property_keys_are_the_union_over_nodes(mini_data_dir: Path) -> None:
    schema = build_registry(mini_data_dir).dataset("mini")
    assert schema.label_properties("Technique") == frozenset(
        {"attack_id", "name", "description"}
    )
    assert schema.label_properties("Tactic") == frozenset({"name"})
    assert schema.label_properties("NoSuchLabel") == frozenset()


# -- facet derivation --------------------------------------------------------


def test_technique_facets_both_directions(mini_data_dir: Path) -> None:
    schema = build_registry(mini_data_dir).dataset("mini")
    facets = schema.label_facets("Technique")
    assert set(facets) == {
        PlausibleFacet("HAS_SUBTECHNIQUE", "out", "SubTechnique"),
        PlausibleFacet("MITIGATES", "in", "Mitigation"),
        PlausibleFacet("HAS_TECHNIQUE", "in", "Tactic"),
    }
    # Deterministically ordered.
    assert list(facets) == sorted(facets)


def test_inbound_facet_is_visible_from_the_target_label(mini_data_dir: Path) -> None:
    # The Tacos/Lettuce property: given m1 -[MITIGATES]-> t1, the *Technique*
    # side must surface the inbound MITIGATES facet, and the Mitigation side the
    # outbound one. This is the bidirectional visibility the Gremlin dossier lost.
    schema = build_registry(mini_data_dir).dataset("mini")
    assert PlausibleFacet("MITIGATES", "in", "Mitigation") in schema.label_facets("Technique")
    assert PlausibleFacet("MITIGATES", "out", "Technique") in schema.label_facets("Mitigation")


def test_self_referential_edge_yields_both_directions(mini_data_dir: Path) -> None:
    schema = build_registry(mini_data_dir).dataset("mini")
    assert set(schema.label_facets("Pattern")) == {
        PlausibleFacet("CanFollow", "out", "Pattern"),
        PlausibleFacet("CanFollow", "in", "Pattern"),
    }


def test_dangling_endpoint_contributes_no_triple(mini_data_dir: Path) -> None:
    schema = build_registry(mini_data_dir).dataset("mini")
    # r6 (USES, ghost -> t1) has a source outside the node file: no USES facet.
    assert all(f.rel_type != "USES" for f in schema.label_facets("Technique"))


# -- facet_exists (validator surface) ---------------------------------------


def test_facet_exists_is_the_validator_check(mini_data_dir: Path) -> None:
    reg = build_registry(mini_data_dir)
    assert reg.facet_exists("Technique", "MITIGATES", "in", "Mitigation", dataset="mini")
    assert reg.facet_exists("Technique", "MITIGATES", "in", dataset="mini")  # any neighbour
    # Wrong direction, wrong neighbour, wrong rel, and a bad direction token.
    assert not reg.facet_exists("Technique", "MITIGATES", "out", "Mitigation", dataset="mini")
    assert not reg.facet_exists("Technique", "MITIGATES", "in", "Tactic", dataset="mini")
    assert not reg.facet_exists("Technique", "DETECTS", "in", dataset="mini")
    assert not reg.facet_exists("Technique", "MITIGATES", "sideways", dataset="mini")


# -- multi-dataset + label collisions ---------------------------------------


def test_datasets_are_kept_separate(tmp_path: Path) -> None:
    _write_canonical(tmp_path, "mini", _NODES, _RELS)
    _write_canonical(
        tmp_path,
        "other",
        [
            {"id": "x", "label": "Mitigation", "properties": {"foo": 1}},
            {"id": "y", "label": "Thing", "properties": {}},
        ],
        [{"id": "e", "type": "BLOCKS", "source_id": "x", "target_id": "y"}],
    )
    reg = build_registry(tmp_path)
    assert set(reg.dataset_names()) == {"mini", "other"}
    # "Mitigation" exists in both with different property keys — kept per dataset.
    assert reg.label_properties("Mitigation", dataset="mini") == frozenset({"attack_id", "name"})
    assert reg.label_properties("Mitigation", dataset="other") == frozenset({"foo"})
    # Cross-dataset union when no dataset is named.
    assert reg.label_properties("Mitigation") == frozenset({"attack_id", "name", "foo"})


def test_discover_datasets(tmp_path: Path) -> None:
    _write_canonical(tmp_path, "mini", _NODES, _RELS)
    _write_canonical(tmp_path, "other", _NODES, _RELS)
    assert discover_datasets(tmp_path) == ["mini", "other"]
    assert discover_datasets(tmp_path / "nope") == []


# -- caching -----------------------------------------------------------------


def test_get_registry_is_cached_per_path(tmp_path: Path) -> None:
    _write_canonical(tmp_path, "mini", _NODES, _RELS)
    get_registry.cache_clear()
    first = get_registry(tmp_path)
    second = get_registry(tmp_path)
    assert first is second  # same object -> cache hit, not rebuilt
    get_registry.cache_clear()


# -- degree stats guard ------------------------------------------------------


def test_degree_stats_bounds_facets_below_degree(mini_data_dir: Path) -> None:
    stats = degree_stats(mini_data_dir, "mini")
    assert stats["nodes"] == 6
    # t1 has degree 4 (subtech + mitigates + has_technique + dangling-uses) but
    # only 4 distinct facet rows at most; the guard is facets <= a small constant
    # regardless of degree — the plan's "the facet block is free".
    assert stats["max_facet_rows"] <= stats["nodes"]
    assert stats["max_degree"] >= stats["max_facet_rows"]


# -- opt-in cross-check against the real ATT&CK canonical --------------------


def _real_data_present() -> bool:
    return Path("data/graphs/attack/canonical/nodes.jsonl").is_file()


@pytest.mark.skipif(not _real_data_present(), reason="real canonical artifacts not present")
def test_real_attack_technique_facets_and_labels() -> None:
    get_registry.cache_clear()
    schema = build_registry("data").dataset("attack")
    assert schema is not None
    assert schema.labels() == frozenset(
        {
            "Analytic", "Campaign", "DataComponent", "DetectionStrategy", "Group",
            "Matrix", "Mitigation", "Software", "SubTechnique", "Tactic", "Technique",
        }
    )
    tech = set(schema.label_facets("Technique"))
    assert PlausibleFacet("HAS_SUBTECHNIQUE", "out", "SubTechnique") in tech
    assert PlausibleFacet("MITIGATES", "in", "Mitigation") in tech
    assert PlausibleFacet("DETECTS", "in", "DetectionStrategy") in tech
    assert "description" in schema.label_properties("Technique")


# -- native properties: one rule, two readers (Q55) --------------------------


def test_native_property_rule_is_the_loader_s_own() -> None:
    """The registry must not disagree with the store about what is queryable.

    A builder emits a ``WHERE`` clause only for a property the registry calls
    native. If that rule ever drifts from the loader's, the clause matches
    nothing rather than erroring — which is exactly how 23 development questions
    lost their whole gold coverage before this was tied together.
    """
    from utils.graph_loader.stores.neo4j import _native_property_values
    from utils.specialists.schema.build import build_dataset_schema  # noqa: F401

    props = {
        "Abstraction": "Standard",           # scalar
        "x_mitre_platforms": ["Windows"],    # list of scalars
        "x_mitre_version": 2,                # numeric scalar
        "revoked": False,                    # boolean scalar
        "external_references": [{"a": 1}],   # list of maps — not storable
        "nested": {"a": 1},                  # map — not storable
        "id": "T1055",                       # core, set explicitly
    }
    native = set(_native_property_values(props))
    assert native == {
        "Abstraction",
        "x_mitre_platforms",
        "x_mitre_version",
        "revoked",
    }


def test_a_property_seen_once_as_a_map_is_not_native_anywhere() -> None:
    """One non-storable observation disqualifies the property for that label.

    The store cannot hold it for *that* node, so a filter on it would silently
    miss the node rather than report it. All-or-nothing is the only reading that
    cannot produce a quiet wrong answer.
    """
    import json
    import tempfile
    from pathlib import Path

    from utils.specialists.schema.build import build_dataset_schema

    with tempfile.TemporaryDirectory() as tmp:
        nodes = Path(tmp) / "nodes.jsonl"
        edges = Path(tmp) / "relationships.jsonl"
        nodes.write_text(
            json.dumps({"id": "a", "label": "L", "properties": {"p": "scalar"}})
            + "\n"
            + json.dumps({"id": "b", "label": "L", "properties": {"p": {"k": 1}}})
            + "\n"
        )
        edges.write_text("")
        schema = build_dataset_schema("d", nodes, edges)

    assert not schema.is_native_property("L", "p")
