"""OrchestrationConfig env parsing."""

from utils.orchestration.config import (
    DEFAULT_ASSESS_MODE,
    DEFAULT_MAX_HOPS,
    DEFAULT_RECURSION_LIMIT,
    OrchestrationConfig,
)


def _clear_loop_env(monkeypatch):
    monkeypatch.delenv("ORCH_MAX_HOPS", raising=False)
    monkeypatch.delenv("ORCH_ASSESS_MODE", raising=False)


def test_defaults(monkeypatch):
    monkeypatch.delenv("ORCH_CHECKPOINTER", raising=False)
    monkeypatch.delenv("ORCH_RECURSION_LIMIT", raising=False)
    _clear_loop_env(monkeypatch)
    config = OrchestrationConfig.from_env()
    assert config.checkpointer is False
    assert config.recursion_limit == DEFAULT_RECURSION_LIMIT
    # Loop is enabled by default (5); ORCH_MAX_HOPS=1 forces the single pass.
    assert config.max_hops == DEFAULT_MAX_HOPS == 5
    assert config.assess_mode == DEFAULT_ASSESS_MODE == "deterministic"


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("ORCH_CHECKPOINTER", "true")
    monkeypatch.setenv("ORCH_RECURSION_LIMIT", "50")
    monkeypatch.setenv("ORCH_MAX_HOPS", "5")
    monkeypatch.setenv("ORCH_ASSESS_MODE", "LLM")  # case-insensitive
    config = OrchestrationConfig.from_env()
    assert config.checkpointer is True
    assert config.recursion_limit == 50
    assert config.max_hops == 5
    assert config.assess_mode == "llm"


def test_invalid_values_fall_back(monkeypatch):
    monkeypatch.setenv("ORCH_CHECKPOINTER", "maybe")
    monkeypatch.setenv("ORCH_RECURSION_LIMIT", "not-a-number")
    monkeypatch.setenv("ORCH_MAX_HOPS", "not-a-number")
    monkeypatch.setenv("ORCH_ASSESS_MODE", "oracle")
    config = OrchestrationConfig.from_env()
    assert config.checkpointer is False
    assert config.recursion_limit == DEFAULT_RECURSION_LIMIT
    assert config.max_hops == DEFAULT_MAX_HOPS
    assert config.assess_mode == DEFAULT_ASSESS_MODE


def test_max_hops_floor(monkeypatch):
    """A zero/negative cap would deadlock the loop; clamp up to the default."""
    _clear_loop_env(monkeypatch)
    monkeypatch.setenv("ORCH_MAX_HOPS", "0")
    assert OrchestrationConfig.from_env().max_hops == DEFAULT_MAX_HOPS
    monkeypatch.setenv("ORCH_MAX_HOPS", "-3")
    assert OrchestrationConfig.from_env().max_hops == DEFAULT_MAX_HOPS
