#!/usr/bin/env python3
"""The never-raise contract, the three empty states, and what a probe proves.

These pin behaviour the UI depends on: discovery is called on a UI event and
must return a renderable result for every failure a settings modal can provoke,
and the Test button must not pass against a server that answers but cannot
complete anything.
"""

from __future__ import annotations

import requests

from utils.llm.client import discover_models, probe, sort_models
from utils.llm.config import LLMProvider, LLMSettings
from utils.llm.types import EMPTY, NO_LISTING, UNREACHABLE, ModelInfo

LOCAL = LLMSettings(base_url="http://localhost:9090/v1", model="default-model")


class FakeResponse:
    def __init__(self, status_code=200, body=None, text=""):
        self.status_code = status_code
        self._body = body
        self.text = text

    def json(self):
        if self._body is None:
            raise ValueError("not JSON")
        return self._body


def patch_get(monkeypatch, result):
    def fake_get(url, **kwargs):
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(requests, "get", fake_get)


def patch_post(monkeypatch, result):
    def fake_post(url, **kwargs):
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(requests, "post", fake_post)


# --------------------------------------------------------------------------- #
# Discovery never raises, and distinguishes its empty states
# --------------------------------------------------------------------------- #


def test_a_dead_server_is_a_result_not_an_exception(monkeypatch):
    """Someone's GPU box being off is a normal state, not a fault of ours."""
    patch_get(monkeypatch, requests.ConnectionError("connection refused"))
    result = discover_models(LOCAL)
    assert result.ok is False
    assert result.state == UNREACHABLE
    assert "localhost:9090" in result.reason
    assert result.models == []


def test_a_reachable_server_with_nothing_pulled_is_not_an_error(monkeypatch):
    patch_get(monkeypatch, FakeResponse(body={"data": []}))
    result = discover_models(LOCAL)
    assert result.ok is True
    assert result.state == EMPTY
    assert "no models" in result.reason


def test_a_gateway_without_a_listing_endpoint_says_so(monkeypatch):
    """404 on /models means type the name by hand, not that the server is down."""
    patch_get(monkeypatch, FakeResponse(status_code=404, text="not found"))
    result = discover_models(LOCAL)
    assert result.ok is True
    assert result.state == NO_LISTING
    assert "manually" in result.reason


def test_bad_credentials_are_reported_as_such(monkeypatch):
    patch_get(monkeypatch, FakeResponse(status_code=401, text="unauthorized"))
    result = discover_models(LLMSettings(provider=LLMProvider.OPENAI, api_key="bad"))
    assert result.ok is False
    assert "credentials" in result.reason


def test_a_non_json_listing_does_not_raise(monkeypatch):
    patch_get(monkeypatch, FakeResponse(body=None, text="<html>proxy error</html>"))
    result = discover_models(LOCAL)
    assert result.state == NO_LISTING


def test_a_listing_of_the_wrong_shape_does_not_raise(monkeypatch):
    patch_get(monkeypatch, FakeResponse(body=["not", "a", "dict"]))
    assert discover_models(LOCAL).state == NO_LISTING


def test_a_successful_listing_returns_sorted_models(monkeypatch):
    patch_get(
        monkeypatch,
        FakeResponse(body={"data": [{"id": "zebra"}, {"id": "text-embedding-3"}, {"id": "alpha"}]}),
    )
    result = discover_models(LOCAL)
    assert result.ok is True
    assert result.state == ""
    assert [m.id for m in result.models] == ["alpha", "zebra", "text-embedding-3"]


def test_embedding_models_sort_last_so_one_never_becomes_the_default():
    ordered = sort_models([ModelInfo(id="text-embedding-3"), ModelInfo(id="qwen3")])
    assert ordered[0].id == "qwen3"


# --------------------------------------------------------------------------- #
# The probe proves an answer, not a socket
# --------------------------------------------------------------------------- #


def test_probe_passes_only_on_real_content(monkeypatch):
    patch_post(
        monkeypatch,
        FakeResponse(
            body={
                "model": "qwen38-27B-v2",
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 9, "completion_tokens": 1, "total_tokens": 10},
            }
        ),
    )
    result = probe(LOCAL)
    assert result.ok is True
    assert result.model == "qwen38-27B-v2"
    assert "answered in" in result.summary


def test_probe_fails_on_a_server_that_is_still_loading_weights(monkeypatch):
    """The 2026-09-05 case: port open, ten replies, no choices key at all.

    A TCP check and a /models call both pass here, which is why neither is the
    connection test.
    """
    patch_post(monkeypatch, FakeResponse(body={"id": "x", "object": "chat.completion"}))
    result = probe(LOCAL)
    assert result.ok is False
    assert "no content" in result.reason


def test_probe_fails_when_a_reasoning_model_spends_the_whole_budget(monkeypatch):
    patch_post(
        monkeypatch,
        FakeResponse(
            body={
                "choices": [{"message": {"content": None}, "finish_reason": "length"}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 256, "total_tokens": 276},
            }
        ),
    )
    result = probe(LOCAL)
    assert result.ok is False
    assert "finish_reason=length" in result.reason


def test_probe_reports_an_http_error_verbatim(monkeypatch):
    patch_post(monkeypatch, FakeResponse(status_code=404, text='{"error":"model not found"}'))
    result = probe(LOCAL)
    assert result.ok is False
    assert "model not found" in result.reason, "the actionable part must survive"


def test_probe_never_raises_on_a_transport_failure(monkeypatch):
    patch_post(monkeypatch, requests.Timeout("timed out"))
    result = probe(LOCAL)
    assert result.ok is False
    assert "timed out" in result.reason


def test_probe_asks_for_a_budget_a_reasoning_model_can_answer_within(monkeypatch):
    """Too small a cap truncates to empty, which reads as an outage."""
    seen = {}

    def fake_post(url, **kwargs):
        seen.update(kwargs["json"])
        return FakeResponse(body={"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr(requests, "post", fake_post)
    probe(LLMSettings(max_tokens=4, model="m"))
    assert seen["max_tokens"] >= 64


def test_connect_and_read_timeouts_are_separate_numbers(monkeypatch):
    """A dead server must fail in seconds while real generation runs for minutes.

    One value cannot be both, and this codebase has already lost a run to a clock
    that cut off the reasoning a raised token budget was meant to allow.
    """
    seen = {}

    def fake_post(url, **kwargs):
        seen["timeout"] = kwargs["timeout"]
        return FakeResponse(body={"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr(requests, "post", fake_post)
    from utils.llm.client import chat
    from utils.llm.types import Message

    chat(LLMSettings(connect_timeout_s=2.0, timeout_s=900.0, model="m"), [Message.user("hi")])
    connect, read = seen["timeout"]
    assert connect == 2.0
    assert read == 900.0
    assert connect < read


def test_discovery_uses_a_short_read_budget_because_it_runs_on_a_click(monkeypatch):
    seen = {}

    def fake_get(url, **kwargs):
        seen["timeout"] = kwargs["timeout"]
        return FakeResponse(body={"data": []})

    monkeypatch.setattr(requests, "get", fake_get)
    discover_models(LLMSettings(timeout_s=900.0, model="m"))
    _, read = seen["timeout"]
    assert read < 900.0, "a settings modal must not hang for the generation timeout"
