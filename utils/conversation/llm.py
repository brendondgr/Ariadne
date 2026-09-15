#!/usr/bin/env python3
"""A small OpenAI-compatible chat client shared by the conversational agents.

The router, answer, validation, and naming agents all make short
classification / generation calls against the same endpoint. This wraps the
``requests.post(... /chat/completions)`` pattern used across the codebase behind
one testable seam. When the LLM is disabled or the call fails, callers get
:class:`LLMUnavailable` and fall back to deterministic behavior — no agent is
allowed to hard-fail a turn because the model is down.

Every reply also carries a ``finish_reason`` and a ``usage`` block. A
``finish_reason == "length"`` means the model stopped because it ran out of
output budget (the request ``max_tokens`` or, more often on a local server, the
model's context window minus the prompt) — the reply is *truncated*, not
complete. Ignoring that signal is how a chopped-off, mid-word answer reaches the
analyst. :meth:`ConversationLLM.complete_verbose` surfaces it (and logs it with
token counts) so callers can react; :meth:`ConversationLLM.complete` keeps the
plain string contract for the short classification callers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from utils.conversation.config import ConversationLLMConfig
from utils.llm import LLMUnavailable as TransportUnavailable
from utils.llm import chat as llm_chat

logger = logging.getLogger("ariadne.conversation.llm")

# The OpenAI-compatible ``finish_reason`` value that means "stopped at the output
# limit" — i.e. the content is truncated rather than a complete answer.
FINISH_LENGTH = "length"


class LLMUnavailable(RuntimeError):
    """Raised when the LLM is disabled or the chat call cannot be completed."""


@dataclass(frozen=True)
class CompletionResult:
    """One chat completion plus the signals needed to detect truncation.

    ``content`` is normalized to a string ("" when the server returns null on a
    length stop). ``finish_reason`` is the raw stop reason ("stop", "length",
    …). ``usage`` is the token-accounting block (prompt/completion/total), empty
    when the server omits it.
    """

    content: str
    finish_reason: str = ""
    usage: dict[str, Any] = field(default_factory=dict)

    @property
    def truncated(self) -> bool:
        """True when the model stopped because it hit its output-token limit."""
        return self.finish_reason == FINISH_LENGTH


class ConversationLLM:
    """Thin OpenAI-compatible chat wrapper bound to one LLM config."""

    def __init__(self, config: ConversationLLMConfig) -> None:
        self._config = config

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    def complete_verbose(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> CompletionResult:
        """Return the full :class:`CompletionResult`, or raise :class:`LLMUnavailable`.

        Unlike :meth:`complete`, this does *not* raise on empty content — a
        truncation that produced no usable text is a real, reportable outcome
        the caller may want to handle (e.g. keep the deterministic answer). A
        ``length`` finish is logged with token counts so the operator can see
        when the model's context window — not ``max_tokens`` — is the ceiling.
        """
        if not self._config.enabled:
            raise LLMUnavailable("conversation LLM disabled")

        settings = self._config.llm_settings()
        budget = max_tokens or settings.max_tokens
        # Send the reasoning cap, which this client did not.
        #
        # `chat()` has always taken a `sampling` block and this caller never
        # passed one, so `thinking_token_budget` never reached the wire for ANY
        # conversation agent -- router, orchestration, validation, answer or the
        # thread titler. The workbench's Thinking control therefore governed only
        # the synthesis narrator while appearing to govern the two stages that
        # actually cost the time: validation ~28.6 s and answer ~10.7 s of a
        # 43 s turn (`EXP-2026-09-020` A-8, A-9).
        #
        # Only the budget is set here, not the full greedy block: this client
        # takes an explicit `temperature` per call (the titler asks for 0.3), and
        # `sampling_params` would overwrite it with 0.
        sampling: dict[str, object] | None = None
        if settings.thinking_budget or settings.thinking_budget_explicit:
            sampling = {"thinking_token_budget": settings.thinking_budget}
        try:
            completion = llm_chat(
                settings, messages, max_tokens=budget, temperature=temperature,
                sampling=sampling,
            )
        except TransportUnavailable as exc:
            # Re-raised as this module's own LLMUnavailable so every caller's
            # existing `except LLMUnavailable` keeps working unchanged.
            raise LLMUnavailable(str(exc)) from exc

        usage = {
            "prompt_tokens": completion.usage.prompt_tokens,
            "completion_tokens": completion.usage.completion_tokens,
            "total_tokens": completion.usage.total_tokens,
        } if completion.usage.reported else {}
        result = CompletionResult(
            content=completion.content,
            finish_reason=completion.finish_reason,
            usage=usage,
        )
        if result.truncated:
            logger.warning(
                "conversation LLM output truncated (finish_reason=length): "
                "prompt_tokens=%s completion_tokens=%s max_tokens=%s — raise "
                "ARIADNE_LLM_MAX_TOKENS (or this stage's override) or the "
                "model's context window",
                usage.get("prompt_tokens"),
                usage.get("completion_tokens"),
                budget,
            )
        return result

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> str:
        """Return the assistant message content, or raise :class:`LLMUnavailable`.

        The plain-string contract for the short classification/generation callers
        (router, validation, orchestration, naming). Empty content still raises
        so those callers fall back deterministically — but a length stop that
        produced nothing is reported as a truncation, not a dead model, so the
        operator reaches for the right knob.
        """
        result = self.complete_verbose(
            messages, max_tokens=max_tokens, temperature=temperature
        )
        if not result.content:
            if result.truncated:
                raise LLMUnavailable(
                    "model output truncated before any content (raise "
                    "CONVERSATION_LLM_MAX_TOKENS or the model's context window)"
                )
            raise LLMUnavailable("model returned no content")
        return result.content
