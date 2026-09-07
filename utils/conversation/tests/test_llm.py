#!/usr/bin/env python3
"""Tests for the shared conversation LLM client — truncation signal handling.

No network: ``requests.post`` is stubbed with an OpenAI-compatible response
shape carrying ``finish_reason`` and ``usage``, so the truncation-detection path
is exercised deterministically.
"""

from __future__ import annotations

import logging

import pytest

from utils.conversation.config import ConversationLLMConfig
from utils.conversation.llm import ConversationLLM, LLMUnavailable


def _cfg(**over) -> ConversationLLMConfig:
    base = dict(enabled=True, base_url="http://llm/v1", model="m", max_tokens=100)
    base.update(over)
    return ConversationLLMConfig(**base)


def _response(content, *, finish_reason="stop", usage=None, status=200):
    class _Resp:
        status_code = status
        text = "err"

        def json(self):
            return {
                "choices": [
                    {"message": {"content": content}, "finish_reason": finish_reason}
                ],
                "usage": usage or {"prompt_tokens": 10, "completion_tokens": 5},
            }

    return _Resp()


def _stub_post(monkeypatch, response=None, exc=None):
    calls: list[dict] = []

    # **kwargs because the shared transport in utils.llm.client sends `headers`
    # (an Authorization only materializes when a key is configured) and a
    # (connect, read) timeout tuple. The stand-in must accept what the real
    # requests.post accepts, or a signature mismatch reads as a transport bug.
    def fake_post(url, json=None, timeout=None, **kwargs):  # noqa: A002 - requests API shape
        calls.append({"url": url, "payload": json})
        if exc is not None:
            raise exc
        return response

    monkeypatch.setattr("requests.post", fake_post)
    return calls


def test_complete_verbose_returns_content_and_reason(monkeypatch):
    calls = _stub_post(monkeypatch, response=_response("hello", finish_reason="stop"))
    result = ConversationLLM(_cfg()).complete_verbose([{"role": "user", "content": "x"}])
    assert result.content == "hello"
    assert result.finish_reason == "stop"
    assert result.truncated is False
    assert result.usage["prompt_tokens"] == 10
    assert calls[0]["url"].endswith("/chat/completions")
    assert calls[0]["payload"]["max_tokens"] == 100


def test_complete_verbose_flags_truncation_and_keeps_partial(monkeypatch, caplog):
    partial = "This is generally achieved through two methods: Disk Content Wipe"
    _stub_post(
        monkeypatch,
        response=_response(
            partial,
            finish_reason="length",
            usage={"prompt_tokens": 3900, "completion_tokens": 60},
        ),
    )
    with caplog.at_level(logging.WARNING, logger="ariadne.conversation.llm"):
        result = ConversationLLM(_cfg()).complete_verbose([{"role": "user", "content": "x"}])
    # Verbose does NOT raise on a truncation — the partial is returned + flagged.
    assert result.content == partial
    assert result.truncated is True
    assert "truncated" in caplog.text and "prompt_tokens=3900" in caplog.text


def test_complete_verbose_null_content_on_length_normalizes_to_empty(monkeypatch):
    # Some servers return null content when the whole budget is spent before any
    # visible token — normalize to "" but still flag the truncation.
    _stub_post(monkeypatch, response=_response(None, finish_reason="length"))
    result = ConversationLLM(_cfg()).complete_verbose([{"role": "user", "content": "x"}])
    assert result.content == ""
    assert result.truncated is True


def test_complete_returns_content(monkeypatch):
    _stub_post(monkeypatch, response=_response("answer", finish_reason="stop"))
    assert ConversationLLM(_cfg()).complete([{"role": "user", "content": "x"}]) == "answer"


def test_complete_raises_truncation_message_when_empty_length(monkeypatch):
    _stub_post(monkeypatch, response=_response(None, finish_reason="length"))
    with pytest.raises(LLMUnavailable, match="truncated"):
        ConversationLLM(_cfg()).complete([{"role": "user", "content": "x"}])


def test_complete_raises_no_content_when_empty_non_length(monkeypatch):
    _stub_post(monkeypatch, response=_response("", finish_reason="stop"))
    with pytest.raises(LLMUnavailable, match="no content"):
        ConversationLLM(_cfg()).complete([{"role": "user", "content": "x"}])


def test_disabled_client_raises(monkeypatch):
    _stub_post(monkeypatch, response=_response("x"))
    with pytest.raises(LLMUnavailable, match="disabled"):
        ConversationLLM(_cfg(enabled=False)).complete_verbose([{"role": "user", "content": "x"}])


def test_http_error_raises(monkeypatch):
    _stub_post(monkeypatch, response=_response("x", status=500))
    with pytest.raises(LLMUnavailable, match="HTTP 500"):
        ConversationLLM(_cfg()).complete_verbose([{"role": "user", "content": "x"}])


def test_request_exception_raises(monkeypatch):
    import requests

    _stub_post(monkeypatch, exc=requests.ConnectionError("refused"))
    # The shared transport names the provider and the unreachable host instead
    # of "request failed", and carries the cause verbatim. Assert the cause.
    with pytest.raises(LLMUnavailable, match="refused"):
        ConversationLLM(_cfg()).complete_verbose([{"role": "user", "content": "x"}])
