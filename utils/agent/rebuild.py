#!/usr/bin/env python3
"""Rebuild the model's messages from a run log (Era 2, Step 3).

After GAIFA's ``context.rebuild``. The messages are never kept anywhere but the
log: before every model call they are rebuilt from the events, so what the
model sees is always exactly what the log says happened.

Event payload conventions this module reads (the driver writes them):

- ``request``: the :class:`~utils.agent.contracts.AgentRequest`, as JSON;
- ``model_call``: ``{"step", "text", "tool_calls": [{"id", "name", "arguments",
  "raw_arguments"?, "error"?}], "finish_reason", "usage", "seconds", ...}``;
- ``tool_result``: ``{"id", "name", "content", "seconds"}``.

Thinking is never stored in a form that is sent back, and never rebuilt.
"""

from __future__ import annotations

import json
from typing import Any

from utils.agent.log import Event

#: What the model sees for a call whose result never arrived (a crash between
#: the call and its result, replayed without re-running it).
NOT_RUN = "[not run: the run stopped before this call finished]"

#: Events after which nothing new was decided; a fork drops them from its tail.
_TRAILING_NOISE = ("state", "repair", "error", "validator", "answer", "envelope")


def _wire_call(c: dict[str, Any]) -> dict[str, Any]:
    if c.get("error") is not None or c.get("arguments") is None:
        args = c.get("raw_arguments") or "{}"
    else:
        args = json.dumps(c["arguments"], ensure_ascii=False, sort_keys=True)
    return {"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": args}}


def _content(payload: dict[str, Any]) -> str:
    content = payload.get("content")
    return content if isinstance(content, str) else json.dumps(content, ensure_ascii=False,
                                                                 default=str, sort_keys=True)


def results_by_id(events: list[Event]) -> dict[str, Event]:
    return {e.payload["id"]: e for e in events if e.type == "tool_result"}


def rebuild(events: list[Event], system: str | None = None, *,
            user_text: str | None = None) -> list[dict[str, Any]]:
    """The message list for the next model call.

    ``user_text`` overrides how the question is put to the model (a later step's
    prompt builder adds the card summary); by default it is the question.
    """
    if not events or events[0].type != "request":
        raise ValueError("a run log starts with its request event")
    results = results_by_id(events)
    msgs: list[dict[str, Any]] = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": user_text or events[0].payload["question"]})
    for e in events:
        if e.type != "model_call":
            continue
        calls = e.payload.get("tool_calls") or []
        msg: dict[str, Any] = {"role": "assistant", "content": e.payload.get("text") or ""}
        if calls:
            msg["tool_calls"] = [_wire_call(c) for c in calls]
        msgs.append(msg)
        for c in calls:
            r = results.get(c["id"])
            msgs.append({"role": "tool", "tool_call_id": c["id"],
                         "content": _content(r.payload) if r is not None else NOT_RUN})
    return msgs


def last_model_call(events: list[Event]) -> Event | None:
    for e in reversed(events):
        if e.type == "model_call":
            return e
    return None


def pending_calls(events: list[Event]) -> list[dict[str, Any]]:
    """Calls of the last model turn that have no result yet, in order.

    A run that crashed after the model answered but before its tools finished
    resumes by running exactly these, without asking the model again.
    """
    last = last_model_call(events)
    if last is None:
        return []
    done = {e.payload["id"] for e in events if e.type == "tool_result" and e.seq > last.seq}
    return [c for c in (last.payload.get("tool_calls") or []) if c["id"] not in done]


def trim_unresolved(events: list[Event]) -> list[Event]:
    """A fork never ends inside a pending step.

    Trailing bookkeeping (state, repairs, errors, a verdict or an envelope) is
    dropped, and if the last model turn has a call without a result, that whole
    turn and everything after it is dropped, so the fork re-asks the model.
    """
    out = list(events)
    while out and out[-1].type in _TRAILING_NOISE:
        out.pop()
    last = last_model_call(out)
    if last is not None and pending_calls(out):
        out = [e for e in out if e.seq < last.seq]
        while out and out[-1].type in _TRAILING_NOISE:
            out.pop()
    return out


__all__ = ["NOT_RUN", "last_model_call", "pending_calls", "rebuild", "results_by_id", "trim_unresolved"]
