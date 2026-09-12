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

    The *requested* property is the answer. Two of the development half's
    exhibited failures are exactly this: the platforms of T1027.006 and the
    contributors of T1530 sat in the evidence and never reached a claim, and the
    narrator that would have said it anyway had timed out on 43% of the run.

    This test used to also assert that the generic attribute listing still
    skipped lists, on the reasoning that listing every list a record carries is
    noise. That reasoning was wrong and cost whole questions: a group's
    ``aliases`` IS the answer to "what else is this group called", and the
    answer stated the group's ``revoked`` flag and not one of its names
    (`EXP-2026-09-018`, I-12). The generic listing now includes lists, after the
    scalars so nothing that fitted before is displaced.
    """
    from utils.synthesis.composer import _requested_property_claim

    record = make_record(
        "AN0307",
        label="Analytic",
        properties={"x_mitre_platforms": ["Linux", "Windows", "macOS"]},
    )
    result = make_result(records=[record])

    generic = dict(_attribute_pairs(record))
    assert generic["x_mitre_platforms"] == "Linux Windows macOS"

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
    # The scope line's warrant is the QUERY, not the records: a related
    # neighbour carries no properties, so a neighbour-side filter can never be
    # verified from the evidence the claim cites. A query that does not name the
    # property cannot have filtered on it.
    unfiltered = make_result(records=[record])
    filtered = make_result(
        records=[record],
        query="MATCH (n)-[:USES]->(m) WHERE $filterValue IN m.`x_mitre_platforms` RETURN m",
    )
    bound = ("Technique", "x_mitre_platforms", "macOS")

    plain = _enumeration_claim(unfiltered, record)
    assert "restricted to" not in plain.text

    # Asked for, but the query did not do it — so it is not stated.
    assert "restricted to" not in _enumeration_claim(unfiltered, record, bound).text

    scoped = _enumeration_claim(filtered, record, bound)
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
    # The identifier's own words, minus the verb the sentence already carries:
    # rendering it literally gave "has no has execution step".
    assert "CAPEC-513" in claim.text and "has no execution steps" in claim.text
    assert claim.citations


# -- nameless neighbours carry their text (EXP-2026-09-018, I-12) ------------


def test_a_nameless_neighbour_is_listed_by_its_text_not_its_internal_id():
    """A CAPEC prerequisite IS its text; its identifier is a path nobody publishes.

    The normalizer fills `name` from the node's id when the node has none, so a
    naive name check reads `capec:attack-pattern:94:prerequisite:1` as a title
    and lists it. That answered "what prerequisites does each of those require"
    with six opaque strings and not one prerequisite.
    """
    text = "An attacker can eavesdrop on the communication between the components."
    anchor = make_record(
        "CAPEC-271",
        name="Schema Poisoning",
        label="AttackPattern",
        related=[
            {"id": "CAPEC-94", "name": "Adversary in the Middle",
             "label": "AttackPattern", "description": "A different thing entirely."},
            {"id": "capec:attack-pattern:94:prerequisite:3",
             "name": "capec:attack-pattern:94:prerequisite:3",
             "label": "Prerequisite", "description": text},
            {"id": "capec:attack-pattern:28:step:1", "name": "Step 1",
             "label": "ExecutionStep", "description": "[Observe] The attacker observes."},
        ],
    )
    evidence = make_evidence(
        [make_result(
            text="Which patterns can precede CAPEC-271, and what prerequisites do those require?",
            records=[anchor], summary="Found 1 CAPEC record(s): CAPEC-271.")]
    )
    answer = _compose(evidence)
    enum = [c for c in answer.claims if c.kind == "enumeration"]
    # One claim per neighbour LABEL: a pattern, a prerequisite and an execution
    # step are three different kinds of thing and a single list could only call
    # them "related item(s)".
    assert len(enum) == 3
    assert any("attack pattern" in c.text for c in enum)
    body = " ".join(c.text for c in enum)
    assert text in body
    assert "[Observe] The attacker observes." in body
    # A published identifier is what an analyst looks up, so it survives…
    assert "CAPEC-94" in body
    # …and a synthetic path never reaches the reader.
    assert "prerequisite:3" not in body
    assert "step:1" not in body
    # The ids stay on the claims for auditing even when the prose shows text.
    assert any("capec:attack-pattern:94:prerequisite:3" in c.entity_ids for c in enum)


def test_a_false_attribute_is_stated_not_swallowed():
    """"Is T1052 a sub-technique?" is answered by the literal False.

    Flattening a value with ``value or ""`` turns ``False`` and ``0`` into the
    empty string, and an empty attribute is dropped — so the one property the
    question asked about vanished from the answer.
    """
    record = make_record(
        "T1052",
        name="Exfiltration Over Physical Medium",
        label="Technique",
        properties={"x_mitre_is_subtechnique": False, "revoked": False,
                    "x_mitre_version": "1.3"},
    )
    pairs = dict(_attribute_pairs(record))
    assert pairs["x_mitre_is_subtechnique"] == "False"
    assert pairs["revoked"] == "False"


def test_a_steps_position_and_phase_lead_its_text():
    """"1 Explore [Fingerprint the OS] …" — the catalogue prints all three.

    An answer carrying only the description cannot say which step of which phase
    it is quoting. Short scalars lead; a long one would be a second description
    and is left to its own claim.

    They lead in PROPERTY-NAME order, not the catalogue's print order. CAPEC
    prints "1 Explore"; this says "Explore 1". Encoding the print order would
    mean a per-label table of MITRE conventions inside a composer that is
    deliberately schema-driven, and it buys nothing: both carry the same two
    facts, and a reader and a grader see the step and the phase either way.
    """
    anchor = make_record(
        "CAPEC-126", name="Path Traversal", label="AttackPattern",
        related=[{
            "id": "capec:attack-pattern:126:step:1",
            "name": "Step 1", "label": "ExecutionStep",
            "step": "1", "phase": "Explore",
            "description": "[Fingerprint the OS] The attacker needs the file separator.",
        }],
    )
    evidence = make_evidence(
        [make_result(text="Through which execution steps is CAPEC-126 carried out?",
                     records=[anchor], summary="Found 1 CAPEC record(s).")]
    )
    body = [c for c in _compose(evidence).claims if c.kind == "enumeration"][0].text
    assert "Explore 1 [Fingerprint the OS] The attacker needs the file separator." in body


def test_a_node_whose_content_is_only_lists_states_all_of_them():
    """A CAPEC consequence has no description: it is its scopes and its impacts.

    The scopes arrive as a JSON-encoded string that flattens past any
    label-sized bound, so capping the lead deleted four of seven consequences
    from one answer. The cap applies only when a description follows it.
    """
    anchor = make_record(
        "CAPEC-248", name="Command Injection", label="AttackPattern",
        related=[{
            "id": "capec:attack-pattern:248:consequence:5",
            "name": "capec:attack-pattern:248:consequence:5",
            "label": "Consequence",
            "impacts": '["Gain Privileges"]',
            "scopes": '["Accountability", "Authentication", "Authorization", "Non-Repudiation"]',
        }],
    )
    evidence = make_evidence(
        [make_result(text="What consequences can CAPEC-248 have?",
                     records=[anchor], summary="Found 1 CAPEC record(s).")]
    )
    body = [c for c in _compose(evidence).claims if c.kind == "enumeration"][0].text
    for word in ("Gain Privileges", "Accountability", "Authentication",
                 "Authorization", "Non-Repudiation"):
        assert word in body
    assert "[" not in body and '"' not in body, "JSON punctuation must not reach the reader"


def test_a_sub_question_another_result_answered_is_not_abstained_on():
    """The iterative loop re-runs a hop; both attempts reach the composer.

    Abstaining on the empty attempt put "the executed query returned CAPEC-150
    with no linked records" into an answer that listed its seven weaknesses four
    sentences earlier, and the grader recorded the contradiction as a
    hallucination (`EXP-2026-09-018`, I-14).
    """
    text = "For each of those: the CWE weaknesses each of those exploits."
    empty = make_result(text=text, records=[], summary="No CAPEC records found.")
    empty.query = "g.V().has('id', within(ids))"
    filled = make_result(
        text=text,
        records=[make_record("CAPEC-150", name="Collect Data", label="AttackPattern",
                             related=[{"id": "CWE-552", "name": "Files or Directories",
                                       "label": "Weakness"}])],
        summary="Found 1 CAPEC record(s): CAPEC-150.",
    )
    answer = _compose(make_evidence([empty, filled]))
    assert answer.abstentions == []
    assert any("CWE-552" in c.text for c in answer.claims)

    # A sub-question NOTHING answered still abstains, honestly.
    only_empty = _compose(make_evidence([empty]))
    assert len(only_empty.abstentions) == 1


def test_text_items_are_not_listed_as_though_they_were_identifiers():
    """A two-leg walk returns patterns AND consequences in one flat related set.

    A single claim over both could only call them "related item(s)" and had to
    list `CAPEC-182` beside `Other Confidentiality` as though the two were the
    same kind of thing — which the grader read literally, recording the
    consequence text as an invented identifier in three answers. One claim per
    neighbour label, and text items separated by semicolons so a multi-word one
    stays legible as a single item.
    """
    anchor = make_record(
        "CAPEC-248", name="Command Injection", label="AttackPattern",
        related=[
            {"id": "CAPEC-182", "name": "Flash Injection", "label": "AttackPattern",
             "type": "CAN_ALSO_BE"},
            {"id": "capec:attack-pattern:248:consequence:1",
             "name": "capec:attack-pattern:248:consequence:1", "label": "Consequence",
             "type": "HAS_CONSEQUENCE",
             "impacts": '["Modify Data"]', "scopes": '["Integrity"]'},
            {"id": "capec:attack-pattern:248:consequence:2",
             "name": "capec:attack-pattern:248:consequence:2", "label": "Consequence",
             "type": "HAS_CONSEQUENCE",
             "impacts": '["Read Data"]', "scopes": '["Confidentiality"]'},
        ],
    )
    evidence = make_evidence(
        [make_result(text="What consequences can CAPEC-248 have?", records=[anchor],
                     summary="Found 1 CAPEC record(s).")]
    )
    enum = [c for c in _compose(evidence).claims if c.kind == "enumeration"]
    assert len(enum) == 2
    patterns = next(c for c in enum if "CAPEC-182" in c.text)
    consequences = next(c for c in enum if c is not patterns)
    assert "related item" not in patterns.text and "related item" not in consequences.text
    assert "CAPEC-182" not in consequences.text
    assert "; " in consequences.text, "multi-word items are semicolon-separated"


# -- I-16: an absence is judged against the edge the store resolved ----------


def test_a_views_members_are_not_denied_because_the_question_said_member_of():
    """CAPEC-703 is a View; its members hang off ``IN_VIEW``, never ``MEMBER_OF``.

    The bank asks for containment as ``HAS_MEMBER``, the planner resolves it to
    ``MEMBER_OF``, and the graph stores a View's membership as ``IN_VIEW``. The
    composer used to look for related entries typed with the *question's* name,
    find none, and write "CAPEC-703 has no MEMBER_OF relationships" directly
    beneath the fifteen members it had just enumerated — a false statement with
    full provenance, which is the worst thing this system can emit.
    """
    from utils.synthesis.composer import _relation_is_empty

    view = make_record(
        "CAPEC-703",
        name="Industrial Control System (ICS) Patterns",
        source="capec",
        label="View",
        related=[
            {"id": "CAPEC-438", "label": "AttackPattern", "type": "IN_VIEW"},
            {"id": "CAPEC-439", "label": "AttackPattern", "type": "IN_VIEW"},
        ],
    )
    result = make_result(
        source="capec",
        records=[view],
        query='g.V().has("id", within(ids)).in("IN_VIEW").elementMap()',
    )
    # Every alias of containment, from either vocabulary.
    for asked in ("MEMBER_OF", "HAS_MEMBER", "IN_VIEW"):
        assert not _relation_is_empty(result, asked), asked


def test_a_genuinely_absent_relation_is_still_stated():
    """The suppression is one-way: ``MITIGATES`` on a Campaign is really absent.

    "Which techniques does C0046 mitigate" walks the campaign's ``USES`` edge
    because ``MITIGATES`` is not a Campaign facet at all, and the answer must
    say so rather than quietly enumerate what it did find. Folding containment
    aliases must not fold two relations that merely happen to co-occur.
    """
    from utils.synthesis.composer import _relation_is_empty

    campaign = make_record(
        "C0046",
        name="ArcaneDoor",
        label="Campaign",
        related=[
            {"id": "T1556", "label": "Technique", "type": "USES"},
            {"id": "S1188", "label": "Software", "type": "USES"},
        ],
    )
    result = make_result(records=[campaign], query="MATCH (n)-[:USES]->(m) RETURN m")
    assert _relation_is_empty(result, "MITIGATES")


def test_an_absence_never_contradicts_the_noun_the_answer_enumerates():
    """"T1518 has no tactics" sat beneath "T1518 has 1 tactic: TA0007".

    ``Tactic -[HAS_TECHNIQUE]-> Technique`` is the same relation the question
    named as ``HAS_TACTIC``, read from the other end, so no amount of edge-name
    folding reconciles the two. What does reconcile them is the answer's own
    words: the enumeration about to be written calls these neighbours by the
    very noun the absence is about to deny.
    """
    from utils.synthesis.composer import _relation_is_empty

    technique = make_record(
        "T1518",
        name="Software Discovery",
        label="Technique",
        related=[{"id": "TA0007", "label": "Tactic", "type": "HAS_TECHNIQUE"}],
    )
    result = make_result(
        records=[technique],
        query="MATCH (n)<-[:HAS_TECHNIQUE]-(m) RETURN m",
    )
    assert not _relation_is_empty(result, "HAS_TACTIC")


def test_a_facet_count_is_read_through_the_alias_too():
    """``describe`` answers with counts, not neighbours — and counts alias too.

    A View asked for its ``MEMBER_OF`` members through ``describe`` gets back a
    facet saying ``IN_VIEW: 15`` and no materialised neighbours at all. Reading
    that as "no MEMBER_OF facet, and none materialised" asserts an absence over
    a measured fifteen, so both the warrant and the suppression fold the alias.
    """
    from utils.synthesis.composer import _facet_counts_zero, _relation_is_empty

    view = make_record(
        "CAPEC-1000",
        name="Mechanisms of Attack",
        source="capec",
        label="View",
        related=[],
        facets=[{"rel": "IN_VIEW", "count": 15}],
    )
    populated = make_result(source="capec", records=[view], query="describe CAPEC-1000")
    assert not _facet_counts_zero(populated, "MEMBER_OF")
    assert not _relation_is_empty(populated, "MEMBER_OF")

    # A measured zero on the resolved edge still warrants the claim.
    empty_view = make_record(
        "CAPEC-1000",
        source="capec",
        label="View",
        related=[],
        facets=[{"rel": "IN_VIEW", "count": 0}],
    )
    measured = make_result(
        source="capec", records=[empty_view], query="describe CAPEC-1000"
    )
    assert _facet_counts_zero(measured, "MEMBER_OF")
    assert _relation_is_empty(measured, "MEMBER_OF")


def test_synthesis_and_the_builder_share_one_record_of_containment():
    """The alias list is imported, never restated — this is the guard on that."""
    from utils.specialists.gremlin.builder import MEMBERSHIP_ALIASES
    from utils.synthesis.composer import _normalise_rel, _relation_aliases

    folded = frozenset(_normalise_rel(name) for name in MEMBERSHIP_ALIASES)
    for name in MEMBERSHIP_ALIASES:
        assert _relation_aliases(name) == folded
    # A relation outside the class folds to itself and nothing else.
    assert _relation_aliases("MITIGATES") == frozenset({"MITIGATES"})
