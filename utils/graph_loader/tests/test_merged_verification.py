#!/usr/bin/env python3
"""Post-load verification in a deliberately merged store (C-015).

`verify_loaded_graph` compares graph-wide totals against one dataset's manifest.
That is exactly right for the one-dataset-per-store arrangement every backend
uses today, and exactly wrong for the merged-graph counterfactual: loading
ATT&CK and then CAPEC into one instance leaves ~9138 nodes where CAPEC's
manifest expects 4769, and `Mitigation` holds both catalogues' mitigations. The
data landed correctly; the invariant simply stopped being the invariant.

`ARIADNE_ALLOW_MERGED_GRAPH=1` relaxes *overshoot* only. Undershoot still fails
everywhere, because a count below expectation means records did not land, and
that is a real failure in any store. The opt-in is explicit rather than a silent
tolerance: on a normal single-dataset load a mismatch means something is wrong
and must keep failing loudly.
"""

from __future__ import annotations

import pytest

from utils.graph_loader.models import CountSummary
from utils.graph_loader.stores.memory import MemoryGraphStore


def _store_with(nodes: int, label: str = "Technique") -> MemoryGraphStore:
    store = MemoryGraphStore()
    store.connect()
    store.ensure_schema({})
    store.upsert_nodes([
        {"id": f"n{i}", "label": label, "labels": [label], "properties": {}}
        for i in range(nodes)
    ])
    return store


def _expected(nodes: int, label: str = "Technique") -> CountSummary:
    return CountSummary(
        nodes=nodes, edges=0, nodes_by_label={label: nodes}, edges_by_type={}
    )


def test_a_normal_load_still_fails_on_any_mismatch(monkeypatch) -> None:
    monkeypatch.delenv("ARIADNE_ALLOW_MERGED_GRAPH", raising=False)
    store = _store_with(9)
    result = store.verify_loaded_graph(_expected(4))
    assert not result.passed, "overshoot must fail when the merged opt-in is absent"


def test_a_merged_store_tolerates_a_superset(monkeypatch) -> None:
    """The second dataset's records are legitimately extra, not corruption."""
    monkeypatch.setenv("ARIADNE_ALLOW_MERGED_GRAPH", "1")
    store = _store_with(9)
    assert store.verify_loaded_graph(_expected(4)).passed


def test_a_merged_store_still_fails_when_records_are_missing(monkeypatch) -> None:
    """The check that actually matters must survive the relaxation.

    If it did not, a merged load that silently dropped half its records would
    report success, and the counterfactual would be measured against a graph
    missing the data it exists to hold.
    """
    monkeypatch.setenv("ARIADNE_ALLOW_MERGED_GRAPH", "1")
    store = _store_with(3)
    result = store.verify_loaded_graph(_expected(10))
    assert not result.passed
    assert any("node count" in e for e in result.errors)


def test_a_merged_store_fails_on_a_missing_label(monkeypatch) -> None:
    monkeypatch.setenv("ARIADNE_ALLOW_MERGED_GRAPH", "1")
    store = _store_with(5, label="Technique")
    expected = CountSummary(
        nodes=5, edges=0, nodes_by_label={"Technique": 5, "AttackPattern": 8},
        edges_by_type={},
    )
    result = store.verify_loaded_graph(expected)
    assert not result.passed
    assert any("AttackPattern" in e for e in result.errors)


def test_an_exact_match_passes_either_way(monkeypatch) -> None:
    for value in (None, "1"):
        if value is None:
            monkeypatch.delenv("ARIADNE_ALLOW_MERGED_GRAPH", raising=False)
        else:
            monkeypatch.setenv("ARIADNE_ALLOW_MERGED_GRAPH", value)
        assert _store_with(6).verify_loaded_graph(_expected(6)).passed


@pytest.mark.parametrize("flag", ["0", "false", "no", "", "off"])
def test_only_an_affirmative_flag_relaxes_the_check(monkeypatch, flag: str) -> None:
    """A typo'd flag must not quietly disable a real invariant."""
    monkeypatch.setenv("ARIADNE_ALLOW_MERGED_GRAPH", flag)
    assert not _store_with(9).verify_loaded_graph(_expected(4)).passed
