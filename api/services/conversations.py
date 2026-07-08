"""Conversation-thread CRUD and the memory-inclusive conversation SSE stream.

This service owns persistence: it reads/writes threads through the
:class:`ConversationStore`, rebuilds each turn's memory from stored turns, drives
``iter_conversation``, presents its events as SSE (reusing the query service's
pipeline renderer so the pipeline looks identical), and — when the turn finishes —
records the user + assistant turns and auto-titles a brand-new thread.

The existing ``/api/query`` path is untouched; conversational turns ride here.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Iterator

from utils.conversation.config import ConversationConfig, conversation_db_path
from utils.conversation.llm import ConversationLLM
from utils.conversation.main import iter_conversation
from utils.conversation.naming import title_for
from utils.conversation.persistence import facts_from_synthesized, history_from_turns
from utils.conversation.store import ConversationNotFound, ConversationStore
from utils.orchestration.main import PipelineRun
from api.services.query import render_pipeline_event

logger = logging.getLogger("ariadne.api.conversations")

# Raw pipeline events forwarded through the conversation stream that need the
# query renderer; everything else is a conversation-native JSON dict.
_PIPELINE_EVENTS = {
    "probe",
    "plan",
    "skipped",
    "specialist-start",
    "specialist",
    "evidence",
    "answer",
}

_store: ConversationStore | None = None


def get_store() -> ConversationStore:
    """Return the process-wide conversation store (lazily opened)."""
    global _store
    if _store is None:
        _store = ConversationStore(conversation_db_path())
    return _store


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# --------------------------------------------------------------------------- #
# CRUD
# --------------------------------------------------------------------------- #


def list_conversations(*, store: ConversationStore | None = None) -> list[dict[str, Any]]:
    store = store or get_store()
    return [c.to_dict() for c in store.list_conversations()]


def create_conversation(
    title: str | None = None, *, store: ConversationStore | None = None
) -> dict[str, Any]:
    store = store or get_store()
    return store.create_conversation((title or "New conversation").strip() or "New conversation").to_dict()


def get_conversation(
    conversation_id: str, *, store: ConversationStore | None = None
) -> dict[str, Any] | None:
    store = store or get_store()
    convo = store.get_conversation(conversation_id)
    if convo is None:
        return None
    turns = store.list_turns(conversation_id)
    return {**convo.to_dict(), "turns": [t.to_dict() for t in turns]}


def rename_conversation(
    conversation_id: str, title: str, *, store: ConversationStore | None = None
) -> dict[str, Any] | None:
    store = store or get_store()
    try:
        return store.rename_conversation(conversation_id, title.strip() or "Untitled").to_dict()
    except ConversationNotFound:
        return None


def delete_conversation(
    conversation_id: str, *, store: ConversationStore | None = None
) -> bool:
    store = store or get_store()
    return store.delete_conversation(conversation_id)


# --------------------------------------------------------------------------- #
# Streaming a conversational turn
# --------------------------------------------------------------------------- #


def stream_conversation_events(
    question: str,
    conversation_id: str,
    *,
    mode: str = "query",
    use_llm: bool = False,
    store: ConversationStore | None = None,
    config: ConversationConfig | None = None,
    naming_client: ConversationLLM | None = None,
    **build_kwargs: Any,
) -> Iterator[str]:
    """Yield SSE frames for one conversational turn and persist it on completion.

    ``build_kwargs`` pass through to the conversation graph (injected clients /
    runner) for tests.
    """
    store = store or get_store()
    config = (config or ConversationConfig.from_env()).with_llm_enabled(use_llm)
    drafter = "llm" if use_llm else "deterministic"

    try:
        question = (question or "").strip()
        if not question:
            yield _sse("error", {"message": "Question must not be empty."})
            return

        convo = store.get_conversation(conversation_id)
        if convo is None:
            yield _sse("error", {"message": f"Conversation {conversation_id!r} not found."})
            return

        is_first_turn = convo.turn_count == 0
        history = history_from_turns(
            store.list_turns(conversation_id), limit=config.history_turns
        )

        run = PipelineRun(question=question, mode=mode)
        # Accumulators for persistence at the terminal `conversation` event.
        acc: dict[str, Any] = {
            "resolved_question": question,
            "route": "graph",
            "route_reason": "",
            "final_answer": "",
            "validation": None,
            "synthesized": None,
            "status": "answered",
            "exit_code": 0,
            "events": [],
        }

        for event, payload in iter_conversation(
            question,
            conversation_id=conversation_id,
            history=history,
            mode=mode,
            use_llm=use_llm,
            config=config,
            run=run,
            **build_kwargs,
        ):
            # Snapshot the raw synthesis object (for facts) before it is rendered.
            if event == "answer" and isinstance(payload, dict):
                acc["synthesized"] = payload.get("synthesized")

            name, data = _present(event, payload, run)

            # Track conversation-native fields for the stored turn.
            if event == "context":
                acc["resolved_question"] = data.get("resolved_question", question)
            elif event == "route":
                acc["route"] = data.get("decision", "graph")
                acc["route_reason"] = data.get("reason", "")
            elif event == "validation":
                acc["validation"] = data
            elif event == "final":
                acc["final_answer"] = data.get("final_answer", "")
            elif event == "done":
                acc["status"] = data.get("status", "answered")
                acc["exit_code"] = data.get("exit_code", 0)

            if event == "conversation":
                # Persist the turn, auto-title a new thread, and enrich the event.
                title = _persist_turn(
                    store, conversation_id, question, mode, drafter, acc,
                    config, is_first_turn, naming_client,
                )
                yield _sse("conversation", {**data, "title": title})
                continue

            if name is not None:
                acc["events"].append({"type": name, "data": data})
                yield _sse(name, data)

    except Exception as exc:  # noqa: BLE001 - any failure becomes a clean error event
        logger.exception("conversation pipeline failed")
        yield _sse("error", {"message": f"{type(exc).__name__}: {exc}"})


def _present(
    event: str, payload: dict[str, Any], run: PipelineRun
) -> tuple[str | None, dict[str, Any]]:
    """Return the ``(name, json)`` to stream for one conversation event."""
    if event in _PIPELINE_EVENTS:
        rendered = render_pipeline_event(event, payload, run)
        if rendered is None:
            return None, {}
        return rendered
    if event == "done":
        # Enrich the conversation's terminal done with the recorded timings.
        return "done", {**payload, "timings": run.timings}
    # Conversation-native events (status/context/route/validation/final/conversation)
    # are already JSON-serializable dicts.
    return event, payload


def _persist_turn(
    store: ConversationStore,
    conversation_id: str,
    question: str,
    mode: str,
    drafter: str,
    acc: dict[str, Any],
    config: ConversationConfig,
    is_first_turn: bool,
    naming_client: ConversationLLM | None,
) -> str:
    """Record the user + assistant turns and return the (possibly new) thread title."""
    facts = facts_from_synthesized(acc.get("synthesized"))
    assistant_payload = {
        "final_answer": acc["final_answer"],
        "route": acc["route"],
        "route_reason": acc["route_reason"],
        "resolved_question": acc["resolved_question"],
        "validation": acc["validation"],
        "facts": facts,
        "status": acc["status"],
        "exit_code": acc["exit_code"],
        "events": acc["events"],
    }
    store.append_turn(
        conversation_id, "user", question=question, mode=mode, drafter=drafter
    )
    store.append_turn(
        conversation_id,
        "assistant",
        question=acc["resolved_question"],
        payload=assistant_payload,
        mode=mode,
        drafter=drafter,
        route=acc["route"],
    )

    if is_first_turn:
        title = title_for(question, config, naming_client)
        store.rename_conversation(conversation_id, title)
        return title
    convo = store.get_conversation(conversation_id)
    return convo.title if convo else ""
