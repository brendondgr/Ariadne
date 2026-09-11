#!/usr/bin/env python3
"""The deterministic composer: claims cite their records, empties abstain."""

from __future__ import annotations

from utils.synthesis.composer import (
    DeterministicComposer,
    _attribute_pairs,
    abstention_statement,
)
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


def test_a_small_related_set_is_enumerated_too():
    """The reversal: a two-ancestor abstraction lookup DOES get an enumeration claim.

    This test previously asserted the opposite — that a set small enough not to
    be truncated "stays a plain fact" — on the reasoning that the fact claim's
    prose would already have named it. EXP-2026-08-007 refuted that on the blind
    holdout, and this exact shape is why.

    The prose only names related ids on the ATT&CK side.
    ``cypher/normalizer.summarize`` emits "Found 3 item(s) related to T1055
    (e.g. …)", but ``gremlin/normalizer.summarize`` emits "Found 1 CAPEC
    record(s): CAPEC-606." and never mentions the related set. So on CAPEC a
    small related set was retrieved, grounded, and then stated nowhere at all.

    All three of the blind holdout's ``under_enumeration`` cases were this:
    H-ABS-01 (2 ancestors, judged 0.35), H-CSQ-01 (1 consequence) and H-PRE-01
    (3 prerequisites) — each a CAPEC single record whose answer named only the
    anchor. The evidence was right there; the answer just did not say it.
    """
    anchor = make_record(
        "CAPEC-555", source="capec", label="AttackPattern",
        related=[{"id": "CAPEC-560", "role": "parent"}, {"id": "CAPEC-1", "role": "grandparent"}],
    )
    evidence = make_evidence(
        [make_result(source="capec", text="What abstraction level is CAPEC-555?",
                     records=[anchor], summary="One pattern.")]
    )
    enum = _enum_claims(_compose(evidence))
    assert len(enum) == 1
    assert set(enum[0].entity_ids) == {"CAPEC-560", "CAPEC-1"}
    # the role annotation is what makes a hierarchy answer readable
    assert "parent" in enum[0].text and "grandparent" in enum[0].text
    # and it must still verify as grounded, or we have traded one defect for another
    verified = verify_answer(_compose(evidence), evidence)
    assert all(v.supported for v in verified.verification.verdicts)


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


def test_hierarchy_enumeration_labels_standard_vs_meta_roles():
    """C-ABS: the ancestors carry roles, so the claim says which is standard/meta
    and names both ids — not the old 'evidence does not contain them'."""
    anchor = make_record(
        "CAPEC-7", name="Blind SQL Injection", source="capec", label="AttackPattern",
        related=[
            {"id": "CAPEC-66", "role": "standard", "name": "SQL Injection"},
            {"id": "CAPEC-248", "role": "meta", "name": "Command Injection"},
        ],
    )
    evidence = make_evidence(
        [make_result(source="capec",
                     text="Walk the abstraction hierarchy up from CAPEC-7: what are its standard and meta ancestors?",
                     records=[anchor], summary="Two ancestors.")]
    )
    enum = _enum_claims(_compose(evidence))
    assert len(enum) == 1
    assert set(enum[0].entity_ids) == {"CAPEC-66", "CAPEC-248"}
    # roles are annotated in the prose
    assert "CAPEC-66 (standard)" in enum[0].text
    assert "CAPEC-248 (meta)" in enum[0].text


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


# -- definitional description (the "answered with the wrong field" fix) ------


def _texts(answer):
    return " || ".join(c.text for c in answer.claims)


def test_a_single_record_result_states_what_the_entity_is():
    """H-LKP-01's shape: "what is X / how does it work" answered with STIX bookkeeping.

    The composer excludes `description` from attribute claims (it is prose, not a
    scalar) and the normalizer summary is an id-line, so the substantive field
    was never stated. Three blind-holdout lookups were judged 0.5 for this, each
    time with the judge noting the description sat unread in the evidence.
    """
    anchor = make_record(
        "T1036.010", name="Masquerade Account Name",
        properties={
            "description": "Adversaries may match or approximate the names of legitimate accounts.",
            "revoked": False,
            "x_mitre_version": "2.0",
        },
    )
    evidence = make_evidence([make_result(
        text="What is T1036.010 (Masquerade Account Name) — how does this technique work?",
        records=[anchor], summary="Found ATT&CK record T1036.010: Masquerade Account Name.",
    )])
    answer = _compose(evidence)
    assert "approximate the names of legitimate accounts" in _texts(answer)
    verified = verify_answer(_compose(evidence), evidence)
    assert all(v.supported for v in verified.verification.verdicts)


def test_the_description_claim_does_not_depend_on_question_phrasing():
    """H-LKP-03 asks "what does this actually involve?" — no "what is" trigger.

    Gating on `is_definitional_request` was tried and rejected: it matches
    "What is T1036.010…" but not "CAPEC-321 … what does this attack pattern
    actually involve?", and those are the same kind of question. The gate is the
    shape of the result instead — one record means the question is about it.
    """
    anchor = make_record(
        "CAPEC-321", source="capec", label="AttackPattern", name="TCP Sequence Number Probe",
        properties={"description": "An adversary probes TCP sequence number assignment.",
                    "Status": "Stable"},
    )
    evidence = make_evidence([make_result(
        source="capec", text="CAPEC-321 (TCP Sequence Number Probe) — what does this involve?",
        records=[anchor], summary="Found 1 CAPEC record(s): CAPEC-321.",
    )])
    assert "probes TCP sequence number assignment" in _texts(_compose(evidence))


def test_a_multi_record_result_gets_no_description_claim():
    """37 techniques must not drag 37 descriptions into the answer."""
    records = [
        make_record(f"T10{i:02d}", name=f"tech {i}", properties={"description": f"desc {i}"})
        for i in range(5)
    ]
    evidence = make_evidence([make_result(
        text="Which techniques does G0082 use?", records=records, summary="Five techniques.",
    )])
    assert "desc 0" not in _texts(_compose(evidence))


def test_a_record_with_no_description_adds_no_claim():
    anchor = make_record("T1001", name="Data Obfuscation", properties={"revoked": False})
    evidence = make_evidence([make_result(
        text="What is T1001?", records=[anchor], summary="One record.")])
    before = len(_compose(evidence).claims)
    anchor2 = make_record("T1001", name="Data Obfuscation",
                          properties={"revoked": False, "description": "Adversaries obfuscate."})
    evidence2 = make_evidence([make_result(
        text="What is T1001?", records=[anchor2], summary="One record.")])
    assert len(_compose(evidence2).claims) == before + 1


def test_cross_references_in_a_description_lose_their_identifiers():
    """MITRE descriptions link to other entities; the URL carries an id.

    Emitting the raw markdown would put `T1136` into the answer text without it
    being in any claim's `entity_ids` and without the cited record grounding it —
    manufacturing the ungrounded-mention problem this claim exists to reduce.
    """
    anchor = make_record(
        "T1036.010", name="Masquerade Account Name",
        properties={"description": (
            "Accounts may be renamed during "
            "[Create Account](https://attack.mitre.org/techniques/T1136) operations."
        )},
    )
    evidence = make_evidence([make_result(
        text="What is T1036.010?", records=[anchor], summary="One record.")])
    text = _texts(_compose(evidence))
    assert "Create Account" in text
    assert "T1136" not in text
    assert "https://" not in text


def test_a_long_description_is_cut_at_a_sentence_boundary():
    body = ("First sentence here. " * 60).strip()
    anchor = make_record("T1001", name="X", properties={"description": body})
    evidence = make_evidence([make_result(
        text="What is T1001?", records=[anchor], summary="One record.")])
    claim = next(c for c in _compose(evidence).claims if "First sentence" in c.text)
    assert claim.text.rstrip().endswith(".")
    assert "…" not in claim.text
    assert len(claim.text) < 900


# -- the answer contract (EXP-2026-09-018 Step 4) ----------------------------


def test_a_list_valued_requested_property_reaches_a_claim() -> None:
    """``x_mitre_platforms`` is a list, and lists were dropped.

    ``_attribute_pairs`` skips list values on purpose — a generic listing of
    every list a record carries is noise. But the *requested* property is the
    answer. Two of the development half's exhibited failures are exactly this:
    the platforms of T1027.006 and the contributors of T1530 sat in the evidence
    and never reached a claim, and the narrator that would have said it anyway
    had timed out on 43% of the run.
    """
    from utils.synthesis.composer import _requested_property_claim

    record = make_record(
        "AN0307",
        label="Analytic",
        properties={"x_mitre_platforms": ["Linux", "Windows", "macOS"]},
    )
    result = make_result(records=[record])

    generic = [key for key, _ in _attribute_pairs(record)]
    assert "x_mitre_platforms" not in generic, "the generic listing still skips lists"

    claim = _requested_property_claim(result, record, "x_mitre_platforms")
    assert claim is not None
    for platform in ("Linux", "Windows", "macOS"):
        assert platform in claim.text
    assert claim.citations and claim.entity_ids == ("AN0307",)


def test_a_scalar_requested_property_also_reaches_a_claim() -> None:
    from utils.synthesis.composer import _requested_property_claim

    record = make_record("CAPEC-66", source="capec", label="AttackPattern",
                         properties={"Abstraction": "Standard"})
    claim = _requested_property_claim(make_result(source="capec", records=[record]),
                                      record, "Abstraction")
    assert claim is not None and "Standard" in claim.text


def test_a_missing_requested_property_produces_no_claim() -> None:
    """Nothing is invented: an absent value yields no claim at all."""
    from utils.synthesis.composer import _requested_property_claim

    record = make_record("T1055", properties={"name": "Process Injection"})
    assert _requested_property_claim(make_result(records=[record]), record,
                                     "x_mitre_platforms") is None


def test_an_enumeration_says_what_it_was_restricted_to() -> None:
    """A filtered set that reads as a complete one is worse than an unfiltered one.

    The reader has no way to tell. So the scope goes in the claim text beside
    the count it qualifies.
    """
    from utils.synthesis.composer import _enumeration_claim

    record = make_record(
        "G0006",
        label="Group",
        related=[{"id": "T1055", "label": "Technique", "type": "USES"},
                 {"id": "T1059", "label": "Technique", "type": "USES"}],
    )
    result = make_result(records=[record])

    plain = _enumeration_claim(result, record)
    assert "restricted to" not in plain.text

    scoped = _enumeration_claim(
        result, record, ("Technique", "x_mitre_platforms", "macOS")
    )
    assert "restricted to mitre platforms macOS" in scoped.text
    assert scoped.entity_ids == plain.entity_ids


def test_an_empty_requested_relation_is_stated_as_an_answer() -> None:
    """"CAPEC-513 has no execution steps" is a real answer, not a missing one.

    The composer used to list whatever else came back. The claim carries the
    executed query as its proof exactly as an abstention does, and the verifier
    admits it only when that query ran clean — see test_abstention.py.
    """
    from utils.synthesis.composer import _absence_claim

    record = make_record("CAPEC-513", source="capec", label="Category", related=[])
    claim = _absence_claim(make_result(source="capec", records=[record]),
                           "HAS_EXECUTION_STEP")

    assert claim.kind == "absence"
    assert "CAPEC-513" in claim.text and "no has execution step" in claim.text
    assert claim.citations
