#!/usr/bin/env python3
"""Adversarial tests for the verification pass.

Every test here injects a claim the evidence does not support — a fabricated
ID, a citation to a record that was never retrieved, a claim against a source
that returned nothing — and asserts the verifier cuts it. This is the test of
the guard itself: if a fabricated claim survives, Step 6 does not exist.
"""

from __future__ import annotations

from utils.synthesis.composer import DeterministicComposer
from utils.synthesis.contracts import Citation, Claim, SynthesizedAnswer
from utils.synthesis.verifier import verify_answer

from ._fixtures import make_evidence, make_record, make_result


def _evidence_one_technique():
    record = make_record(
        "T1047",
        name="Windows Management Instrumentation",
        related=[{"id": "M1038", "name": "Execution Prevention"}],
    )
    return make_evidence([make_result(records=[record], summary="T1047 found.")])


def _answer(claims, request="q"):
    return SynthesizedAnswer(request=request, claims=list(claims))


def _cite(primary_id="T1047", source="attack", record_id=""):
    return Citation(source=source, primary_id=primary_id, record_id=record_id)


def test_supported_claim_passes():
    claim = Claim(
        text="T1047 is mitigated by M1038.",
        citations=(_cite(),),
        entity_ids=("T1047", "M1038"),  # M1038 grounded via related
    )
    answer = verify_answer(_answer([claim]), _evidence_one_technique())
    assert answer.verification.ok
    assert answer.rendered_claims() == [claim]


def test_uncited_claim_is_cut():
    claim = Claim(text="T1047 exists.", citations=(), entity_ids=("T1047",))
    answer = verify_answer(_answer([claim]), _evidence_one_technique())
    assert not answer.verification.ok
    assert answer.rendered_claims() == []
    (_, verdict), = answer.flagged_claims()
    assert any("uncited" in r for r in verdict.reasons)


def test_fabricated_entity_is_cut():
    claim = Claim(
        text="T1047 is mitigated by M9999.",  # invented mitigation
        citations=(_cite(),),
        entity_ids=("T1047", "M9999"),
    )
    answer = verify_answer(_answer([claim]), _evidence_one_technique())
    assert not answer.verification.ok
    (_, verdict), = answer.flagged_claims()
    assert any("M9999" in r and "not grounded" in r for r in verdict.reasons)


def test_citation_to_unretrieved_record_is_cut():
    claim = Claim(
        text="T1566 was retrieved.",
        citations=(_cite(primary_id="T1566"),),  # never retrieved
        entity_ids=("T1566",),
    )
    answer = verify_answer(_answer([claim]), _evidence_one_technique())
    (_, verdict), = answer.flagged_claims()
    assert any("does not match any retrieved record" in r for r in verdict.reasons)


def test_claim_citing_empty_source_is_cut():
    evidence = make_evidence(
        [
            make_result(records=[make_record("T1047")]),
            make_result(
                source="capec", sub_question_id="q2", records=[], ok=True
            ),
        ]
    )
    claim = Claim(
        text="CAPEC-555 maps to this.",
        citations=(_cite(primary_id="CAPEC-555", source="capec"),),
        entity_ids=("CAPEC-555",),
    )
    answer = verify_answer(_answer([claim]), evidence)
    (_, verdict), = answer.flagged_claims()
    assert any("returned no records" in r for r in verdict.reasons)


def test_wrong_record_id_on_real_primary_id_still_supported():
    # The record was genuinely retrieved; an imprecise backend pointer is not
    # fabrication.
    claim = Claim(
        text="T1047 found.",
        citations=(_cite(record_id="bogus-backend-id"),),
        entity_ids=("T1047",),
    )
    answer = verify_answer(_answer([claim]), _evidence_one_technique())
    assert answer.verification.ok


def test_gremlin_id_forms_ground_canonical_entities():
    record = make_record(
        "capec:attack-pattern:555",
        source="capec",
        backend="gremlin",
        label="AttackPattern",
        join_values=("T1021",),
        related=[{"id": "cwe:522", "name": "Insufficiently Protected Credentials"}],
    )
    evidence = make_evidence([make_result(source="capec", records=[record])])
    claim = Claim(
        text="CAPEC-555 relates to CWE-522.",
        citations=(Citation(source="capec", primary_id="CAPEC-555"),),
        entity_ids=("CAPEC-555", "CWE-522"),
    )
    answer = verify_answer(_answer([claim]), evidence)
    assert answer.verification.ok, answer.verification.to_dict()


def test_correlation_backed_by_join_index_passes():
    attack = make_result(records=[make_record("T1021", join_values=("T1021",))])
    capec = make_result(
        source="capec",
        sub_question_id="q2",
        records=[
            make_record(
                "CAPEC-555", source="capec", label="AttackPattern", join_values=("T1021",)
            )
        ],
    )
    evidence = make_evidence([attack, capec])
    claim = Claim(
        text="T1021 is corroborated across attack and capec.",
        citations=(
            _cite(primary_id="T1021"),
            Citation(source="capec", primary_id="CAPEC-555"),
        ),
        entity_ids=("T1021",),
        kind="correlation",
    )
    answer = verify_answer(_answer([claim]), evidence)
    assert answer.verification.ok


def test_single_source_correlation_is_cut():
    evidence = _evidence_one_technique()
    claim = Claim(
        text="T1047 is corroborated across sources.",
        citations=(_cite(),),
        entity_ids=("T1047",),
        kind="correlation",
    )
    answer = verify_answer(_answer([claim]), evidence)
    (_, verdict), = answer.flagged_claims()
    assert any("join index" in r for r in verdict.reasons)


def test_mixed_claims_cut_only_the_bad_one():
    good = Claim(text="T1047 found.", citations=(_cite(),), entity_ids=("T1047",))
    bad = Claim(text="T1047 mitigated by M9999.", citations=(_cite(),), entity_ids=("M9999",))
    answer = verify_answer(_answer([good, bad]), _evidence_one_technique())
    assert answer.rendered_claims() == [good]
    assert answer.verification.supported_count == 1
    assert answer.verification.unsupported_count == 1
    assert abs(answer.verification.unsupported_claim_rate - 0.5) < 1e-9


def test_deterministic_composer_output_verifies_clean():
    # Consistency: the mechanical composer's claims must all survive its own
    # verifier over mixed evidence (records + empty + cross-source join).
    attack = make_result(
        records=[
            make_record("T1021", join_values=("T1021",)),
            make_record("T1047", join_values=("T1047",)),
        ],
        summary="Two techniques.",
    )
    capec = make_result(
        source="capec",
        sub_question_id="q2",
        records=[
            make_record(
                "CAPEC-555", source="capec", label="AttackPattern", join_values=("T1021",)
            )
        ],
        summary="One pattern.",
    )
    empty = make_result(sub_question_id="q3", records=[], ok=True, query="MATCH ...")
    evidence = make_evidence([attack, capec, empty])

    answer = verify_answer(DeterministicComposer().compose(evidence), evidence)
    assert answer.verification.ok, answer.verification.to_dict()
    assert answer.verification.repaired_abstentions == 0
    assert len(answer.rendered_claims()) == len(answer.claims) == 3  # 2 facts + 1 corr
    assert len(answer.abstentions) == 1


# -- cross-source reconciliation (contested claims) --------------------------
#
# A conflict never *cuts* a claim (both records are real) — it flags the
# supported claim "contested" and rides the report as a Conflict.


def _conflicting_name_evidence():
    """attack names T1055 'Process Injection'; capec's mapping calls it
    'Thread Hijacking' — a genuine cross-source name disagreement."""
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
                related=[{"id": "T1055", "name": "Thread Hijacking"}],
            )
        ],
    )
    return make_evidence([attack, capec])


def test_contested_claim_stays_supported_and_rendered():
    claim = Claim(
        text="T1055 is Process Injection.",
        citations=(_cite("T1055"),),
        entity_ids=("T1055",),
    )
    answer = verify_answer(_answer([claim]), _conflicting_name_evidence())

    report = answer.verification
    assert report.conflict_count == 1
    assert report.conflicts[0].kind == "name"
    # flagged, not cut: the claim is still supported and still rendered.
    assert answer.rendered_claims() == [claim]
    (verdict,) = report.verdicts
    assert verdict.supported
    assert verdict.is_contested
    assert verdict.contested == ("T1055",)


def test_conflict_free_answer_has_no_conflicts_and_identical_payload():
    claim = Claim(
        text="T1047 is mitigated by M1038.",
        citations=(_cite(),),
        entity_ids=("T1047", "M1038"),
    )
    answer = verify_answer(_answer([claim]), _evidence_one_technique())

    report = answer.verification
    assert report.conflict_count == 0
    assert report.contested_count == 0
    # omit-when-empty keeps the report payload byte-identical to pre-reconcile.
    d = report.to_dict()
    assert "conflicts" not in d
    assert "conflict_count" not in d
    assert "contested" not in d["verdicts"][0]
