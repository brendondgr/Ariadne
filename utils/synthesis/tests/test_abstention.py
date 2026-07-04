#!/usr/bin/env python3
"""Abstention enforcement: honest empties always abstain, with the query shown."""

from __future__ import annotations

from utils.synthesis.contracts import Abstention, SynthesizedAnswer
from utils.synthesis.verifier import verify_answer

from ._fixtures import make_evidence, make_record, make_result

_QUERY = "MATCH (t:Technique {attack_id: $id})<-[:MITIGATES]-(m) RETURN m"


def _empty_evidence():
    return make_evidence(
        [
            make_result(
                records=[],
                ok=True,
                query=_QUERY,
                text="mitigations for T9999?",
            )
        ]
    )


def test_missing_abstention_is_repaired_with_executed_query():
    # An LLM composer that simply omits the abstention cannot skip it: the
    # verifier derives it from evidence.
    answer = verify_answer(SynthesizedAnswer(request="q"), _empty_evidence())
    assert len(answer.abstentions) == 1
    abst = answer.abstentions[0]
    assert abst.query == _QUERY
    assert abst.sub_question_id == "q1"
    assert "doesn't establish" in abst.statement
    assert answer.verification.repaired_abstentions == 1


def test_supplied_abstention_with_correct_query_is_kept_verbatim():
    supplied = Abstention(
        sub_question_id="q1",
        source="attack",
        statement="ATT&CK lists no mitigations for this technique.",
        query=_QUERY,
    )
    answer = verify_answer(
        SynthesizedAnswer(request="q", abstentions=[supplied]), _empty_evidence()
    )
    assert answer.abstentions == [supplied]
    assert answer.verification.repaired_abstentions == 0


def test_wrong_query_proof_is_replaced_with_executed_query():
    supplied = Abstention(
        sub_question_id="q1",
        source="attack",
        statement="ATT&CK lists no mitigations for this technique.",
        query="MATCH (fabricated) RETURN fabricated",
    )
    answer = verify_answer(
        SynthesizedAnswer(request="q", abstentions=[supplied]), _empty_evidence()
    )
    assert answer.abstentions[0].query == _QUERY
    assert answer.abstentions[0].statement == supplied.statement
    assert answer.verification.repaired_abstentions == 1


def test_false_abstention_over_real_evidence_is_removed():
    # Abstaining on a sub-question that DID return records hides evidence.
    evidence = make_evidence([make_result(records=[make_record("T1047")])])
    supplied = Abstention(
        sub_question_id="q1",
        source="attack",
        statement="The sources don't establish this.",
        query="whatever",
    )
    answer = verify_answer(
        SynthesizedAnswer(request="q", abstentions=[supplied]), evidence
    )
    assert answer.abstentions == []
    assert answer.verification.repaired_abstentions == 1


def test_failed_specialist_does_not_abstain():
    # ok=False is a failure note, not an evidence-backed absence: no query ran
    # to completion, so there is no proof to show.
    evidence = make_evidence([make_result(records=[], ok=False, error="boom")])
    answer = verify_answer(SynthesizedAnswer(request="q"), evidence)
    assert answer.abstentions == []


def test_multiple_empties_each_get_their_own_abstention():
    evidence = make_evidence(
        [
            make_result(sub_question_id="q1", records=[], ok=True, query="Q1"),
            make_result(
                source="capec", sub_question_id="q2", records=[], ok=True, query="Q2"
            ),
        ]
    )
    answer = verify_answer(SynthesizedAnswer(request="q"), evidence)
    assert {(a.sub_question_id, a.query) for a in answer.abstentions} == {
        ("q1", "Q1"),
        ("q2", "Q2"),
    }


# -- schema-boundary abstentions (Step 7) --------------------------------------


def _boundary_evidence():
    # A boundary refusal: the specialist executed NO query because the source
    # doesn't model the asked-about entity (e.g. Asset, ICS-only).
    return make_evidence(
        [
            make_result(
                records=[],
                ok=True,
                query="",
                text="What assets does technique T1047 target?",
            )
        ]
    )


def test_boundary_refusal_abstains_with_boundary_statement():
    answer = verify_answer(SynthesizedAnswer(request="q"), _boundary_evidence())
    assert len(answer.abstentions) == 1
    abst = answer.abstentions[0]
    assert abst.query == ""  # no query is the honest proof shape here
    assert "doesn't establish" in abst.statement
    assert "doesn't model" in abst.statement
    assert "no query was executed" in abst.statement
    # And it must NOT claim a query ran cleanly.
    assert "ran cleanly" not in abst.statement


def test_fabricated_query_proof_on_boundary_is_stripped():
    # An LLM composer inventing a plausible query as "proof" for a boundary
    # sub-question is repaired: the enforced abstention carries no query.
    supplied = Abstention(
        sub_question_id="q1",
        source="attack",
        statement="No assets found.",
        query="MATCH (t:Technique)-[:TARGETS]->(a:Asset) RETURN a",
    )
    answer = verify_answer(
        SynthesizedAnswer(request="q", abstentions=[supplied]), _boundary_evidence()
    )
    assert len(answer.abstentions) == 1
    assert answer.abstentions[0].query == ""
    assert answer.verification.repaired_abstentions == 1


def test_genuine_empty_still_requires_the_executed_query_wording():
    answer = verify_answer(SynthesizedAnswer(request="q"), _empty_evidence())
    assert "ran cleanly" in answer.abstentions[0].statement
    assert answer.abstentions[0].query == _QUERY
