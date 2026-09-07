"""Unit tests for the SSE keep-alive wrapper.

These use a deliberately slow fake producer rather than the real pipeline: the
property under test is timing, and a test that needed a model to be slow would
be both slow and flaky.
"""

from __future__ import annotations

import time
from typing import Iterator

import pytest

from api.services.heartbeat import HEARTBEAT, with_heartbeat


def _slow(items: list[object], delay_s: float) -> Iterator[object]:
    for item in items:
        time.sleep(delay_s)
        yield item


def test_quiet_producer_yields_heartbeats() -> None:
    out = list(with_heartbeat(_slow(["a"], 0.25), interval_s=0.05))
    assert out[-1] == "a"
    assert out.count(HEARTBEAT) >= 2, "a silent stage must keep the socket warm"


def test_items_are_preserved_in_order_and_never_replaced() -> None:
    out = [x for x in with_heartbeat(_slow(["a", "b", "c"], 0.02), interval_s=0.05)]
    assert [x for x in out if x is not HEARTBEAT] == ["a", "b", "c"]


def test_fast_producer_needs_no_heartbeat() -> None:
    out = list(with_heartbeat(iter(["a", "b"]), interval_s=5.0))
    assert out == ["a", "b"]


def test_producer_exception_reaches_the_consumer() -> None:
    def boom() -> Iterator[object]:
        yield "a"
        raise RuntimeError("pipeline failed")

    seen: list[object] = []
    with pytest.raises(RuntimeError, match="pipeline failed"):
        for item in with_heartbeat(boom(), interval_s=5.0):
            seen.append(item)
    assert seen == ["a"], "items before the failure are still delivered"


def test_empty_producer_terminates() -> None:
    assert list(with_heartbeat(iter([]), interval_s=5.0)) == []


def test_interval_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    from api.services import heartbeat

    monkeypatch.setenv(heartbeat.INTERVAL_ENV_VAR, "0.05")
    out = list(with_heartbeat(_slow(["a"], 0.25)))
    assert out.count(HEARTBEAT) >= 2


def test_unusable_interval_falls_back_to_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    from api.services import heartbeat

    for bad in ("", "nonsense", "0", "-3"):
        monkeypatch.setenv(heartbeat.INTERVAL_ENV_VAR, bad)
        assert heartbeat.heartbeat_interval_s() == heartbeat.DEFAULT_INTERVAL_S
