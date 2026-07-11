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
