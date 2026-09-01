#!/usr/bin/env python3
"""Composition enumerator — no database, no LLM.

The enumerator produces gold. Every score the expanded bank ever reports is
measured against it, so a wrong gold set is not a bug that shows up as a test
failure — it shows up as a *system* score, months later, pointing the wrong way.
These tests exist because nothing downstream can catch that.

The strongest check is the last group: gold computed by walking `raw_graph` must
equal gold computed by `gold_bank`, which parses the same two files by a
different route and shares no code. The federated chain check is the sharpest of
all, because it is the one place the two catalogues have to be joined, and a
join done wrong produces a plausible non-empty answer rather than an error.
"""

from __future__ import annotations

import json
import re

import pytest

from utils.specialists.evalset import composition as comp
from utils.specialists.evalset import raw_graph as rg
from utils.specialists.evalset.gold_bank import load_gold_bank
from utils.specialists.evalset.schema_census import build_census


@pytest.fixture(scope="module")
def graph() -> rg.RawGraph:
    return rg.build()


@pytest.fixture(scope="module")
def census() -> dict:
    return build_census()


@pytest.fixture(scope="module")
def specs(graph: rg.RawGraph, census: dict) -> list[comp.Spec]:
    return comp.enumerate_specs(graph, census, per_shape_limit=4)


# --- the invariants every spec must hold -------------------------------------


def test_only_D0_has_empty_gold(specs: list[comp.Spec]) -> None:
    """An answerable question with no answer is a question defect, not a hard one."""
    assert comp.summarise(specs)["empty_gold_outside_D0"] == 0
    assert all(not s.gold for s in specs if s.tier == "D0")


def test_enumeration_is_deterministic(graph: rg.RawGraph, census: dict) -> None:
    """Same graph, same seed, same specs — or no result is reproducible."""
    first = comp.enumerate_specs(graph, census, per_shape_limit=2, seed=7)
    second = comp.enumerate_specs(graph, census, per_shape_limit=2, seed=7)
    assert [s.id for s in first] == [s.id for s in second]
    assert [s.gold for s in first] == [s.gold for s in second]


def test_a_different_seed_draws_differently(graph: rg.RawGraph, census: dict) -> None:
    """A seed that changes nothing would make the sampling a lie."""
    a = comp.enumerate_specs(graph, census, per_shape_limit=2, seed=7)
    b = comp.enumerate_specs(graph, census, per_shape_limit=2, seed=8)
    assert {s.id for s in a} != {s.id for s in b}


def test_every_spec_is_anchored_on_something_nameable(specs: list[comp.Spec]) -> None:
    """A question has to be able to refer to its own subject."""
    for spec in specs:
        assert spec.anchor_key
        assert spec.anchor_label not in comp.DERIVED_LABELS


def test_the_neutral_query_is_not_a_dialect(specs: list[comp.Spec]) -> None:
    """A gold query in Cypher or Gremlin would favour whichever arm speaks it."""
    blob = json.dumps([s.query for s in specs])
    for token in ("MATCH ", "RETURN ", "g.V(", "->()", "MERGE "):
        assert token not in blob


def test_query_round_trips_to_the_same_gold(graph: rg.RawGraph, specs: list[comp.Spec]) -> None:
    """The published query must reproduce the published gold.

    If these drift, the released benchmark ships an answer key that its own
    query does not produce.
    """
    for spec in specs[:400]:
        if spec.kind == "property":
            continue
        steps = tuple(
            comp.Step(
                predicate=s["predicate"], reverse=s["direction"] == "in", label=s["label"]
            )
            for s in spec.query["steps"]
        )
        filters = tuple(comp.Filter(**f) for f in spec.query["filters"])
        assert comp.gold_for(graph, spec.anchor_id, steps, filters) == spec.gold, spec.id


# --- tier semantics ----------------------------------------------------------


def test_tiers_are_structurally_what_they_claim(specs: list[comp.Spec]) -> None:
    for spec in specs:
        if spec.tier == "D1":
            assert not spec.steps
        elif spec.tier == "D2":
            assert len(spec.steps) == 1 and not spec.steps[0].reverse
        elif spec.tier == "D3":
            assert len(spec.steps) == 1 and spec.steps[0].reverse
        elif spec.tier == "D4":
            assert len(spec.steps) == 2
            assert not any(s.predicate == "MAPS_TO[ATTACK]" for s in spec.steps)
        elif spec.tier == "D5":
            assert spec.filters
        elif spec.tier == "D6":
            assert any(s.predicate == "MAPS_TO[ATTACK]" for s in spec.steps)


def test_D5_constraints_actually_remove_something(
    graph: rg.RawGraph, specs: list[comp.Spec]
) -> None:
    """A filter that changes no answer lets a system ignoring it score full marks."""
    for spec in specs:
        if spec.tier != "D5":
            continue
        unfiltered = comp.gold_for(graph, spec.anchor_id, spec.steps)
        assert spec.gold != unfiltered, spec.id
        assert set(spec.gold) < set(unfiltered), spec.id


def test_D0_is_plausible_not_a_category_error(specs: list[comp.Spec]) -> None:
    """"Which attack patterns can this ATT&CK analytic also be" tests nothing."""
    capec_only = {"ChildOf", "CanPrecede", "CanAlsoBe", "PeerOf", "CanFollow"}
    for spec in specs:
        if spec.tier != "D0" or not spec.steps:
            continue
        if spec.steps[0].predicate in capec_only:
            assert spec.anchor_label in {"AttackPattern", "Category", "View", "Weakness"}, spec.id


def test_D6_never_anchors_on_a_dangling_reference(
    graph: rg.RawGraph, specs: list[comp.Spec]
) -> None:
    """Their gold would be empty for a reason the question does not disclose."""
    dangling = {n.id for n in graph.dangling()}
    for spec in specs:
        if spec.tier == "D6" and spec.anchor_label == "AttackPattern":
            mapped = set(graph.out(spec.anchor_id, "MAPS_TO[ATTACK]"))
            if mapped:
                assert mapped - dangling, spec.id


# --- agreement with the independent derivation -------------------------------

#: shape -> (gold_bank table, whether that table is keyed by the edge's object).
#: `technique_mitigations` is keyed by technique — the object — and the other
#: four by their subject. Getting this backwards produces an empty expectation
#: that reads as a mismatch, which is how it was caught.
_GOLD_TABLES: dict[str, tuple[tuple[str, str], bool]] = {
    "Mitigation -[mitigates]-> Technique": (("attack", "technique_mitigations"), True),
    "Group -[uses]-> Technique": (("attack", "group_techniques"), False),
    "Software -[uses]-> Technique": (("attack", "software_techniques"), False),
    "AttackPattern -[MAPS_TO[ATTACK]]-> Technique": (("capec", "attack_mappings"), False),
    "AttackPattern -[EXPLOITS_WEAKNESS]-> Weakness": (("capec", "related_weaknesses"), False),
}


def _expected(table: dict, key: str, *, forward: bool) -> set[str]:
    if forward:
        return set(table.get(key, []))
    return {k for k, values in table.items() if key in values}


def test_single_hop_gold_matches_gold_bank(specs: list[comp.Spec]) -> None:
    gold = load_gold_bank()
    compared = 0
    for spec in specs:
        if spec.tier not in {"D2", "D3"} or len(spec.steps) != 1:
            continue
        entry = _GOLD_TABLES.get(spec.shapes[0])
        if entry is None:
            continue
        (source, name), object_keyed = entry
        table = gold[source][name]
        # The table is keyed by subject unless `object_keyed`; a D3 spec walks
        # the edge backwards, so the two flips cancel.
        forward = (spec.tier == "D2") != object_keyed
        # `gold_bank` parses declarations, so it keeps the 10 CAPEC-declared
        # technique ids ATT&CK has no live object for. A spec splits those out
        # as `dangling`; the union is the comparable quantity.
        declared = set(spec.gold) | set(spec.dangling)
        assert _expected(table, spec.anchor_key, forward=forward) == declared, spec.id
        compared += 1
    assert compared >= 20, f"only {compared} specs were covered by the cross-check"


def test_the_dangling_split_is_actually_exercised(
    graph: rg.RawGraph, census: dict
) -> None:
    """A split nothing triggers is a split nobody has tested.

    The 10 dangling ids are concentrated in a handful of CAPEC patterns, so a
    small per-shape sample can miss them entirely. This draws the whole mapping
    shape rather than a sample of it.
    """
    specs = comp.enumerate_specs(graph, census, per_shape_limit=None, tiers=["D2"])
    mapping = [
        s for s in specs if s.shapes[0] == "AttackPattern -[MAPS_TO[ATTACK]]-> Technique"
    ]
    with_dangling = [s for s in mapping if s.dangling]
    assert with_dangling, "no mapping spec reached a dangling reference"
    dangling_keys = {n.key for n in graph.dangling()}
    for spec in with_dangling:
        assert set(spec.dangling) <= dangling_keys
        assert not (set(spec.gold) & set(spec.dangling))


def test_sub_element_gold_is_prose_not_an_invented_id(specs: list[comp.Spec]) -> None:
    """`CAPEC-31#HAS_CONSEQUENCE-1` is this pipeline's invention, not an answer.

    Grading "what consequences can CAPEC-31 have" against synthetic ids would
    score a correct prose answer as entirely wrong. The first render pilot
    produced exactly that question with exactly that gold, which is how this
    was found.
    """
    derived = [s for s in specs if s.return_label in comp.DERIVED_LABELS and s.gold]
    assert derived, "expected specs returning CAPEC sub-elements"
    for spec in derived:
        assert spec.gold_kind == "text_set", spec.id
        for answer in spec.gold:
            # Match the synthetic id shape, not a bare "#": CAPEC example text
            # legitimately contains URL fragments.
            assert not re.match(r"^CAPEC-\d+#", answer), (spec.id, answer[:80])


def test_gold_kind_matches_what_the_answer_actually_is(specs: list[comp.Spec]) -> None:
    for spec in specs:
        if spec.kind == "property":
            assert spec.gold_kind in {"set", "text"}
        elif spec.return_label in comp.DERIVED_LABELS:
            assert spec.gold_kind == "text_set", spec.id
        else:
            assert spec.gold_kind == "set", spec.id


def test_federated_chain_gold_matches_gold_bank(specs: list[comp.Spec]) -> None:
    """The one place the catalogues are joined; a wrong join looks like an answer."""
    gold = load_gold_bank()
    mappings = gold["capec"]["attack_mappings"]
    mitigations = gold["attack"]["technique_mitigations"]
    compared = 0
    for spec in specs:
        if spec.tier != "D6" or spec.anchor_label != "AttackPattern":
            continue
        if [s.predicate for s in spec.steps] != ["MAPS_TO[ATTACK]", "mitigates"]:
            continue
        expected: set[str] = set()
        for technique in mappings.get(spec.anchor_key, []):
            expected |= set(mitigations.get(technique, []))
        assert expected == set(spec.gold), spec.id
        compared += 1
    assert compared >= 4, f"only {compared} federated chains were checked"
