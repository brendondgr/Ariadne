#!/usr/bin/env python3
"""Pure-unit tests for GremlinValidator (no DB required).

Tests every rule category: structural, read-only safety, schema conformance
(labels, edge types, directions), and cap injection (limit inject/clamp,
traversal depth).  All assertions are deterministic.
"""

from __future__ import annotations

import pytest

from utils.specialists.tests._fixtures import fixture_card
from utils.specialists.validation import QueryDraft
from utils.specialists.gremlin.validator import GremlinValidator


@pytest.fixture()
def card():
    return fixture_card("capec")


@pytest.fixture()
def validator():
    return GremlinValidator()


@pytest.fixture()
def limits(card):
    return {
        "max_traversal_depth": 3,
        "max_result_rows": 1000,
        "query_timeout_ms": 5000,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _draft(query: str, params: dict | None = None) -> QueryDraft:
    return QueryDraft(query=query, params=params or {})


def _validate(validator, card, limits, query: str):
    return validator.validate(_draft(query), card, limits)


# ---------------------------------------------------------------------------
# Structural checks
# ---------------------------------------------------------------------------

class TestStructural:
    def test_valid_start_gV(self, validator, card, limits):
        result = _validate(validator, card, limits,
            'g.V().hasLabel("AttackPattern").elementMap().limit(10)')
        assert result.ok

    def test_valid_start_gE(self, validator, card, limits):
        result = _validate(validator, card, limits, 'g.E().limit(5)')
        assert result.ok

    def test_rejects_match_start(self, validator, card, limits):
        result = _validate(validator, card, limits,
            'MATCH (n) RETURN n')
        assert not result.ok
        assert any("g.V(" in r or "g.E(" in r for r in result.reasons)

    def test_rejects_plain_string(self, validator, card, limits):
        result = _validate(validator, card, limits, "SELECT * FROM nodes")
        assert not result.ok


# ---------------------------------------------------------------------------
# Read-only safety checks
# ---------------------------------------------------------------------------

class TestReadOnly:
    def test_rejects_addV(self, validator, card, limits):
        result = _validate(validator, card, limits,
            'g.V().addV("AttackPattern").property("id", "x")')
        assert not result.ok
        assert any("addV" in r for r in result.reasons)

    def test_rejects_addE(self, validator, card, limits):
        result = _validate(validator, card, limits,
            'g.V().hasLabel("AttackPattern").addE("MAPS_TO")')
        assert not result.ok
        assert any("addE" in r for r in result.reasons)

    def test_rejects_drop(self, validator, card, limits):
        result = _validate(validator, card, limits,
            'g.V().hasLabel("AttackPattern").drop()')
        assert not result.ok
        assert any("drop" in r for r in result.reasons)

    def test_rejects_property_step(self, validator, card, limits):
        result = _validate(validator, card, limits,
            'g.V().hasLabel("AttackPattern").property("name", "evil")')
        assert not result.ok
        assert any("property" in r for r in result.reasons)

    def test_allows_values_step(self, validator, card, limits):
        """values() is a read step and must not be rejected."""
        result = _validate(validator, card, limits,
            'g.V().hasLabel("AttackPattern").values("name").limit(10)')
        assert result.ok


# ---------------------------------------------------------------------------
# Schema checks — node labels
# ---------------------------------------------------------------------------

class TestSchemaLabels:
    def test_allows_known_label(self, validator, card, limits):
        result = _validate(validator, card, limits,
            'g.V().hasLabel("AttackPattern").elementMap().limit(5)')
        assert result.ok

    def test_rejects_unknown_label(self, validator, card, limits):
        result = _validate(validator, card, limits,
            'g.V().hasLabel("Foo").elementMap().limit(5)')
        assert not result.ok
        assert any("Foo" in r for r in result.reasons)

    def test_allows_taxonomy_entry_label(self, validator, card, limits):
        result = _validate(validator, card, limits,
            'g.V().hasLabel("TaxonomyEntry").elementMap().limit(5)')
        assert result.ok


# ---------------------------------------------------------------------------
# Schema checks — edge types
# ---------------------------------------------------------------------------

class TestSchemaEdges:
    def test_rejects_unknown_relationship(self, validator, card, limits):
        result = _validate(validator, card, limits,
            'g.V().hasLabel("AttackPattern").out("NOPE").elementMap().limit(5)')
        assert not result.ok
        assert any("NOPE" in r for r in result.reasons)

    def test_allows_exploits_weakness(self, validator, card, limits):
        result = _validate(validator, card, limits,
            'g.V().hasLabel("AttackPattern").out("EXPLOITS_WEAKNESS")'
            '.hasLabel("Weakness").elementMap().limit(5)')
        assert result.ok

    def test_allows_maps_to(self, validator, card, limits):
        result = _validate(validator, card, limits,
            'g.V().hasLabel("AttackPattern").out("MAPS_TO")'
            '.hasLabel("TaxonomyEntry").elementMap().limit(10)')
        assert result.ok


# ---------------------------------------------------------------------------
# Schema checks — edge direction
# ---------------------------------------------------------------------------

class TestSchemaDirections:
    def test_rejects_wrong_direction_exploits_weakness(self, validator, card, limits):
        """EXPLOITS_WEAKNESS goes AttackPattern->Weakness; traversing out() from
        Weakness anchor must be rejected."""
        result = _validate(validator, card, limits,
            'g.V().hasLabel("Weakness").out("EXPLOITS_WEAKNESS").elementMap().limit(5)')
        assert not result.ok
        assert any("EXPLOITS_WEAKNESS" in r for r in result.reasons)

    def test_rejects_wrong_direction_maps_to(self, validator, card, limits):
        """MAPS_TO goes AttackPattern->TaxonomyEntry; out() from TaxonomyEntry is wrong."""
        result = _validate(validator, card, limits,
            'g.V().hasLabel("TaxonomyEntry").out("MAPS_TO").elementMap().limit(5)')
        assert not result.ok
        assert any("MAPS_TO" in r for r in result.reasons)

    def test_correct_direction_has_mitigation(self, validator, card, limits):
        result = _validate(validator, card, limits,
            'g.V().hasLabel("AttackPattern").out("HAS_MITIGATION")'
            '.hasLabel("Mitigation").elementMap().limit(5)')
        assert result.ok


# ---------------------------------------------------------------------------
# Cap injection — limit
# ---------------------------------------------------------------------------

class TestLimitInjection:
    def test_injects_limit_when_absent(self, validator, card, limits):
        result = _validate(validator, card, limits,
            'g.V().hasLabel("AttackPattern").elementMap()')
        assert result.ok
        assert any("inject" in note.lower() for note in result.injected)
        assert ".limit(" in result.query

    def test_preserves_limit_within_cap(self, validator, card, limits):
        result = _validate(validator, card, limits,
            'g.V().hasLabel("AttackPattern").elementMap().limit(50)')
        assert result.ok
        assert ".limit(50)" in result.query
        assert not result.injected  # nothing injected

    def test_clamps_overlimit(self, validator, card, limits):
        result = _validate(validator, card, limits,
            'g.V().hasLabel("AttackPattern").elementMap().limit(9999)')
        assert result.ok
        assert ".limit(1000)" in result.query
        assert any("clamp" in note.lower() for note in result.injected)


# ---------------------------------------------------------------------------
# Full positive round-trips (templates produced by builder)
# ---------------------------------------------------------------------------

class TestPositiveRoundTrips:
    def test_capec_lookup_template(self, validator, card, limits):
        query = (
            'g.V().hasLabel("AttackPattern").has("id", within(ids))'
            '.elementMap().limit(lim)'
        )
        # lim=1000 in params; validator works on literal query text so let's
        # substitute lim with an integer-like binding representation.
        # The validator checks the literal query; bindings are separate.
        # Replace binding placeholder with a value for the limit regex to match.
        q_concrete = query.replace("limit(lim)", "limit(100)")
        result = _validate(validator, card, limits, q_concrete)
        assert result.ok, result.reasons

    def test_capec_maps_to_template(self, validator, card, limits):
        query = (
            'g.V().hasLabel("AttackPattern").has("id", within(ids)).as("ap")'
            '.out("MAPS_TO").hasLabel("TaxonomyEntry").has("taxonomy_name","ATTACK").as("tax")'
            '.select("ap","tax").by(elementMap()).limit(100)'
        )
        result = _validate(validator, card, limits, query)
        assert result.ok, result.reasons

    def test_capec_neighbors_template(self, validator, card, limits):
        query = (
            'g.V().hasLabel("AttackPattern").has("id", within(ids)).as("ap")'
            '.out("EXPLOITS_WEAKNESS").hasLabel("Weakness").as("nbr")'
            '.select("ap","nbr").by(elementMap()).limit(100)'
        )
        result = _validate(validator, card, limits, query)
        assert result.ok, result.reasons


# ---------------------------------------------------------------------------
# Traversal-depth cap — over-deep traversals are REJECTED, not just noted
# ---------------------------------------------------------------------------

class TestDepthCap:
    def test_rejects_over_depth_traversal(self, validator, card, limits):
        # Four chained CHILD_OF hops (AttackPattern->AttackPattern is schema-valid)
        # exceed max_traversal_depth=3 and must be rejected before execution.
        # Queries speak the loaded graph's SCREAMING_SNAKE edge convention.
        query = (
            'g.V().hasLabel("AttackPattern")'
            '.out("CHILD_OF").out("CHILD_OF").out("CHILD_OF").out("CHILD_OF")'
            '.elementMap().limit(10)'
        )
        result = _validate(validator, card, limits, query)
        assert not result.ok
        assert any("max_traversal_depth" in r for r in result.reasons)

    def test_allows_depth_at_limit(self, validator, card, limits):
        # Exactly three hops is within the cap.
        query = (
            'g.V().hasLabel("AttackPattern")'
            '.out("CHILD_OF").out("CHILD_OF").out("CHILD_OF")'
            '.elementMap().limit(10)'
        )
        result = _validate(validator, card, limits, query)
        assert result.ok, result.reasons

    def test_rejects_card_vocabulary_edge_labels(self, validator, card, limits):
        # The loaded graph has no 'ChildOf' edges (they load as CHILD_OF), so a
        # query using the card's source vocabulary would run clean and return
        # zero rows — exactly the silent-wrong-answer class the gate must stop.
        query = (
            'g.V().hasLabel("AttackPattern")'
            '.out("ChildOf").elementMap().limit(10)'
        )
        result = _validate(validator, card, limits, query)
        assert not result.ok
        assert any("unknown relationship type" in r for r in result.reasons)
