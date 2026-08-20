#!/usr/bin/env python3
"""Generating a bank: disjointness, reproducibility, and the Author's guardrails.

Two properties are load-bearing and they pull against each other.

**The committed draw must not move.** `holdout_protocol.draw()` at the default
seed produced the anchors that EXP-2026-08-002 was built on, and that draw is
timestamped in `docs/evaluation/holdout-v1/anchors.json`. Adding an exclusion
parameter and a scale parameter must be a no-op at their defaults, or every v1
figure loses its provenance. The first test here pins that against the committed
file — a check the suite did not previously have.

**Successive banks must not overlap.** A fresh seed alone is not enough: over 59
reseeds against v1, 51% shared at least one anchor. Exclusion is the mechanism,
and its failure mode is silent — an overlapping bank still looks like a bank.
"""

from __future__ import annotations

import json

import pytest

from utils.specialists.evalset import make_bank
from utils.specialists.evalset.author import identifiers_in, rejection_reason
from utils.specialists.evalset.gold_bank import load_gold_bank
from utils.specialists.evalset.holdout_protocol import (
    AUTHOR_MODEL,
    HOLDOUT_SEED,
    REPO_ROOT,
    DrawExhausted,
    attack_population,
    compile_bank,
    capec_population,
    cwe_population,
    draw,
)

COMMITTED_ANCHORS = REPO_ROOT / "docs" / "evaluation" / "holdout-v1" / "anchors.json"


@pytest.fixture(scope="module")
def gold() -> dict:
    return load_gold_bank()


# -- the committed draw is immovable ----------------------------------------


@pytest.mark.skipif(not COMMITTED_ANCHORS.is_file(), reason="v1 anchors not present")
def test_the_committed_v1_draw_still_reproduces(gold: dict) -> None:
    """The exclusion and scale parameters must be no-ops at their defaults."""
    committed = json.loads(COMMITTED_ANCHORS.read_text())
    fresh = draw(gold)
    assert fresh["anchors"] == committed["anchors"]
    assert fresh["populations"] == committed["populations"]
    assert fresh["overdraw"] == committed["overdraw"]


def test_an_empty_exclusion_changes_nothing(gold: dict) -> None:
    assert draw(gold, exclude=set())["anchors"] == draw(gold)["anchors"]
    assert draw(gold, scale=1)["anchors"] == draw(gold)["anchors"]


# -- disjointness ------------------------------------------------------------


def test_excluded_anchors_never_appear(gold: dict) -> None:
    first = draw(gold, seed=HOLDOUT_SEED)
    used = {e["anchor"] for e in first["anchors"]}
    second = draw(gold, seed=20260819, exclude=used)
    assert used & {e["anchor"] for e in second["anchors"]} == set()


def test_exclusion_accumulates_over_successive_banks(gold: dict) -> None:
    """Three banks in a row, each disjoint from every one before it."""
    seen: set[str] = set()
    for seed in (HOLDOUT_SEED, 20260819, 20260820):
        anchors = {e["anchor"] for e in draw(gold, seed=seed, exclude=seen)["anchors"]}
        assert anchors & seen == set(), f"seed {seed} re-drew an earlier anchor"
        assert len(anchors) == 30
        seen |= anchors
    assert len(seen) == 90


def test_a_bare_reseed_is_not_enough(gold: dict) -> None:
    """State the reason exclusion exists, so nobody removes it as redundant.

    Not every reseed collides, so this asserts the measured population property
    rather than a single pair: across a span of seeds, some draw overlaps v1.
    """
    v1 = {e["anchor"] for e in draw(gold)["anchors"]}
    overlaps = [
        len(v1 & {e["anchor"] for e in draw(gold, seed=s)["anchors"]})
        for s in range(20260810, 20260825)
    ]
    assert any(overlaps), "expected at least one bare reseed to collide with v1"


def test_an_impossible_exclusion_raises_rather_than_shrinking(gold: dict) -> None:
    """A short bank would be silently incomparable to the last one."""
    everything = (
        set(attack_population(gold))
        | set(capec_population(gold))
        | set(cwe_population(gold))
    )
    with pytest.raises(DrawExhausted):
        draw(gold, seed=1, exclude=everything)


# -- scale -------------------------------------------------------------------


def test_scale_multiplies_the_bank_and_keeps_the_ratios(gold: dict) -> None:
    doubled = draw(gold, seed=777, scale=2)
    assert len(doubled["anchors"]) == 60
    assert doubled["strata"] == {"attack": 24, "capec": 16, "federated": 20}
    partitions = [e.get("partition") for e in doubled["anchors"] if e.get("partition")]
    assert partitions.count("answerable") == 12
    assert partitions.count("abstention-expected") == 8


def test_scale_must_be_positive(gold: dict) -> None:
    with pytest.raises(ValueError):
        draw(gold, scale=0)


# -- the Author's output guardrails -----------------------------------------


def test_a_question_naming_another_identifier_is_rejected() -> None:
    bad = "How does T1055.011 relate to T1003, and what mitigations apply?"
    assert "names other identifiers" in (rejection_reason(bad, "T1055.011") or "")


def test_a_question_that_never_names_its_anchor_is_rejected() -> None:
    assert "does not name its anchor" in (
        rejection_reason("What mitigations apply to this technique?", "T1176") or ""
    )


def test_a_parent_technique_is_not_a_stray_identifier() -> None:
    """`T1055.011` contains `T1055`; that must not read as naming two things."""
    good = "What mitigations are recommended for T1055.011 (Extra Window Memory Injection)?"
    assert rejection_reason(good, "T1055.011") is None


def test_a_clean_question_passes() -> None:
    assert rejection_reason("What does CAPEC-66 (SQL Injection) exploit?", "CAPEC-66") is None


def test_an_empty_answer_is_rejected() -> None:
    assert rejection_reason("   ", "T1176") == "empty"


def test_an_essay_is_rejected() -> None:
    essay = "T1176 " + ("x" * 700)
    assert "too long" in (rejection_reason(essay, "T1176") or "")


def test_identifier_scanning_covers_every_catalogue_shape() -> None:
    text = "T1055.011 TA0002 G0016 S0154 M1038 C0027 CAPEC-66 CWE-89"
    assert identifiers_in(text) == {
        "T1055.011", "TA0002", "G0016", "S0154", "M1038", "C0027", "CAPEC-66", "CWE-89",
    }


# -- the registry ------------------------------------------------------------


def test_the_registry_unions_every_recorded_bank() -> None:
    registry = {"banks": {
        "a": {"anchors": ["T1", "T2"]},
        "b": {"anchors": ["T2", "T3"]},
    }}
    assert make_bank.used_anchors(registry) == {"T1", "T2", "T3"}


def test_a_missing_registry_reads_as_empty(tmp_path) -> None:
    assert make_bank.used_anchors(make_bank.load_registry(tmp_path / "nope.json")) == set()


def test_the_committed_registry_covers_holdout_v1(gold: dict) -> None:
    """v1's anchors must be excluded by default, or bank 2 overlaps the burned set."""
    recorded = make_bank.used_anchors(make_bank.load_registry())
    assert {e["anchor"] for e in draw(gold)["anchors"]} <= recorded


# -- backend concurrency -----------------------------------------------------


def test_a_serial_model_is_clamped_to_one_worker() -> None:
    """`local` is llama.cpp single-stream; concurrency queues rather than parallelises.

    Asking it for 8 workers does not merely fail to speed anything up — every
    request lands behind the first and drifts towards the timeout, so a bank
    that would have generated slowly instead fails slowly. The clamp is not a
    performance tweak; it is what stops a correct run from looking like a dead
    server.
    """
    from utils.specialists.evalset.author import workers_for

    assert workers_for("local", 8) == 1
    assert workers_for("local", 1) == 1


def test_a_batching_model_keeps_its_workers() -> None:
    from utils.specialists.evalset.author import workers_for

    assert workers_for("skynet", 8) == 8
    assert workers_for("skynet", 0) == 1


def test_every_question_records_the_model_that_actually_wrote_it() -> None:
    """Per-question provenance must agree with the bank's own card.

    ``_meta`` hardcoded v1's hand-driven author, so bank-2026-08-19 — authored
    by ``local`` — shipped 30 questions each claiming a different author than
    the card printed two directories up. Provenance that disagrees with itself
    is worse than absent provenance: it reads as fact.
    """
    gold = load_gold_bank()
    drawn = draw(gold, seed=20260819, exclude=set(), scale=1)
    authored = {entry["id"]: f"What about {entry['anchor']}?" for entry in drawn["anchors"]}
    bank, _ = compile_bank(drawn, authored, gold, author_model="local @ http://x/v1")
    models = {q["holdout_meta"]["author_model"] for q in bank["questions"]}
    assert models == {"local @ http://x/v1"}
    assert bank["meta"]["author_model"] == "local @ http://x/v1"


def test_the_committed_v1_provenance_is_unchanged_when_no_model_is_passed() -> None:
    """Threading the value must not rewrite the bank already on disk."""
    gold = load_gold_bank()
    drawn = draw(gold, seed=HOLDOUT_SEED, exclude=set(), scale=1)
    authored = {entry["id"]: f"What about {entry['anchor']}?" for entry in drawn["anchors"]}
    bank, _ = compile_bank(drawn, authored, gold)
    assert {q["holdout_meta"]["author_model"] for q in bank["questions"]} == {AUTHOR_MODEL}
