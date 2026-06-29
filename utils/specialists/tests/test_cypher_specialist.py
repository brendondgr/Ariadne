#!/usr/bin/env python3
"""Tests for the assembled Cypher specialist.

Unit tests use a fake connector with canned rows (no database).
The live test builds the real specialist against the Docker Neo4j stack and is
guarded by a pytest.skip if the server is unreachable.
"""

from __future__ import annotations

from typing import Any

import pytest

from utils.specialists.contracts import EvidenceRecord, SpecialistTask
from utils.specialists.cypher.builder import CypherQueryBuilder
from utils.specialists.cypher.normalizer import CypherNormalizer
from utils.specialists.cypher.specialist import build_cypher_specialist
from utils.specialists.cypher.validator import CypherValidator
from utils.specialists.evidence import check_contract
from utils.specialists.tests._fixtures import fixture_card


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def card():
    return fixture_card("attack")


@pytest.fixture
def mitigation_rows() -> list[dict[str, Any]]:
    """Canned rows simulating a technique_mitigations query result."""
    return [
        {
            "technique_id": "T1047",
            "technique_name": "Windows Management Instrumentation",
            "mitigation_id": "M1038",
            "mitigation_name": "Execution Prevention",
        },
        {
            "technique_id": "T1047",
            "technique_name": "Windows Management Instrumentation",
            "mitigation_id": "M1040",
            "mitigation_name": "Behavior Prevention on Endpoint",
        },
        {
            "technique_id": "T1047",
            "technique_name": "Windows Management Instrumentation",
            "mitigation_id": "M1018",
            "mitigation_name": "User Account Management",
        },
        {
            "technique_id": "T1047",
            "technique_name": "Windows Management Instrumentation",
            "mitigation_id": "M1026",
            "mitigation_name": "Privileged Account Management",
        },
    ]


# ---------------------------------------------------------------------------
# Fake connector for unit tests
# ---------------------------------------------------------------------------


class FakeConnector:
    """Returns canned rows without touching a database."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self.connected = False
        self.closed = False
        self.run_calls: list[tuple[str, dict, dict]] = []

    def connect(self) -> None:
        self.connected = True

    def close(self) -> None:
        self.closed = True

    def run(
        self, query: str, params: dict[str, Any], limits: dict[str, int]
    ) -> list[dict[str, Any]]:
        self.run_calls.append((query, params, limits))
        return list(self._rows)


# ---------------------------------------------------------------------------
# Unit test: normalizer groups rows by technique
# ---------------------------------------------------------------------------


def test_normalizer_groups_mitigations(card, mitigation_rows):
    """technique_mitigations rows are collapsed into one record per technique."""
    from utils.specialists.base import QuerySpecialist
    from utils.specialists.resolve import resolve
    from utils.specialists.validation import QueryDraft

    normalizer = CypherNormalizer()
    task = SpecialistTask(
        sub_question_id="q1",
        source="attack",
        text="What mitigates T1047?",
        entities=("Technique", "Mitigation"),
        limits={"max_traversal_depth": 3, "max_result_rows": 100, "query_timeout_ms": 5000},
        seed_ids=("T1047",),
    )
    resolved = resolve(task, card)
    query = (
        "MATCH (t:Technique)<-[:MITIGATES]-(m:Mitigation) "
        "WHERE t.attack_id IN $ids "
        "RETURN t.attack_id AS technique_id, t.name AS technique_name, "
        "m.attack_id AS mitigation_id, m.name AS mitigation_name LIMIT 100"
    )
    records = normalizer.normalize(mitigation_rows, resolved, query, card)

    # Should be one record per technique_id
    assert len(records) == 1
    rec = records[0]
    assert rec.primary_id == "T1047"
    assert rec.label == "Technique"
    assert rec.join_values == ("T1047",)  # T-number passes join check

    # All four mitigations are in related
    related_ids = {r["id"] for r in rec.related}
    assert "M1038" in related_ids
    assert "M1040" in related_ids
    assert "M1018" in related_ids
    assert "M1026" in related_ids


# ---------------------------------------------------------------------------
# Unit test: contract passes for grouped records
# ---------------------------------------------------------------------------


def test_normalizer_records_pass_contract(card, mitigation_rows):
    """Every emitted record satisfies the evidence contract."""
    from utils.specialists.resolve import resolve

    normalizer = CypherNormalizer()
    task = SpecialistTask(
        sub_question_id="q1",
        source="attack",
        text="Mitigations for T1047",
        entities=("Technique", "Mitigation"),
        limits={"max_traversal_depth": 3, "max_result_rows": 100, "query_timeout_ms": 5000},
        seed_ids=("T1047",),
    )
    resolved = resolve(task, card)
    query = "MATCH (t:Technique)<-[:MITIGATES]-(m:Mitigation) RETURN t, m LIMIT 100"
    records = normalizer.normalize(mitigation_rows, resolved, query, card)

    violations = check_contract(records)
    assert not violations, violations


# ---------------------------------------------------------------------------
# Unit test: full specialist loop with fake connector
# ---------------------------------------------------------------------------


def test_specialist_full_loop_with_fake_connector(card, mitigation_rows):
    """Build a specialist with a fake connector and run a task end-to-end."""
    from utils.specialists.base import QuerySpecialist
    from utils.specialists.config import SpecialistConfig
    from pathlib import Path

    fake_connector = FakeConnector(mitigation_rows)
    config = SpecialistConfig(data_dir=Path("data"), max_retries=1)
    specialist = QuerySpecialist(
        card=card,
        builder=CypherQueryBuilder(),
        validator=CypherValidator(),
        connector=fake_connector,
        normalizer=CypherNormalizer(),
        max_retries=1,
    )
    task = SpecialistTask(
        sub_question_id="q-unit-1",
        source="attack",
        text="What are the mitigations for T1047?",
        entities=("Technique", "Mitigation"),
        limits={"max_traversal_depth": 3, "max_result_rows": 100, "query_timeout_ms": 5000},
        seed_ids=("T1047",),
    )
    result = specialist.run(task)

    assert result.ok, result.error
    assert len(result.records) == 1
    rec = result.records[0]
    assert rec.primary_id == "T1047"
    assert rec.join_values == ("T1047",)
    related_ids = {r["id"] for r in rec.related}
    assert "M1038" in related_ids
    # Connector was opened and closed
    assert fake_connector.connected
    assert fake_connector.closed


# ---------------------------------------------------------------------------
# Unit test: join_values is a T-number (join integrity would pass)
# ---------------------------------------------------------------------------


def test_join_values_are_technique_ids(card, mitigation_rows):
    """join_values must contain only well-formed T-numbers to pass join_integrity_problems."""
    from utils.specialists.resolve import resolve
    import re

    normalizer = CypherNormalizer()
    task = SpecialistTask(
        sub_question_id="q1",
        source="attack",
        text="T1047",
        entities=("Technique", "Mitigation"),
        limits={"max_traversal_depth": 3, "max_result_rows": 100, "query_timeout_ms": 5000},
        seed_ids=("T1047",),
    )
    resolved = resolve(task, card)
    query = "MATCH (t:Technique)<-[:MITIGATES]-(m:Mitigation) RETURN t, m LIMIT 100"
    records = normalizer.normalize(mitigation_rows, resolved, query, card)

    t_re = re.compile(r"^T\d{4}(?:\.\d{3})?$")
    for rec in records:
        for val in rec.join_values:
            assert t_re.match(val), f"Non-T-number in join_values: {val!r}"


# ---------------------------------------------------------------------------
# Live integration test (skipped if Neo4j is unreachable)
# ---------------------------------------------------------------------------


def _neo4j_reachable() -> bool:
    """Quick check that Neo4j is up and authenticated."""
    try:
        from utils.config import load_env
        load_env()
        import os
        import neo4j
        from neo4j import GraphDatabase, Query

        driver = GraphDatabase.driver(
            os.environ.get("NEO4J_URI", "bolt://localhost:5456"),
            auth=(
                os.environ.get("NEO4J_USER", "neo4j"),
                os.environ.get("NEO4J_PASSWORD", "password"),
            ),
        )
        with driver.session(default_access_mode=neo4j.READ_ACCESS) as s:
            s.run(Query("RETURN 1", timeout=3.0))
        driver.close()
        return True
    except Exception:
        return False


@pytest.mark.integration
def test_live_t1047_mitigations():
    """Run the real specialist against Neo4j and assert M1038 is found."""
    if not _neo4j_reachable():
        pytest.skip("Neo4j is not reachable — skipping live test")

    from utils.config import load_env
    load_env()

    from utils.planner.cards import SourceCardView
    from utils.specialists.config import SpecialistConfig
    import json

    with open("data/source_cards/attack.json") as f:
        raw = json.load(f)
    real_card = SourceCardView.from_card_dict(raw)
    config = SpecialistConfig.from_env()

    specialist = build_cypher_specialist(real_card, config)
    task = SpecialistTask(
        sub_question_id="live-q1",
        source="attack",
        text="What are the mitigations for T1047?",
        entities=("Technique", "Mitigation"),
        limits={"max_traversal_depth": 3, "max_result_rows": 50, "query_timeout_ms": 5000},
        seed_ids=("T1047",),
    )
    result = specialist.run(task)

    assert result.ok, f"Specialist failed: {result.error}\n{result.traces}"
    assert result.records, "Expected at least one record for T1047"

    # T1047 record should exist
    t1047_records = [r for r in result.records if r.primary_id == "T1047"]
    assert t1047_records, "No record found with primary_id='T1047'"

    # M1038 must be in the related mitigations
    t1047 = t1047_records[0]
    related_ids = {r.get("id") for r in t1047.related}
    assert "M1038" in related_ids, (
        f"Expected M1038 (Execution Prevention) in related mitigations, got: {related_ids}"
    )

    # All records must pass the evidence contract
    violations = check_contract(result.records)
    assert not violations, f"Contract violations: {violations}"

    # join_values must be valid T-numbers
    import re
    t_re = re.compile(r"^T\d{4}(?:\.\d{3})?$")
    for rec in result.records:
        for val in rec.join_values:
            assert t_re.match(val), f"Malformed join value: {val!r}"
