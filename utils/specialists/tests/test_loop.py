#!/usr/bin/env python3
"""Tests for the shared specialist scaffold loop (intake → … → handoff)."""

from __future__ import annotations

from utils.specialists.base import QuerySpecialist
from utils.specialists.errors import ExecutionError
from utils.specialists.tests._fixtures import (
    StubBuilder,
    StubConnector,
    StubNormalizer,
    StubValidator,
    fixture_card,
    make_task,
)


def _specialist(card, *, builder=None, validator=None, connector=None, max_retries=2):
    return QuerySpecialist(
        card=card,
        builder=builder or StubBuilder(),
        validator=validator or StubValidator(),
        connector=connector or StubConnector(),
        normalizer=StubNormalizer(card),
        max_retries=max_retries,
    )


def _steps(result) -> list[str]:
    return [t.step for t in result.traces]


def test_happy_path_returns_records_and_full_trace() -> None:
    card = fixture_card("attack")
    connector = StubConnector(rows=[{"id": "ap--1", "attack_id": "T1047", "name": "WMI"}])
    spec = _specialist(card, connector=connector)
    result = spec.run(make_task())
    assert result.ok
    assert not result.partial
    assert [r.primary_id for r in result.records] == ["T1047"]
    assert _steps(result) == ["intake", "resolve", "gate", "execute", "assess", "normalize"]
    assert connector.connected and connector.closed
    assert result.summary == "1 record(s)"


def test_intake_rejects_wrong_source_without_connecting() -> None:
    card = fixture_card("attack")
    connector = StubConnector()
    spec = _specialist(card, connector=connector)
    result = spec.run(make_task(source="capec"))
    assert not result.ok
    assert result.error and "serves 'attack'" in result.error
    assert _steps(result) == ["intake"]
    assert not connector.connected


def test_gate_rejection_exhausts_retries_and_never_hits_db() -> None:
    card = fixture_card("attack")
    connector = StubConnector()
    spec = _specialist(
        card,
        validator=StubValidator(reject=["unknown label X"]),
        connector=connector,
        max_retries=2,
    )
    result = spec.run(make_task())
    assert not result.ok
    assert result.partial
    assert "pre-run gate rejected" in (result.error or "")
    # 1 initial + 2 retries = 3 gate attempts, none executed.
    assert _steps(result).count("gate") == 3
    assert connector.run_count == 0
    assert not connector.connected


def test_builder_receives_gate_feedback_on_retry() -> None:
    card = fixture_card("attack")
    builder = StubBuilder()
    spec = _specialist(
        card, builder=builder, validator=StubValidator(reject=["fix me"]), max_retries=1
    )
    spec.run(make_task())
    # First call has no feedback; the retry is handed the gate's reasons.
    assert builder.feedback_seen[0] is None
    assert builder.feedback_seen[1] == ["fix me"]


def test_execution_error_is_terminal_and_closes_connector() -> None:
    card = fixture_card("attack")
    connector = StubConnector(raise_on_run=ExecutionError("server timeout"))
    spec = _specialist(card, connector=connector)
    result = spec.run(make_task())
    assert not result.ok
    assert result.partial
    assert "server timeout" in (result.error or "")
    assert "execute" in _steps(result)
    assert connector.closed


def test_empty_result_is_valid_not_an_error() -> None:
    card = fixture_card("attack")
    spec = _specialist(card, connector=StubConnector(rows=[]))
    result = spec.run(make_task())
    assert result.ok
    assert result.records == []
    assert result.summary == "0 record(s)"
