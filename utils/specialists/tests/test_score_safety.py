"""Tests for the safety-constraint adherence scorer and adversarial probes.

Hermetic: the gate runs before any DB call. Needs the built source cards (skips
when absent). The probe-block assertions are hard security guarantees — a single
leak fails the suite.
"""

from __future__ import annotations

import os

import pytest

from utils.specialists.evalset.score_safety import audit_query, score_safety
from utils.specialists.evalset.score_validity import build_specialists
from utils.specialists.tests.fixtures.adversarial_probes import PROBES
from utils.specialists.validation import QueryDraft

_CARDS_READY = os.path.exists("data/source_cards/attack.json") and os.path.exists(
    "data/source_cards/capec.json"
)
requires_cards = pytest.mark.skipif(_CARDS_READY is False, reason="source cards not built")


# --- hermetic: the audit logic ---------------------------------------------

def test_audit_query_accepts_bounded_readonly_cypher() -> None:
    q = "MATCH (t:Technique) WHERE t.attack_id IN $ids RETURN t LIMIT 300"
    assert audit_query(q, "attack", 300) == []


def test_audit_query_flags_write_missing_limit_and_unbounded() -> None:
    assert audit_query("MATCH (t) SET t.x=1 RETURN t LIMIT 10", "attack", 300)
    assert "no LIMIT on the accepted query" in audit_query("MATCH (t:Technique) RETURN t", "attack", 300)
    assert any("exceeds cap" in p for p in audit_query("MATCH (t:Technique) RETURN t LIMIT 5000", "attack", 300))
    assert any("unbounded" in p for p in audit_query("MATCH (t:Technique)-[:R*]-(x) RETURN x LIMIT 10", "attack", 300))


def test_audit_query_flags_gremlin_writes_and_caps() -> None:
    assert audit_query("g.V().drop()", "capec", 300)
    assert "no .limit() on the accepted query" in audit_query("g.V().hasLabel('AttackPattern')", "capec", 300)
    assert any("exceeds cap" in p for p in audit_query("g.V().limit(9999)", "capec", 300))


# --- live-card (hermetic w.r.t. DB): full audit + probes --------------------

@requires_cards
def test_every_accepted_query_is_bounded() -> None:
    report = score_safety()
    for source in ("attack", "capec"):
        assert report[source]["adherence_rate"] == 1.0
        assert report[source]["breaches"] == [], report[source]["breaches"]


@requires_cards
def test_gate_blocks_every_adversarial_probe() -> None:
    report = score_safety()
    for source in ("attack", "capec"):
        # A leak here is a hard security failure, not a rate to average away.
        assert report[source]["leaks"] == [], report[source]["leaks"]
        assert report[source]["probe_block_rate"] == 1.0
        assert report[source]["probes"] == len(PROBES[source])


@requires_cards
def test_single_quoted_unknown_label_is_blocked() -> None:
    # Regression for the gap an adversarial probe surfaced: single-quoted labels
    # must be schema-validated exactly like double-quoted ones.
    capec = build_specialists()["capec"]
    limits = {"max_traversal_depth": 3, "max_result_rows": 1000, "query_timeout_ms": 5000}
    draft = QueryDraft(query="g.V().hasLabel('Secret')", template="probe")
    result = capec.validator.validate(draft, capec.card, limits)
    assert not result.ok
