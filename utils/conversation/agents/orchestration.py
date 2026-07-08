#!/usr/bin/env python3
"""The Orchestration (context-resolution) entry agent.

The first node of every turn. It rewrites the user's latest message into a
standalone question by resolving references against the thread so far — e.g.
"tell me more about T1598" becomes "Provide details on ATT&CK technique T1598
(Phishing for Information)". Downstream nodes (router, graph extraction) then
operate on a self-contained question.

Deterministic fallback (LLM off / first turn / failure): use the message as-is.
That keeps single-turn behavior identical to today and never blocks a turn.
"""

from __future__ import annotations

from typing import Any

from utils.conversation.agents._common import (
    emit_event,
    history_is_empty,
    render_history_messages,
)
from utils.conversation.config import ConversationConfig
from utils.conversation.llm import ConversationLLM, LLMUnavailable

_SYSTEM = (
    "You rewrite the user's latest message into a single standalone question "
    "for a cybersecurity knowledge-graph assistant, resolving pronouns and "
    "references (e.g. 'it', 'that technique', 'the second one') using the "
    "conversation so far. Preserve the user's intent exactly. Do NOT answer the "
    "question or add facts — only rewrite it. If the message is already "
    "standalone, return it unchanged. Respond with ONLY the rewritten question, "
    "no preamble."
)


def resolve_question(
    question: str,
    history: list[dict[str, Any]] | None,
    config: ConversationConfig,
    client: ConversationLLM | None = None,
) -> tuple[str, bool]:
    """Return ``(resolved_question, rewritten)``."""
    client = client or ConversationLLM(config.llm)
    if history_is_empty(history) or not client.enabled:
        return question, False

    messages = (
        [{"role": "system", "content": _SYSTEM}]
        + render_history_messages(history, config.history_turns)
        + [{"role": "user", "content": question}]
    )
    try:
        rewritten = client.complete(messages, max_tokens=200).strip()
    except LLMUnavailable:
        return question, False
    if not rewritten:
        return question, False
    return rewritten, rewritten.strip() != question.strip()


def make_orchestration_node(
    config: ConversationConfig, client: ConversationLLM | None = None
):
    """Build the entry node that resolves references and emits the resolved question."""

    def orchestration_node(state: dict[str, Any]) -> dict[str, Any]:
        question = state.get("question", "")
        resolved, rewritten = resolve_question(
            question, state.get("history"), config, client
        )
        emit_event(
            ("status", {"phase": "orchestrating", "message": "Understanding the request"})
        )
        emit_event(("context", {"resolved_question": resolved, "rewritten": rewritten}))
        return {
            "resolved_question": resolved,
            "trace": [
                {"node": "orchestration", "rewritten": rewritten, "resolved": resolved}
            ],
        }

    return orchestration_node
