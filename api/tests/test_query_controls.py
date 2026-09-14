#!/usr/bin/env python3
"""The workbench's three controls reach the agents they name.

`EXP-2026-09-020` A-8 timed a "deterministic" turn at 43.27 s around a pipeline
that answered at 1.09 s: `validation` ~28.6 s and `answer` ~10.7 s, with no
control able to stop either. These pin that each control now does.
"""

from __future__ import annotations

from typing import Any

from api.services import conversations as convo_service
from api.tests.test_conversations import temp_store  # noqa: F401 - pytest fixture


def _captured(monkeypatch) -> dict[str, Any]:
    seen: dict[str, Any] = {}

    def _fake_iter_conversation(question: str, **kw: Any):
        seen.update(kw)
        return iter(())

    monkeypatch.setattr(convo_service, "iter_conversation", _fake_iter_conversation)
    return seen


def _run(monkeypatch, temp_store, **kw):
    seen = _captured(monkeypatch)
    convo = temp_store.create_conversation("New conversation")
    list(
        convo_service.stream_conversation_events(
            "q", convo.id, store=temp_store, **kw
        )
    )
    return seen


def test_verify_off_disables_only_the_validation_agent(monkeypatch, temp_store):
    seen = _run(monkeypatch, temp_store, verify=False, narrate=True)
    assert seen["validation_client"].enabled is False
    # router and orchestration are untouched -- they are what make a thread
    # conversational, and they are cheap.
    assert "router_client" not in seen
    assert "orchestration_client" not in seen


def test_verify_on_leaves_the_validation_agent_to_the_config(monkeypatch, temp_store):
    seen = _run(monkeypatch, temp_store, verify=True)
    assert "validation_client" not in seen


def test_prose_off_disables_only_the_answer_agent(monkeypatch, temp_store):
    seen = _run(monkeypatch, temp_store, narrate=False, verify=True)
    assert seen["answer_client"].enabled is False
    assert "validation_client" not in seen


def test_thinking_budget_reaches_the_conversation_config(monkeypatch, temp_store):
    seen = _run(monkeypatch, temp_store, thinking_budget=2048)
    assert seen["config"].llm.thinking_budget == 2048


def test_no_budget_leaves_the_environment_alone(monkeypatch, temp_store):
    """None means "don't touch it", so an untouched deployment is unchanged."""
    from utils.conversation.config import ConversationConfig

    base = ConversationConfig.from_env()
    seen = _run(monkeypatch, temp_store, thinking_budget=None)
    assert seen["config"].llm.thinking_budget == base.llm.thinking_budget


def test_an_injected_client_still_wins(monkeypatch, temp_store):
    """Tests inject their own clients; the gate must not clobber them."""
    sentinel = object()
    seen = _run(monkeypatch, temp_store, verify=False, validation_client=sentinel)
    assert seen["validation_client"] is sentinel
