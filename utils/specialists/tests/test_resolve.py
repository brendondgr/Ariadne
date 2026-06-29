#!/usr/bin/env python3
"""Tests for the shared resolve-to-schema step."""

from __future__ import annotations

from utils.specialists.contracts import SpecialistTask
from utils.specialists.resolve import (
    extract_attack_ids,
    extract_capec_ids,
    resolve,
)
from utils.specialists.tests._fixtures import fixture_card


def test_extract_attack_ids_handles_sub_techniques_and_dedupes() -> None:
    ids = extract_attack_ids("T1047 and T1574.010, plus T1047 again")
    assert ids == ("T1047", "T1574.010")


def test_extract_capec_ids_normalises_to_dash_form() -> None:
    assert extract_capec_ids("CAPEC-66 and capec 70") == ("CAPEC-66", "CAPEC-70")


def test_resolve_partitions_entities_against_card() -> None:
    card = fixture_card("attack")
    task = SpecialistTask(
        sub_question_id="q1",
        source="attack",
        text="Which mitigations apply to T1047?",
        entities=("Technique", "Mitigation", "NotARealLabel", "USES"),
    )
    resolved = resolve(task, card)
    assert "Technique" in resolved.labels
    assert "Mitigation" in resolved.labels
    assert "USES" in resolved.relationships
    assert "NotARealLabel" in resolved.unknown_entities
    assert "T1047" in resolved.seed_ids
    assert "T1047" in resolved.attack_ids


def test_resolve_capec_seed_ids_and_join_endpoint() -> None:
    card = fixture_card("capec")
    task = SpecialistTask(
        sub_question_id="q2",
        source="capec",
        text="Which CAPEC-66 patterns map to ATT&CK techniques?",
        entities=("AttackPattern", "MAPS_TO", "TaxonomyEntry"),
        join_key="attack-technique-id",
    )
    resolved = resolve(task, card)
    assert "CAPEC-66" in resolved.seed_ids
    assert resolved.has_join
    assert resolved.join_endpoint is not None
    # The CAPEC endpoint bridges via MAPS_TO -> TaxonomyEntry.entry_id.
    assert resolved.join_endpoint.property == "entry_id"


def test_resolve_attack_does_not_confuse_tactic_with_technique() -> None:
    card = fixture_card("attack")
    task = SpecialistTask("q3", "attack", "Tactic TA0006 and technique T1003", entities=())
    resolved = resolve(task, card)
    assert "TA0006" in resolved.seed_ids
    assert "T1003" in resolved.seed_ids
    # TA0006 must not also appear as a bare technique id.
    assert "T0006" not in resolved.seed_ids
