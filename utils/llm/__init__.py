#!/usr/bin/env python3
"""Ariadne's language-model seam: one config group, one transport, N providers.

    from utils.llm import Message, chat, discover_models, probe, resolve

    settings = resolve("synthesis")      # inherits ARIADNE_LLM_* unless overridden
    result = chat(settings, [Message.user("hi")])

See :mod:`utils.llm.config` for how settings resolve and why the per-stage
overrides still exist, and :mod:`utils.llm.types` for what every backend is
normalized into.
"""

from utils.llm.client import chat, discover_models, probe, sort_models
from utils.llm.config import (
    STAGES,
    FieldError,
    LLMProvider,
    LLMSettings,
    env_key,
    primary_env_keys,
    resolve,
    resolve_all,
    stage_env_keys,
)
from utils.llm.types import (
    ChatResult,
    DiscoveryResult,
    LLMUnavailable,
    Message,
    ModelInfo,
    ProbeResult,
    Usage,
)

__all__ = [
    "STAGES",
    "ChatResult",
    "DiscoveryResult",
    "FieldError",
    "LLMProvider",
    "LLMSettings",
    "LLMUnavailable",
    "Message",
    "ModelInfo",
    "ProbeResult",
    "Usage",
    "chat",
    "discover_models",
    "env_key",
    "primary_env_keys",
    "probe",
    "resolve",
    "resolve_all",
    "sort_models",
    "stage_env_keys",
]
