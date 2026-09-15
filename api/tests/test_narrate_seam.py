#!/usr/bin/env python3
"""`narrate` turns on the narrator and nothing else.

`use_llm` sets the planner, specialist AND synthesis seams together, so asking
for readable prose through it also hands query construction to a model -- the
baseline that scores 0.5000 where the template cascade scores 0.9467
(`EXP-2026-09-007`). These tests pin that the two are separate at the API.
"""

from __future__ import annotations

from typing import Any

from api.services import query as query_service


def _capture(monkeypatch) -> dict[str, Any]:
    seen: dict[str, Any] = {}

    def _fake_iter_pipeline(question: str, **kw: Any):
        seen.update(kw)
        return iter(())

    # Patch the name BOUND IN THE SERVICE. query.py does
    # `from utils.orchestration.main import iter_pipeline` at import, so
    # patching the source module leaves the bound reference untouched and the
    # real pipeline runs -- which is how the first version of this test took 27
    # seconds and asserted against an empty dict.
    monkeypatch.setattr(query_service, "iter_pipeline", _fake_iter_pipeline)
    return seen


def test_narrate_passes_an_explicit_synthesis_config_and_leaves_use_llm_off(monkeypatch):
    seen = _capture(monkeypatch)
    list(query_service.stream_query_events("q", mode="query", narrate=True))
    assert seen.get("use_llm") is False, "narrate must not turn on the query builder"
    config = seen.get("synthesis_config")
    assert config is not None and config.llm_enabled is True


def test_without_narrate_no_synthesis_config_is_forced(monkeypatch):
    seen = _capture(monkeypatch)
    list(query_service.stream_query_events("q", mode="query"))
    assert seen.get("use_llm") is False
    assert seen.get("synthesis_config") is None


def test_the_two_flags_are_independent(monkeypatch):
    """`drafter=llm` without `narrate` must not be rewritten into a narrator ask."""
    seen = _capture(monkeypatch)
    list(query_service.stream_query_events("q", mode="query", use_llm=True))
    assert seen.get("use_llm") is True
    assert seen.get("synthesis_config") is None


def test_thinking_budget_reaches_the_synthesis_config(monkeypatch):
    """The dropdown's cap must arrive as an explicit, transmitted value.

    `/api/query` sent `thinking_budget=` to a service that had no such
    parameter, so every workbench query 500'd with a TypeError before the
    pipeline started.
    """
    seen = _capture(monkeypatch)
    list(query_service.stream_query_events("q", mode="query", narrate=True,
                                           thinking_budget=512))
    config = seen["synthesis_config"]
    assert config.llm_enabled is True
    assert config.llm_thinking_budget == 512
    assert config.llm_thinking_budget_explicit is True


def test_an_explicit_zero_budget_is_marked_explicit(monkeypatch):
    """0 means "no reasoning", not "nobody configured a cap"."""
    seen = _capture(monkeypatch)
    list(query_service.stream_query_events("q", mode="query", narrate=True,
                                           thinking_budget=0))
    config = seen["synthesis_config"]
    assert config.llm_thinking_budget == 0
    assert config.llm_thinking_budget_explicit is True


def test_a_budget_alone_does_not_turn_the_narrator_on(monkeypatch):
    """Passing a config takes over from `llm_enabled=use_llm`; posture is pinned here."""
    monkeypatch.setenv("SYNTHESIS_LLM_ENABLED", "true")
    seen = _capture(monkeypatch)
    list(query_service.stream_query_events("q", mode="query", thinking_budget=256))
    config = seen["synthesis_config"]
    assert config.llm_enabled is False, "a deterministic request stays deterministic"
    assert config.llm_thinking_budget == 256


def test_a_budget_with_the_llm_drafter_keeps_synthesis_on(monkeypatch):
    seen = _capture(monkeypatch)
    list(query_service.stream_query_events("q", mode="query", use_llm=True,
                                           thinking_budget=256))
    assert seen["synthesis_config"].llm_enabled is True
