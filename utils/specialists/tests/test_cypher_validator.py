#!/usr/bin/env python3
"""Pure-unit tests for CypherValidator — no database required.

Covers every documented rule:
  - Structural: single statement, MATCH + RETURN required.
  - Read-only: rejects write clauses from the card safety block.
  - Schema: rejects unknown node labels and relationship types; rejects
    attack_id filter with no node label.
  - Cap injection: LIMIT appended when missing, clamped when over the max.
"""

from __future__ import annotations

import pytest

from utils.specialists.cypher.validator import CypherValidator
from utils.specialists.tests._fixtures import fixture_card
from utils.specialists.validation import QueryDraft


@pytest.fixture
def card():
    return fixture_card("attack")


@pytest.fixture
def validator():
    return CypherValidator()


@pytest.fixture
def limits():
    return {"max_traversal_depth": 3, "max_result_rows": 100, "query_timeout_ms": 5000}


def _make_draft(query: str) -> QueryDraft:
    return QueryDraft(query=query, params={}, template="test")


# ---------------------------------------------------------------------------
# Positive — a well-formed query passes the gate
# ---------------------------------------------------------------------------


def test_valid_query_passes(validator, card, limits):
    draft = _make_draft(
        "MATCH (t:Technique)<-[:MITIGATES]-(m:Mitigation) "
        "WHERE t.attack_id IN $ids "
        "RETURN t.attack_id AS id, m.name AS mitigation"
    )
    result = validator.validate(draft, card, limits)
    assert result.ok, result.reasons
    assert "LIMIT" in result.query  # cap was injected


# ---------------------------------------------------------------------------
# Structural failures
# ---------------------------------------------------------------------------


def test_rejects_multi_statement(validator, card, limits):
    draft = _make_draft(
        "MATCH (t:Technique) RETURN t; MATCH (n) RETURN n"
    )
    result = validator.validate(draft, card, limits)
    assert not result.ok
    assert any("multiple statements" in r for r in result.reasons)


def test_rejects_missing_match(validator, card, limits):
    draft = _make_draft("RETURN 1")
    result = validator.validate(draft, card, limits)
    assert not result.ok
    assert any("MATCH" in r for r in result.reasons)


def test_rejects_missing_return(validator, card, limits):
    draft = _make_draft("MATCH (t:Technique) WHERE t.name = 'X' DELETE t")
    result = validator.validate(draft, card, limits)
    assert not result.ok
    # Should flag both: missing RETURN and write clause
    assert any("RETURN" in r for r in result.reasons)


def test_trailing_semicolon_is_allowed(validator, card, limits):
    draft = _make_draft(
        "MATCH (t:Technique) RETURN t.attack_id AS id, t.name AS name;"
    )
    result = validator.validate(draft, card, limits)
    assert result.ok, result.reasons


# ---------------------------------------------------------------------------
# Read-only violations
# ---------------------------------------------------------------------------


def test_rejects_create(validator, card, limits):
    draft = _make_draft(
        "MATCH (t:Technique) CREATE (m:Mitigation {name: 'x'}) RETURN m"
    )
    result = validator.validate(draft, card, limits)
    assert not result.ok
    assert any("CREATE" in r for r in result.reasons)


def test_rejects_set(validator, card, limits):
    draft = _make_draft(
        "MATCH (t:Technique) WHERE t.attack_id = 'T1047' "
        "SET t.name = 'hacked' RETURN t"
    )
    result = validator.validate(draft, card, limits)
    assert not result.ok
    assert any("SET" in r for r in result.reasons)


def test_rejects_delete(validator, card, limits):
    draft = _make_draft(
        "MATCH (t:Technique) WHERE t.attack_id = 'T1047' DELETE t RETURN 1"
    )
    result = validator.validate(draft, card, limits)
    assert not result.ok
    assert any("DELETE" in r for r in result.reasons)


def test_rejects_merge(validator, card, limits):
    draft = _make_draft(
        "MATCH (t:Technique) MERGE (m:Mitigation {name: 'x'}) RETURN m"
    )
    result = validator.validate(draft, card, limits)
    assert not result.ok
    assert any("MERGE" in r for r in result.reasons)


# ---------------------------------------------------------------------------
# Schema violations
# ---------------------------------------------------------------------------


def test_rejects_unknown_label(validator, card, limits):
    draft = _make_draft(
        "MATCH (n:Foo) RETURN n.attack_id AS id, n.name AS name"
    )
    result = validator.validate(draft, card, limits)
    assert not result.ok
    assert any("Foo" in r for r in result.reasons)


def test_rejects_unknown_relationship(validator, card, limits):
    draft = _make_draft(
        "MATCH (t:Technique)-[:INVENTED_BY]->(g:Group) "
        "RETURN t.attack_id AS id, t.name AS name"
    )
    result = validator.validate(draft, card, limits)
    assert not result.ok
    assert any("INVENTED_BY" in r for r in result.reasons)


def test_rejects_attack_id_filter_without_label(validator, card, limits):
    """attack_id filter with no node label should be rejected (ambiguous STIX type)."""
    draft = _make_draft(
        "MATCH (n) WHERE n.attack_id IN $ids RETURN n.name AS name"
    )
    result = validator.validate(draft, card, limits)
    assert not result.ok
    assert any("attack_id" in r and "label" in r for r in result.reasons)


# ---------------------------------------------------------------------------
# LIMIT injection and clamping
# ---------------------------------------------------------------------------


def test_limit_injected_when_missing(validator, card, limits):
    draft = _make_draft(
        "MATCH (t:Technique) RETURN t.attack_id AS id, t.name AS name"
    )
    result = validator.validate(draft, card, limits)
    assert result.ok, result.reasons
    assert "LIMIT 100" in result.query
    assert any("appended" in note for note in result.injected)


def test_limit_clamped_when_over_max(validator, card, limits):
    draft = _make_draft(
        "MATCH (t:Technique) RETURN t.attack_id AS id, t.name AS name LIMIT 9999"
    )
    result = validator.validate(draft, card, limits)
    assert result.ok, result.reasons
    assert "LIMIT 100" in result.query
    assert "LIMIT 9999" not in result.query
    assert any("clamped" in note for note in result.injected)


def test_limit_kept_when_within_max(validator, card, limits):
    draft = _make_draft(
        "MATCH (t:Technique) RETURN t.attack_id AS id, t.name AS name LIMIT 10"
    )
    result = validator.validate(draft, card, limits)
    assert result.ok, result.reasons
    assert "LIMIT 10" in result.query
    assert not result.injected  # no injection was needed


# ---------------------------------------------------------------------------
# Variable-length path cap — unbounded / over-deep expansions are rejected
# ---------------------------------------------------------------------------


def test_rejects_unbounded_variable_length_path(validator, card, limits):
    draft = _make_draft(
        "MATCH (g:Group)-[:USES*]->(t:Technique) "
        "RETURN t.attack_id AS id, t.name AS name"
    )
    result = validator.validate(draft, card, limits)
    assert not result.ok
    assert any("unbounded" in r for r in result.reasons)


def test_rejects_over_depth_variable_length_path(validator, card, limits):
    draft = _make_draft(
        "MATCH (g:Group)-[:USES*1..9]->(t:Technique) "
        "RETURN t.attack_id AS id, t.name AS name"
    )
    result = validator.validate(draft, card, limits)
    assert not result.ok
    assert any("exceeds" in r and "max_traversal_depth" in r for r in result.reasons)


def test_allows_bounded_variable_length_within_cap(validator, card, limits):
    draft = _make_draft(
        "MATCH (g:Group)-[:USES*1..2]->(t:Technique) "
        "RETURN t.attack_id AS id, t.name AS name"
    )
    result = validator.validate(draft, card, limits)
    assert result.ok, result.reasons
