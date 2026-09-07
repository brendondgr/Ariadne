"""Contract tests for /api/llm/models and /api/llm/test.

Two invariants the settings modal depends on:

  * **Neither route ever 5xxs on a bad endpoint.** An unreachable local server is
    a normal operating state, not a fault of this service. A settings page that
    shows an error banner when someone's GPU box is off trains people to ignore
    banners.
  * **Both accept unsaved values.** A Refresh that only works after Save is the
    same "spell the model name exactly right" problem in a new place.
"""

from __future__ import annotations

import pytest
import requests
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


class FakeResponse:
    def __init__(self, status_code=200, body=None, text=""):
        self.status_code = status_code
        self._body = body
        self.text = text

    def json(self):
        if self._body is None:
            raise ValueError("not JSON")
        return self._body


@pytest.fixture
def offline(monkeypatch):
    """Refuse every outbound call, so a test can never reach a real endpoint."""
    def refuse(*args, **kwargs):
        raise requests.ConnectionError("connection refused")

    monkeypatch.setattr(requests, "get", refuse)
    monkeypatch.setattr(requests, "post", refuse)


# --------------------------------------------------------------------------- #
# Discovery
# --------------------------------------------------------------------------- #


def test_unreachable_endpoint_is_200_with_ok_false(offline) -> None:
    resp = client.post("/api/llm/models", json={"base_url": "http://localhost:1/v1"})
    assert resp.status_code == 200, "someone's GPU box being off is not a server error"
    body = resp.json()
    assert body["ok"] is False
    assert body["state"] == "unreachable"
    assert body["reason"]
    assert body["models"] == []


def test_discovery_lists_what_the_server_serves(monkeypatch) -> None:
    monkeypatch.setattr(
        requests,
        "get",
        lambda url, **kw: FakeResponse(
            body={"data": [{"id": "qwen38-27B-v2", "max_model_len": 32768}, {"id": "alpha"}]}
        ),
    )
    body = client.post("/api/llm/models", json={"base_url": "http://gpu:8000/v1"}).json()
    assert body["ok"] is True
    assert [m["id"] for m in body["models"]] == ["alpha", "qwen38-27B-v2"]
    assert "32K ctx" in [m["label"] for m in body["models"]][1]


def test_discovery_targets_the_unsaved_url_not_the_stored_one(monkeypatch) -> None:
    """Refresh must work on a URL the operator typed but has not saved."""
    seen = {}

    def fake_get(url, **kwargs):
        seen["url"] = url
        return FakeResponse(body={"data": []})

    monkeypatch.setattr(requests, "get", fake_get)
    client.post("/api/llm/models", json={"base_url": "http://typed-just-now:1234/v1"})
    assert seen["url"].startswith("http://typed-just-now:1234/v1")


def test_reachable_but_empty_is_its_own_state(monkeypatch) -> None:
    monkeypatch.setattr(requests, "get", lambda url, **kw: FakeResponse(body={"data": []}))
    body = client.post("/api/llm/models", json={"base_url": "http://gpu:8000/v1"}).json()
    assert body["ok"] is True
    assert body["state"] == "empty", "distinct from unreachable; needs a different fix"


def test_no_listing_endpoint_is_its_own_state(monkeypatch) -> None:
    monkeypatch.setattr(requests, "get", lambda url, **kw: FakeResponse(status_code=404))
    body = client.post("/api/llm/models", json={"base_url": "http://gateway/v1"}).json()
    assert body["state"] == "no-listing"
    assert "manually" in body["reason"]


def test_discovery_never_leaks_the_api_key(monkeypatch) -> None:
    monkeypatch.setattr(requests, "get", lambda url, **kw: FakeResponse(body={"data": []}))
    resp = client.post(
        "/api/llm/models",
        json={"base_url": "http://gpu:8000/v1", "api_key": "sk-never-echo-me"},
    )
    assert "sk-never-echo-me" not in resp.text


# --------------------------------------------------------------------------- #
# The connection test
# --------------------------------------------------------------------------- #


def test_test_endpoint_passes_on_real_content(monkeypatch) -> None:
    monkeypatch.setattr(
        requests,
        "post",
        lambda url, **kw: FakeResponse(
            body={"model": "qwen38-27B-v2", "choices": [{"message": {"content": "ok"}}]}
        ),
    )
    body = client.post("/api/llm/test", json={"base_url": "http://gpu:8000/v1"}).json()
    assert body["ok"] is True
    assert body["model"] == "qwen38-27B-v2"
    assert "answered in" in body["summary"]


def test_test_endpoint_fails_on_a_server_still_loading_weights(monkeypatch) -> None:
    """Port open, replies arriving, no choices key. Both weaker checks pass here."""
    monkeypatch.setattr(
        requests, "post", lambda url, **kw: FakeResponse(body={"object": "chat.completion"})
    )
    body = client.post("/api/llm/test", json={"base_url": "http://gpu:8000/v1"}).json()
    assert body["ok"] is False
    assert "no content" in body["reason"]


def test_test_endpoint_is_200_even_when_the_endpoint_is_dead(offline) -> None:
    resp = client.post("/api/llm/test", json={"base_url": "http://localhost:1/v1"})
    assert resp.status_code == 200, "a failing test is information, not a server error"
    assert resp.json()["ok"] is False


def test_test_endpoint_reports_an_http_error_verbatim(monkeypatch) -> None:
    monkeypatch.setattr(
        requests,
        "post",
        lambda url, **kw: FakeResponse(status_code=404, text='{"error":"model not found"}'),
    )
    body = client.post("/api/llm/test", json={"base_url": "http://gpu:8000/v1"}).json()
    assert body["ok"] is False
    assert "model not found" in body["reason"], "the actionable half must survive"


def test_a_bad_url_is_rejected_before_any_call(offline) -> None:
    assert client.post("/api/llm/models", json={"base_url": "ftp://nope"}).status_code == 422
