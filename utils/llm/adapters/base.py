#!/usr/bin/env python3
"""The adapter contract, plus the pieces every adapter shares."""

from __future__ import annotations

from typing import Any, Protocol

from utils.llm.config import LLMSettings
from utils.llm.types import ChatResult, Message, ModelInfo


class Adapter(Protocol):
    """Translate between Ariadne's normalized types and one provider's wire format."""

    #: Used in log lines and in the probe verdict shown to the operator.
    name: str

    def chat_request(
        self,
        settings: LLMSettings,
        messages: list[Message],
        *,
        max_tokens: int,
        temperature: float,
        sampling: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, str], dict[str, Any]]:
        """Build ``(url, headers, json_payload)`` for one completion."""
        ...

    def parse_chat(self, body: dict[str, Any]) -> ChatResult:
        """Turn a decoded response body into a :class:`ChatResult`."""
        ...

    def models_request(self, settings: LLMSettings) -> tuple[str, dict[str, str]] | None:
        """``(url, headers)`` for model listing, or ``None`` if unsupported."""
        ...

    def parse_models(self, body: dict[str, Any]) -> list[ModelInfo]:
        """Turn a decoded listing body into normalized model entries."""
        ...


def split_system(messages: list[Message]) -> tuple[str, list[Message]]:
    """Pull system turns out of the list, joined, for providers that demand it.

    Anthropic and Gemini both reject a ``system`` role inside the message array —
    Anthropic with a 400, Gemini by ignoring it, which is worse. Several system
    messages are joined rather than dropped: the codebase builds prompts by
    appending context blocks, so silently keeping only the first would delete
    grounding the caller thought it had sent.
    """
    system = "\n\n".join(m.content for m in messages if m.role == "system" and m.content)
    rest = [m for m in messages if m.role != "system"]
    return system, rest


def bearer(settings: LLMSettings) -> dict[str, str]:
    """An ``Authorization`` header when a key is configured, else nothing.

    Omitting the header entirely (rather than sending an empty one) is what keeps
    a local server working: several reject a malformed Authorization outright,
    and no Ariadne call site sent one at all before this module existed.
    """
    return {"Authorization": f"Bearer {settings.api_key}"} if settings.api_key else {}
