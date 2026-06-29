#!/usr/bin/env python3
"""Tests for the input/output contracts (pure data, JSON round-trips)."""

from __future__ import annotations

from utils.specialists.contracts import (
    EvidenceRecord,
    Provenance,
    SpecialistResult,
    SpecialistTask,
)


def test_specialist_task_round_trip() -> None:
    task = SpecialistTask(
        sub_question_id="q1",
        source="attack",
        text="mitigations for T1047",
        entities=("Technique", "Mitigation"),
        limits={"max_traversal_depth": 3, "max_result_rows": 1000, "query_timeout_ms": 5000},
        join_key="attack-technique-id",
        seed_ids=("T1047",),
        rationale="why",
    )
    again = SpecialistTask.from_dict(task.to_dict())
    assert again == task
    assert again.max_rows() == 1000
    assert again.max_depth() == 3
    assert again.timeout_ms() == 5000


def test_task_limit_accessors_default_when_missing() -> None:
    task = SpecialistTask(sub_question_id="q1", source="capec", text="x", limits={})
    assert task.max_rows() == 1000
    assert task.max_depth() == 3
    assert task.timeout_ms() == 5000


def test_from_sub_question_duck_types_planner_subquestion() -> None:
    from utils.planner.schema import Limits, SubQuestion

    sq = SubQuestion(
        id="q2",
        source="capec",
        text="CAPEC patterns mapping to ATT&CK",
        entities=["AttackPattern", "MAPS_TO"],
        limits=Limits(max_traversal_depth=2, max_result_rows=500, query_timeout_ms=4000),
        join_key="attack-technique-id",
    )
    task = SpecialistTask.from_sub_question(sq, seed_ids=("CAPEC-66",))
    assert task.sub_question_id == "q2"
    assert task.source == "capec"
    assert task.entities == ("AttackPattern", "MAPS_TO")
    assert task.limits["max_result_rows"] == 500
    assert task.join_key == "attack-technique-id"
    assert task.seed_ids == ("CAPEC-66",)


def test_result_join_values_dedupe_and_to_dict() -> None:
    prov = Provenance(
        source="MITRE ATT&CK Enterprise",
        dataset="attack",
        backend="neo4j",
        query="MATCH (n) RETURN n LIMIT 1",
        record_id="attack-pattern--x",
        timestamp="2026-06-29T00:00:00+00:00",
    )
    rec_a = EvidenceRecord("T1047", "attack-id", "Technique", "WMI", join_values=("T1047",), provenance=prov)
    rec_b = EvidenceRecord("T1059", "attack-id", "Technique", "Cmd", join_values=("T1059", "T1047"), provenance=prov)
    result = SpecialistResult(task=SpecialistTask("q1", "attack", "x"), records=[rec_a, rec_b], ok=True)
    assert result.join_values() == ["T1047", "T1059"]
    data = result.to_dict()
    assert data["record_count"] == 2
    assert data["join_values"] == ["T1047", "T1059"]
    assert data["records"][0]["provenance"]["backend"] == "neo4j"
