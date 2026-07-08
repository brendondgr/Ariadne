#!/usr/bin/env python3
"""The prose narrator: stubbed HTTP, prompt shape, and best-effort wiring.

No network: ``requests.post`` is stubbed. The narrator asks for a few sentences
of plain prose (not the claims JSON), so it stays reliable where the full claims
call truncates; on failure the deterministic narrative is kept.
"""

from __future__ import annotations

import pytest

from utils.synthesis.composer import DeterministicComposer
from utils.synthesis.config import SynthesisConfig
from utils.synthesis.factory import synthesize
from utils.synthesis.llm_composer import ComposerUnavailable
from utils.synthesis.narrator import build_narrator_messages, compose_narrative

from ._fixtures import make_evidence, make_record, make_result


def _evidence():
    attack = make_result(
        records=[make_record("T1047", name="WMI", join_values=("T1047",))],
        summary="One technique.",
    )
    return make_evidence([attack])


def _text_response(text: str) -> object:
    class _Resp:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": text}}]}

    return _Resp()


def _stub_post(monkeypatch, response=None, exc=None):
    calls: list[dict] = []

    def fake_post(url, json=None, timeout=None):  # noqa: A002 - requests API shape
        calls.append({"url": url, "payload": json})
        if exc is not None:
            raise exc
        return response

    monkeypatch.setattr("requests.post", fake_post)
    return calls


def test_narrator_prompt_asks_for_prose_not_json():
    messages = build_narrator_messages(_evidence())
    system = messages[0]["content"]
    assert messages[0]["role"] == "system"
    assert "No JSON" in system and "sentences" in system
    # The evidence framing is shared with the claims composer.
    assert "ANALYST REQUEST" in messages[1]["content"]


def test_compose_narrative_returns_stripped_prose(monkeypatch):
    calls = _stub_post(monkeypatch, response=_text_response("  T1047 is WMI.\n"))
    text = compose_narrative(_evidence(), SynthesisConfig())
    assert text == "T1047 is WMI."
    assert calls[0]["url"].endswith("/chat/completions")


def test_compose_narrative_empty_content_raises(monkeypatch):
    _stub_post(monkeypatch, response=_text_response("   "))
    with pytest.raises(ComposerUnavailable, match="no content"):
        compose_narrative(_evidence(), SynthesisConfig())


def test_synthesize_applies_llm_narrative_when_enabled(monkeypatch):
    _stub_post(monkeypatch, response=_text_response("A clear natural-language answer."))
    answer = synthesize(_evidence(), SynthesisConfig(llm_enabled=True))
    assert answer.narrative == "A clear natural-language answer."


def test_synthesize_keeps_deterministic_narrative_when_llm_off(monkeypatch):
    # LLM disabled → narrator never runs → the deterministic narrative stands.
    def boom(*a, **k):  # pragma: no cover - must not be called
        raise AssertionError("narrator must not call the LLM when disabled")

    monkeypatch.setattr("requests.post", boom)
    answer = synthesize(_evidence(), SynthesisConfig())
    assert answer.narrative == "One technique."
    assert answer.composer == "deterministic"


def test_synthesize_falls_back_to_deterministic_narrative_on_narrator_failure(monkeypatch):
    import requests

    _stub_post(monkeypatch, exc=requests.ConnectionError("refused"))
    # Inject a deterministic claims composer so only the narrator's call fails.
    answer = synthesize(
        _evidence(),
        SynthesisConfig(llm_enabled=True),
        composer=DeterministicComposer(SynthesisConfig()),
    )
    assert answer.narrative == "One technique."  # deterministic narrative preserved
    assert "narrator unavailable" in (answer.fallback_reason or "").lower()
