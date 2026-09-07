#!/usr/bin/env python3
"""Offline checks against each backend's real response shape.

No network, no keys, no GPU. The bodies below are transcribed from the actual
wire formats, including the parts that fail *silently* — a null ``content`` on a
length stop, Anthropic's typed content blocks, Gemini's 200-with-no-candidates
for a blocked prompt. Those are the cases a live smoke test against a healthy
server would never reach, which is exactly why they are pinned here.
"""

from __future__ import annotations

import pytest

from utils.llm.adapters import adapter_for
from utils.llm.adapters.anthropic import API_VERSION
from utils.llm.adapters.base import split_system
from utils.llm.config import LLMProvider, LLMSettings
from utils.llm.types import FINISH_LENGTH, Message

SYSTEM = Message.system("You are a router.")
USER = Message.user("Which source holds T1566?")
ASSISTANT = Message.assistant("attack")


def settings_for(provider: LLMProvider, **kwargs) -> LLMSettings:
    return LLMSettings(
        provider=provider,
        base_url=kwargs.pop("base_url", provider.default_base_url()),
        model=kwargs.pop("model", "test-model"),
        **kwargs,
    )


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #


def test_split_system_joins_rather_than_dropping():
    """Prompts here are built by appending blocks; keeping only the first
    would silently delete grounding the caller thought it sent."""
    system, rest = split_system(
        [Message.system("rules"), Message.system("context"), USER]
    )
    assert system == "rules\n\ncontext"
    assert rest == [USER]


# --------------------------------------------------------------------------- #
# OpenAI-compatible
# --------------------------------------------------------------------------- #


def test_openai_request_is_what_the_hand_rolled_clients_sent():
    """No key configured must reproduce the pre-refactor request exactly."""
    settings = settings_for(LLMProvider.OPENAI_COMPATIBLE, base_url="http://localhost:9090/v1")
    url, headers, payload = adapter_for(settings.provider).chat_request(
        settings, [SYSTEM, USER], max_tokens=2048, temperature=0.0
    )
    assert url == "http://localhost:9090/v1/chat/completions"
    assert "Authorization" not in headers, "an unauthenticated local server got no header before"
    assert payload["messages"] == [
        {"role": "system", "content": SYSTEM.content},
        {"role": "user", "content": USER.content},
    ]
    assert payload["max_tokens"] == 2048
    assert payload["temperature"] == 0.0


def test_openai_sends_a_bearer_header_only_when_a_key_is_set():
    settings = settings_for(LLMProvider.OPENAI, api_key="sk-abc")
    _, headers, _ = adapter_for(settings.provider).chat_request(
        settings, [USER], max_tokens=16, temperature=0.0
    )
    assert headers["Authorization"] == "Bearer sk-abc"


def test_openai_sampling_block_is_spread_into_the_payload():
    settings = settings_for(LLMProvider.OPENAI_COMPATIBLE)
    _, _, payload = adapter_for(settings.provider).chat_request(
        settings,
        [USER],
        max_tokens=100,
        temperature=0.0,
        sampling={"seed": 1729, "top_p": 1, "chat_template_kwargs": {"thinking_budget": 512}},
    )
    assert payload["seed"] == 1729
    assert payload["chat_template_kwargs"] == {"thinking_budget": 512}


def test_openai_null_content_on_a_length_stop_becomes_an_empty_string():
    """Several servers return null here; a caller doing .strip() would crash."""
    body = {
        "model": "qwen38-27B-v2",
        "choices": [{"message": {"role": "assistant", "content": None}, "finish_reason": "length"}],
        "usage": {"prompt_tokens": 900, "completion_tokens": 4096, "total_tokens": 4996},
    }
    result = adapter_for(LLMProvider.OPENAI_COMPATIBLE).parse_chat(body)
    assert result.content == ""
    assert result.truncated is True
    assert result.usage.completion_tokens == 4096


def test_openai_empty_choices_is_parsed_not_indexed():
    """The shape vLLM returns while it is still loading weights."""
    result = adapter_for(LLMProvider.OPENAI_COMPATIBLE).parse_chat({"choices": []})
    assert result.content == ""
    assert result.usage.reported is False


def test_openai_model_listing_reads_vllms_context_window():
    body = {
        "data": [
            {"id": "default-model", "object": "model", "owned_by": "vllm", "max_model_len": 32768},
            {"id": "text-embedding-3-small", "object": "model", "owned_by": "openai"},
        ]
    }
    models = adapter_for(LLMProvider.OPENAI_COMPATIBLE).parse_models(body)
    assert [m.id for m in models] == ["default-model", "text-embedding-3-small"]
    assert models[0].context_window == 32768
    assert models[1].context_window is None, "unknown must stay None, never a guess"


def test_openai_listing_of_the_wrong_shape_yields_nothing_rather_than_raising():
    assert adapter_for(LLMProvider.OPENAI_COMPATIBLE).parse_models({"models": []}) == []


# --------------------------------------------------------------------------- #
# Anthropic
# --------------------------------------------------------------------------- #


def test_anthropic_hoists_the_system_prompt_out_of_messages():
    settings = settings_for(LLMProvider.ANTHROPIC, api_key="sk-ant")
    url, headers, payload = adapter_for(settings.provider).chat_request(
        settings, [SYSTEM, USER, ASSISTANT], max_tokens=512, temperature=0.0
    )
    assert url.endswith("/messages")
    assert payload["system"] == SYSTEM.content
    assert [m["role"] for m in payload["messages"]] == ["user", "assistant"]
    assert all(m["role"] != "system" for m in payload["messages"]), "a 400 otherwise"


def test_anthropic_auth_is_x_api_key_with_a_pinned_version():
    settings = settings_for(LLMProvider.ANTHROPIC, api_key="sk-ant")
    _, headers, _ = adapter_for(settings.provider).chat_request(
        settings, [USER], max_tokens=16, temperature=0.0
    )
    assert headers["x-api-key"] == "sk-ant"
    assert headers["anthropic-version"] == API_VERSION
    assert "Authorization" not in headers


def test_anthropic_always_sends_max_tokens():
    """It is a required field; omitting it is a 400, not a default."""
    settings = settings_for(LLMProvider.ANTHROPIC, api_key="k")
    _, _, payload = adapter_for(settings.provider).chat_request(
        settings, [USER], max_tokens=777, temperature=0.0
    )
    assert payload["max_tokens"] == 777


def test_anthropic_drops_seed_and_the_vllm_thinking_channels():
    """Sending an unknown top-level key here is a 400."""
    settings = settings_for(LLMProvider.ANTHROPIC, api_key="k")
    _, _, payload = adapter_for(settings.provider).chat_request(
        settings,
        [USER],
        max_tokens=100,
        temperature=0.0,
        sampling={"seed": 1729, "top_p": 1},
    )
    assert "seed" not in payload
    assert payload["top_p"] == 1


def test_anthropic_thinking_budget_drops_temperature():
    """Extended thinking and an explicit temperature cannot both be sent."""
    settings = settings_for(LLMProvider.ANTHROPIC, api_key="k")
    _, _, payload = adapter_for(settings.provider).chat_request(
        settings,
        [USER],
        max_tokens=4096,
        temperature=0.0,
        sampling={"extra_body": {"thinking_budget": 1024}},
    )
    assert payload["thinking"] == {"type": "enabled", "budget_tokens": 1024}
    assert "temperature" not in payload


def test_anthropic_content_blocks_are_joined_and_stop_reason_normalized():
    body = {
        "model": "claude-opus-5",
        "content": [
            {"type": "thinking", "thinking": "hidden"},
            {"type": "text", "text": "T1566 lives in "},
            {"type": "text", "text": "attack."},
        ],
        "stop_reason": "max_tokens",
        "usage": {"input_tokens": 120, "output_tokens": 40},
    }
    result = adapter_for(LLMProvider.ANTHROPIC).parse_chat(body)
    assert result.content == "T1566 lives in attack."
    assert result.finish_reason == FINISH_LENGTH, "normalized so .truncated works everywhere"
    assert result.truncated is True
    assert result.usage.total_tokens == 160


def test_anthropic_listing_reports_real_capability_metadata():
    body = {
        "data": [
            {
                "id": "claude-opus-5",
                "display_name": "Claude Opus 5",
                "max_input_tokens": 1000000,
                "max_tokens": 128000,
                "capabilities": {"thinking": {"supported": True}},
            }
        ]
    }
    models = adapter_for(LLMProvider.ANTHROPIC).parse_models(body)
    assert models[0].display_name == "Claude Opus 5"
    assert models[0].context_window == 1000000
    assert models[0].max_output_tokens == 128000


# --------------------------------------------------------------------------- #
# Gemini
# --------------------------------------------------------------------------- #


def test_gemini_renames_the_container_role_and_token_field():
    settings = settings_for(LLMProvider.GEMINI, api_key="g-key", model="gemini-3.7-flash")
    url, headers, payload = adapter_for(settings.provider).chat_request(
        settings, [SYSTEM, USER, ASSISTANT], max_tokens=800, temperature=0.0
    )
    assert url.endswith("/models/gemini-3.7-flash:generateContent")
    assert headers["x-goog-api-key"] == "g-key"
    assert payload["systemInstruction"] == {"parts": [{"text": SYSTEM.content}]}
    assert [c["role"] for c in payload["contents"]] == ["user", "model"]
    assert payload["generationConfig"]["maxOutputTokens"] == 800
    assert "max_tokens" not in payload


def test_gemini_strips_a_models_prefix_from_the_configured_id():
    settings = settings_for(LLMProvider.GEMINI, api_key="k", model="models/gemini-3.7-flash")
    url, _, _ = adapter_for(settings.provider).chat_request(
        settings, [USER], max_tokens=16, temperature=0.0
    )
    assert url.endswith("/models/gemini-3.7-flash:generateContent")


def test_gemini_drops_seed_because_an_ignored_key_looks_like_success():
    settings = settings_for(LLMProvider.GEMINI, api_key="k")
    _, _, payload = adapter_for(settings.provider).chat_request(
        settings, [USER], max_tokens=16, temperature=0.0, sampling={"seed": 1729, "top_p": 1}
    )
    assert "seed" not in payload["generationConfig"]
    assert payload["generationConfig"]["topP"] == 1


def test_gemini_blocked_prompt_names_the_block_rather_than_reporting_silence():
    """200 with no candidates is a policy decision, not an empty answer."""
    body = {"promptFeedback": {"blockReason": "SAFETY"}}
    result = adapter_for(LLMProvider.GEMINI).parse_chat(body)
    assert result.content == ""
    assert result.finish_reason == "blocked: SAFETY"


def test_gemini_parses_parts_and_normalizes_max_tokens():
    body = {
        "candidates": [
            {
                "content": {"parts": [{"text": "T1566 "}, {"text": "is phishing."}], "role": "model"},
                "finishReason": "MAX_TOKENS",
            }
        ],
        "usageMetadata": {"promptTokenCount": 30, "candidatesTokenCount": 12, "totalTokenCount": 42},
        "modelVersion": "gemini-3.7-flash",
    }
    result = adapter_for(LLMProvider.GEMINI).parse_chat(body)
    assert result.content == "T1566 is phishing."
    assert result.truncated is True
    assert result.usage.total_tokens == 42


def test_gemini_listing_strips_prefixes_and_filters_non_chat_models():
    body = {
        "models": [
            {
                "name": "models/gemini-3.7-flash",
                "displayName": "Gemini 3.7 Flash",
                "inputTokenLimit": 1048576,
                "outputTokenLimit": 65536,
                "supportedGenerationMethods": ["generateContent"],
            },
            {
                "name": "models/embedding-001",
                "supportedGenerationMethods": ["embedContent"],
            },
        ]
    }
    models = adapter_for(LLMProvider.GEMINI).parse_models(body)
    assert [m.id for m in models] == ["gemini-3.7-flash"], "no bare prefix, no embedder"
    assert models[0].context_window == 1048576
