#!/usr/bin/env python3

from __future__ import annotations

from utils.kg_builder.schema.capec import (
    CAPEC_ALLOWED_EDGE_PATTERNS,
    CAPEC_DERIVED_RELATIONSHIP_TYPES,
    CAPEC_NODE_LABELS,
    CAPEC_RELATIONSHIP_NATURES,
    CAPEC_RELATIONSHIP_TYPES,
    CAPEC_REQUIRED_NODE_PROPERTIES,
    build_schema_document,
    capec_canonical_labels,
)


def test_capec_node_labels_include_required_entities() -> None:
    required = {
        "AttackPattern",
        "Category",
        "View",
        "Weakness",
        "TaxonomyEntry",
        "ExternalReference",
        "ExecutionStep",
        "Skill",
        "Consequence",
        "Mitigation",
    }
    assert required.issubset(CAPEC_NODE_LABELS)


def test_capec_relationship_types_include_natures_and_derived_edges() -> None:
    for nature in ("ChildOf", "ParentOf", "CanPrecede", "CanFollow"):
        assert nature in CAPEC_RELATIONSHIP_NATURES
        assert nature in CAPEC_RELATIONSHIP_TYPES

    derived = {
        "EXPLOITS_WEAKNESS",
        "MAPS_TO",
        "MEMBER_OF",
        "IN_VIEW",
        "HAS_EXECUTION_STEP",
        "NEXT_STEP",
        "REQUIRES_SKILL",
        "HAS_CONSEQUENCE",
        "HAS_MITIGATION",
        "HAS_REFERENCE",
    }
    assert derived.issubset(CAPEC_DERIVED_RELATIONSHIP_TYPES)
    assert derived.issubset(CAPEC_RELATIONSHIP_TYPES)


def test_capec_required_properties_and_edge_patterns() -> None:
    assert CAPEC_REQUIRED_NODE_PROPERTIES["AttackPattern"] == ("id", "name")
    assert ("AttackPattern", "Weakness") in CAPEC_ALLOWED_EDGE_PATTERNS["EXPLOITS_WEAKNESS"]
    assert ("AttackPattern", "TaxonomyEntry") in CAPEC_ALLOWED_EDGE_PATTERNS["MAPS_TO"]
    assert ("ExecutionStep", "ExecutionStep") in CAPEC_ALLOWED_EDGE_PATTERNS["NEXT_STEP"]


def test_build_schema_document_includes_dataset_metadata() -> None:
    schema = build_schema_document("1.0")
    assert schema["dataset"] == "capec"
    assert "AttackPattern" in schema["node_labels"]
    assert "MAPS_TO" in schema["relationship_types"]


def test_capec_canonical_labels_include_capec_object() -> None:
    assert capec_canonical_labels("AttackPattern") == ["AttackPattern", "CapecObject"]


# -- the allowlist against the canonical snapshot ---------------------------
#
# Q45. `utils/specialists/gremlin/validator.py` treats a relationship missing
# from a *non-empty* allowlist as forbidden, so a declared edge with no pattern
# is rejected before its query runs. ATT&CK's allowlist is empty and therefore
# unconstrained, which means the more completely specified catalogue is the one
# that gets punished when this list falls behind. These two tests are what stop
# that happening again.


def _snapshot_edge_pairs() -> dict[str, set[tuple[str, str]]]:
    """Endpoint label pairs the canonical CAPEC snapshot actually carries."""
    import json
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[3] / "data/graphs/capec/canonical"
    nodes = root / "nodes.jsonl"
    relationships = root / "relationships.jsonl"
    if not nodes.exists() or not relationships.exists():
        import pytest

        pytest.skip("canonical CAPEC snapshot not built in this checkout")

    label = {}
    with nodes.open() as handle:
        for line in handle:
            node = json.loads(line)
            label[node["id"]] = node["label"]
    pairs: dict[str, set[tuple[str, str]]] = {}
    with relationships.open() as handle:
        for line in handle:
            edge = json.loads(line)
            pairs.setdefault(edge["type"], set()).add(
                (label[edge["source_id"]], label[edge["target_id"]])
            )
    return pairs


def test_every_declared_relationship_type_has_a_pattern() -> None:
    """A declared edge with no pattern is a forbidden edge, not an open one."""
    missing = sorted(CAPEC_RELATIONSHIP_TYPES - set(CAPEC_ALLOWED_EDGE_PATTERNS))
    assert missing == [], (
        f"declared but not allowlisted, so the gate will reject them: {missing}"
    )
    empty = sorted(k for k, v in CAPEC_ALLOWED_EDGE_PATTERNS.items() if not v)
    assert empty == [], f"allowlisted with an empty pattern set: {empty}"


def test_every_observed_edge_pair_is_allowlisted() -> None:
    """The patterns are derived from the data, not from the edge's name.

    The containment is one-way on purpose. Observed must be a subset of allowed,
    which is the safety property: nothing the graph holds is rejected. The
    reverse does not hold and should not be asserted — ``HAS_REFERENCE``
    allowlists Category and View sources that the current snapshot happens not to
    carry, and ``ParentOf`` is declared with zero observations. Demanding
    equality would make a *smaller* dataset fail the test.
    """
    observed = _snapshot_edge_pairs()
    unexpected = {
        rel_type: sorted(pairs - CAPEC_ALLOWED_EDGE_PATTERNS.get(rel_type, frozenset()))
        for rel_type, pairs in sorted(observed.items())
        if pairs - CAPEC_ALLOWED_EDGE_PATTERNS.get(rel_type, frozenset())
    }
    assert unexpected == {}, (
        "the snapshot carries endpoint pairs the allowlist forbids; the gate "
        f"will reject real edges: {unexpected}"
    )


def test_the_five_edges_behind_q45_carry_their_observed_pair() -> None:
    """Named individually, because these are the five Q45 is about."""
    assert CAPEC_ALLOWED_EDGE_PATTERNS["HAS_PREREQUISITE"] == frozenset(
        {("AttackPattern", "Prerequisite")}
    )
    assert CAPEC_ALLOWED_EDGE_PATTERNS["HAS_INDICATOR"] == frozenset(
        {("AttackPattern", "Indicator")}
    )
    assert CAPEC_ALLOWED_EDGE_PATTERNS["HAS_EXAMPLE"] == frozenset(
        {("AttackPattern", "Example")}
    )
    assert CAPEC_ALLOWED_EDGE_PATTERNS["REQUIRES_RESOURCE"] == frozenset(
        {("AttackPattern", "Resource")}
    )
    assert CAPEC_ALLOWED_EDGE_PATTERNS["HAS_ALTERNATE_TERM"] == frozenset(
        {("AttackPattern", "AlternateTerm")}
    )
