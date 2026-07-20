#!/usr/bin/env python3
"""The deterministic composer: claims cite their records, empties abstain."""

from __future__ import annotations

from utils.synthesis.composer import DeterministicComposer, abstention_statement
from utils.synthesis.config import SynthesisConfig
from utils.synthesis.verifier import verify_answer

from ._fixtures import make_evidence, make_record, make_result


def _compose(evidence, **config_kwargs):
    return DeterministicComposer(SynthesisConfig(**config_kwargs)).compose(evidence)


# -- structured enumeration (the under-enumeration fix) ----------------------


def _enum_claims(answer):
    return [c for c in answer.claims if c.kind == "enumeration"]


def test_enumerative_question_emits_full_enumeration_claim():
    """'which techniques' → one claim naming EVERY related id, cited to the anchor."""
    ids = [f"T{1000 + i}" for i in range(20)]
    anchor = make_record(
        "S0266",
        name="TrickBot",
        label="Software",
        related=[{"id": t, "name": f"tech {t}", "label": "Technique"} for t in ids],
    )
    evidence = make_evidence(
        [make_result(text="Which techniques does software S0266 (TrickBot) use?",
                     records=[anchor], summary="TrickBot uses many techniques.")]
    )
    answer = _compose(evidence)
    enum = _enum_claims(answer)
    assert len(enum) == 1
    # every related id is surfaced (not just a sample)
    assert set(enum[0].entity_ids) == set(ids)
    assert enum[0].citations[0].primary_id == "S0266"
    # and it verifies as supported (grounded by the anchor's id pool)
    verified = verify_answer(_compose(evidence), evidence)
    assert all(v.supported for v in verified.verification.verdicts)


def test_non_enumerative_small_related_set_gets_no_enumeration_claim():
    """An abstraction lookup (2 ancestors, not enumerative) stays a plain fact."""
    anchor = make_record(
        "CAPEC-555", source="capec", label="AttackPattern",
        related=[{"id": "CAPEC-560", "role": "parent"}, {"id": "CAPEC-1", "role": "grandparent"}],
    )
    evidence = make_evidence(
        [make_result(source="capec", text="What abstraction level is CAPEC-555?",
                     records=[anchor], summary="One pattern.")]
    )
    assert _enum_claims(_compose(evidence)) == []


def test_large_related_set_enumerates_even_without_enumerative_phrasing():
    """Safety net: a related set larger than the citation cap is always listed."""
    ids = [f"T{2000 + i}" for i in range(12)]  # > default cap of 8
    anchor = make_record(
        "T1003", related=[{"id": t, "label": "Technique"} for t in ids],
    )
    evidence = make_evidence(
        [make_result(text="tell me about T1003", records=[anchor], summary="A technique.")]
    )
    enum = _enum_claims(_compose(evidence))
    assert len(enum) == 1
    assert set(enum[0].entity_ids) == set(ids)


def test_enumeration_preserves_non_mitre_related_ids_verbatim():
    """CAPEC consequence child ids are not MITRE-shaped — they must survive whole."""
    cons = [f"capec:attack-pattern:66:consequence:{i}" for i in range(1, 5)]
    anchor = make_record(
        "CAPEC-66", source="capec", label="AttackPattern",
        related=[{"id": c, "label": "Consequence"} for c in cons],
    )
    evidence = make_evidence(
        [make_result(source="capec", text="What consequences does CAPEC-66 have?",
                     records=[anchor], summary="Four consequences.")]
    )
    enum = _enum_claims(_compose(evidence))
    assert len(enum) == 1
    assert set(enum[0].entity_ids) == set(cons)


def test_many_primary_records_are_enumerated_by_primary_id():
    """Shape B: a group's 12 technique records (each its own record, no related)
    — the fact claim samples 8, the enumeration claim lists all 12."""
    ids = [f"T{3000 + i}" for i in range(12)]  # > default cap of 8
    records = [make_record(t, join_values=(t,)) for t in ids]
    evidence = make_evidence(
        [make_result(text="Which techniques does group G0007 use?", records=records,
                     summary="Found 12 techniques.")]
    )
    answer = _compose(evidence)
    enum = _enum_claims(answer)
    assert len(enum) == 1
    assert set(enum[0].entity_ids) == set(ids)
    verified = verify_answer(_compose(evidence), evidence)
    assert all(v.supported for v in verified.verification.verdicts)


def test_few_primary_records_need_no_enumeration_claim():
    """At or below the citation cap the fact claim already surfaces every id."""
    records = [make_record(f"T10{i}", join_values=(f"T10{i}",)) for i in range(3)]
    evidence = make_evidence([make_result(text="Which techniques?", records=records)])
    assert _enum_claims(_compose(evidence)) == []


def test_enumeration_claim_text_names_the_ids():
    """The full list rides the claim text too, so a reader sees it, not just a count."""
    ids = ["M1041", "M1015", "M1043"]
    anchor = make_record("T1003", related=[{"id": m, "label": "Mitigation"} for m in ids])
    evidence = make_evidence(
        [make_result(text="What mitigations does ATT&CK list for T1003?", records=[anchor])]
    )
    enum = _enum_claims(_compose(evidence))[0]
    for m in ids:
        assert m in enum.text


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
