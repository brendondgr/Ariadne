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


# -- the absence claim (EXP-2026-09-018 Step 4) ------------------------------


def test_an_absence_claim_is_admitted_only_off_a_clean_query() -> None:
    """Asserting that nothing is there is the one claim a record cannot ground.

    Its proof is the query, so the verifier checks the query instead: the result
    must have run clean and carried no error. Without this the composer could
    state "X has no execution steps" off a failed lookup — a falsehood with full
    provenance, which is the single worst thing a grounded system can emit.
    """
    from utils.synthesis.composer import _absence_claim
    from utils.synthesis.verifier import _verify_claim

    record = make_record("CAPEC-513", source="capec", label="Category", related=[])
    clean = make_result(source="capec", records=[record])
    claim = _absence_claim(clean, "HAS_EXECUTION_STEP")

    by_source = {"capec": [record]}
    ok = _verify_claim(claim, by_source, set(), None, make_evidence([clean]))
    assert ok.verdict == "supported", ok.reasons

    broken = make_result(source="capec", records=[record], ok=False,
                         error="connection reset")
    bad = _verify_claim(claim, by_source, set(), None, make_evidence([broken]))
    assert bad.verdict == "unsupported"
    assert any("did not run clean" in r for r in bad.reasons)


def test_an_absence_claim_is_refused_when_the_relation_is_actually_there() -> None:
    """A related entry OF THAT RELATION means the set is not empty."""
    from utils.synthesis.composer import _absence_claim
    from utils.synthesis.verifier import _verify_claim

    empty = make_record("CAPEC-513", source="capec", label="Category", related=[])
    entities = ("Category", "HAS_EXECUTION_STEP", "ExecutionStep")
    claim = _absence_claim(
        make_result(source="capec", records=[empty], entities=entities),
        "HAS_EXECUTION_STEP",
    )

    populated = make_record(
        "CAPEC-513", source="capec", label="Category",
        related=[{"id": "capec:step:1", "label": "ExecutionStep",
                  "type": "HAS_EXECUTION_STEP"}],
    )
    result = make_result(source="capec", records=[populated], entities=entities)
    verdict = _verify_claim(claim, {"capec": [populated]}, set(), None,
                            make_evidence([result]))

    assert verdict.verdict == "unsupported"
    assert any("contradicted by the evidence" in r for r in verdict.reasons)


def test_an_absence_claim_is_refused_when_only_a_facet_says_the_edge_is_there() -> None:
    """`describe` returns facet COUNTS without materialising neighbours.

    A record can carry an empty `related` list and a facet saying the edge
    exists. Reading the empty list as absence produced the first
    `fabricated_mapping` flags against the repaired arm: "CAPEC-33 has no maps
    to" beside a facet reporting one outbound MAPS_TO. Absence of materialised
    neighbours is not absence of the edge.
    """
    from utils.synthesis.composer import _absence_claim, _relation_is_empty
    from utils.synthesis.verifier import _verify_claim

    entities = ("AttackPattern", "MAPS_TO", "TaxonomyEntry")
    faceted = make_record(
        "CAPEC-33", source="capec", label="AttackPattern", related=[],
        facets=[{"rel": "MAPS_TO", "direction": "out",
                 "neighbour_label": "TaxonomyEntry", "count": 1}],
    )
    result = make_result(
        source="capec", records=[faceted], entities=entities,
        query='g.V().has("id", within(ids)).out("MAPS_TO")',
    )

    assert not _relation_is_empty(result, "MAPS_TO")

    claim = _absence_claim(result, "MAPS_TO")
    verdict = _verify_claim(claim, {"capec": [faceted]}, set(), None,
                            make_evidence([result]))
    assert verdict.verdict == "unsupported"


def test_an_unrelated_neighbour_does_not_suppress_the_absence_claim() -> None:
    """A Category asked for its prerequisites carries its MEMBERS, not none.

    Testing "does this record have any related entries at all" made the answer
    enumerate the members and never say the requested set was empty — it
    answered a different question, and four D0 questions lost the score they had
    been getting by abstaining for the wrong reason.
    """
    from utils.synthesis.composer import _relation_is_empty

    record = make_record(
        "capec:category:689", source="capec", label="Category",
        related=[{"id": "CAPEC-675", "label": "AttackPattern",
                  "type": "HAS_MEMBER"}],
    )
    # The query must have ASKED about the relation before its emptiness means
    # anything: an absence asserted from a retrieval that never looked is not
    # grounded in the retrieval it cites.
    asked = make_result(
        source="capec", records=[record],
        entities=("Category", "HAS_PREREQUISITE", "Prerequisite"),
        query='g.V().has("id", within(ids)).union(__.out("HAS_PREREQUISITE"), '
              '__.in("HAS_MEMBER"))',
    )
    assert _relation_is_empty(asked, "HAS_PREREQUISITE")
    assert not _relation_is_empty(asked, "HAS_MEMBER")

    never_asked = make_result(
        source="capec", records=[record],
        entities=("Category", "HAS_PREREQUISITE", "Prerequisite"),
        query='g.V().has("id", within(ids)).in("HAS_MEMBER")',
    )
    assert not _relation_is_empty(never_asked, "HAS_PREREQUISITE")


def test_relation_names_fold_across_the_two_spellings() -> None:
    """The card says `CanAlsoBe`; the loaded graph says `CAN_ALSO_BE`."""
    from utils.synthesis.composer import _relation_is_empty

    record = make_record(
        "CAPEC-33", source="capec", label="AttackPattern",
        related=[{"id": "CAPEC-273", "label": "AttackPattern",
                  "type": "CAN_ALSO_BE"}],
    )
    result = make_result(
        source="capec", records=[record],
        query='g.V().has("id", within(ids)).out("CAN_ALSO_BE")',
    )
    assert not _relation_is_empty(result, "CanAlsoBe")
