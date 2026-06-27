#!/usr/bin/env python3

from __future__ import annotations

import time

import pytest

from utils.planner.cards import SourceCardView
from utils.planner.config import PlannerConfig
from utils.planner.discovery import (
    LiveSourceProbe,
    get_live_sources,
)
from utils.planner.tests._fixtures import load_fixture_cards


# -- fake stores -----------------------------------------------------------


class FakeStore:
    def __init__(self, *, total: int = 100, per_label: int = 5, connect_error: Exception | None = None,
                 sleep: float = 0.0) -> None:
        self._total = total
        self._per_label = per_label
        self._connect_error = connect_error
        self._sleep = sleep
        self.closed = False

    def connect(self) -> None:
        if self._sleep:
            time.sleep(self._sleep)
        if self._connect_error is not None:
            raise self._connect_error

    def close(self) -> None:
        self.closed = True

    def count_nodes(self) -> int:
        return self._total

    def count_by_label(self, label: str) -> int:
        return self._per_label


def _config(**kw) -> PlannerConfig:
    base = dict(data_dir="data", probe_timeout_s=2.0, cache_ttl_s=5.0, min_live_nodes=1)
    base.update(kw)
    return PlannerConfig(**base)  # type: ignore[arg-type]


def _factory(store: FakeStore):
    def factory(card: SourceCardView, config: PlannerConfig) -> FakeStore:
        return store
    return factory


# -- single-source content probe -------------------------------------------


def test_live_source_with_content_is_live() -> None:
    capec = load_fixture_cards()["capec"]
    probe = LiveSourceProbe(_config(), store_factory=_factory(FakeStore(total=4888, per_label=10)))
    result = probe.probe_source(capec)
    assert result.live
    assert result.node_count == 4888
    assert result.observed_labels  # at least one expected label present
    assert result.reason == "live"


def test_reachable_but_empty_graph_is_down() -> None:
    capec = load_fixture_cards()["capec"]
    probe = LiveSourceProbe(_config(), store_factory=_factory(FakeStore(total=0)))
    result = probe.probe_source(capec)
    assert not result.live
    assert "empty" in result.reason


def test_up_but_expected_labels_absent_is_down() -> None:
    capec = load_fixture_cards()["capec"]
    # non-trivial node count, but no expected label resolves (per_label=0)
    probe = LiveSourceProbe(_config(), store_factory=_factory(FakeStore(total=50, per_label=0)))
    result = probe.probe_source(capec)
    assert not result.live
    assert "expected labels" in result.reason


def test_connect_failure_is_down_with_reason() -> None:
    attack = load_fixture_cards()["attack"]
    probe = LiveSourceProbe(
        _config(), store_factory=_factory(FakeStore(connect_error=ConnectionError("refused")))
    )
    result = probe.probe_source(attack)
    assert not result.live
    assert "unreachable or unauthorized" in result.reason


def test_hanging_probe_times_out_and_is_down() -> None:
    attack = load_fixture_cards()["attack"]
    probe = LiveSourceProbe(
        _config(probe_timeout_s=0.2), store_factory=_factory(FakeStore(sleep=2.0))
    )
    started = time.monotonic()
    result = probe.probe_source(attack)
    elapsed = time.monotonic() - started
    assert not result.live
    assert "timed out" in result.reason
    assert elapsed < 1.5  # did not wait for the full 2s hang


# -- per-request caching ----------------------------------------------------


class CountingFactory:
    def __init__(self, store: FakeStore) -> None:
        self.calls = 0
        self._store = store

    def __call__(self, card: SourceCardView, config: PlannerConfig) -> FakeStore:
        self.calls += 1
        return self._store


def test_cache_reused_within_ttl_then_reprobed() -> None:
    cards = load_fixture_cards()
    fake = FakeStore(total=100, per_label=5)
    factory = CountingFactory(fake)
    clock = {"t": 1000.0}
    probe = LiveSourceProbe(_config(cache_ttl_s=5.0), store_factory=factory, clock=lambda: clock["t"])

    probe.get_live_sources(cards)
    first_calls = factory.calls
    assert first_calls == len(cards)  # one probe per card

    # within TTL: cache hit, no new probes
    clock["t"] = 1003.0
    probe.get_live_sources(cards)
    assert factory.calls == first_calls

    # past TTL: re-probe
    clock["t"] = 1010.0
    probe.get_live_sources(cards)
    assert factory.calls == first_calls + len(cards)

    # force ignores cache
    probe.get_live_sources(cards, force=True)
    assert factory.calls == first_calls + 2 * len(cards)


def test_view_live_and_down_partitions() -> None:
    cards = load_fixture_cards()

    def factory(card: SourceCardView, config: PlannerConfig) -> FakeStore:
        if card.dataset == "capec":
            return FakeStore(total=4888, per_label=10)
        return FakeStore(connect_error=ConnectionError("down"))

    view = get_live_sources(cards, _config(), store_factory=factory)
    assert view.is_live("capec")
    assert not view.is_live("attack")
    assert view.live_datasets() == ["capec"]
    assert view.down_datasets() == ["attack"]


@pytest.mark.parametrize("dataset", ["attack", "capec"])
def test_unknown_backend_is_down(dataset: str) -> None:
    card = SourceCardView.from_card_dict(
        {"dataset": dataset, "runtime_backend": "mystery", "node_labels": ["X"], "relationship_types": []}
    )
    probe = LiveSourceProbe(_config(), store_factory=_factory(FakeStore()))
    result = probe.probe_source(card)
    assert not result.live
