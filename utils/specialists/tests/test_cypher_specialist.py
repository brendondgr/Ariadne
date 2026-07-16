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


# ===========================================================================
# Step-10 new template tests
# ===========================================================================

_LIMITS = {"max_traversal_depth": 3, "max_result_rows": 100, "query_timeout_ms": 5000}


def _resolve(task):
    from utils.specialists.resolve import resolve
    return resolve(task, fixture_card("attack"))


def _validate(draft):
    """Return the validated result; caller asserts result.ok."""
    validator = CypherValidator()
    card = fixture_card("attack")
    return validator.validate(draft, card, _LIMITS)


# ---------------------------------------------------------------------------
# 1. technique_detection
# ---------------------------------------------------------------------------


def test_routing_technique_detection(card):
    """Technique seeds + DetectionStrategy entity → technique_detection template."""
    task = SpecialistTask(
        sub_question_id="q-td-1",
        source="attack",
        text="How is T1059 detected?",
        entities=("Technique", "DetectionStrategy"),
        limits=_LIMITS,
        seed_ids=("T1059",),
    )
    resolved = _resolve(task)
    builder = CypherQueryBuilder()
    draft = builder.build(resolved)
    assert draft.template == "technique_detection"
    result = _validate(draft)
    assert result.ok, result.reasons


def test_normalizer_technique_detection(card):
    """Rows with technique_id+detection_id group by technique; related includes detection + analytic."""
    rows = [
        {
            "technique_id": "T1059",
            "technique_name": "Command and Scripting Interpreter",
            "detection_id": "DET0001",
            "detection_name": "Process Monitoring",
            "analytic_id": "AN0001",
            "analytic_name": "Powershell Analytic",
        },
        {
            "technique_id": "T1059",
            "technique_name": "Command and Scripting Interpreter",
            "detection_id": "DET0001",
            "detection_name": "Process Monitoring",
            "analytic_id": None,
            "analytic_name": None,
        },
    ]
    normalizer = CypherNormalizer()
    task = SpecialistTask(
        sub_question_id="q-td-n",
        source="attack",
        text="How is T1059 detected?",
        entities=("Technique", "DetectionStrategy"),
        limits=_LIMITS,
        seed_ids=("T1059",),
    )
    resolved = _resolve(task)
    records = normalizer.normalize(rows, resolved, "FAKE QUERY", card)
    assert len(records) == 1
    rec = records[0]
    assert rec.primary_id == "T1059"
    assert rec.label == "Technique"
    assert rec.join_values == ("T1059",)
    related_ids = {r["id"] for r in rec.related}
    assert "DET0001" in related_ids
    assert "AN0001" in related_ids


def test_routing_technique_detection_subtechnique(card):
    """Sub-technique seeds + DetectionStrategy → technique_detection (SubTechnique anchor)."""
    task = SpecialistTask(
        sub_question_id="q-td-sub",
        source="attack",
        text="Detection for T1059.001?",
        entities=("SubTechnique", "DetectionStrategy"),
        limits=_LIMITS,
        seed_ids=("T1059.001",),
    )
    resolved = _resolve(task)
    builder = CypherQueryBuilder()
    draft = builder.build(resolved)
    assert draft.template == "technique_detection"
    result = _validate(draft)
    assert result.ok, result.reasons


# ---------------------------------------------------------------------------
# 2. subtechnique_parent
# ---------------------------------------------------------------------------


def test_routing_subtechnique_parent(card):
    """HAS_SUBTECHNIQUE relationship + seeds → subtechnique_parent template."""
    task = SpecialistTask(
        sub_question_id="q-sp-1",
        source="attack",
        text="What is the parent of T1059.001?",
        entities=("HAS_SUBTECHNIQUE",),
        limits=_LIMITS,
        seed_ids=("T1059.001",),
    )
    resolved = _resolve(task)
    builder = CypherQueryBuilder()
    draft = builder.build(resolved)
    assert draft.template == "subtechnique_parent"
    result = _validate(draft)
    assert result.ok, result.reasons


def test_normalizer_subtechnique_parent(card):
    """Rows with parent_id+subtechnique_id group by parent; related = subtechnique dicts."""
    rows = [
        {
            "parent_id": "T1059",
            "parent_name": "Command and Scripting Interpreter",
            "subtechnique_id": "T1059.001",
            "subtechnique_name": "PowerShell",
        },
        {
            "parent_id": "T1059",
            "parent_name": "Command and Scripting Interpreter",
            "subtechnique_id": "T1059.003",
            "subtechnique_name": "Windows Command Shell",
        },
    ]
    normalizer = CypherNormalizer()
    task = SpecialistTask(
        sub_question_id="q-sp-n",
        source="attack",
        text="sub of T1059",
        entities=("HAS_SUBTECHNIQUE",),
        limits=_LIMITS,
        seed_ids=("T1059",),
    )
    resolved = _resolve(task)
    records = normalizer.normalize(rows, resolved, "FAKE QUERY", card)
    assert len(records) == 1
    rec = records[0]
    assert rec.primary_id == "T1059"
    assert rec.label == "Technique"
    assert rec.join_values == ("T1059",)
    related_ids = {r["id"] for r in rec.related}
    assert "T1059.001" in related_ids
    assert "T1059.003" in related_ids


# ---------------------------------------------------------------------------
# 3. software_techniques
# ---------------------------------------------------------------------------


def test_routing_software_techniques(card):
    """Software + Technique entities + S-seed → software_techniques template."""
    task = SpecialistTask(
        sub_question_id="q-st-1",
        source="attack",
        text="What techniques does S0002 use?",
        entities=("Software", "Technique"),
        limits=_LIMITS,
        seed_ids=("S0002",),
    )
    resolved = _resolve(task)
    builder = CypherQueryBuilder()
    draft = builder.build(resolved)
    assert draft.template == "software_techniques"
    result = _validate(draft)
    assert result.ok, result.reasons


def test_normalizer_software_techniques(card):
    """Rows with software_id+technique_id group by software; join_values = T-ids."""
    rows = [
        {
            "software_id": "S0002",
            "software_name": "Mimikatz",
            "technique_id": "T1003",
            "technique_name": "OS Credential Dumping",
        },
        {
            "software_id": "S0002",
            "software_name": "Mimikatz",
            "technique_id": "T1550",
            "technique_name": "Use Alternate Auth Material",
        },
    ]
    normalizer = CypherNormalizer()
    task = SpecialistTask(
        sub_question_id="q-st-n",
        source="attack",
        text="S0002 techniques",
        entities=("Software", "Technique"),
        limits=_LIMITS,
        seed_ids=("S0002",),
    )
    resolved = _resolve(task)
    records = normalizer.normalize(rows, resolved, "FAKE QUERY", card)
    assert len(records) == 1
    rec = records[0]
    assert rec.primary_id == "S0002"
    assert rec.label == "Software"
    related_ids = {r["id"] for r in rec.related}
    assert "T1003" in related_ids
    assert "T1550" in related_ids
    assert "T1003" in rec.join_values
    assert "T1550" in rec.join_values


# Non-regression: Software-only entity (describe)
def test_nonregression_software_only_describe(card):
    """entities=(Software,) with S0154 seed must still route describe, not software_techniques."""
    task = SpecialistTask(
        sub_question_id="q-nr-sw",
        source="attack",
        text="What is S0154?",
        entities=("Software",),
        limits=_LIMITS,
        seed_ids=("S0154",),
    )
    resolved = _resolve(task)
    builder = CypherQueryBuilder()
    draft = builder.build(resolved)
    assert draft.template == "describe"


# ---------------------------------------------------------------------------
# 4. tactic_technique_mitigations
# ---------------------------------------------------------------------------


def test_routing_tactic_technique_mitigations(card):
    """TA seed + M seed + Tactic + Mitigation entities → tactic_technique_mitigations."""
    task = SpecialistTask(
        sub_question_id="q-ttm-1",
        source="attack",
        text="Mitigations for techniques in TA0002 matching M1038?",
        entities=("Tactic", "Mitigation"),
        limits=_LIMITS,
        seed_ids=("TA0002", "M1038"),
    )
    resolved = _resolve(task)
    builder = CypherQueryBuilder()
    draft = builder.build(resolved)
    assert draft.template == "tactic_technique_mitigations"
    result = _validate(draft)
    assert result.ok, result.reasons
    assert "tactic_ids" in draft.params
    assert "mitigation_ids" in draft.params
    assert draft.params["tactic_ids"] == ["TA0002"]
    assert draft.params["mitigation_ids"] == ["M1038"]


def test_normalizer_tactic_technique_mitigations(card):
    """Rows with tactic_id+technique_id+mitigation_id group by technique; related = tactic + mitigation."""
    rows = [
        {
            "tactic_id": "TA0002",
            "tactic_name": "Execution",
            "technique_id": "T1059",
            "technique_name": "Command and Scripting Interpreter",
            "mitigation_id": "M1038",
            "mitigation_name": "Execution Prevention",
        },
    ]
    normalizer = CypherNormalizer()
    task = SpecialistTask(
        sub_question_id="q-ttm-n",
        source="attack",
        text="TA0002 M1038",
        entities=("Tactic", "Mitigation"),
        limits=_LIMITS,
        seed_ids=("TA0002", "M1038"),
    )
    resolved = _resolve(task)
    records = normalizer.normalize(rows, resolved, "FAKE QUERY", card)
    assert len(records) == 1
    rec = records[0]
    assert rec.primary_id == "T1059"
    assert rec.join_values == ("T1059",)
    related_ids = {r["id"] for r in rec.related}
    assert "TA0002" in related_ids
    assert "M1038" in related_ids


# Non-regression: Tactic + Technique seeds → tactic_techniques (not tactic_technique_mitigations)
def test_nonregression_tactic_techniques_still_routes(card):
    """entities=(Tactic, Technique) with TA seed → tactic_techniques (no M seed)."""
    task = SpecialistTask(
        sub_question_id="q-nr-tt",
        source="attack",
        text="Techniques in TA0002?",
        entities=("Tactic", "Technique"),
        limits=_LIMITS,
        seed_ids=("TA0002",),
    )
    resolved = _resolve(task)
    builder = CypherQueryBuilder()
    draft = builder.build(resolved)
    # No T-seeds present, so technique_tactics does not fire; no M seeds so
    # tactic_technique_mitigations does not fire → falls through to tactic_techniques
    assert draft.template == "tactic_techniques"


# ---------------------------------------------------------------------------
# 5. technique_tactics
# ---------------------------------------------------------------------------


def test_routing_technique_tactics(card):
    """Tactic entity + T-seeds → technique_tactics template."""
    task = SpecialistTask(
        sub_question_id="q-ttac-1",
        source="attack",
        text="Which tactics contain T1059?",
        entities=("Tactic", "Technique"),
        limits=_LIMITS,
        seed_ids=("T1059",),
    )
    resolved = _resolve(task)
    builder = CypherQueryBuilder()
    draft = builder.build(resolved)
    assert draft.template == "technique_tactics"
    result = _validate(draft)
    assert result.ok, result.reasons


def test_normalizer_technique_tactics(card):
    """Rows with technique_id+in_tactic_id group by technique; related = tactic dicts."""
    rows = [
        {
            "technique_id": "T1059",
            "technique_name": "Command and Scripting Interpreter",
            "in_tactic_id": "TA0002",
            "in_tactic_name": "Execution",
        },
        {
            "technique_id": "T1059",
            "technique_name": "Command and Scripting Interpreter",
            "in_tactic_id": "TA0011",
            "in_tactic_name": "Command and Control",
        },
    ]
    normalizer = CypherNormalizer()
    task = SpecialistTask(
        sub_question_id="q-ttac-n",
        source="attack",
        text="T1059 tactics",
        entities=("Tactic", "Technique"),
        limits=_LIMITS,
        seed_ids=("T1059",),
    )
    resolved = _resolve(task)
    records = normalizer.normalize(rows, resolved, "FAKE QUERY", card)
    assert len(records) == 1
    rec = records[0]
    assert rec.primary_id == "T1059"
    assert rec.label == "Technique"
    assert rec.join_values == ("T1059",)
    related_ids = {r["id"] for r in rec.related}
    assert "TA0002" in related_ids
    assert "TA0011" in related_ids


# ---------------------------------------------------------------------------
# 6. datacomponent_analytics
# ---------------------------------------------------------------------------


def test_routing_datacomponent_analytics(card):
    """DataComponent + Analytic entities + DC-seed → datacomponent_analytics template."""
    task = SpecialistTask(
        sub_question_id="q-dca-1",
        source="attack",
        text="Analytics monitoring DC0001?",
        entities=("DataComponent", "Analytic"),
        limits=_LIMITS,
        seed_ids=("DC0001",),
    )
    resolved = _resolve(task)
    builder = CypherQueryBuilder()
    draft = builder.build(resolved)
    assert draft.template == "datacomponent_analytics"
    result = _validate(draft)
    assert result.ok, result.reasons


def test_normalizer_datacomponent_analytics(card):
    """Rows with datacomponent_id+analytic_id group by DC; no join_values."""
    rows = [
        {
            "datacomponent_id": "DC0001",
            "datacomponent_name": "Network Connection Creation",
            "analytic_id": "AN0010",
            "analytic_name": "Suspicious Outbound Connection",
        },
        {
            "datacomponent_id": "DC0001",
            "datacomponent_name": "Network Connection Creation",
            "analytic_id": "AN0011",
            "analytic_name": "Beacon Detection",
        },
    ]
    normalizer = CypherNormalizer()
    task = SpecialistTask(
        sub_question_id="q-dca-n",
        source="attack",
        text="Analytics for DC0001",
        entities=("DataComponent", "Analytic"),
        limits=_LIMITS,
        seed_ids=("DC0001",),
    )
    resolved = _resolve(task)
    records = normalizer.normalize(rows, resolved, "FAKE QUERY", card)
    assert len(records) == 1
    rec = records[0]
    assert rec.primary_id == "DC0001"
    assert rec.label == "DataComponent"
    assert rec.join_values == ()
    related_ids = {r["id"] for r in rec.related}
    assert "AN0010" in related_ids
    assert "AN0011" in related_ids


# ---------------------------------------------------------------------------
# Non-regression: existing templates still route correctly
# ---------------------------------------------------------------------------


def test_nonregression_technique_mitigations_still_routes(card):
    """entities=(Technique, Mitigation) with T seed → technique_mitigations."""
    task = SpecialistTask(
        sub_question_id="q-nr-tm",
        source="attack",
        text="What mitigates T1047?",
        entities=("Technique", "Mitigation"),
        limits=_LIMITS,
        seed_ids=("T1047",),
    )
    resolved = _resolve(task)
    builder = CypherQueryBuilder()
    draft = builder.build(resolved)
    assert draft.template == "technique_mitigations"


# ---------------------------------------------------------------------------
# describe: single-entity "tell me about this" deep dive (subsumes the old
# node_lookup / node_dossier split — describe always returns the full record).
# ---------------------------------------------------------------------------


def test_routing_describe_on_describe_intent(card):
    """A single-seed 'details on M1049' task routes to the describe template."""
    task = SpecialistTask(
        sub_question_id="q-dossier-1",
        source="attack",
        text="Provide more details on M1049.",
        entities=("Mitigation",),
        limits=_LIMITS,
        seed_ids=("M1049",),
    )
    resolved = _resolve(task)
    draft = CypherQueryBuilder().build(resolved)
    assert draft.template == "describe"
    # It projects the full properties blob and the aggregated 1-hop facet block.
    assert "properties_json" in draft.query
    assert "OPTIONAL MATCH (n)-[r]-(m)" in draft.query
    assert "facets AS facets" in draft.query
    assert "(n:Mitigation)" in draft.query
    result = _validate(draft)
    assert result.ok, result.reasons


def test_describe_infers_label_from_seed_when_unnamed(card):
    """With no entity label named, describe anchors on the seed-id prefix."""
    task = SpecialistTask(
        sub_question_id="q-dossier-2",
        source="attack",
        text="Tell me more about M1049",
        entities=(),
        limits=_LIMITS,
        seed_ids=("M1049",),
    )
    resolved = _resolve(task)
    draft = CypherQueryBuilder().build(resolved)
    assert draft.template == "describe"
    assert "(n:Mitigation)" in draft.query
    assert _validate(draft).ok


def test_describe_seed_id_label_wins_over_wrong_attached_label(card):
    """A seed id's shape is authoritative: T1566 describes as Technique even when a
    wrong entity label (the planner's 'Analytic' probe fallback) was attached.

    Regression for the live bug where 'What is T1566?' compiled to
    ``MATCH (n:Analytic) WHERE n.attack_id IN ['T1566']`` and returned nothing.
    """
    task = SpecialistTask(
        sub_question_id="q-mislabel",
        source="attack",
        text="What is T1566?",
        entities=("Analytic",),  # wrong label the deterministic planner fell back to
        limits=_LIMITS,
        seed_ids=("T1566",),
    )
    resolved = _resolve(task)
    draft = CypherQueryBuilder().build(resolved)
    assert draft.template == "describe"
    assert "(n:Technique)" in draft.query and "(n:Analytic)" not in draft.query
    assert _validate(draft).ok


def test_bare_seed_id_also_routes_to_describe(card):
    """A bare id lookup with no 'details/about' verb still routes to describe.

    describe subsumes the old node_lookup/node_dossier split: there is no
    longer a "lean lookup vs rich dossier" distinction, so a bare id and a
    describe-verb id both take the same full-record path.
    """
    task = SpecialistTask(
        sub_question_id="q-dossier-3",
        source="attack",
        text="M1049",
        entities=("Mitigation",),
        limits=_LIMITS,
        seed_ids=("M1049",),
    )
    resolved = _resolve(task)
    draft = CypherQueryBuilder().build(resolved)
    assert draft.template == "describe"
    assert "properties_json" in draft.query


# ---------------------------------------------------------------------------
# describe_by_name: definitional "what is <name>?" with no id
# ---------------------------------------------------------------------------


def test_routing_describe_by_name_on_definitional_question(card):
    """A name-only definitional question routes to the describe_by_name template."""
    task = SpecialistTask(
        sub_question_id="q-name-1",
        source="attack",
        text="What exactly is User Training and Software Configuration respectively?",
        entities=(),
        limits=_LIMITS,
        seed_ids=(),
    )
    resolved = _resolve(task)
    draft = CypherQueryBuilder().build(resolved)
    assert draft.template == "describe_by_name"
    # Same full-record row shape as the by-id path, matched by name.
    assert "properties_json" in draft.query
    assert "OPTIONAL MATCH (n)-[r]-(m)" in draft.query
    assert "facets AS facets" in draft.query
    assert "toLower(n.name) CONTAINS term" in draft.query
    # The extracted names are the lower-cased query parameters (no ids).
    assert draft.params["names"] == ["user training", "software configuration"]
    result = _validate(draft)
    assert result.ok, result.reasons


def test_describe_by_name_validator_round_trip_is_label_scoped(card):
    """The name query scopes to real card labels and survives the validator."""
    task = SpecialistTask(
        sub_question_id="q-name-2",
        source="attack",
        text="What is Phishing?",
        entities=(),
        limits=_LIMITS,
        seed_ids=(),
    )
    draft = CypherQueryBuilder().build(_resolve(task))
    assert draft.template == "describe_by_name"
    # Multi-label OR guard uses only real ATT&CK labels.
    assert "n:Mitigation" in draft.query and "n:Technique" in draft.query
    assert _validate(draft).ok


def test_definitional_without_name_terms_falls_back_to_label_scan(card):
    """A definitional question that names no entity does not force a name dossier."""
    task = SpecialistTask(
        sub_question_id="q-name-3",
        source="attack",
        text="What is the mitigation?",  # only stopwords/schema words → no name terms
        entities=(),
        limits=_LIMITS,
        seed_ids=(),
    )
    resolved = _resolve(task)
    assert resolved.name_terms == ()
    draft = CypherQueryBuilder().build(resolved)
    assert draft.template == "label_scan"


def test_seeded_definitional_uses_id_path_not_name_path(card):
    """A definitional question that cites an id keeps the by-id path, never describe_by_name.

    "What exactly is M1049?" has a seed, so it takes the id branch (describe by
    id) — describe_by_name only rescues the *seedless* case.
    """
    task = SpecialistTask(
        sub_question_id="q-name-4",
        source="attack",
        text="What exactly is M1049?",
        entities=("Mitigation",),
        limits=_LIMITS,
        seed_ids=("M1049",),
    )
    draft = CypherQueryBuilder().build(_resolve(task))
    assert draft.template != "describe_by_name"
    assert draft.template == "describe"


def _describe_task():
    return SpecialistTask(
        sub_question_id="q-dossier-n",
        source="attack",
        text="Provide more details on M1049.",
        entities=("Mitigation",),
        limits=_LIMITS,
        seed_ids=("M1049",),
    )


def test_normalizer_describe_parses_full_properties_and_facets(card):
    """The describe row's properties_json yields the full record; edges fold into facet counts."""
    import json as _json

    rows = [
        {
            "id": "M1049",
            "name": "Antivirus/Antimalware",
            "properties_json": _json.dumps(
                {"attack_id": "M1049", "description": "Antivirus solutions use signatures and heuristics."}
            ),
            "facets": [
                {"rel": "MITIGATES", "outgoing": True, "label": "Technique", "count": 23},
            ],
        }
    ]
    resolved = _resolve(_describe_task())
    rec = CypherNormalizer().normalize(rows, resolved, "FAKE", card)[0]
    assert rec.primary_id == "M1049"
    assert rec.label == "Mitigation"
    # properties carries the full parsed blob — no allow-list.
    assert rec.properties["description"].startswith("Antivirus solutions")
    assert rec.properties["attack_id"] == "M1049"
    assert "neighbor_total" not in rec.properties
    # facets carries the folded {rel, direction, label, count} block. The
    # registry also folds in the plausible-but-unobserved MITIGATES->SubTechnique
    # facet as an honest zero, so match on (rel, label) to grab the observed one.
    facet = next(f for f in rec.facets if f["rel"] == "MITIGATES" and f["label"] == "Technique")
    assert facet["direction"] == "out"
    assert facet["count"] == 23
    # describe returns facet counts, not individual neighbours.
    assert rec.related == []


def test_normalizer_describe_description_only_node_has_empty_facets(card):
    """A node with no observed edges still yields a full record (not dropped)."""
    import json as _json

    rows = [
        {
            "id": "M1049",
            "name": "Antivirus/Antimalware",
            "properties_json": _json.dumps({"description": "Detects malware."}),
            "facets": [],
        }
    ]
    resolved = _resolve(_describe_task())
    records = CypherNormalizer().normalize(rows, resolved, "FAKE", card)
    assert len(records) == 1
    assert records[0].properties["description"] == "Detects malware."
    assert records[0].related == []
    # No observed edges still folds in the registry's plausible facets as
    # honest zeros rather than an empty block.
    assert all(f["count"] == 0 for f in records[0].facets)


def test_normalizer_dossier_tolerates_bad_properties_json(card):
    """A malformed properties_json degrades to no description, not an exception."""
    rows = [{"id": "M1049", "name": "Antivirus/Antimalware", "properties_json": "{not json", "facets": []}]
    resolved = _resolve(_describe_task())
    rec = CypherNormalizer().normalize(rows, resolved, "FAKE", card)[0]
    assert "description" not in rec.properties
    assert rec.name == "Antivirus/Antimalware"
