#!/usr/bin/env python3
"""One tool-call format for every model (Era 2, Step 2).

Every caller -- the agent loop, the matrix runner, an experiment -- speaks
OpenAI-style ``tools`` and ``tool_calls``, whatever model is behind the
endpoint. This module converts in and out of each model's quirks so the loop
never sees a model-specific format:

- **Out:** messages are sent as OpenAI chat messages. The thinking a model
  produced is kept on the reply and never sent back. An assistant turn with tool
  calls is sent with ``content: ""`` (several servers reject ``null``), and a
  tool result's content is always a string.
- **In:** native ``tool_calls`` first; otherwise calls the model wrote into its
  text are recovered (:mod:`utils.llm.repair`). Arguments are parsed with the
  repair ladder; a call whose arguments are still invalid is kept as a
  ``bad_arguments`` call so the loop can send it back with the schema.

**Retries and caps** (the token policy):

- a reply that degenerates into repetition is cut off (the stream is closed),
  retried once, and if it repeats again returned as ``status="runaway"`` with an
  error -- an honest failure, not an answer;
- an empty streamed reply is retried once without streaming;
- a reply that hits ``max_tokens`` with nothing usable is ``cut_off_at_cap``,
  which is a budget fact, never reported as a model error.

**Fallback** is off unless the caller passes one. When used, the reply records
both models (``fallback_from``), and experiment runners refuse such rows
(:func:`refuse_fallback`).

Every repair and retry is a :class:`~utils.llm.repair.RepairEvent` on the reply.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from utils.llm.client import RawCompletion, complete_raw
from utils.llm.registry import ModelSpec
from utils.llm.repair import (
    RepairEvent,
    looping,
    parse_arguments,
    recover_leaked_calls,
    split_thinking,
)
from utils.llm.types import LLMUnavailable

#: Reply statuses. ``ok`` means the model produced text or calls, possibly
#: repaired; the repairs say how.
STATUSES = ("ok", "cut_off_at_cap", "empty", "runaway")


@dataclass
class ToolCall:
    """One call in the universal format."""

    id: str
    name: str
    #: Parsed arguments, or ``None`` when they could not be read (see ``error``).
    arguments: dict[str, Any] | None
    #: The argument text exactly as the model wrote it.
    raw_arguments: str = ""
    #: ``"native"`` or the repair kind it was recovered by (``leaked_call_*``).
    source: str = "native"
    #: Set for a ``bad_arguments`` call; the loop returns it with the schema.
    error: str | None = None

    @property
    def bad_arguments(self) -> bool:
        return self.error is not None

    def to_wire(self) -> dict[str, Any]:
        """The OpenAI form, for the assistant turn sent back to the model."""
        args = json.dumps(self.arguments) if self.arguments is not None else (self.raw_arguments or "{}")
        return {"id": self.id, "type": "function", "function": {"name": self.name, "arguments": args}}

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"id": self.id, "name": self.name, "arguments": self.arguments,
                               "source": self.source}
        if self.error:
            out["error"] = self.error
            out["raw_arguments"] = self.raw_arguments
        return out


@dataclass
class ModelReply:
    """A model's reply after the format conversion and every logged repair."""

    model: str
    text: str = ""
    thinking: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = ""
    status: str = "ok"
    error: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    envelope_model: str = ""
    latency_s: float = 0.0
    attempts: int = 1
    repairs: list[RepairEvent] = field(default_factory=list)
    #: The registry name of the model that was asked first, when a fallback answered.
    fallback_from: str | None = None
    request_extra: dict[str, Any] = field(default_factory=dict)
    #: The model ended its turn inside the template's open think block (no
    #: think-close token), so the server filed whatever it wrote as reasoning.
    unclosed_think: bool = False

    @property
    def repaired(self) -> bool:
        return bool(self.repairs)

    def assistant_message(self) -> dict[str, Any]:
        """The turn to append to the conversation. Thinking is never sent back."""
        msg: dict[str, Any] = {"role": "assistant", "content": self.text or ""}
        if self.tool_calls:
            msg["tool_calls"] = [c.to_wire() for c in self.tool_calls]
        return msg

    def as_row(self) -> dict[str, Any]:
        """A flat record for an event log or a results file."""
        return {
            "model": self.model,
            "status": self.status,
            "error": self.error,
            "text": self.text,
            "thinking_chars": len(self.thinking),
            "tool_calls": [c.as_dict() for c in self.tool_calls],
            "finish_reason": self.finish_reason,
            "usage": self.usage,
            "envelope_model": self.envelope_model,
            "latency_s": self.latency_s,
            "attempts": self.attempts,
            "repairs": [r.as_dict() for r in self.repairs],
            "fallback_from": self.fallback_from,
            "request_extra": self.request_extra,
        }


def tool_result_message(call_id: str, content: Any) -> dict[str, Any]:
    """A ``tool`` turn. Non-string content is JSON-encoded."""
    text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False, default=str)
    return {"role": "tool", "tool_call_id": call_id, "content": text}


def to_wire_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Messages as the server should see them: no thinking, no ``null`` content."""
    out = []
    for m in messages:
        m = {k: v for k, v in m.items() if k not in ("thinking", "reasoning", "reasoning_content")}
        if m.get("content") is None:
            m["content"] = ""
        if m.get("role") == "tool" and not isinstance(m.get("content"), str):
            m["content"] = json.dumps(m["content"], ensure_ascii=False, default=str)
        out.append(m)
    return out


def tool_names(tools: list[dict[str, Any]] | None) -> set[str]:
    return {((t.get("function") or {}).get("name") or t.get("name") or "") for t in (tools or [])} - {""}


def _recover_leaks(reply: ModelReply, known: set[str], cut_off: bool) -> None:
    """Move tool calls written into ``reply.text`` into ``reply.tool_calls``, logging each."""
    rest, leaked = recover_leaked_calls(reply.text, known)
    for i, lc in enumerate(leaked):
        cid = f"leak_{i}"
        reply.repairs.append(RepairEvent(lc.kind, lc.name, cid))
        parsed = parse_arguments(lc.arguments, cid, cut_off=cut_off and i == len(leaked) - 1)
        reply.repairs.extend(parsed.events)
        reply.tool_calls.append(ToolCall(cid, lc.name, parsed.value, lc.arguments, lc.kind, parsed.error))
    if leaked:
        reply.text = rest


def finalize(raw: RawCompletion, model: str, known: set[str], *,
             think_close_token_id: int | None = None) -> ModelReply:
    """Turn one raw completion into a :class:`ModelReply`. Pure.

    Thinking markers are split off the text; native calls have their arguments
    parsed; if there are no native calls, calls written into the text are
    recovered. Every change is a repair event.
    """
    reply = ModelReply(model=model, finish_reason=raw.finish_reason, usage=dict(raw.usage),
                       envelope_model=raw.envelope_model, latency_s=raw.latency_s)
    thinking, text, events = split_thinking(raw.content, raw.reasoning)
    reply.thinking, reply.text = thinking, text
    reply.repairs.extend(events)

    cut_off = raw.finish_reason == "length"
    for i, tc in enumerate(raw.tool_calls):
        cid = tc.get("id") or f"tc_{i}"
        # Only the last call can be cut off by the cap; earlier ones lost their
        # closing braces to the streaming parser and may be closed.
        parsed = parse_arguments(tc.get("arguments"), cid, cut_off=cut_off and i == len(raw.tool_calls) - 1)
        reply.repairs.extend(parsed.events)
        reply.tool_calls.append(ToolCall(cid, tc.get("name") or "", parsed.value,
                                         tc.get("arguments") or "", "native", parsed.error))

    if not reply.tool_calls and reply.text and known:
        _recover_leaks(reply, known, cut_off)

    # A thinking template opens <think> in the prompt. If the model ends its turn
    # without ever closing it, the server files everything it wrote as reasoning
    # and the reply text is empty. That text is NOT promoted to an answer: it is
    # a malformed turn, and _turn re-asks it with thinking off.
    if (not reply.text and not reply.tool_calls and think_close_token_id is not None
            and raw.finish_reason == "stop" and raw.token_ids and think_close_token_id not in raw.token_ids):
        reply.unclosed_think = True

    if not reply.text and not reply.tool_calls:
        if raw.finish_reason == "length":
            reply.status = "cut_off_at_cap"
            reply.repairs.append(RepairEvent(
                "cut_off_at_cap",
                f"completion_tokens={raw.usage.get('completion_tokens', 0)}, thinking {len(reply.thinking)} chars"))
        else:
            reply.status = "empty"
    return reply


def _runaway(content: str, reasoning: str) -> bool:
    return looping(content) or looping(reasoning)


def _attempt(spec: ModelSpec, payload: dict[str, Any], *, stream: bool) -> RawCompletion:
    return complete_raw(spec.endpoint, payload, headers=spec.headers, stream=stream,
                        connect_timeout_s=spec.connect_timeout_s, read_timeout_s=spec.read_timeout_s,
                        should_stop=_runaway if stream else None)


def chat(
    spec: ModelSpec,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    *,
    tool_choice: str | dict[str, Any] = "auto",
    max_tokens: int | None = None,
    temperature: float = 0.0,
    reasoning: str | None = None,
    extra: dict[str, Any] | None = None,
    stream: bool = True,
    fallback: ModelSpec | None = None,
) -> ModelReply:
    """One model turn in the universal format.

    Raises :class:`LLMUnavailable` when the model cannot be reached and no
    fallback was given. Everything else -- empty, cut off, runaway, bad
    arguments -- comes back as a :class:`ModelReply` the caller can log.
    """
    if spec.kind != "llm":
        raise ValueError(f"{spec.name} is a {spec.kind} model; chat() needs an llm")
    budget = max_tokens if max_tokens is not None else spec.max_tokens
    if budget < 2048:
        raise ValueError(f"max_tokens={budget} is below 2,048: reasoning models truncate to empty")
    request_extra = {**spec.reasoning_extra(reasoning), **(extra or {})}
    payload: dict[str, Any] = {
        "model": spec.alias,
        "messages": to_wire_messages(messages),
        "max_tokens": budget,
        "temperature": temperature,
        **request_extra,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = tool_choice
    if spec.think_close_token_id is not None:
        payload.setdefault("return_token_ids", True)       # needed to prove an unclosed think block
    known = tool_names(tools)

    try:
        reply = _turn(spec, payload, known, stream=stream)
    except LLMUnavailable:
        if fallback is None:
            raise
        reply = chat(fallback, messages, tools, tool_choice=tool_choice, max_tokens=max_tokens,
                     temperature=temperature, extra=extra, stream=stream)
        reply.fallback_from = spec.name
        return reply
    reply.request_extra = {**request_extra, **reply.request_extra}   # a retry records what it changed
    return reply


def _turn(spec: ModelSpec, payload: dict[str, Any], known: set[str], *, stream: bool) -> ModelReply:
    pending: list[RepairEvent] = []
    attempts = 1
    raw = _attempt(spec, payload, stream=stream)
    if raw.stopped == "runaway":
        pending.append(RepairEvent("runaway_retry", f"cut after {len(raw.content) + len(raw.reasoning)} chars"))
        attempts += 1
        raw = _attempt(spec, payload, stream=stream)
        if raw.stopped == "runaway":
            reply = ModelReply(model=spec.name, finish_reason="runaway", status="runaway",
                               error="the model repeated itself on two attempts; no answer",
                               usage=dict(raw.usage), envelope_model=raw.envelope_model,
                               latency_s=raw.latency_s, attempts=attempts)
            reply.repairs = [*pending, RepairEvent("runaway_error")]
            return reply
    reply = finalize(raw, spec.name, known, think_close_token_id=spec.think_close_token_id)
    if reply.unclosed_think and spec.reasoning_param and spec.reasoning_off is not None:
        # The model ended its turn inside the open think block. Re-ask once with
        # thinking off: the template then closes the block itself, so the answer
        # comes back as reply text. Logged; the reply records the setting used.
        pending.append(RepairEvent("unclosed_think_retry",
                                   f"{len(raw.token_ids)} tokens, no think-close {spec.think_close_token_id}; "
                                   f"wrote {reply.thinking[:60]!r}"))
        attempts += 1
        retry = {**payload, spec.reasoning_param: spec.reasoning_off}
        raw = _attempt(spec, retry, stream=stream)
        reply = finalize(raw, spec.name, known, think_close_token_id=spec.think_close_token_id)
        reply.request_extra = {**reply.request_extra, spec.reasoning_param: spec.reasoning_off,
                               "retried_from_thinking": True}
        reply.repairs = [*pending, *reply.repairs]
        reply.attempts = attempts
        return reply
    if reply.status == "empty" and stream:
        pending.append(RepairEvent("empty_retry", f"finish_reason={raw.finish_reason!r}"))
        attempts += 1
        raw = _attempt(spec, payload, stream=False)
        reply = finalize(raw, spec.name, known, think_close_token_id=spec.think_close_token_id)
    reply.repairs = [*pending, *reply.repairs]
    reply.attempts = attempts
    return reply


def refuse_fallback(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Raise if any row was answered by a fallback model. Experiment runners call this."""
    fell = [r for r in rows if r.get("fallback_from")]
    if fell:
        raise RuntimeError(f"{len(fell)} row(s) were answered by a fallback model; an experiment may not use them")
    return rows


__all__ = [
    "STATUSES",
    "ModelReply",
    "ToolCall",
    "chat",
    "finalize",
    "refuse_fallback",
    "to_wire_messages",
    "tool_names",
    "tool_result_message",
]
