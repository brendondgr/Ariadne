#!/usr/bin/env python3
"""Tests for the evidence emitter and the deterministic contract check."""

from __future__ import annotations

import re

from utils.specialists.contracts import EvidenceRecord, Provenance
from utils.specialists.evidence import check_contract, emit_record, now_iso
from utils.specialists.tests._fixtures import fixture_card


def test_now_iso_is_iso8601_utc() -> None:
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", now_iso())


def test_emit_record_attaches_full_provenance() -> None:
    card = fixture_card("attack")
    rec = emit_record(
        card=card,
        query="MATCH (t:Technique {attack_id:$id}) RETURN t LIMIT 1",
        record_id="attack-pattern--01a5",
        primary_id="T1047",
        id_scheme="attack-id",
        label="Technique",
        name="Windows Management Instrumentation",
        join_values=("T1047",),
    )
    assert check_contract([rec]) == []
    assert rec.provenance is not None
    assert rec.provenance.backend == "neo4j"
    assert rec.provenance.source  # enriched source_name present
    assert rec.provenance.dataset == "attack"


def test_check_contract_flags_missing_provenance_and_scheme() -> None:
    broken = EvidenceRecord(primary_id="", id_scheme="", label="", name="", provenance=None)
    problems = check_contract([broken])
    assert any("provenance" in p for p in problems)
    assert any("id_scheme" in p for p in problems)


def test_check_contract_flags_blank_provenance_fields() -> None:
    prov = Provenance(source="", dataset="attack", backend="neo4j", query="", record_id="r1", timestamp="")
    rec = EvidenceRecord("T1", "attack-id", "Technique", "x", provenance=prov)
    problems = check_contract([rec])
    assert any("query" in p for p in problems)
    assert any("timestamp" in p for p in problems)
    assert any("source" in p for p in problems)
