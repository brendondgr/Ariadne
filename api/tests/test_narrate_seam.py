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
