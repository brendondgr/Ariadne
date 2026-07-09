#!/usr/bin/env python3
"""The deterministic composer: claims cite their records, empties abstain."""

from __future__ import annotations

from utils.synthesis.composer import DeterministicComposer, abstention_statement
from utils.synthesis.config import SynthesisConfig

from ._fixtures import make_evidence, make_record, make_result


def _compose(evidence, **config_kwargs):
    return DeterministicComposer(SynthesisConfig(**config_kwargs)).compose(evidence)


def test_result_with_records_becomes_cited_fact_claim():
    records = [make_record("T1047", name="WMI"), make_record("T1021", name="Remote Services")]
    evidence = make_evidence(
        [make_result(records=records, summary="Two techniques matched.")]
    )
    answer = _compose(evidence)

    assert len(answer.claims) == 1
    claim = answer.claims[0]
    assert claim.kind == "fact"
    assert claim.text == "Two techniques matched."
    assert claim.sub_question_id == "q1"
    assert [c.primary_id for c in claim.citations] == ["T1047", "T1021"]
    assert all(c.source == "attack" for c in claim.citations)
    assert all(c.record_id for c in claim.citations)  # provenance carried through
    assert claim.entity_ids == ("T1047", "T1021")
    assert answer.abstentions == []
    assert answer.composer == "deterministic"


def test_narrative_assembles_claim_sentences_into_prose():
    evidence = make_evidence(
        [make_result(records=[make_record("T1047", name="WMI")], summary="WMI matched.")]
    )
    answer = _compose(evidence)
    assert answer.narrative == "WMI matched."


def test_narrative_is_honest_when_no_evidence():
    answer = _compose(make_evidence([make_result(records=[], summary="", ok=False)]))
    # Honest AND actionable: no grounded fact, so it says the sources don't cover
    # the request and how to disambiguate (name it / give an id).
    assert "cover this request" in answer.narrative
    assert "give its id" in answer.narrative


def test_missing_summary_gets_generated_text_still_cited():
    evidence = make_evidence([make_result(records=[make_record("T1566")], summary="")])
    claim = _compose(evidence).claims[0]
    assert "1 record(s)" in claim.text and "attack" in claim.text
    assert claim.entity_ids == ("T1566",)


def test_citation_cap_bounds_claim_citations():
    records = [make_record(f"T10{i:02d}") for i in range(12)]
    evidence = make_evidence([make_result(records=records)])
    claim = _compose(evidence, max_citations=8).claims[0]
    assert len(claim.citations) == 8
    assert len(claim.entity_ids) == 8


def test_honest_empty_becomes_abstention_with_executed_query():
    query = "MATCH (t:Technique {attack_id: $id})-[:MITIGATES]-(m) RETURN m"
    evidence = make_evidence(
        [make_result(records=[], ok=True, query=query, text="mitigations of T9999?")]
    )
    answer = _compose(evidence)

    assert answer.claims == []
    assert len(answer.abstentions) == 1
    abst = answer.abstentions[0]
    assert abst.query == query
    assert abst.source == "attack"
    assert abst.statement == abstention_statement("attack", "mitigations of T9999?", query)
    assert "ran cleanly" in abst.statement
    assert "doesn't establish" in abst.statement
    assert "question(s) the sources don't establish" in answer.headline


def test_failed_specialist_becomes_note_not_claim_or_abstention():
    evidence = make_evidence(
        [make_result(records=[], ok=False, error="gate rejected: depth cap")]
    )
    answer = _compose(evidence)
    assert answer.claims == []
    assert answer.abstentions == []
    assert any("gate rejected" in n for n in answer.notes)


def test_cross_source_join_becomes_correlation_claim():
    attack = make_result(
        source="attack",
        records=[make_record("T1021", join_values=("T1021",))],
        summary="ATT&CK technique found.",
    )
    capec = make_result(
        source="capec",
        sub_question_id="q2",
        records=[
            make_record(
                "CAPEC-555",
                source="capec",
                backend="gremlin",
                label="AttackPattern",
                join_values=("T1021",),
            )
        ],
        summary="CAPEC pattern found.",
    )
    answer = _compose(make_evidence([attack, capec]))

    correlations = [c for c in answer.claims if c.kind == "correlation"]
    assert len(correlations) == 1
    corr = correlations[0]
    assert corr.entity_ids == ("T1021",)
    assert "attack and capec" in corr.text
    cited = {(c.source, c.primary_id) for c in corr.citations}
    assert ("attack", "T1021") in cited and ("capec", "CAPEC-555") in cited
    assert "1 cross-source correlation(s)" in answer.headline


def test_same_source_shared_value_is_not_a_correlation():
    r1 = make_result(records=[make_record("T1021", join_values=("T1021",))])
    r2 = make_result(
        sub_question_id="q2",
        records=[make_record("T1021.001", join_values=("T1021",))],
    )
    answer = _compose(make_evidence([r1, r2]))
    assert [c for c in answer.claims if c.kind == "correlation"] == []


def test_unsupported_and_skipped_become_notes():
    evidence = make_evidence(
        [make_result(records=[make_record("T1047")])],
        unsupported=[{"description": "CVE data", "reason": "no live source holds it"}],
        skipped=[{"source": "d3fend", "reason": "no specialist available"}],
        partial=True,
    )
    answer = _compose(evidence)
    assert any("CVE data" in n for n in answer.notes)
    assert any("d3fend" in n for n in answer.notes)
    assert "1 part(s) unsupported" in answer.headline


# -- Definitional Name Lookup (5/6): clear, actionable abstention -----------


def test_name_lookup_miss_names_the_entity_in_the_abstention():
    # An empty result from a definitional name lookup names what it searched for.
    evidence = make_evidence(
        [make_result(records=[], ok=True, query="MATCH (n) WHERE toLower(n.name) CONTAINS term RETURN n",
                     text="What is Flibbertigibbet?")],
        request="What is Flibbertigibbet?",
    )
    answer = _compose(evidence)
    assert answer.claims == []
    assert len(answer.abstentions) == 1
    stmt = answer.abstentions[0].statement
    assert "Flibbertigibbet" in stmt
    assert "give its" in stmt and "id" in stmt  # tells the analyst how to disambiguate


def test_empty_definitional_answer_has_actionable_narrative():
    evidence = make_evidence(
        [make_result(records=[], ok=True, query="MATCH (n) WHERE toLower(n.name) CONTAINS term RETURN n",
                     text="What is Flibbertigibbet?")],
        request="What is Flibbertigibbet?",
    )
    answer = _compose(evidence)
    assert "Flibbertigibbet" in answer.narrative
    assert "couldn't find" in answer.narrative.lower()


def test_garbled_model_unsupported_reason_is_not_leaked():
    # The local planner model's free-text reason must never reach the analyst.
    evidence = make_evidence(
        [],
        request="What exactly is User Training and Software Configuration respectively?",
        unsupported=[{"description": "What", "reason": "The request 'What' is incomplete."}],
    )
    answer = _compose(evidence)
    joined = " ".join(answer.notes) + " " + answer.narrative
    assert "incomplete" not in joined  # garbled reason is dropped
    assert "'What'" not in joined
    # The narrative names the entities the analyst actually asked about.
    assert "User Training" in answer.narrative and "Software Configuration" in answer.narrative


def test_clean_source_down_reason_is_kept_verbatim():
    # A legitimate source-availability reason is still surfaced as-is.
    evidence = make_evidence(
        [],
        request="Which CVEs affect X?",
        unsupported=[{"description": "Part needs NVD (nvd).", "reason": "nvd is not live: source down"}],
    )
    answer = _compose(evidence)
    assert any("not live" in n for n in answer.notes)


def test_clarification_does_not_override_a_grounded_narrative():
    evidence = make_evidence(
        [make_result(records=[make_record("M1017", name="User Training")], summary="User Training matched.")],
        request="What is User Training?",
    )
    answer = _compose(evidence)
    assert answer.narrative == "User Training matched."


def test_draft_is_unverified_and_renders_nothing():
    answer = _compose(make_evidence([make_result(records=[make_record("T1047")])]))
    assert answer.verification is None
    assert answer.rendered_claims() == []
