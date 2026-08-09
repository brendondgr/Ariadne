#!/usr/bin/env python3
"""Holdout sampler integrity — no database, no LLM.

These tests exist to catch the two silent failures plan 02 §0 names: anchors
drawn from the rich part of the graph, and a draw that cannot be reproduced. If
the draw stops being deterministic, or starts correlating with degree, the
holdout stops measuring what it claims to and nothing else in the repository
would notice.
"""

from __future__ import annotations

import pytest

from utils.specialists.evalset import holdout_protocol as hp
from utils.specialists.evalset.gold_bank import load_gold_bank


@pytest.fixture(scope="module")
def gold() -> dict:
    return load_gold_bank()


@pytest.fixture(scope="module")
def result(gold: dict) -> dict:
    return hp.draw(gold)


# -- reproducibility --------------------------------------------------------


def test_seed_is_not_the_bootstrap_seed() -> None:
    """1729 is `utils/evaluation/stats.py`'s resampling seed; §2.3 forbids reuse."""
    assert hp.HOLDOUT_SEED != 1729


def test_draw_is_deterministic(gold: dict) -> None:
    first, second = hp.draw(gold), hp.draw(gold)
    assert [a["anchor"] for a in first["anchors"]] == [a["anchor"] for a in second["anchors"]]
    assert first["populations"] == second["populations"]


def test_a_different_seed_gives_a_different_draw(gold: dict) -> None:
    other = hp.draw(gold, seed=hp.HOLDOUT_SEED + 1)
    base = hp.draw(gold)
    assert [a["anchor"] for a in other["anchors"]] != [a["anchor"] for a in base["anchors"]]


# -- populations ------------------------------------------------------------


def test_population_sizes_match_the_pinned_snapshot(result: dict) -> None:
    """The counts plan 02 §2.1 states, recomputed rather than trusted."""
    assert result["populations"]["attack"]["size"] == 697   # 222 Technique + 475 Sub
    assert result["populations"]["capec"]["size"] == 558    # live patterns
    assert result["populations"]["cwe"]["size"] == 336      # bridged weaknesses


def test_no_excluded_attack_id_is_in_the_population(gold: dict) -> None:
    excluded = set(gold["attack"]["excluded_ids"])
    assert not excluded & set(hp.attack_population(gold))


def test_no_retired_capec_pattern_is_in_the_population(gold: dict) -> None:
    retired = set(gold["capec"]["deprecated"])
    assert not retired & set(hp.capec_population(gold))


def test_capec_population_keeps_the_unmapped_majority(gold: dict) -> None:
    """§2.4 — filtering these out would be filtering out the point."""
    population = hp.capec_population(gold)
    unmapped = [c for c in population if not hp.live_mappings(gold, c)]
    assert len(unmapped) > len(population) / 2


# -- strata -----------------------------------------------------------------


def test_strata_counts_are_exact(result: dict) -> None:
    counts: dict[str, int] = {}
    for entry in result["anchors"]:
        counts[entry["stratum"]] = counts.get(entry["stratum"], 0) + 1
    assert counts == hp.STRATA
    assert len(result["anchors"]) == 30


def test_every_anchor_is_distinct(result: dict) -> None:
    anchors = [a["anchor"] for a in result["anchors"]]
    assert len(set(anchors)) == len(anchors)


def test_ids_are_unique_and_h_prefixed(result: dict) -> None:
    ids = [a["id"] for a in result["anchors"]]
    assert len(set(ids)) == 30
    assert all(i.startswith("H-") for i in ids)


def test_every_category_is_covered(result: dict) -> None:
    drawn = {a["category"] for a in result["anchors"]}
    assert drawn >= set(hp.ATTACK_CATEGORIES)
    assert drawn >= set(hp.CAPEC_CATEGORIES)
    assert drawn == (
        set(hp.ATTACK_CATEGORIES) | set(hp.CAPEC_CATEGORIES) | set(hp.FEDERATED_CATEGORIES)
    )


# -- the federated partition ------------------------------------------------


def test_federated_partition_hits_the_targets(result: dict) -> None:
    fed = [a for a in result["anchors"] if a["stratum"] == "federated"]
    answerable = [a for a in fed if a["partition"] == "answerable"]
    abstention = [a for a in fed if a["partition"] == "abstention-expected"]
    assert len(answerable) == hp.FEDERATED_ANSWERABLE
    assert len(abstention) == hp.FEDERATED_ABSTENTION


def test_partition_is_decided_only_by_live_correlation(gold: dict, result: dict) -> None:
    """The partition rule is "does the chain terminate live", nothing else."""
    for entry in result["anchors"]:
        if entry["stratum"] != "federated":
            continue
        correlate = hp.federated_correlation(gold, entry["category"], entry["anchor"])
        expected = "answerable" if correlate else "abstention-expected"
        assert entry["partition"] == expected
        assert entry["correlation_size"] == len(correlate)


def test_federated_was_over_drawn_not_filtered(result: dict) -> None:
    """§2.4 requires the surplus to be recorded, so the partition is auditable."""
    assert any(o["stratum"] == "federated" for o in result["overdraw"])


# -- no richness weighting --------------------------------------------------


def test_single_source_anchors_are_feasible_but_not_rich(gold: dict, result: dict) -> None:
    """Feasibility means "the relation exists", never "it has many neighbours".

    A weighted sampler would show up as a floor on neighbour count well above 1.
    """
    sizes = [
        len(hp.neighbours(gold, a["category"], a["anchor"]))
        for a in result["anchors"]
        if a["stratum"] in ("attack", "capec") and a["category"] != "lookup"
    ]
    assert all(size >= 1 for size in sizes)
    assert min(sizes) == 1, "no anchor with a single neighbour was drawn — check for weighting"


def test_drawn_anchors_are_not_the_famous_ones(result: dict) -> None:
    """A model asked to invent anchors reaches for these; a uniform draw does not."""
    famous = {"T1003", "T1055", "T1059", "T1027", "T1078", "CAPEC-66", "CAPEC-98"}
    assert not famous & {a["anchor"] for a in result["anchors"]}


# -- the Author prompt ------------------------------------------------------


def test_author_prompt_leaks_nothing(result: dict) -> None:
    """The write-lock is what the prompt does NOT contain (plan §3)."""
    forbidden = (
        "utils/", "docs/", "README", ".json", ".py", "template", "expected_template",
        "gold", "assert", "Cypher", "Gremlin", "Neo4j",
    )
    for entry in result["anchors"]:
        prompt = hp.author_prompt(entry)
        lowered = prompt.lower()
        for token in forbidden:
            assert token.lower() not in lowered, f"{entry['id']} prompt leaks {token!r}"


def test_author_prompt_carries_exactly_the_permitted_facts(result: dict) -> None:
    for entry in result["anchors"]:
        prompt = hp.author_prompt(entry)
        assert entry["anchor"] in prompt
        assert entry["name"] in prompt
        assert entry["entity_type"] in prompt
        # …and no other anchor from the draw.
        others = {a["anchor"] for a in result["anchors"]} - {entry["anchor"]}
        assert not any(other in prompt for other in others)
