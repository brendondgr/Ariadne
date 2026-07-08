#!/usr/bin/env python3
"""LLM auto-titling for conversation threads.

``title_for`` names a thread from its first user message. The LLM produces a
short, descriptive title; when the LLM is off or fails, a deterministic fallback
derives a clean title from the message itself, so every thread always gets a
sensible name and LLM-off builds stay reproducible.
"""

from __future__ import annotations

from utils.conversation.config import ConversationConfig
from utils.conversation.llm import ConversationLLM, LLMUnavailable

_MAX_TITLE_CHARS = 60

_SYSTEM = (
    "You name a conversation thread for a cybersecurity knowledge-graph "
    "assistant. Given the user's first message, return a short, specific title "
    "of at most 6 words. No quotes, no trailing punctuation, Title Case. Return "
    "ONLY the title."
)


def _clean(text: str) -> str:
    return " ".join(text.strip().split())


def deterministic_title(question: str) -> str:
    """Derive a title from the question text (the always-available fallback)."""
    cleaned = _clean(question)
    if not cleaned:
        return "New conversation"
    if len(cleaned) <= _MAX_TITLE_CHARS:
        return cleaned
    # Truncate at a word boundary within the limit.
    clipped = cleaned[:_MAX_TITLE_CHARS].rsplit(" ", 1)[0].strip()
    return (clipped or cleaned[:_MAX_TITLE_CHARS]).rstrip(",.;:") + "…"


def title_for(
    question: str,
    config: ConversationConfig,
    client: ConversationLLM | None = None,
) -> str:
    """Return a thread title for the first user message."""
    client = client or ConversationLLM(config.llm)
    if not client.enabled:
        return deterministic_title(question)
    messages = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": question},
    ]
    try:
        raw = client.complete(messages, max_tokens=32, temperature=0.3)
    except LLMUnavailable:
        return deterministic_title(question)
    title = _clean(raw).strip('"').rstrip(",.;:")
    if not title:
        return deterministic_title(question)
    if len(title) > _MAX_TITLE_CHARS:
        title = title[:_MAX_TITLE_CHARS].rsplit(" ", 1)[0].strip() + "…"
    return title
