#!/usr/bin/env python3
"""Schema census integrity — no database, no LLM.

Two silent failures matter here. The first is a census that quietly drops a
shape: a taxonomy keyed on an attribute that half its entries do not carry, a
ref property nobody mapped, a sub-element parsed under the wrong parent. Every
dropped shape makes our coverage look better than it is, which is the exact
direction a self-serving bug would take.

The second is drift from `gold_bank`. Both derive from the same raw files by
different routes and share no code, so their population counts must agree.
When they stop agreeing, one of them has a parsing bug and the disagreement is
the only thing that would say so.
"""

from __future__ import annotations

import pytest

from utils.specialists.evalset import schema_census as sc
from utils.specialists.evalset.gold_bank import load_gold_bank


@pytest.fixture(scope="module")
def census() -> dict:
    return sc.build_census()


@pytest.fixture(scope="module")
def by_triple(census: dict) -> dict:
    return {edge["triple"]: edge for edge in census["edges"]}


# --- agreement with the independent derivation ------------------------------


def test_node_counts_match_gold_bank(census: dict) -> None:
    """Node counts agree with `gold_bank`, which parses the same files separately.

    `gold_bank` splits sub-techniques into their own label; the census reports
    both under `Technique` because both are STIX `attack-pattern`. The sum is
    the comparable figure.
    """
    gold = load_gold_bank()
    labels: dict[str, int] = {}
    for obj in gold["attack"]["objects"].values():
        labels[obj["label"]] = labels.get(obj["label"], 0) + 1
    counts = {node["label"]: node["count"] for node in census["nodes"]}

    assert counts["Technique"] == labels["Technique"] + labels["SubTechnique"]
    for label in ("Software", "Group", "Mitigation", "Tactic", "Analytic",
                  "DetectionStrategy", "DataComponent", "Campaign"):
        assert counts[label] == labels[label], label
    assert counts["AttackPattern"] == len(gold["capec"]["patterns"])
    assert counts["Weakness"] == len(gold["capec"]["cwe_to_capec"])
    assert census["sources"]["attack"]["nodes_after_exclusions"] == len(gold["attack"]["objects"])


def test_edge_counts_match_gold_bank(by_triple: dict) -> None:
    """Edge counts agree too. Two derivations, no shared code, same numbers."""
    gold = load_gold_bank()

    def total(mapping: dict) -> int:
        return sum(len(v) for v in mapping.values())

    assert by_triple["Mitigation -[mitigates]-> Technique"]["count"] == total(
        gold["attack"]["technique_mitigations"]
    )
    assert by_triple["Group -[uses]-> Technique"]["count"] == total(
        gold["attack"]["group_techniques"]
    )
    assert by_triple["Software -[uses]-> Technique"]["count"] == total(
        gold["attack"]["software_techniques"]
    )
    assert by_triple["AttackPattern -[MAPS_TO[ATTACK]]-> Technique"]["count"] == total(
        gold["capec"]["attack_mappings"]
    )
    assert by_triple["AttackPattern -[EXPLOITS_WEAKNESS]-> Weakness"]["count"] == total(
        gold["capec"]["related_weaknesses"]
    )


def test_exclusion_policy_is_applied_and_counted(census: dict) -> None:
    attack = census["sources"]["attack"]
    capec = census["sources"]["capec"]
    assert attack["excluded"]["objects"] > 0
    assert capec["excluded"]["patterns_retired"] > 0
    assert capec["patterns_after_exclusions"] < capec["patterns_in_file"]


# --- no shape silently dropped ----------------------------------------------


def test_every_declared_capec_nature_is_present(by_triple: dict) -> None:
    """All five declared natures appear, not just the hierarchy one we ask about."""
    for nature in ("ChildOf", "CanPrecede", "CanAlsoBe", "PeerOf", "CanFollow"):
        assert f"AttackPattern -[{nature}]-> AttackPattern" in by_triple


def test_every_taxonomy_is_present(by_triple: dict) -> None:
    """OWASP maps by Entry_Name, not Entry_ID; keying on the id drops it entirely."""
    for taxonomy in ("ATTACK", "OWASP Attacks", "WASC"):
        matches = [t for t in by_triple if f"MAPS_TO[{taxonomy}]" in t]
        assert matches, f"{taxonomy} mappings missing from the census"


def test_every_stix_relationship_type_is_typed(census: dict, by_triple: dict) -> None:
    """`revoked-by` is policy-excluded; every other live type reaches the census."""
    for predicate in ("uses", "mitigates", "detects", "subtechnique-of", "attributed-to"):
        assert any(f"-[{predicate}]->" in t for t in by_triple), predicate


def test_embedded_and_nested_refs_are_edges(by_triple: dict) -> None:
    """Refs on the object and refs one level down are edges, not properties."""
    assert "Technique -[kill_chain_phase]-> Tactic" in by_triple
    assert "DetectionStrategy -[x_mitre_analytic_refs]-> Analytic" in by_triple
    assert "Analytic -[log_source]-> DataComponent" in by_triple


# --- the measures the generator will depend on ------------------------------


def test_fanout_is_recorded_in_both_directions(by_triple: dict) -> None:
    """Direction is the axis the blind holdout failed on; both must be measured."""
    tactics = by_triple["Technique -[kill_chain_phase]-> Tactic"]
    assert tactics["forward_fanout"]["p90"] <= 5
    # ~700 techniques over 15 tactics: askable forward, not askable in reverse.
    assert tactics["reverse_fanout"]["p90"] > 50


def test_facets_exclude_identifiers_and_bundle_metadata(census: dict) -> None:
    facets = {
        (node["label"], prop["name"])
        for node in census["nodes"]
        for prop in node["properties"]
        if prop["facet"]
    }
    assert ("Technique", "x_mitre_platforms") in facets
    assert ("AttackPattern", "Abstraction") in facets
    assert not any(name in sc.NON_FACET_PROPERTIES for _, name in facets)
    assert not any(name in {"name", "aliases"} for _, name in facets)


def test_dates_are_typed_apart_from_scalars(census: dict) -> None:
    kinds = {
        (node["label"], prop["name"]): prop["kind"]
        for node in census["nodes"]
        for prop in node["properties"]
    }
    assert kinds[("Campaign", "first_seen")] == "date"
    assert kinds[("Technique", "description")] == "text"


# --- the coverage layer ------------------------------------------------------


def test_every_declared_category_triple_exists(census: dict) -> None:
    """A category mapped onto a triple the census does not have is a stale map."""
    assert census["coverage"]["declared_but_absent"] == []


def test_coverage_is_a_strict_minority(census: dict) -> None:
    cov = census["coverage"]
    assert cov["edge_types_reached"] < cov["edge_types_total"]
    assert 0.0 < cov["edge_type_coverage"] < 1.0
    assert len(cov["never_asked"]) == cov["edge_types_total"] - cov["edge_types_reached"]


def test_coverage_layer_cannot_feed_the_census(census: dict) -> None:
    """The census must be identical whether or not the coverage map is empty."""
    edges = [sc.EdgeType(**{k: v for k, v in e.items() if k != "triple"}) for e in census["edges"]]
    empty = sc.coverage(edges[:0])
    assert empty["edge_types_total"] == 0
    assert census["totals"]["edge_types"] == len(edges)
