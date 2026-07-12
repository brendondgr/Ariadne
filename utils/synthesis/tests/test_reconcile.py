#!/usr/bin/env python3
"""Unit tests for the deterministic cross-source contradiction reconciler.

Each case builds real ``FederatedEvidence`` from the shared fixtures so the
reconciler is exercised against the exact contracts the live pipeline produces.
The critical case is the last one: corroborating-but-consistent evidence must
produce **zero** conflicts (no false positives).
"""

from __future__ import annotations

from utils.synthesis.reconcile import conflicted_values, detect_conflicts

from ._fixtures import make_evidence, make_record, make_result


def test_name_disagreement_across_sources():
    """Two sources name the same technique id differently → one name conflict."""
    attack = make_result(
        source="attack",
        sub_question_id="q1",
        records=[make_record("T1055", name="Process Injection", source="attack")],
    )
    # CAPEC embeds its own (wrong) label for the same technique via a related entry.
    capec = make_result(
        source="capec",
        sub_question_id="q2",
        records=[
            make_record(
                "CAPEC-242",
                name="Code Injection",
                source="capec",
                label="AttackPattern",
                join_values=("T1055",),
                related=[{"id": "T1055", "name": "Thread Hijacking"}],
            )
        ],
    )
    conflicts = detect_conflicts(make_evidence([attack, capec]))

    assert len(conflicts) == 1
    c = conflicts[0]
    assert c.kind == "name"
    assert c.join_value == "T1055"
    assert set(c.sources) == {"attack", "capec"}
    assert c.values["attack"] == "Process Injection"
    assert c.values["capec"] == "Thread Hijacking"
    assert c.authoritative_source == "attack"
    assert conflicted_values(conflicts) == {"T1055"}


def test_cosmetic_name_difference_is_not_a_conflict():
    """Case/whitespace/punctuation-only differences must not fire."""
    attack = make_result(
        source="attack",
        records=[make_record("T1055", name="Process Injection", source="attack")],
    )
    capec = make_result(
        source="capec",
        sub_question_id="q2",
        records=[
            make_record(
                "CAPEC-242",
                name="Code Injection",
                source="capec",
                label="AttackPattern",
                join_values=("T1055",),
                related=[{"id": "T1055", "name": "  process injection! "}],
            )
        ],
    )
    assert detect_conflicts(make_evidence([attack, capec])) == []


def test_deprecated_technique_still_referenced():
    """ATT&CK retires a technique CAPEC still maps to → one status conflict."""
    attack = make_result(
        source="attack",
        sub_question_id="q1",
        records=[
            make_record(
                "T1156",
                name="Bash History",
                source="attack",
                properties={"x_mitre_deprecated": True},
            )
        ],
    )
    capec = make_result(
        source="capec",
        sub_question_id="q2",
        records=[
            make_record(
                "CAPEC-13",
                name="Subverting Environment Variable Values",
                source="capec",
                label="AttackPattern",
                join_values=("T1156",),
            )
        ],
    )
    conflicts = detect_conflicts(make_evidence([attack, capec]))

    assert len(conflicts) == 1
    c = conflicts[0]
    assert c.kind == "status"
    assert c.join_value == "T1156"
    assert c.authoritative_source == "attack"
    assert c.values["attack"] == "deprecated/revoked"
    assert c.values["capec"] == "referenced as current"


def test_status_string_form_is_detected():
    """A `status: revoked` property (not just a boolean flag) counts as retired."""
    attack = make_result(
        source="attack",
        records=[
            make_record("T1099", name="Timestomp", source="attack", properties={"status": "revoked"})
        ],
    )
    capec = make_result(
        source="capec",
        sub_question_id="q2",
        records=[
            make_record(
                "CAPEC-1",
                name="Accessing Functionality",
                source="capec",
                label="AttackPattern",
                join_values=("T1099",),
            )
        ],
    )
    conflicts = detect_conflicts(make_evidence([attack, capec]))
    assert [c.kind for c in conflicts] == ["status"]


def test_deprecated_but_unreferenced_is_not_a_conflict():
    """A retired technique nobody else maps to is not a contradiction."""
    attack = make_result(
        source="attack",
        records=[
            make_record("T1156", name="Bash History", source="attack", properties={"deprecated": True})
        ],
    )
    assert detect_conflicts(make_evidence([attack])) == []


def test_consistent_corroboration_yields_no_conflicts():
    """The no-false-positive guard: agreeing sources over a shared join produce
    zero conflicts even though the technique id is corroborated cross-source."""
    attack = make_result(
        source="attack",
        sub_question_id="q1",
        records=[make_record("T1055", name="Process Injection", source="attack")],
    )
    capec = make_result(
        source="capec",
        sub_question_id="q2",
        records=[
            make_record(
                "CAPEC-242",
                name="Code Injection",
                source="capec",
                label="AttackPattern",
                join_values=("T1055",),
                related=[{"id": "T1055", "name": "Process Injection"}],
            )
        ],
    )
    assert detect_conflicts(make_evidence([attack, capec])) == []
