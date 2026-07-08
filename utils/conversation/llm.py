#!/usr/bin/env python3
"""A small OpenAI-compatible chat client shared by the conversational agents.

The router, answer, validation, and naming agents all make short
classification / generation calls against the same endpoint. This wraps the
``requests.post(... /chat/completions)`` pattern used across the codebase behind
one testable seam. When the LLM is disabled or the call fails, callers get
:class:`LLMUnavailable` and fall back to deterministic behavior — no agent is
allowed to hard-fail a turn because the model is down.
"""

from __future__ import annotations

from utils.conversation.config import ConversationLLMConfig


class LLMUnavailable(RuntimeError):
    """Raised when the LLM is disabled or the chat call cannot be completed."""


class ConversationLLM:
    """Thin OpenAI-compatible chat wrapper bound to one LLM config."""

    def __init__(self, config: ConversationLLMConfig) -> None:
        self._config = config

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> str:
        """Return the assistant message content, or raise :class:`LLMUnavailable`."""
        if not self._config.enabled:
            raise LLMUnavailable("conversation LLM disabled")

        import requests

        payload = {
            "model": self._config.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens or self._config.max_tokens,
        }
        try:
            resp = requests.post(
                self._config.endpoint, json=payload, timeout=self._config.timeout_s
            )
        except requests.RequestException as exc:  # pragma: no cover - network
            raise LLMUnavailable(f"request failed: {exc}") from exc
        if resp.status_code != 200:
            raise LLMUnavailable(f"HTTP {resp.status_code}: {resp.text[:200]}")
        try:
            content = resp.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMUnavailable(f"unexpected response shape: {exc}") from exc
        if not content:
            raise LLMUnavailable("model returned no content")
        return content
