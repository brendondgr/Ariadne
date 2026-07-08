#!/usr/bin/env python3
"""The conversational orchestration super-graph.

Wires the layered architecture the analyst asked for around the existing
pipeline (which is reused verbatim inside the Graph Extraction node):

    START
      -> orchestration (resolve references from memory)
      -> router
          -[quick]-> answer -> finalize -> END
          -[graph]-> extraction -> validation
                        -[insufficient & under cap]-> extraction
                        -[sufficient / capped]------> answer -> finalize -> END

Every node emits its custom stream events (``status``/``context``/``route``/
forwarded pipeline events/``validation``/``final``/``conversation``/``done``);
``iter_conversation`` in ``main`` drains them.

All LLM clients default to the config's shared client (off by default ->
deterministic path: route=graph, validation=pass, answer=narrative). Tests inject
per-role stubs and an alternate extraction runner so no live backend is needed.
"""

from __future__ import annotations

from typing import Any, Callable

from langgraph.graph import END, START, StateGraph

from utils.conversation.agents._common import emit_event
from utils.conversation.agents.answer import make_answer_node
from utils.conversation.agents.graph_extraction import default_runner, make_extraction_node
from utils.conversation.agents.orchestration import make_orchestration_node
from utils.conversation.agents.router import ROUTE_QUICK, make_router_node
from utils.conversation.agents.validation import VERDICT_INSUFFICIENT, make_validation_node
from utils.conversation.config import ConversationConfig
from utils.conversation.llm import ConversationLLM
from utils.conversation.state import ConversationState

# A persist hook (Step 6) runs at finalize: it records the turn and returns the
# thread title. ``(state, status, exit_code) -> title``.
PersistHook = Callable[..., str]


def _route_decider(state: dict[str, Any]) -> str:
    return ROUTE_QUICK if state.get("route") == ROUTE_QUICK else "graph"


def _validation_decider(state: dict[str, Any]) -> str:
    return "retry" if state.get("validation_verdict") == VERDICT_INSUFFICIENT else "done"


def _make_finalize_node(persist: PersistHook | None):
    def finalize_node(state: dict[str, Any]) -> dict[str, Any]:
        if state.get("route") == ROUTE_QUICK:
            status, exit_code = "answered", 0
        else:
            status = state.get("status") or "answered"
            exit_code = int(state.get("exit_code", 0))

        title = ""
        if persist is not None:
            title = persist(state, status=status, exit_code=exit_code) or ""

        emit_event(
            (
                "conversation",
                {"conversation_id": state.get("conversation_id", ""), "title": title},
            )
        )
        emit_event(("done", {"status": status, "exit_code": exit_code}))
        return {"status": status, "exit_code": exit_code}

    return finalize_node


def build_conversation_graph(
    config: ConversationConfig,
    *,
    runner: Callable[..., Any] = default_runner,
    orchestration_client: ConversationLLM | None = None,
    router_client: ConversationLLM | None = None,
    validation_client: ConversationLLM | None = None,
    answer_client: ConversationLLM | None = None,
    persist: PersistHook | None = None,
    pipeline_kwargs: dict[str, Any] | None = None,
):
    """Compile the conversational orchestration graph."""
    graph = StateGraph(ConversationState)
    graph.add_node("orchestration", make_orchestration_node(config, orchestration_client))
    graph.add_node("router", make_router_node(config, router_client))
    graph.add_node(
        "extraction",
        make_extraction_node(config, runner=runner, pipeline_kwargs=pipeline_kwargs),
    )
    graph.add_node("validation", make_validation_node(config, validation_client))
    graph.add_node("answer", make_answer_node(config, answer_client))
    graph.add_node("finalize", _make_finalize_node(persist))

    graph.add_edge(START, "orchestration")
    graph.add_edge("orchestration", "router")
    graph.add_conditional_edges(
        "router", _route_decider, {ROUTE_QUICK: "answer", "graph": "extraction"}
    )
    graph.add_edge("extraction", "validation")
    graph.add_conditional_edges(
        "validation", _validation_decider, {"retry": "extraction", "done": "answer"}
    )
    graph.add_edge("answer", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()
