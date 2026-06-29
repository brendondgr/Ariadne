#!/usr/bin/env python3
"""Tests for the shared validator base (orchestration + read-only helper)."""

from __future__ import annotations

from typing import Any

from utils.specialists.validation import BaseValidator, QueryDraft, word_present


def test_word_present_whole_word_case_insensitive() -> None:
    assert word_present("MATCH (n) CREATE (m)", "create")
    assert word_present("match (n) detach delete n", "DETACH DELETE")
    # substring that is not a whole word must not match
    assert not word_present("MATCH (n) RETURN n.created_at", "create")


def test_word_present_handles_non_word_terms() -> None:
    assert word_present("CALL { MATCH (n) }", "CALL { ")


class _OrderValidator(BaseValidator):
    kind = "test"

    def __init__(self, *, struct=None, ro=None, schema=None) -> None:
        self._struct = struct or []
        self._ro = ro or []
        self._schema = schema or []
        self.injected_called = False

    def structural_reasons(self, query: str) -> list[str]:
        return list(self._struct)

    def violates_read_only(self, query: str, card: Any) -> list[str]:
        return list(self._ro)

    def schema_reasons(self, query: str, card: Any) -> list[str]:
        return list(self._schema)

    def inject_caps(self, query: str, limits: dict[str, int], card: Any) -> tuple[str, list[str]]:
        self.injected_called = True
        return query + " LIMIT 10", ["injected LIMIT 10"]


def test_validate_collects_all_reasons_and_skips_injection_on_failure() -> None:
    v = _OrderValidator(struct=["bad shape"], ro=["write step"], schema=["unknown label"])
    result = v.validate(QueryDraft(query="MATCH (n) RETURN n"), card=None, limits={})
    assert not result.ok
    assert set(result.reasons) == {"bad shape", "write step", "unknown label"}
    assert not v.injected_called  # caps are never injected for a rejected query


def test_validate_injects_caps_when_clean() -> None:
    v = _OrderValidator()
    result = v.validate(QueryDraft(query="MATCH (n) RETURN n"), card=None, limits={"max_result_rows": 10})
    assert result.ok
    assert result.query.endswith("LIMIT 10")
    assert result.injected == ["injected LIMIT 10"]


def test_validate_rejects_empty_query() -> None:
    v = _OrderValidator()
    result = v.validate(QueryDraft(query="   "), card=None, limits={})
    assert not result.ok
    assert result.reasons == ["empty query"]
