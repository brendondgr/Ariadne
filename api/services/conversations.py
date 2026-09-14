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
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from typing import Any, Iterator

from utils.conversation.config import ConversationConfig, conversation_db_path
from utils.conversation.llm import ConversationLLM
from utils.conversation.main import iter_conversation
from utils.conversation.naming import deterministic_title, title_for
from utils.conversation.persistence import (
    conversation_anchor,
    dossier_payload,
    dossiers_from_records,
    facts_from_synthesized,
    history_from_turns,
    memory_injection,
    retrieved_anchor_ids,
)
from utils.conversation.store import ConversationNotFound, ConversationStore
from utils.orchestration.main import PipelineRun
from api.services.heartbeat import HEARTBEAT, with_heartbeat
from api.services.query import _keepalive, render_pipeline_event

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
    verify: bool = False,
    narrate: bool = False,
    thinking_budget: int | None = None,
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
    if thinking_budget is not None:
        config = replace(
            config, llm=replace(config.llm, thinking_budget=int(thinking_budget))
        )
    drafter = "llm" if use_llm else "deterministic"

    # Gate the two expensive agents individually rather than the whole layer.
    # `router` and `orchestration` stay on in every mode -- routing and reference
    # resolution are what make a thread conversational. `validation` and `answer`
    # are the costly ones: ~28.6 s and ~10.7 s of a 43 s turn whose pipeline
    # answered at 1.09 s (`EXP-2026-09-020` A-8).
    #
    # Injecting a disabled client is the existing mechanism rather than a new
    # branch: `evaluate_sufficiency` short-circuits to VERDICT_PASS when its
    # client is disabled, and the answer agent falls back to the pipeline's
    # composed narrative. `graph.py` already documents that pair as the
    # deterministic path. `setdefault` so an explicitly injected client (tests)
    # still wins.
    # Authoritative in BOTH directions. Declining to disable is not the same as
    # enabling: with CONVERSATION_LLM_ENABLED=false in the environment, a
    # `verify: on` that merely left the agent to the config left it off, and the
    # control silently did nothing (measured: 0.08 s for a turn that should have
    # cost ~30 s). The toggle on screen is the authority, which is the whole
    # point of making `with_llm_enabled` two-way.
    _on = ConversationLLM(replace(config.llm, enabled=True))
    _off = ConversationLLM(replace(config.llm, enabled=False))
    build_kwargs.setdefault("validation_client", _on if verify else _off)
    build_kwargs.setdefault("answer_client", _on if narrate else _off)

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
        # Title a new thread FIRST, and off the critical path.
        #
        # `title_for` reads the question and nothing else -- not the plan, not
        # the evidence, not the answer -- so its old position at the end of
        # `_persist_turn` was incidental rather than a dependency. There it cost
        # ~2.9s at the tail of a first turn and left the sidebar reading "New
        # conversation" until after the answer was already on screen.
        #
        # Started here it runs alongside the router and the pipeline, so it
        # costs nothing, and the title is emitted as soon as it resolves. The
        # titler already falls back to `deterministic_title(question)` when the
        # LLM is off or unavailable, so a slow or failed call degrades to the
        # same title it would have produced synchronously.
        title_pool: ThreadPoolExecutor | None = None
        title_future = None
        if is_first_turn:
            title_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="title")
            title_future = title_pool.submit(
                title_for, question, config, naming_client
            )
        title_sent = False

        turns = store.list_turns(conversation_id)
        history = history_from_turns(turns, limit=config.history_turns)
        # Deterministic (LLM-free) focus entities from the thread so an entity-free
        # follow-up ("explore the execution steps involved") stays anchored to the
        # just-discussed entity even when the reference-resolution LLM is down.
        anchor = conversation_anchor(turns)
        # Hybrid entity memory: an always-on index of held entities plus the full
        # dossier for the ones this turn refers to, injected as a synthetic
        # assistant entry (facts surface via known_facts; empty content is skipped
        # by render_history_messages) — no LangGraph agent changes required.
        injected_facts = memory_injection(question, turns)
        if injected_facts:
            history = [*history, {"role": "assistant", "content": "", "facts": injected_facts}]

        run = PipelineRun(question=question, mode=mode)
        # Accumulators for persistence at the terminal `conversation` event.
        acc: dict[str, Any] = {
            "resolved_question": question,
            "route": "graph",
            "route_reason": "",
            "final_answer": "",
            "validation": None,
            "synthesized": None,
            "evidence": None,
            "status": "answered",
            "exit_code": 0,
            "events": [],
        }

        # Same reason as the query stream: the chat pane watches a socket that
        # goes quiet for the whole of every LLM stage, and its watchdog cannot
        # tell that from a dead backend.
        for item in with_heartbeat(
            iter_conversation(
                question,
                conversation_id=conversation_id,
                history=history,
                anchor=anchor,
                mode=mode,
                use_llm=use_llm,
                narrate=narrate,
                config=config,
                run=run,
                **build_kwargs,
            )
        ):
            if item is HEARTBEAT:
                yield _keepalive()
                continue
            event, payload = item
            # Snapshot the raw synthesis object (facts) and federated evidence
            # (entity dossiers) before they are rendered. Both ride the `answer`
            # event; the earlier `evidence` event is a fallback source.
            if event == "answer" and isinstance(payload, dict):
                acc["synthesized"] = payload.get("synthesized")
                if payload.get("evidence") is not None:
                    acc["evidence"] = payload.get("evidence")
            if event == "evidence" and isinstance(payload, dict):
                acc["evidence"] = payload.get("evidence")

            # Emit the title the moment it is ready, without waiting on it.
            if title_future is not None and not title_sent and title_future.done():
                title_sent = True
                try:
                    early_title = title_future.result()
                except Exception:  # noqa: BLE001 - a failed title never sinks a turn
                    early_title = None
                if early_title:
                    store.rename_conversation(conversation_id, early_title)
                    yield _sse("title", {"conversation_id": conversation_id,
                                         "title": early_title})

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
                resolved_title = None
                if title_future is not None:
                    try:
                        # Bounded: the turn is already answered, and the titler
                        # falls back on its own, so a hung call must not hold the
                        # stream open.
                        resolved_title = title_future.result(timeout=5.0)
                    except Exception:  # noqa: BLE001 - fall back below
                        resolved_title = None
                title = _persist_turn(
                    store, conversation_id, question, mode, drafter, acc,
                    config, is_first_turn, naming_client, title=resolved_title,
                )
                yield _sse("conversation", {**data, "title": title})
                continue

            if name is not None:
                acc["events"].append({"type": name, "data": data})
                yield _sse(name, data)

    except Exception as exc:  # noqa: BLE001 - any failure becomes a clean error event
        logger.exception("conversation pipeline failed")
        yield _sse("error", {"message": f"{type(exc).__name__}: {exc}"})
    finally:
        # The titling worker outlives the generator if the client disconnects
        # mid-stream, so it is shut down on every exit path including that one.
        # `cancel_futures` drops a call that has not started; one already in
        # flight is left to finish rather than abandoned mid-request.
        pool = locals().get("title_pool")
        if pool is not None:
            pool.shutdown(wait=False, cancel_futures=True)


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
    title: str | None = None,
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
    # Cache any single-entity dossiers this turn retrieved, keyed by entity id, so
    # a later turn can pull one in without re-querying (hybrid on-demand memory).
    evidence = acc.get("evidence")
    records: list[Any] = []
    for result in getattr(evidence, "results", None) or []:
        records.extend(getattr(result, "records", None) or [])
    dossiers = dossiers_from_records(records)
    if dossiers:
        assistant_payload["entity_dossiers"] = dossier_payload(dossiers)
    # Record the focused primary ids this turn retrieved (the authoritative anchor
    # for a later entity-free follow-up); empty for a broad list or a miss.
    retrieved = retrieved_anchor_ids(evidence)
    if retrieved:
        assistant_payload["retrieved_ids"] = retrieved
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
        # Normally already resolved by the worker started at turn open; computed
        # here only when that future failed or was never started.
        #
        # Guarded, because the fallback calls the SAME client that just failed.
        # `title_for` catches LLMUnavailable but not an arbitrary transport
        # error, so an unguarded retry turned a failed title into a failed TURN
        # -- the stream ended in `error` instead of `done`, losing an answer that
        # had already been composed and verified over a thread's name.
        if not title:
            try:
                title = title_for(question, config, naming_client)
            except Exception:  # noqa: BLE001 - a thread's name is not the answer
                logger.info("auto-title failed; using the deterministic name")
                title = deterministic_title(question)
        store.rename_conversation(conversation_id, title)
        return title
    convo = store.get_conversation(conversation_id)
    return convo.title if convo else ""
