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


def test_extract_cwe_ids_normalises_to_dash_form() -> None:
    from utils.specialists.resolve import extract_cwe_ids

    assert extract_cwe_ids("CWE-89 and cwe 522, CWE-89 again") == ("CWE-89", "CWE-522")


def test_resolve_capec_extracts_cwe_seeds_from_text() -> None:
    # CWE ids are CAPEC-native seeds (the Weakness vertices anchoring the
    # CWE -> CAPEC -> ATT&CK chain); CAPEC ids still come first when both appear.
    card = fixture_card("capec")
    task = SpecialistTask(
        sub_question_id="q-cwe",
        source="capec",
        text="Which attack patterns exploit CWE-522 and map to ATT&CK techniques?",
        entities=("Weakness", "AttackPattern", "TaxonomyEntry"),
        join_key="attack-technique-id",
    )
    resolved = resolve(task, card)
    assert resolved.seed_ids == ("CWE-522",)


def test_resolve_attack_text_does_not_gain_cwe_seeds() -> None:
    card = fixture_card("attack")
    task = SpecialistTask(
        sub_question_id="q-cwe-a",
        source="attack",
        text="Does CWE-522 relate to T1110?",
        entities=("Technique",),
    )
    resolved = resolve(task, card)
    assert "CWE-522" not in resolved.seed_ids
    assert "T1110" in resolved.seed_ids


def test_resolve_capec_falls_back_to_technique_seeds() -> None:
    # A capec task naming only a T-id anchors the reverse MAPS_TO join.
    card = fixture_card("capec")
    task = SpecialistTask(
        sub_question_id="q-rev",
        source="capec",
        text="Which CAPEC patterns map to ATT&CK technique T1040?",
        entities=("AttackPattern", "TaxonomyEntry"),
        join_key="attack-technique-id",
    )
    resolved = resolve(task, card)
    assert resolved.seed_ids == ("T1040",)


def test_resolve_capec_prefers_capec_ids_over_other_shapes() -> None:
    card = fixture_card("capec")
    task = SpecialistTask(
        sub_question_id="q-mixed",
        source="capec",
        text="Does CAPEC-555 map to T1021 (see CWE-522)?",
        entities=("AttackPattern", "TaxonomyEntry"),
        join_key="attack-technique-id",
    )
    resolved = resolve(task, card)
    assert resolved.seed_ids == ("CAPEC-555",)


# -- name-term extraction + definitional intent -----------------------------


def test_resolve_extracts_titlecase_name_terms_from_definitional_question() -> None:
    # The reported failing question: two multi-word mitigation names, no ids.
    card = fixture_card("attack")
    task = SpecialistTask(
        "q-name",
        "attack",
        "What exactly is User Training and Software Configuration respectively?",
        entities=(),
    )
    resolved = resolve(task, card)
    assert resolved.name_terms == ("User Training", "Software Configuration")
    assert resolved.seed_ids == ()  # a name-only question carries no id anchors


def test_resolve_extracts_quoted_name_term() -> None:
    card = fixture_card("attack")
    task = SpecialistTask("q-q", "attack", "Describe 'Credential Access' please", entities=())
    resolved = resolve(task, card)
    assert resolved.name_terms == ("Credential Access",)


def test_resolve_name_terms_single_titlecase_word() -> None:
    card = fixture_card("capec")
    task = SpecialistTask("q-p", "capec", "What is Phishing?", entities=())
    resolved = resolve(task, card)
    assert resolved.name_terms == ("Phishing",)


def test_resolve_name_terms_drop_schema_words_and_ids() -> None:
    # A lone schema label word ("Mitigation") and an id are never name anchors.
    card = fixture_card("attack")
    task = SpecialistTask(
        "q-s", "attack", "Which Mitigation covers M1017?", entities=("Mitigation",)
    )
    resolved = resolve(task, card)
    assert "Mitigation" not in resolved.name_terms
    assert all("M1017" not in term for term in resolved.name_terms)


def test_resolve_name_terms_keep_connectors_but_split_on_and() -> None:
    # A within-name connector ("for"/"of") keeps a single name whole; "and"
    # separates two names (so a CONTAINS match stays precise, not spuriously
    # matching a common word like "Third" left standing alone).
    card = fixture_card("attack")
    t1 = SpecialistTask("q-c1", "attack", "What is Phishing for Information?", entities=())
    assert resolve(t1, card).name_terms == ("Phishing for Information",)
    t2 = SpecialistTask(
        "q-c2", "attack", "What is User Training and Software Configuration?", entities=()
    )
    assert resolve(t2, card).name_terms == ("User Training", "Software Configuration")


# Definitional intent detection moved to the planner (utils.planner.intent.
# is_definitional_request) once describe made the specialist-side intent gating
# obsolete; it is covered by utils/planner/tests/test_intent.py.
