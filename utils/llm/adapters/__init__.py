#!/usr/bin/env python3
"""Per-provider translation. Adapters are pure: they never open a socket.

Each adapter turns :class:`~utils.llm.config.LLMSettings` plus normalized
messages into ``(url, headers, payload)``, and turns a decoded response body
back into a :class:`~utils.llm.types.ChatResult`. HTTP — timeouts, retries,
error mapping — lives in :mod:`utils.llm.client`, once.

That split is the whole point. It means every backend's real response shape can
be tested offline with no network, no keys and no GPU, and it means adding a
fifth backend is a new file rather than a grep for ``if provider ==``.
"""

from __future__ import annotations

from utils.llm.config import LLMProvider

from .anthropic import AnthropicAdapter
from .base import Adapter
from .gemini import GeminiAdapter
from .openai_compat import OpenAICompatAdapter

_ADAPTERS: dict[LLMProvider, Adapter] = {
    LLMProvider.OPENAI_COMPATIBLE: OpenAICompatAdapter(),
    # OpenAI proper and Ollama's /v1 both speak Chat Completions; they differ
    # only in auth and defaults, which LLMSettings already carries.
    LLMProvider.OPENAI: OpenAICompatAdapter(),
    LLMProvider.OLLAMA: OpenAICompatAdapter(),
    LLMProvider.ANTHROPIC: AnthropicAdapter(),
    LLMProvider.GEMINI: GeminiAdapter(),
}


def adapter_for(provider: LLMProvider) -> Adapter:
    """The adapter for ``provider``; OpenAI-compatible is the fallback."""
    return _ADAPTERS.get(provider, _ADAPTERS[LLMProvider.OPENAI_COMPATIBLE])


__all__ = ["Adapter", "adapter_for", "AnthropicAdapter", "GeminiAdapter", "OpenAICompatAdapter"]
