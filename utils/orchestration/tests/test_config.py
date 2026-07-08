"""OrchestrationConfig env parsing."""

from utils.orchestration.config import DEFAULT_RECURSION_LIMIT, OrchestrationConfig


def test_defaults(monkeypatch):
    monkeypatch.delenv("ORCH_CHECKPOINTER", raising=False)
    monkeypatch.delenv("ORCH_RECURSION_LIMIT", raising=False)
    config = OrchestrationConfig.from_env()
    assert config.checkpointer is False
    assert config.recursion_limit == DEFAULT_RECURSION_LIMIT


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("ORCH_CHECKPOINTER", "true")
    monkeypatch.setenv("ORCH_RECURSION_LIMIT", "50")
    config = OrchestrationConfig.from_env()
    assert config.checkpointer is True
    assert config.recursion_limit == 50


def test_invalid_values_fall_back(monkeypatch):
    monkeypatch.setenv("ORCH_CHECKPOINTER", "maybe")
    monkeypatch.setenv("ORCH_RECURSION_LIMIT", "not-a-number")
    config = OrchestrationConfig.from_env()
    assert config.checkpointer is False
    assert config.recursion_limit == DEFAULT_RECURSION_LIMIT
