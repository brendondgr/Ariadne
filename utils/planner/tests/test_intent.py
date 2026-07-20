#!/usr/bin/env python3
"""Tests for the deterministic intent classifier (planner step one).

Pins the taxonomy behaviour and its priority order: every label is reachable,
the cross-source cue outranks remediation/enumeration, and the card-aware
fallback separates a weak lookup from an honest ``unsupported``.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from utils.planner.intent import (
    DeterministicIntentClassifier,
    Intent,
    IntentClassification,
    is_definitional_request,
    is_enumerative_request,
)


@pytest.fixture
def clf() -> DeterministicIntentClassifier:
    return DeterministicIntentClassifier()


def _card(labels: list[str], rels: list[str]) -> SimpleNamespace:
    """Minimal stand-in for SourceCardView (the classifier reads only these)."""
    return SimpleNamespace(node_labels=labels, relationship_types=rels)


@pytest.mark.parametrize(
    "request_text, expected",
    [
        ("Which CAPEC patterns map to ATT&CK techniques?", Intent.CORRELATION),
        ("How do CAPEC attack patterns relate to ATT&CK?", Intent.CORRELATION),
        ("What mitigations apply to T1555?", Intent.REMEDIATION),
        ("What is the parent of CAPEC-560?", Intent.TRAVERSAL),
        ("List all techniques that use valid accounts", Intent.ENUMERATION),
        ("What is Phishing?", Intent.DEFINITIONAL),
        ("Define User Training", Intent.DEFINITIONAL),
        ("Show the properties of T1555", Intent.LOOKUP),
    ],
)
def test_each_label_is_reachable(clf, request_text, expected):
    result = clf.classify(request_text)
    assert result.label == expected
    assert Intent.is_valid(result.label)
    assert 0.0 <= result.confidence <= 1.0


def test_correlation_outranks_remediation_and_enumeration(clf):
    # A request that carries correlation + remediation + enumeration cues must
    # read as the cross-source intent (the most specific / load-bearing one).
    result = clf.classify(
        "List which CAPEC patterns map to ATT&CK techniques and their mitigations"
    )
    assert result.label == Intent.CORRELATION
    assert result.cues  # the matched phrases are surfaced for the UI


def test_remediation_outranks_bare_id_lookup(clf):
    result = clf.classify("What mitigations apply to T1555?")
    assert result.label == Intent.REMEDIATION


def test_definitional_reuses_specialist_heuristic(clf):
    assert clf.classify("What exactly is credential dumping?").label == Intent.DEFINITIONAL


def test_capec_attack_pattern_wording_is_not_correlation(clf):
    # "attack pattern" is CAPEC terminology; a CAPEC-internal question must NOT
    # be flagged cross-source just because it contains the word "attack".
    result = clf.classify("Which CWE weaknesses do CAPEC attack patterns exploit?")
    assert result.label != Intent.CORRELATION


def test_fallback_lookup_when_vocabulary_matches(clf):
    card = _card(["Technique", "Mitigation"], ["MITIGATES"])
    result = clf.classify("anything about a technique", {"attack": card})
    assert result.label == Intent.LOOKUP
    assert result.confidence < 0.6  # a weak, low-confidence guess


def test_fallback_unsupported_when_no_vocabulary_matches(clf):
    card = _card(["Technique", "Mitigation"], ["MITIGATES"])
    # No cue fires (no "what is" / list / id / relationship word) and the
    # vocabulary is off-domain, so it is honestly out of scope.
    result = clf.classify("the weather in Tallahassee today", {"attack": card})
    assert result.label == Intent.UNSUPPORTED


def test_fallback_lookup_without_cards(clf):
    # No cards to check vocabulary against: default to a low-confidence lookup,
    # never a guessed unsupported.
    result = clf.classify("some opaque phrase with no cue")
    assert result.label == Intent.LOOKUP
    assert result.source == "deterministic"


def test_classification_round_trips_through_dict():
    original = IntentClassification(
        Intent.CORRELATION, 0.9, "cross-source", ["map to"], "deterministic"
    )
    restored = IntentClassification.from_dict(original.to_dict())
    assert restored == original


def test_from_dict_none_is_none():
    assert IntentClassification.from_dict(None) is None
    assert IntentClassification.from_dict({}) is None


def test_is_definitional_request_recognises_what_is_and_describe():
    # Moved here from the specialists' resolve tests once describe made the
    # specialist-side intent gating obsolete.
    assert is_definitional_request("What is User Training?")
    assert is_definitional_request("What are the phishing mitigations?")
    assert is_definitional_request("what's Data Backup")
    assert is_definitional_request("Define Software Configuration")
    assert is_definitional_request("Tell me about M1049")
    # Non-definitional retrieval questions must stay out of the name path.
    assert not is_definitional_request("Which mitigations apply to T1047?")
    assert not is_definitional_request("How do you detect phishing?")


def test_is_enumerative_request_recognises_which_and_what_plural():
    # "which/list" keyword arm and the "what <plural relationship-noun>" arm.
    assert is_enumerative_request("Which techniques does software S0266 use?")
    assert is_enumerative_request("What mitigations does ATT&CK list for T1003?")
    assert is_enumerative_request("What consequences does CAPEC-66 have?")
    assert is_enumerative_request("What are the execution steps of CAPEC-66?")
    assert is_enumerative_request("list all sub-techniques of T1055")
    assert is_enumerative_request(
        "Walk the abstraction hierarchy up from CAPEC-7: what are its standard and meta ancestors?"
    )
    # A bare-id definitional lookup must NOT read as enumerative — the entity
    # type word (capec/cwe) in the id is deliberately not a relationship noun.
    assert not is_enumerative_request("What abstraction level is CAPEC-555?")
    assert not is_enumerative_request("What is the status of CAPEC-98?")
    assert not is_enumerative_request("What is T1003?")
    assert not is_enumerative_request("Describe CAPEC-98.")
