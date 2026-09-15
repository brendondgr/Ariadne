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
    assert seen["answer_client"].enabled is True
    # router and orchestration are untouched -- they are what make a thread
    # conversational, and they are cheap.
    assert "router_client" not in seen
    assert "orchestration_client" not in seen


def test_verify_on_enables_the_agent_even_when_the_env_disables_it(monkeypatch, temp_store):
    """Declining to disable is not the same as enabling.

    With CONVERSATION_LLM_ENABLED=false, a `verify: on` that merely left the
    agent to the config left it OFF: a turn that should have cost ~30 s measured
    0.08 s and the control silently did nothing.
    """
    seen = _run(monkeypatch, temp_store, verify=True)
    assert seen["validation_client"].enabled is True


def test_prose_off_disables_only_the_answer_agent(monkeypatch, temp_store):
    seen = _run(monkeypatch, temp_store, narrate=False, verify=True)
    assert seen["answer_client"].enabled is False
    assert seen["validation_client"].enabled is True


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


def test_a_thinking_budget_of_zero_is_sent_rather_than_omitted(monkeypatch, temp_store):
    """"None" must mean no reasoning, not "let the model decide".

    DEFAULT_THINKING_BUDGET is also 0 and the sender omits a falsy budget, so
    without the explicit flag a requested "None" sends nothing and the model
    falls back to its own default -- measured at 11.27 s and 313 completion
    tokens against 1.28 s and 31 for an explicit 0 (EXP-2026-09-020 A-9).
    """
    seen = _run(monkeypatch, temp_store, thinking_budget=0)
    llm = seen["config"].llm
    assert llm.thinking_budget == 0
    assert llm.thinking_budget_explicit is True
    # …and it survives the hop to transport settings, which is what the sender reads.
    assert llm.llm_settings().thinking_budget_explicit is True


def test_an_unset_budget_is_still_omitted(monkeypatch, temp_store):
    """An untouched deployment must keep sending nothing."""
    seen = _run(monkeypatch, temp_store, thinking_budget=None)
    assert seen["config"].llm.thinking_budget_explicit is False
