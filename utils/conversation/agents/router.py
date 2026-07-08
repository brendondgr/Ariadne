#!/usr/bin/env python3
"""The redirect (router) agent.

Given the user's message and the thread so far, decide whether the turn can be
answered from memory alone (``quick``) or needs a fresh graph query (``graph``).

Grounding-safe fallback: whenever the LLM is disabled, errors, or returns an
unparseable/unknown decision, the router chooses ``graph``. That guarantees we
never silently answer a fact-seeking question from ungrounded model knowledge —
the whole point of the project's provenance guarantee.
"""

from __future__ import annotations

from typing import Any

from utils.conversation.agents._common import (
    known_facts,
    render_history_messages,
)
from utils.conversation.config import ConversationConfig
from utils.conversation.llm import ConversationLLM, LLMUnavailable

ROUTE_QUICK = "quick"
ROUTE_GRAPH = "graph"

_SYSTEM = (
    "You are the router for a cybersecurity knowledge-graph assistant. Every "
    "factual answer in this system must be grounded in graph evidence (MITRE "
    "ATT&CK via Neo4j, CAPEC via Gremlin). Decide how to handle the user's "
    "latest message.\n\n"
    "Choose \"quick\" ONLY when the message can be fully answered from the "
    "conversation so far — e.g. asking to rephrase/summarize what was already "
    "said, a clarification, a greeting, or a meta-question about the "
    "discussion. In quick mode NO new graph facts may be introduced.\n\n"
    "Choose \"graph\" whenever the message asks for any new fact about ATT&CK "
    "techniques, CAPEC patterns, mitigations, mappings, or anything not already "
    "established in the conversation. When in doubt, choose \"graph\".\n\n"
    "Respond with a single JSON object: "
    '{"route": "quick" | "graph", "reason": "<short reason>"}.'
)


def classify_route(
    question: str,
    history: list[dict[str, Any]] | None,
    config: ConversationConfig,
    client: ConversationLLM | None = None,
) -> tuple[str, str]:
    """Return ``(route, reason)`` for the given message."""
    # Hard override: if quick answers are disabled, always run graph extraction.
    if not config.quick_answer_enabled:
        return ROUTE_GRAPH, "quick answers disabled by config"

    client = client or ConversationLLM(config.llm)
    if not client.enabled:
        return ROUTE_GRAPH, "LLM disabled — defaulting to graph extraction"

    facts = known_facts(history, config.history_turns)
    context = render_history_messages(history, config.history_turns)
    fact_note = (
        "Facts already established this conversation:\n- "
        + "\n- ".join(facts)
        if facts
        else "No facts have been established this conversation yet."
    )
    messages = (
        [{"role": "system", "content": _SYSTEM}]
        + context
        + [
            {
                "role": "user",
                "content": f"{fact_note}\n\nLatest message: {question}",
            }
        ]
    )
    try:
        raw = client.complete(messages, max_tokens=200)
        from utils.conversation.agents._common import extract_json_object

        data = extract_json_object(raw)
    except (LLMUnavailable, ValueError):
        return ROUTE_GRAPH, "router LLM unavailable — defaulting to graph extraction"

    route = str(data.get("route", "")).strip().lower()
    reason = str(data.get("reason", "")).strip() or "router decision"
    if route not in (ROUTE_QUICK, ROUTE_GRAPH):
        return ROUTE_GRAPH, "unrecognized route — defaulting to graph extraction"
    return route, reason


def make_router_node(
    config: ConversationConfig, client: ConversationLLM | None = None
):
    """Build the LangGraph node that writes the route decision into state."""

    def route_node(state: dict[str, Any]) -> dict[str, Any]:
        question = state.get("resolved_question") or state.get("question", "")
        route, reason = classify_route(
            question, state.get("history"), config, client
        )
        return {
            "route": route,
            "route_reason": reason,
            "trace": [{"node": "router", "route": route, "reason": reason}],
        }

    return route_node
