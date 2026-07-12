#!/usr/bin/env python3
"""Tests for provenance-exact synthesis edges (the network plot's Option-B spine).

Edges are derived from the cross-source join index during verification and
pruned to endpoints that survive in supported claims — so the plot draws only
topology the verifier stands behind.
"""

from __future__ import annotations

from utils.synthesis.composer import DeterministicComposer
from utils.synthesis.contracts import Citation, Claim, SynthesisEdge, SynthesizedAnswer
from utils.synthesis.verifier import verify_answer

from ._fixtures import make_evidence, make_record, make_result


def _cross_evidence():
    """CAPEC-555 and T1021 both carry the join value T1021 → a real correlation."""
    capec = make_record(
        "CAPEC-555",
        name="Remote Services Exploitation",
        source="capec",
        backend="gremlin",
        label="AttackPattern",
        join_values=("T1021",),
    )
    attack = make_record("T1021", name="Remote Services", join_values=("T1021",))
    return make_evidence(
        [
            make_result(source="capec", sub_question_id="c1", records=[capec], summary="CAPEC-555 maps to T1021."),
            make_result(source="attack", sub_question_id="a1", records=[attack], summary="T1021 found."),
        ]
    )


# --------------------------------------------------------------------------- #
# Contract round-trip                                                          #
# --------------------------------------------------------------------------- #


def test_edge_round_trips_through_dict():
    edge = SynthesisEdge(source_id="CAPEC-555", target_id="T1021", rel="mapsTo")
    assert SynthesisEdge.from_dict(edge.to_dict()) == edge


def test_answer_to_dict_carries_edges():
    answer = SynthesizedAnswer(
        request="q", edges=[SynthesisEdge("CAPEC-555", "T1021")]
    )
    payload = answer.to_dict()
    assert payload["edges"] == [
        {"source_id": "CAPEC-555", "target_id": "T1021", "rel": "mapsTo"}
    ]


# --------------------------------------------------------------------------- #
# Derivation                                                                   #
# --------------------------------------------------------------------------- #


def test_verified_answer_has_exact_mapsto_edge():
    evidence = _cross_evidence()
    answer = DeterministicComposer().compose(evidence)
    verify_answer(answer, evidence)

    assert answer.edges == [
        SynthesisEdge(source_id="CAPEC-555", target_id="T1021", rel="mapsTo")
    ]


def test_no_edge_without_a_cross_source_join():
    # Single-source evidence: no value is shared across sources → no edges.
    attack = make_record("T1021", name="Remote Services")
    evidence = make_evidence([make_result(records=[attack], summary="T1021 found.")])
    answer = DeterministicComposer().compose(evidence)
    verify_answer(answer, evidence)
    assert answer.edges == []


# --------------------------------------------------------------------------- #
# Pruning                                                                      #
# --------------------------------------------------------------------------- #


def test_edge_pruned_when_no_supported_claim_grounds_its_endpoints():
    # The cross-source join exists in the evidence, but the only claim is
    # fabricated (cites a record that was never retrieved) and gets cut — so
    # neither endpoint is in the supported pool and the edge must not appear.
    evidence = _cross_evidence()
    fabricated = Claim(
        text="CAPEC-999 maps to T1021.",
        citations=(Citation(source="capec", primary_id="CAPEC-999"),),
        entity_ids=("CAPEC-999",),
        kind="fact",
    )
    answer = SynthesizedAnswer(request="q", claims=[fabricated])
    verify_answer(answer, evidence)

    assert answer.verification is not None
    assert answer.verification.unsupported_count == 1
    assert answer.edges == []


# --------------------------------------------------------------------------- #
# mitigatedBy derivation                                                       #
# --------------------------------------------------------------------------- #


def _mitigation_evidence(related=None):
    """A technique record carrying its MITIGATES relationships in ``related``."""
    attack = make_record(
        "T1021",
        name="Remote Services",
        related=related
        if related is not None
        else [{"id": "M1032", "name": "Multi-factor Authentication"}],
    )
    return make_evidence(
        [make_result(records=[attack], summary="T1021 found.")]
    )


def test_verified_answer_has_exact_mitigatedby_edge():
    evidence = _mitigation_evidence()
    answer = DeterministicComposer().compose(evidence)
    verify_answer(answer, evidence)

    assert answer.edges == [
        SynthesisEdge(source_id="T1021", target_id="M1032", rel="mitigatedBy")
    ]


def test_non_mitigation_related_entries_emit_nothing():
    # Tactic membership, detections, and id-less entries live in ``related``
    # too — none of them are MITIGATES relationships.
    evidence = _mitigation_evidence(
        related=[
            {"id": "TA0008", "name": "Lateral Movement"},
            {"id": "DET-1", "name": "Some detection"},
            {"name": "no id at all"},
        ]
    )
    answer = DeterministicComposer().compose(evidence)
    verify_answer(answer, evidence)
    assert answer.edges == []


def test_mitigatedby_pruned_when_technique_unsupported():
    # The technique record exists, but the only claim is fabricated and cut —
    # the technique endpoint is not in the supported pool, so its mitigation
    # edge must not appear either.
    evidence = _mitigation_evidence()
    fabricated = Claim(
        text="T9999 is mitigated.",
        citations=(Citation(source="attack", primary_id="T9999"),),
        entity_ids=("T9999",),
        kind="fact",
    )
    answer = SynthesizedAnswer(request="q", claims=[fabricated])
    verify_answer(answer, evidence)
    assert answer.edges == []


def test_mitigatedby_deduped_across_records():
    # The same T→M pair asserted by two records emits exactly one edge.
    rec1 = make_record("T1021", related=[{"id": "M1032", "name": "MFA"}])
    rec2 = make_record(
        "T1021",
        related=[{"id": "M1032", "name": "MFA"}, {"id": "M1030", "name": "Network Segmentation"}],
        record_id="attack:T1021:b",
    )
    evidence = make_evidence(
        [make_result(records=[rec1, rec2], summary="T1021 found.")]
    )
    answer = DeterministicComposer().compose(evidence)
    verify_answer(answer, evidence)

    assert answer.edges == [
        SynthesisEdge("T1021", "M1032", "mitigatedBy"),
        SynthesisEdge("T1021", "M1030", "mitigatedBy"),
    ]


def test_edges_order_is_mapsto_then_mitigatedby_and_reverification_is_stable():
    # Cross-source join AND related mitigations: mapsTo edges precede
    # mitigatedBy edges, and re-verifying a fresh compose is byte-identical.
    capec = make_record(
        "CAPEC-555",
        name="Remote Services Exploitation",
        source="capec",
        backend="gremlin",
        label="AttackPattern",
        join_values=("T1021",),
    )
    attack = make_record(
        "T1021",
        name="Remote Services",
        join_values=("T1021",),
        related=[{"id": "M1032", "name": "Multi-factor Authentication"}],
    )
    evidence = make_evidence(
        [
            make_result(source="capec", sub_question_id="c1", records=[capec], summary="CAPEC-555 maps to T1021."),
            make_result(source="attack", sub_question_id="a1", records=[attack], summary="T1021 found."),
        ]
    )

    one = verify_answer(DeterministicComposer().compose(evidence), evidence)
    two = verify_answer(DeterministicComposer().compose(evidence), evidence)

    assert one.edges == [
        SynthesisEdge("CAPEC-555", "T1021", "mapsTo"),
        SynthesisEdge("T1021", "M1032", "mitigatedBy"),
    ]
    assert one.to_dict() == two.to_dict()
