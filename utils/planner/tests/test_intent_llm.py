#!/usr/bin/env python3
"""Tests for the LLM intent classifier and the hybrid fallback.

No live HTTP: the OpenAI-compatible POST is monkeypatched, mirroring
``test_llm_drafter.py``. Proves a valid completion parses, every failure mode
raises ``ClassifierUnavailable``, and the hybrid degrades to the deterministic
label (tagged ``source="fallback"``).
"""

from __future__ import annotations

import json

import pytest

from utils.planner.config import PlannerConfig
from utils.planner.intent import DeterministicIntentClassifier, Intent
from utils.planner.intent_llm import (
    ClassifierUnavailable,
    HybridIntentClassifier,
    LLMIntentClassifier,
    select_intent_classifier,
)

DEMO = "Which CAPEC patterns map to ATT&CK techniques?"


class FakeResponse:
    def __init__(self, status_code: int, body: dict | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._body = body
        self.text = text

    def json(self) -> dict:
        if self._body is None:
            raise ValueError("no json")
        return self._body


def _completion(content: str) -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


def _patch_post(monkeypatch, response) -> None:
    import requests

    def fake_post(url, json=None, timeout=None):  # noqa: A002 - mirror requests API
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(requests, "post", fake_post)


def _clf() -> LLMIntentClassifier:
    return LLMIntentClassifier(PlannerConfig(data_dir="data"))


def test_classify_parses_valid_completion(monkeypatch) -> None:
    body = {"label": "correlation", "confidence": 0.92, "rationale": "cross-source", "cues": ["map to"]}
    _patch_post(monkeypatch, FakeResponse(200, _completion(json.dumps(body))))
    result = _clf().classify(DEMO)
    assert result.label == Intent.CORRELATION
    assert result.source == "llm"
    assert result.confidence == pytest.approx(0.92)
    assert result.cues == ["map to"]


def test_classify_clamps_out_of_range_confidence(monkeypatch) -> None:
    body = {"label": "lookup", "confidence": 5.0, "rationale": "", "cues": []}
    _patch_post(monkeypatch, FakeResponse(200, _completion(json.dumps(body))))
    assert _clf().classify(DEMO).confidence == 1.0


def test_classify_rejects_out_of_taxonomy_label(monkeypatch) -> None:
    body = {"label": "banana", "confidence": 0.9}
    _patch_post(monkeypatch, FakeResponse(200, _completion(json.dumps(body))))
    with pytest.raises(ClassifierUnavailable):
        _clf().classify(DEMO)


def test_classify_transport_error_raises(monkeypatch) -> None:
    import requests

    _patch_post(monkeypatch, requests.RequestException("refused"))
    with pytest.raises(ClassifierUnavailable):
        _clf().classify(DEMO)


def test_classify_http_error_raises(monkeypatch) -> None:
    _patch_post(monkeypatch, FakeResponse(500, None, text="boom"))
    with pytest.raises(ClassifierUnavailable):
        _clf().classify(DEMO)


def test_classify_empty_content_raises(monkeypatch) -> None:
    _patch_post(monkeypatch, FakeResponse(200, _completion("")))
    with pytest.raises(ClassifierUnavailable):
        _clf().classify(DEMO)


class _AlwaysFail:
    def classify(self, request, cards=None):
        raise ClassifierUnavailable("down")


def test_hybrid_falls_back_to_deterministic_and_tags_source() -> None:
    hybrid = HybridIntentClassifier(_AlwaysFail(), DeterministicIntentClassifier())
    result = hybrid.classify(DEMO)
    assert result.label == Intent.CORRELATION  # deterministic still classifies it
    assert result.source == "fallback"  # but the source is marked as the fallback
    assert hybrid.last_used == "DeterministicIntentClassifier"


def test_factory_returns_deterministic_when_llm_disabled() -> None:
    clf = select_intent_classifier(PlannerConfig(data_dir="data", intent_llm_enabled=False))
    assert isinstance(clf, DeterministicIntentClassifier)


def test_factory_returns_hybrid_when_llm_enabled() -> None:
    clf = select_intent_classifier(PlannerConfig(data_dir="data", intent_llm_enabled=True))
    assert isinstance(clf, HybridIntentClassifier)
