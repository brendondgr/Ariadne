#!/usr/bin/env python3
"""The final Answer agent.

Both paths converge here to produce the conversational reply the analyst reads:

* quick path — a memory-grounded answer that may use ONLY facts already
  established in the thread (or ask for clarification). No new graph facts.
* graph path — wraps the verified synthesis narrative in a conversation-aware
  reply, keeping the grounded synthesis card as the trust surface beneath it.

Deterministic fallbacks (LLM off or failing):

* graph path -> the synthesis narrative verbatim (identical to today's grounded
  answer — the LLM only adds conversational continuity, never facts).
* quick path -> a summary of the known facts, or an honest clarification prompt.
"""

from __future__ import annotations

from typing import Any

from utils.conversation.agents._common import (
    emit_event,
    known_facts,
    render_history_messages,
)
from utils.conversation.agents.router import ROUTE_QUICK
from utils.conversation.config import ConversationConfig
from utils.conversation.llm import ConversationLLM, LLMUnavailable
from utils.synthesis.contracts import SynthesizedAnswer

_QUICK_SYSTEM = (
    "You are a cybersecurity assistant continuing a conversation. Answer the "
    "user's latest message using ONLY facts already established earlier in this "
    "conversation (listed below) plus general conversational context. You must "
    "NOT introduce any new ATT&CK/CAPEC facts, technique names, mappings, or "
    "mitigations that are not in the established facts. If the answer requires "
    "information not present, say you'll need to look it up in the graphs and "
    "ask the user to confirm. Be concise and natural."
)

_GRAPH_SYSTEM = (
    "You are a cybersecurity assistant continuing a conversation. A grounded, "
    "verified answer to the user's question was produced from the knowledge "
    "graphs and is provided below as GROUNDED ANSWER. Rewrite it into a natural, "
    "conversational reply that connects to what was discussed earlier. Preserve "
    "every fact exactly; do NOT add, drop, or alter any technique id, name, "
    "mapping, or mitigation. Do not invent citations."
)


def _grounded_text(answer: SynthesizedAnswer | None) -> str:
    if answer is None:
        return ""
    return (answer.narrative or answer.headline or "").strip()


def compose_answer(
    state: dict[str, Any],
    config: ConversationConfig,
    client: ConversationLLM | None = None,
) -> tuple[str, str]:
    """Return ``(final_answer, composer)`` where composer is ``llm``/``deterministic``."""
    client = client or ConversationLLM(config.llm)
    route = state.get("route", "graph")
    question = state.get("question", "")
    history = state.get("history")
    facts = known_facts(history, config.history_turns)

    if route == ROUTE_QUICK:
        return _compose_quick(question, history, facts, config, client)
    return _compose_graph(question, history, state.get("answer"), config, client)


def _compose_quick(question, history, facts, config, client) -> tuple[str, str]:
    if client.enabled:
        fact_block = (
            "Established facts:\n- " + "\n- ".join(facts)
            if facts
            else "No specific facts have been established yet."
        )
        messages = (
            [{"role": "system", "content": _QUICK_SYSTEM}]
            + render_history_messages(history, config.history_turns)
            + [{"role": "user", "content": f"{fact_block}\n\nMessage: {question}"}]
        )
        try:
            return client.complete(messages, max_tokens=config.llm.max_tokens), "llm"
        except LLMUnavailable:
            pass
    # Deterministic fallback.
    if facts:
        return "From what we've discussed:\n- " + "\n- ".join(facts), "deterministic"
    return (
        "Could you clarify what you'd like to know? I can look it up in the "
        "ATT&CK and CAPEC graphs.",
        "deterministic",
    )


def _compose_graph(question, history, answer, config, client) -> tuple[str, str]:
    grounded = _grounded_text(answer)
    if not grounded:
        grounded = (
            "I couldn't find grounded evidence for that in the ATT&CK or CAPEC "
            "graphs."
        )
        return grounded, "deterministic"
    if client.enabled:
        messages = (
            [{"role": "system", "content": _GRAPH_SYSTEM}]
            + render_history_messages(history, config.history_turns)
            + [
                {
                    "role": "user",
                    "content": (
                        f"Question: {question}\n\nGROUNDED ANSWER:\n{grounded}"
                    ),
                }
            ]
        )
        try:
            return client.complete(messages, max_tokens=config.llm.max_tokens), "llm"
        except LLMUnavailable:
            pass
    # Deterministic fallback: the verified narrative verbatim.
    return grounded, "deterministic"


def make_answer_node(
    config: ConversationConfig, client: ConversationLLM | None = None
):
    """Build the LangGraph node that composes the final conversational reply."""

    def answer_node(state: dict[str, Any]) -> dict[str, Any]:
        final_answer, composer = compose_answer(state, config, client)
        answer = state.get("answer")
        final = {
            "final_answer": final_answer,
            "route": state.get("route", "graph"),
            "composer": composer,
            "grounded": bool(_grounded_text(answer)) or state.get("route") == ROUTE_QUICK,
        }
        emit_event(("final", final))
        return {
            "final_answer": final_answer,
            "final": final,
            "trace": [{"node": "answer", "composer": composer}],
        }

    return answer_node
