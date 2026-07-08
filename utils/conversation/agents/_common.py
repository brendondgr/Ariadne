#!/usr/bin/env python3
"""Shared helpers for the conversational agents: memory rendering + JSON parsing."""

from __future__ import annotations

import json
from typing import Any


def emit_event(chunk: tuple[str, dict[str, Any]]) -> None:
    """Emit a custom stream event when running inside a LangGraph stream.

    A no-op when called outside a graph run (e.g. unit tests invoking a node
    directly), so nodes stay directly callable.
    """
    try:
        from langgraph.config import get_stream_writer

        get_stream_writer()(chunk)
    except (ImportError, RuntimeError):
        pass


def recent_history(
    history: list[dict[str, Any]] | None, limit: int
) -> list[dict[str, Any]]:
    """Return the last ``limit`` turns (oldest first)."""
    if not history:
        return []
    return list(history)[-limit:] if limit > 0 else list(history)


def render_history_messages(
    history: list[dict[str, Any]] | None, limit: int
) -> list[dict[str, str]]:
    """Render prior turns into OpenAI chat messages for LLM context."""
    messages: list[dict[str, str]] = []
    for turn in recent_history(history, limit):
        role = turn.get("role")
        content = str(turn.get("content", "") or "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    return messages


def known_facts(history: list[dict[str, Any]] | None, limit: int) -> list[str]:
    """Collect verified facts established by prior assistant turns.

    These are the only things the memory-grounded quick path may assert as new
    fact — everything else must be routed to graph extraction.
    """
    facts: list[str] = []
    for turn in recent_history(history, limit):
        if turn.get("role") != "assistant":
            continue
        for fact in turn.get("facts", []) or []:
            text = str(fact).strip()
            if text and text not in facts:
                facts.append(text)
    return facts


def history_is_empty(history: list[dict[str, Any]] | None) -> bool:
    return not any((t.get("content") or t.get("facts")) for t in (history or []))


def extract_json_object(text: str) -> dict[str, Any]:
    """Extract the first balanced top-level JSON object from model output.

    Raises ``ValueError`` on any failure so callers can fall back deterministically.
    """
    if not text:
        raise ValueError("empty model response")
    start = text.find("{")
    if start == -1:
        raise ValueError("no JSON object in model response")
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                blob = text[start : i + 1]
                return json.loads(blob)
    raise ValueError("unbalanced JSON object in model response")
