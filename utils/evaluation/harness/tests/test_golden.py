#!/usr/bin/env python3
"""Golden-loader tests: gold extraction + normalisation (hermetic, no DB)."""

from __future__ import annotations

import pytest

from utils.evaluation.harness.golden import (
    ALL_SETS,
    GoldenEntry,
    extract_gold,
    load_entries,
)


def test_extract_gold_single_source_unions_ids_and_related():
    entry = {
        "assertions": {
            "must_include_ids": ["T1047"],
            "must_include_related": ["M1018", "M1026"],
        }
    }
    ids, kind, expect_empty = extract_gold(entry, "attack")
    assert ids == frozenset({"T1047", "M1018", "M1026"})
    assert kind == "ids"
    assert expect_empty is False


def test_extract_gold_boundary_entry_is_empty_gold():
    entry = {"assertions": {"expect_boundary": True, "min_records": 0}}
    ids, kind, expect_empty = extract_gold(entry, "attack")
    assert ids == frozenset()
    assert expect_empty is True


def test_extract_gold_federated_uses_must_correlate():
    entry = {"assertions": {"must_correlate": ["T1003", "T1555"], "capec": {}, "attack": {}}}
    ids, kind, expect_empty = extract_gold(entry, "federated")
    assert ids == frozenset({"T1003", "T1555"})
    assert kind == "correlate"
    assert expect_empty is False


def test_extract_gold_federated_negative_is_empty_gold():
    entry = {"assertions": {"must_correlate": [], "expect_no_correlation": True}}
    ids, kind, expect_empty = extract_gold(entry, "federated")
    assert ids == frozenset()
    assert expect_empty is True


def test_extract_gold_rejects_unknown_via_load(monkeypatch):
    with pytest.raises(ValueError):
        load_entries(["nonsense"])


def test_load_entries_normalises_real_banks():
    # Uses the committed banks; no DB needed (pure JSON load).
    entries = load_entries(limit=2)
    assert entries, "expected at least some golden entries"
    assert all(isinstance(e, GoldenEntry) for e in entries)
    by_set = {e.set_name for e in entries}
    assert by_set == set(ALL_SETS)
    # limit=2 per set -> at most 6 total
    assert len(entries) <= 6
    for e in entries:
        assert e.kind in ("single", "federated")
        if e.set_name == "federated":
            assert e.kind == "federated"
            assert e.gold_kind == "correlate"
            assert e.source == "federated"
        else:
            assert e.kind == "single"
            assert e.gold_kind == "ids"
            assert e.source in ("attack", "capec")
        assert e.entry["id"] == e.question_id


def test_load_entries_tier_filter():
    easy = load_entries(["attack"], tiers={"easy"})
    assert easy
    assert all(e.tier == "easy" for e in easy)
