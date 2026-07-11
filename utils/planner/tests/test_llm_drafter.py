#!/usr/bin/env python3

from __future__ import annotations

import json
import socket

import pytest

from utils.planner.config import PlannerConfig
from utils.planner.drafter import DeterministicDrafter
from utils.planner.drafter_factory import HybridDrafter, select_drafter
from utils.planner.gate import evaluate
from utils.planner.llm_drafter import (
    DrafterUnavailable,
    OpenAICompatibleDrafter,
    build_messages,
    extract_json_object,
)
from utils.planner.schema import Plan
from utils.planner.tests._fixtures import load_fixture_cards, make_live_view

CARDS = load_fixture_cards()
DEMO = "Which CAPEC patterns map to ATT&CK techniques and their mitigations?"


# -- message building -------------------------------------------------------


def test_build_messages_lists_live_down_and_joins() -> None:
    msgs = build_messages(DEMO, CARDS, make_live_view(live=("capec",)))
    user = msgs[1]["content"]
    assert "LIVE SOURCES" in user and "capec [LIVE]" in user
    assert "attack [DOWN]" in user
    assert "attack-technique-id" in user
    assert DEMO in user


def test_build_messages_includes_feedback() -> None:
    msgs = build_messages(DEMO, CARDS, make_live_view(), feedback=["fix the limits"])
    assert "REJECTED" in msgs[1]["content"]
    assert "fix the limits" in msgs[1]["content"]


def test_system_prompt_states_definitional_name_rule() -> None:
    # The prompt must tell the model a "what is <name>?" question is answerable
    # by name, not something to mark unsupported.
    system = build_messages(DEMO, CARDS, make_live_view())[0]["content"]
    assert "DEFINITIONAL" in system
    assert "resolves entities by name" in system


# -- JSON extraction --------------------------------------------------------


def test_extract_plain_object() -> None:
    assert extract_json_object('{"a": 1}') == {"a": 1}


def test_extract_from_fenced_and_prose() -> None:
    text = 'Sure, here is the plan:\n```json\n{"sub_questions": [], "partial": true}\n```\nDone.'
    assert extract_json_object(text) == {"sub_questions": [], "partial": True}


def test_extract_handles_nested_and_strings_with_braces() -> None:
    text = '{"text": "a } brace { inside", "limits": {"x": 1}}'
    assert extract_json_object(text)["limits"] == {"x": 1}


@pytest.mark.parametrize("bad", ["", "no json here", "{unbalanced", '{"x": notjson}'])
def test_extract_raises_on_bad(bad: str) -> None:
    with pytest.raises(DrafterUnavailable):
        extract_json_object(bad)


# -- HTTP call (mocked) -----------------------------------------------------


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


def _patch_post(monkeypatch, response: FakeResponse | Exception) -> None:
    import requests

    def fake_post(url, json=None, timeout=None):  # noqa: A002 - mirror requests API
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(requests, "post", fake_post)


def test_draft_parses_valid_completion(monkeypatch) -> None:
    plan_json = {
        "sub_questions": [
            {
                "id": "q1", "source": "capec", "text": "find patterns",
                "entities": ["AttackPattern", "MAPS_TO"],
                "limits": {"max_traversal_depth": 3, "max_result_rows": 1000, "query_timeout_ms": 5000},
                "join_key": "attack-technique-id", "rationale": "capec has patterns",
            }
        ],
        "joins": [], "unsupported": [], "assumptions": [], "rationale": "r", "partial": True,
    }
    _patch_post(monkeypatch, FakeResponse(200, _completion(json.dumps(plan_json))))
    drafter = OpenAICompatibleDrafter(PlannerConfig(data_dir="data"))
    plan = drafter.draft(DEMO, CARDS, make_live_view())
    assert isinstance(plan, Plan)
    assert plan.request == DEMO
    assert plan.sub_questions[0].source == "capec"


def test_draft_transport_error_raises_unavailable(monkeypatch) -> None:
    import requests

    _patch_post(monkeypatch, requests.RequestException("connection refused"))
    drafter = OpenAICompatibleDrafter(PlannerConfig(data_dir="data"))
    with pytest.raises(DrafterUnavailable):
        drafter.draft(DEMO, CARDS, make_live_view())


def test_draft_http_error_raises_unavailable(monkeypatch) -> None:
    _patch_post(monkeypatch, FakeResponse(500, None, text="boom"))
    drafter = OpenAICompatibleDrafter(PlannerConfig(data_dir="data"))
    with pytest.raises(DrafterUnavailable):
        drafter.draft(DEMO, CARDS, make_live_view())


def test_draft_empty_content_raises_unavailable(monkeypatch) -> None:
    _patch_post(monkeypatch, FakeResponse(200, _completion("")))
    drafter = OpenAICompatibleDrafter(PlannerConfig(data_dir="data"))
    with pytest.raises(DrafterUnavailable):
        drafter.draft(DEMO, CARDS, make_live_view())


# -- hybrid fallback --------------------------------------------------------


class AlwaysFailDrafter:
    def draft(self, *a, **k):
        raise DrafterUnavailable("down")


def test_hybrid_falls_back_to_deterministic() -> None:
    hybrid = HybridDrafter(AlwaysFailDrafter(), DeterministicDrafter())
    view = make_live_view()
    plan = hybrid.draft(DEMO, CARDS, view)
    assert hybrid.last_used == "DeterministicDrafter"
    assert any("fallback" in a for a in plan.assumptions)
    assert evaluate(plan, CARDS, view).ok


class UnsupportedOnlyDrafter:
    """Succeeds (no transport error) but routes nothing — mimics the LLM marking
    a definitional question 'incomplete/unsupported'."""

    def draft(self, request, cards, live_view, feedback=None, intent=None):
        from utils.planner.schema import Plan, UnsupportedPart

        plan = Plan(request=request)
        plan.unsupported.append(UnsupportedPart(description="What", reason="incomplete"))
        plan.partial = True
        return plan


def test_hybrid_floor_rescues_definitional_when_primary_routes_nothing() -> None:
    hybrid = HybridDrafter(UnsupportedOnlyDrafter(), DeterministicDrafter())
    view = make_live_view()
    plan = hybrid.draft("What is Phishing?", CARDS, view)
    assert plan.sub_questions  # deterministic floor rescued the definitional turn
    assert hybrid.last_used == "DeterministicDrafter"
    assert any("floor" in a for a in plan.assumptions)
    assert evaluate(plan, CARDS, view).ok


def test_hybrid_keeps_primary_when_floor_also_routes_nothing() -> None:
    # A non-definitional, out-of-scope question: the deterministic floor also
    # routes nothing, so the primary plan (and its reasons) is preserved.
    hybrid = HybridDrafter(UnsupportedOnlyDrafter(), DeterministicDrafter())
    plan = hybrid.draft("List all Kubernetes pods.", CARDS, make_live_view())
    assert not plan.sub_questions
    assert hybrid.last_used == "UnsupportedOnlyDrafter"


def test_select_drafter_defaults_to_deterministic() -> None:
    assert isinstance(select_drafter(PlannerConfig(data_dir="data")), DeterministicDrafter)


def test_select_drafter_hybrid_when_enabled() -> None:
    cfg = PlannerConfig(data_dir="data", llm_enabled=True)
    assert isinstance(select_drafter(cfg), HybridDrafter)


# -- guarded live test ------------------------------------------------------


def _llm_reachable(host: str = "localhost", port: int = 9090) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except OSError:
        return False


@pytest.mark.skipif(not _llm_reachable(), reason="local LLM endpoint not reachable")
def test_live_llm_draft_returns_plan() -> None:
    drafter = OpenAICompatibleDrafter(PlannerConfig.from_env())
    try:
        plan = drafter.draft(DEMO, CARDS, make_live_view())
    except DrafterUnavailable as exc:
        pytest.skip(f"LLM produced no usable draft: {exc}")
    assert isinstance(plan, Plan)
    assert plan.request == DEMO
