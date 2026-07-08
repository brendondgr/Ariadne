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
    emit_event,
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
    # A network/timeout error is distinct from an unparseable reply — surface the
    # real cause instead of a blanket "unavailable" so a flaky endpoint is
    # diagnosable. Either way the grounding-safe default is graph extraction.
    try:
        raw = client.complete(messages, max_tokens=200)
    except LLMUnavailable as exc:
        return ROUTE_GRAPH, f"router LLM error ({exc}) — defaulting to graph"

    route, reason = _parse_route(raw)
    if route not in (ROUTE_QUICK, ROUTE_GRAPH):
        return ROUTE_GRAPH, "router reply unparseable — defaulting to graph"
    return route, reason


def _parse_route(raw: str) -> tuple[str, str]:
    """Extract ``(route, reason)`` from a model reply.

    Prefers a JSON object (``{"route": ..., "reason": ...}``, possibly inside a
    ```` ```json ```` fence). Falls back to a lenient keyword scan so a model
    that answers in prose ("route: quick because …") still yields a decision.
    """
    from utils.conversation.agents._common import extract_json_object

    try:
        data = extract_json_object(raw)
        route = str(data.get("route", "")).strip().lower()
        reason = str(data.get("reason", "")).strip() or "router decision"
        if route in (ROUTE_QUICK, ROUTE_GRAPH):
            return route, reason
    except ValueError:
        pass

    # Lenient fallback: pick whichever decision word appears first, if only one
    # is present (avoids guessing when the reasoning mentions both).
    low = raw.lower()
    has_quick, has_graph = ROUTE_QUICK in low, "graph" in low
    if has_quick and not has_graph:
        return ROUTE_QUICK, "router decision (lenient parse)"
    if has_graph and not has_quick:
        return ROUTE_GRAPH, "router decision (lenient parse)"
    return "", "router reply unparseable"


def make_router_node(
    config: ConversationConfig, client: ConversationLLM | None = None
):
    """Build the LangGraph node that writes the route decision into state."""

    def route_node(state: dict[str, Any]) -> dict[str, Any]:
        question = state.get("resolved_question") or state.get("question", "")
        route, reason = classify_route(
            question, state.get("history"), config, client
        )
        emit_event(("route", {"decision": route, "reason": reason}))
        return {
            "route": route,
            "route_reason": reason,
            "trace": [{"node": "router", "route": route, "reason": reason}],
        }

    return route_node
