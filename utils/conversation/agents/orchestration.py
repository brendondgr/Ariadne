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
from utils.conversation.persistence import entity_ids_in, referential_followup

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
        rewritten = client.complete(messages, max_tokens=config.llm.max_tokens).strip()
    except LLMUnavailable:
        return question, False
    if not rewritten:
        return question, False
    return rewritten, rewritten.strip() != question.strip()


def anchor_question(
    resolved: str,
    original: str,
    anchor: list[tuple[str, str]] | None,
) -> tuple[str, str]:
    """Deterministically append the thread's focus entity to an entity-free follow-up.

    Returns ``(question, anchor_id)`` — ``anchor_id`` is ``""`` when no anchoring
    was applied. Gated so it only fires when the resolved question names no entity
    of its own *and* the original message reads as a continuation *and* an anchor
    is held. This is the LLM-free safety net for the case that broke conversational
    memory: the reference-resolution LLM being unavailable (so ``resolved`` is the
    raw follow-up) still leaves the planner with a concrete entity to route on.
    """
    if not anchor or entity_ids_in(resolved) or not referential_followup(original):
        return resolved, ""
    anchor_id, name = anchor[0]
    if not anchor_id:
        return resolved, ""
    label = f"{anchor_id} — {name}" if name else anchor_id
    tail = "." if resolved.strip().endswith((".", "?", "!")) else ""
    return f"{resolved.rstrip()}{tail} (Regarding {label}.)", anchor_id


def make_orchestration_node(
    config: ConversationConfig, client: ConversationLLM | None = None
):
    """Build the entry node that resolves references and emits the resolved question."""

    def orchestration_node(state: dict[str, Any]) -> dict[str, Any]:
        question = state.get("question", "")
        resolved, rewritten = resolve_question(
            question, state.get("history"), config, client
        )
        # Deterministic fallback anchor: if reference resolution left the question
        # without a concrete entity (LLM off/unavailable or a rewrite that dropped
        # it), fold in the thread's held entity so retrieval stays on-topic.
        resolved, anchor_id = anchor_question(resolved, question, state.get("anchor"))
        emit_event(
            ("status", {"phase": "orchestrating", "message": "Understanding the request"})
        )
        emit_event(
            (
                "context",
                {
                    "resolved_question": resolved,
                    "rewritten": rewritten,
                    "anchored": bool(anchor_id),
                    "anchor_id": anchor_id,
                },
            )
        )
        return {
            "resolved_question": resolved,
            "trace": [
                {
                    "node": "orchestration",
                    "rewritten": rewritten,
                    "resolved": resolved,
                    "anchor_id": anchor_id,
                }
            ],
        }

    return orchestration_node
