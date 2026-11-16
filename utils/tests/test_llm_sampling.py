"""The sampling block's opt-in thinking level (Era 2 Step 4, EXP-2026-11-009 A-1)."""

from utils.llm_sampling import sampling_params


def test_no_reasoning_effort_unless_asked(monkeypatch):
    monkeypatch.delenv("LLM_REASONING_EFFORT", raising=False)
    assert "reasoning_effort" not in sampling_params(max_tokens=4096)


def test_reasoning_effort_from_the_environment(monkeypatch):
    monkeypatch.setenv("LLM_REASONING_EFFORT", "medium")
    p = sampling_params(max_tokens=4096)
    assert p["reasoning_effort"] == "medium" and p["temperature"] == 0
