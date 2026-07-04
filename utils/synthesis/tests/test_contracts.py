#!/usr/bin/env python3
"""Contract round-trips and rendering rules for the synthesis dataclasses."""

from __future__ import annotations

from utils.synthesis.contracts import (
    Abstention,
    Citation,
    Claim,
    ClaimVerdict,
    SynthesizedAnswer,
    VerificationReport,
)


def _claim(text: str = "T1047 is mitigated by M1038.") -> Claim:
    return Claim(
        text=text,
        citations=(Citation(source="attack", primary_id="T1047", record_id="n42"),),
        entity_ids=("T1047", "M1038"),
        kind="fact",
        sub_question_id="q1",
    )


def test_claim_round_trip():
    claim = _claim()
    assert Claim.from_dict(claim.to_dict()) == claim


def test_citation_round_trip():
    cite = Citation(source="capec", primary_id="CAPEC-555")
    assert Citation.from_dict(cite.to_dict()) == cite


def test_abstention_round_trip():
    abst = Abstention(
        sub_question_id="q2",
        source="attack",
        statement="The attack source doesn't establish this.",
        query="MATCH (t:Technique {attack_id: $id}) RETURN t",
    )
    assert Abstention.from_dict(abst.to_dict()) == abst


def test_claim_from_dict_tolerates_missing_fields():
    claim = Claim.from_dict({"text": "bare"})
    assert claim.text == "bare"
    assert claim.citations == ()
    assert claim.entity_ids == ()
    assert claim.kind == "fact"


def test_verification_report_metrics():
    report = VerificationReport(
        verdicts=[
            ClaimVerdict(verdict="supported"),
            ClaimVerdict(verdict="unsupported", reasons=["uncited claim"]),
            ClaimVerdict(verdict="supported"),
        ]
    )
    assert report.supported_count == 2
    assert report.unsupported_count == 1
    assert abs(report.unsupported_claim_rate - 1 / 3) < 1e-9
    assert not report.ok
    assert report.to_dict()["claim_count"] == 3


def test_empty_report_is_ok_with_zero_rate():
    report = VerificationReport()
    assert report.ok
    assert report.unsupported_claim_rate == 0.0


def test_unverified_answer_renders_no_claims():
    answer = SynthesizedAnswer(request="q", claims=[_claim()])
    assert answer.rendered_claims() == []
    assert answer.flagged_claims() == []
    assert answer.to_dict()["verification"] is None
    assert answer.to_dict()["rendered_claims"] == []


def test_verified_answer_renders_only_supported_claims():
    good, bad = _claim("good"), _claim("bad")
    answer = SynthesizedAnswer(
        request="q",
        claims=[good, bad],
        verification=VerificationReport(
            verdicts=[
                ClaimVerdict(verdict="supported"),
                ClaimVerdict(verdict="unsupported", reasons=["entity not grounded"]),
            ]
        ),
    )
    assert answer.rendered_claims() == [good]
    flagged = answer.flagged_claims()
    assert len(flagged) == 1 and flagged[0][0] == bad
    assert flagged[0][1].reasons == ["entity not grounded"]

    data = answer.to_dict()
    assert data["claims"][0]["verdict"]["verdict"] == "supported"
    assert data["claims"][1]["verdict"]["verdict"] == "unsupported"
    assert [c["text"] for c in data["rendered_claims"]] == ["good"]
    assert data["verification"]["unsupported_count"] == 1
