#!/usr/bin/env python3
"""Contract tests for the unified LLM settings resolver.

The load-bearing test in this file is
:func:`test_unset_environment_reproduces_historical_defaults`. Collapsing five
env groups into one is only safe if an operator who sets nothing gets exactly
what they got before, because roughly twenty scripts under ``scripts/`` and
every arm in ``docs/research/experiments/`` were run against those numbers.
"""

from __future__ import annotations

import pytest

from utils.config import set_env_values, unset_env_values
from utils.llm.config import (
    DEFAULT_BASE_URL,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_TIMEOUT_S,
    STAGES,
    LLMProvider,
    LLMSettings,
    env_key,
    resolve,
    resolve_all,
    stage_env_keys,
)

#: Every env var this module reads, cleared before each test so a developer's
#: real .env (which pins ORCH_MAX_HOPS and friends) cannot colour the result.
_ALL_KEYS = [env_key(f) for f in stage_env_keys("planner")] + [
    key for stage in STAGES for key in stage_env_keys(stage).values()
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for key in _ALL_KEYS:
        monkeypatch.delenv(key, raising=False)


# --------------------------------------------------------------------------- #
# Inheritance
# --------------------------------------------------------------------------- #


def test_unset_environment_reproduces_historical_defaults():
    """With nothing set, every stage resolves to the pre-refactor values."""
    for stage in STAGES:
        settings = resolve(stage)
        assert settings.base_url == DEFAULT_BASE_URL
        assert settings.model == DEFAULT_MODEL
        assert settings.timeout_s == DEFAULT_TIMEOUT_S
        assert settings.provider is LLMProvider.OPENAI_COMPATIBLE
        assert settings.enabled is False, "the LLM has always been opt-in"
        assert settings.thinking_budget == 0, "0 means send no cap, as before"


def test_every_field_is_marked_inherited_when_nothing_overrides():
    settings = resolve("synthesis")
    assert settings.is_inherited("model")
    assert settings.is_inherited("base_url")
    assert settings.stage == "synthesis"


def test_primary_group_flows_into_every_stage(monkeypatch):
    monkeypatch.setenv("ARIADNE_LLM_BASE_URL", "http://gpu-box:8000/v1")
    monkeypatch.setenv("ARIADNE_LLM_MODEL", "qwen38-27B-v2")
    monkeypatch.setenv("ARIADNE_LLM_ENABLED", "true")
    for stage in STAGES:
        settings = resolve(stage)
        assert settings.base_url == "http://gpu-box:8000/v1"
        assert settings.model == "qwen38-27B-v2"
        assert settings.enabled is True


def test_stage_override_wins_and_is_not_marked_inherited(monkeypatch):
    monkeypatch.setenv("ARIADNE_LLM_MODEL", "primary-model")
    monkeypatch.setenv("EVAL_LLM_MODEL", "judge-model")

    judge = resolve("eval")
    assert judge.model == "judge-model"
    assert not judge.is_inherited("model")
    assert judge.is_inherited("base_url"), "unset fields still follow the primary"

    assert resolve("synthesis").model == "primary-model"


def test_overriding_one_coupled_field_carries_the_other(monkeypatch):
    """A stage cannot pair its own token cap with the primary's budget."""
    monkeypatch.setenv("ARIADNE_LLM_MAX_TOKENS", "32000")
    monkeypatch.setenv("ARIADNE_LLM_THINKING_BUDGET", "16000")
    monkeypatch.setenv("SYNTHESIS_LLM_MAX_TOKENS", "4096")

    synthesis = resolve("synthesis")
    assert synthesis.max_tokens == 4096
    # The primary's 16000 budget would exceed this stage's 4096 cap, so the
    # budget is owned by the stage too and clamped rather than inherited whole.
    assert not synthesis.is_inherited("thinking_budget")
    assert synthesis.thinking_budget < synthesis.max_tokens


def test_defaults_argument_preserves_a_callers_historical_number():
    """The judge's 32000 and the specialist's 2048 must not be moved."""
    judge = resolve("eval", defaults=LLMSettings(max_tokens=32000))
    assert judge.max_tokens == 32000
    specialist = resolve("specialist", defaults=LLMSettings(max_tokens=2048))
    assert specialist.max_tokens == 2048


def test_unknown_stage_is_rejected():
    with pytest.raises(ValueError, match="Unknown LLM stage"):
        resolve("router")


def test_resolve_all_covers_primary_and_every_stage():
    resolved = resolve_all()
    assert set(resolved) == {"primary", *STAGES}


# --------------------------------------------------------------------------- #
# Providers
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "spelling,expected",
    [
        ("anthropic", LLMProvider.ANTHROPIC),
        ("claude", LLMProvider.ANTHROPIC),
        ("google", LLMProvider.GEMINI),
        ("vllm", LLMProvider.OPENAI_COMPATIBLE),
        ("LM-Studio", LLMProvider.OPENAI_COMPATIBLE),
        ("nonsense", LLMProvider.OPENAI_COMPATIBLE),
        ("", LLMProvider.OPENAI_COMPATIBLE),
        (None, LLMProvider.OPENAI_COMPATIBLE),
    ],
)
def test_provider_parsing_never_raises(spelling, expected):
    assert LLMProvider.parse(spelling) is expected


def test_hosted_provider_without_explicit_url_gets_its_vendor_endpoint(monkeypatch):
    monkeypatch.setenv("ARIADNE_LLM_PROVIDER", "anthropic")
    settings = resolve()
    assert settings.base_url == "https://api.anthropic.com/v1"


def test_explicit_url_beats_the_vendor_default(monkeypatch):
    monkeypatch.setenv("ARIADNE_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ARIADNE_LLM_BASE_URL", "http://proxy.internal/v1")
    assert resolve().base_url == "http://proxy.internal/v1"


# --------------------------------------------------------------------------- #
# The thinking-budget invariant
# --------------------------------------------------------------------------- #


def test_budget_at_or_above_max_tokens_is_reported_invalid():
    errors = LLMSettings(max_tokens=4096, thinking_budget=4096).validate()
    assert [e.field for e in errors] == ["thinking_budget"]
    assert "must be less than" in errors[0].message


def test_budget_below_max_tokens_is_valid():
    assert LLMSettings(max_tokens=4096, thinking_budget=2048).validate() == []


def test_zero_budget_stays_valid_and_means_no_cap():
    """Every run predating the cap sent none; 0 must remain expressible."""
    settings = LLMSettings(max_tokens=4096, thinking_budget=0)
    assert settings.validate() == []
    assert settings.clamped().thinking_budget == 0


def test_negative_budget_is_rejected():
    errors = LLMSettings(thinking_budget=-1).validate()
    assert [e.field for e in errors] == ["thinking_budget"]


def test_clamp_is_the_last_resort_for_a_hand_edited_env(monkeypatch):
    monkeypatch.setenv("ARIADNE_LLM_MAX_TOKENS", "1000")
    monkeypatch.setenv("ARIADNE_LLM_THINKING_BUDGET", "5000")
    assert resolve(clamp=True).thinking_budget == 999
    # The API asks for the violation instead, so it can name the field.
    unclamped = resolve(clamp=False)
    assert unclamped.thinking_budget == 5000
    assert unclamped.validate()


def test_hosted_provider_without_a_key_is_reported_invalid():
    errors = LLMSettings(provider=LLMProvider.OPENAI, api_key="").validate()
    assert [e.field for e in errors] == ["api_key"]


def test_local_provider_without_a_key_is_fine():
    assert LLMSettings(provider=LLMProvider.OPENAI_COMPATIBLE, api_key="").validate() == []


def test_bad_base_url_is_reported():
    errors = LLMSettings(base_url="localhost:9090").validate()
    assert [e.field for e in errors] == ["base_url"]


# --------------------------------------------------------------------------- #
# Secrets
# --------------------------------------------------------------------------- #


def test_redacted_drops_the_key_but_keeps_the_set_flag():
    settings = LLMSettings(api_key="sk-secret")
    assert settings.api_key_set is True
    assert settings.redacted().api_key == ""
    assert settings.redacted().api_key_set is False


# --------------------------------------------------------------------------- #
# set / unset round-trip — what makes "inherit" real
# --------------------------------------------------------------------------- #


def test_override_then_inherit_round_trip(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("ARIADNE_LLM_MODEL=primary-model\n", encoding="utf-8")
    monkeypatch.setenv("ARIADNE_LLM_MODEL", "primary-model")

    set_env_values({"EVAL_LLM_MODEL": "judge-model"}, env_file=env_file)
    assert resolve("eval").model == "judge-model"

    unset_env_values(["EVAL_LLM_MODEL"], env_file=env_file)
    judge = resolve("eval")
    assert judge.model == "primary-model"
    assert judge.is_inherited("model")

    body = env_file.read_text(encoding="utf-8")
    assert "# unset by Ariadne: EVAL_LLM_MODEL=judge-model" in body, (
        "the cleared value stays legible rather than vanishing"
    )
    assert "ARIADNE_LLM_MODEL=primary-model" in body


def test_unset_is_a_noop_for_keys_that_were_never_set(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("ARIADNE_LLM_MODEL=m\n", encoding="utf-8")
    unset_env_values(["PLANNER_LLM_MODEL"], env_file=env_file)
    assert env_file.read_text(encoding="utf-8") == "ARIADNE_LLM_MODEL=m\n"
