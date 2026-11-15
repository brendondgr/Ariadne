#!/usr/bin/env python3
"""A minimal driver that runs an agent from its log (Era 2, Step 3).

This is the skeleton the Step 11 loop grows from. It exists now because the
run log's guarantees -- resume after a crash, pause for a clarification and
resume, fork, replay -- are only real if something drives a run *from* the log.
What it does not have yet (Step 11): the answer validator, the guards (repeat
refusal, thrash wrap-up), the prompt builder, the generated tool catalog.

The cycle, every iteration reading the log afresh:

1. a final envelope in the log → return it;
2. calls of the last model turn without results → run them (no new model call);
3. step budget spent → ``insufficient``;
4. otherwise rebuild the messages, ask the model, log its turn.

Two calls are exits, not tools: ``finish(answer, handles)`` ends the run with
the sets those handles name; ``ask_caller(questions, why)`` pauses an
interactive run (``needs_clarification``) until :func:`resume` appends the
caller's answers as that call's result.

Time budgets count *active* time (model and tool seconds from the log), so a
run that crashed or waited for a person is not charged for the gap, and a
resumed run behaves exactly like an uninterrupted one.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from utils.agent.contracts import (
    AgentRequest,
    Answer,
    AnswerEnvelope,
    AnswerSet,
    CitationRef,
    Clarification,
    ClarifyQuestion,
    Trace,
)
from utils.agent.log import Event, RunLog
from utils.agent.rebuild import pending_calls, rebuild
from utils.llm.toolcalls import ModelReply

EXIT_TOOLS = ("finish", "ask_caller")

FINISH_SPEC = {"type": "function", "function": {
    "name": "finish",
    "description": "End the run with the answer. Cite the set handles the answer rests on.",
    "parameters": {"type": "object", "properties": {
        "answer": {"type": "string"},
        "handles": {"type": "array", "items": {"type": "string"}}},
        "required": ["answer", "handles"]}}}

ASK_CALLER_SPEC = {"type": "function", "function": {
    "name": "ask_caller",
    "description": ("Ask the caller to choose between readings of the question when they would give "
                    "different answers and nothing in the graph separates them."),
    "parameters": {"type": "object", "properties": {
        "questions": {"type": "array", "items": {"type": "object", "properties": {
            "header": {"type": "string"}, "question": {"type": "string"},
            "options": {"type": "array", "items": {"type": "object", "properties": {
                "label": {"type": "string"}, "detail": {"type": "string"}}, "required": ["label"]}}},
            "required": ["header", "question", "options"]}},
        "why": {"type": "string"}},
        "required": ["questions", "why"]}}}


class Model(Protocol):
    """Anything that takes messages and tools and returns a :class:`ModelReply`."""

    served_model: str

    def __call__(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ModelReply: ...


@dataclass
class Tool:
    spec: dict[str, Any]
    fn: Callable[..., dict[str, Any]]

    @property
    def name(self) -> str:
        return self.spec["function"]["name"]


@dataclass
class ToolBox:
    tools: dict[str, Tool] = field(default_factory=dict)

    def add(self, spec: dict[str, Any], fn: Callable[..., dict[str, Any]]) -> "ToolBox":
        t = Tool(spec, fn)
        self.tools[t.name] = t
        return self

    def specs(self, interactive: bool) -> list[dict[str, Any]]:
        out = [t.spec for t in self.tools.values()] + [FINISH_SPEC]
        if interactive:
            out.append(ASK_CALLER_SPEC)
        return out


# --------------------------------------------------------------------------- #
# Helpers over the log
# --------------------------------------------------------------------------- #


def _known_sets(events: list[Event]) -> dict[str, dict[str, Any]]:
    sets = {}
    for e in events:
        c = e.payload.get("content") if e.type == "tool_result" else None
        if isinstance(c, dict) and isinstance(c.get("handle"), str):
            sets[c["handle"]] = c
    return sets


def _active_seconds(events: list[Event]) -> float:
    return round(sum(float(e.payload.get("seconds") or 0.0) for e in events
                     if e.type in ("model_call", "tool_result")), 3)


def _trace(events: list[Event]) -> Trace:
    calls = [e for e in events if e.type == "model_call"]
    seen: set[str] = set()
    tools = []
    for e in events:
        if e.type == "tool_call" and e.payload["id"] not in seen:
            seen.add(e.payload["id"])
            tools.append(e.payload["name"])
    return Trace(
        steps=len(calls),
        tools=tools,
        served_model=calls[-1].served_model if calls else None,
        seconds=_active_seconds(events),
        repairs=sum(1 for e in events if e.type == "repair"),
    )


def _final_envelope(log: RunLog, run_id: str, events: list[Event]) -> AnswerEnvelope | None:
    """The envelope, if it is the last thing that happened (state events aside).

    A paused run's envelope stops being final once resume() appends the answers
    after it. If the process died between the envelope and its state change, the
    state is repaired here, so a crash at any append leaves a run that resumes.
    """
    for e in reversed(events):
        if e.type == "state":
            continue
        if e.type != "envelope":
            return None
        env = AnswerEnvelope.model_validate(e.payload)
        want = "needs_clarification" if env.status == "needs_clarification" else "done"
        if log.run(run_id)["state"] != want:
            log.set_state(run_id, want)
        return env
    return None


def _unfinished_exit(events: list[Event]) -> list[dict[str, Any]]:
    """A ``finish`` that has its result but no envelope yet (the process died in between)."""
    last = None
    for e in events:
        if e.type == "model_call":
            last = e
    if last is None or any(e.type == "envelope" and e.seq > last.seq for e in events):
        return []
    done = {e.payload["id"] for e in events if e.type == "tool_result" and e.seq > last.seq}
    return [c for c in (last.payload.get("tool_calls") or [])
            if c["name"] == "finish" and c["id"] in done and c.get("arguments") is not None
            and any(e.type == "tool_result" and e.payload["id"] == c["id"]
                    and (e.payload.get("content") or {}).get("ok") for e in events)]


def _close(log: RunLog, run_id: str, env: AnswerEnvelope, state: str) -> AnswerEnvelope:
    log.append(run_id, "envelope", env.model_dump(mode="json"))
    log.set_state(run_id, state)
    return env


# --------------------------------------------------------------------------- #
# Executing one call
# --------------------------------------------------------------------------- #


def _execute(log: RunLog, run_id: str, req: AgentRequest, call: dict[str, Any], box: ToolBox,
             events: list[Event]) -> AnswerEnvelope | None:
    """Run one call and log it. Returns an envelope when the call ended or paused the run."""
    name, cid, args = call["name"], call["id"], call.get("arguments")
    # Idempotent: after a crash the same call may be executed again; its
    # tool_call, result and clarification are logged once.
    if not any(e.type == "tool_call" and e.payload["id"] == cid for e in events):
        log.append(run_id, "tool_call", {"id": cid, "name": name, "arguments": args})
    has_result = any(e.type == "tool_result" and e.payload["id"] == cid for e in events)
    started = time.monotonic()

    def result(content: dict[str, Any]) -> None:
        if not has_result:
            log.append(run_id, "tool_result", {"id": cid, "name": name, "content": content,
                                               "seconds": round(time.monotonic() - started, 4)})

    if call.get("error") is not None or args is None:
        result({"error": call.get("error") or "arguments missing",
                "fix": "send the arguments as one JSON object matching the tool's schema"})
        return None

    if name == "finish":
        sets = _known_sets(events)
        handles = list(args.get("handles") or [])
        unknown = [h for h in handles if h not in sets]
        if unknown:
            result({"error": f"unknown handle(s) {unknown}", "fix": f"cite handles you were given: {sorted(sets)}"})
            return None
        result({"ok": True})
        evs = log.events(run_id)
        answer_sets = [AnswerSet(handle=h, kind=str(sets[h].get("kind") or ""), total=int(sets[h].get("total") or 0),
                                 complete=bool(sets[h].get("complete", True)),
                                 ids=[str(i) for i in sets[h].get("ids") or []]) for h in handles]
        status = "answered" if all(s.complete for s in answer_sets) else "partial"
        citations = [CitationRef(id=i, source=req.graphs[0]) for s in answer_sets for i in s.ids]
        env = AnswerEnvelope(run_id=run_id, status=status, path="loop",
                             answer=Answer(text=str(args.get("answer") or ""), sets=answer_sets),
                             citations=citations, trace=_trace(evs))
        if not any(e.type == "answer" for e in evs):
            log.append(run_id, "answer", {"text": env.answer.text, "handles": handles})
        return _close(log, run_id, env, "done")

    if name == "ask_caller":
        if not req.interactive:
            result({"error": "this run is not interactive; nobody can answer",
                    "fix": "choose the most likely reading and say so, or finish with what you have"})
            return None
        try:
            clar = Clarification(resume=run_id, why=str(args.get("why") or ""),
                                 questions=[ClarifyQuestion.model_validate(q) for q in args.get("questions") or []])
        except Exception as exc:  # noqa: BLE001 - the model's question was malformed
            result({"error": f"malformed questions: {exc}"[:400],
                    "fix": "1-4 questions, each with a header, the question and 2-4 options"})
            return None
        if not any(e.type == "clarification" and e.payload.get("call_id") == cid for e in events):
            log.append(run_id, "clarification", {"phase": "asked", "call_id": cid,
                                                 **clar.model_dump(mode="json")})
        env = AnswerEnvelope(run_id=run_id, status="needs_clarification", path="loop",
                             clarification=clar, trace=_trace(log.events(run_id)))
        return _close(log, run_id, env, "needs_clarification")

    tool = box.tools.get(name)
    if tool is None:
        result({"error": f"unknown tool {name!r}", "fix": f"use one of {sorted(box.tools) + list(EXIT_TOOLS)}"})
        return None
    try:
        content = tool.fn(**args)
    except TypeError as exc:
        content = {"error": f"bad arguments for {name}: {exc}", "fix": "check the tool's schema"}
    except Exception as exc:  # noqa: BLE001 - a tool failure is the model's information, not a crash
        content = {"error": f"{name} failed: {type(exc).__name__}: {exc}"[:400]}
    result(content)
    return None


# --------------------------------------------------------------------------- #
# The driver
# --------------------------------------------------------------------------- #


def start(log: RunLog, request: AgentRequest) -> str:
    return log.create_run(request)


def drive(log: RunLog, run_id: str, model: Model, box: ToolBox, *, system: str | None = None) -> AnswerEnvelope:
    """Drive a run from its log until it finishes, pauses or exhausts its budget."""
    req = log.request(run_id)
    while True:
        events = log.events(run_id)
        done = _final_envelope(log, run_id, events)
        if done is not None:
            return done

        pend = pending_calls(events) + _unfinished_exit(events)
        if pend:
            for call in pend:
                env = _execute(log, run_id, req, call, box, log.events(run_id))
                if env is not None:
                    return env
            continue

        steps = sum(1 for e in events if e.type == "model_call")
        if steps >= req.budget.steps:
            env = AnswerEnvelope(run_id=run_id, status="insufficient", path="loop", trace=_trace(events),
                                 reason=f"step budget of {req.budget.steps} model calls spent without finish")
            return _close(log, run_id, env, "done")
        if _active_seconds(events) >= req.budget.seconds:
            env = AnswerEnvelope(run_id=run_id, status="insufficient", path="loop", trace=_trace(events),
                                 reason=f"time budget of {req.budget.seconds:g} s spent without finish")
            return _close(log, run_id, env, "done")

        messages = rebuild(events, system)
        started = time.monotonic()
        reply = model(messages, box.specs(req.interactive))
        seconds = round(reply.latency_s or (time.monotonic() - started), 4)
        row = reply.as_row()
        seq = log.append(run_id, "model_call", {
            "step": steps + 1, "text": reply.text, "tool_calls": row["tool_calls"],
            "finish_reason": reply.finish_reason, "status": reply.status, "error": reply.error,
            "usage": reply.usage, "attempts": reply.attempts, "envelope_model": reply.envelope_model,
            "fallback_from": reply.fallback_from, "seconds": seconds,
        }, served_model=model.served_model)
        for r in reply.repairs:
            log.append(run_id, "repair", {"model_call_seq": seq, **r.as_dict()}, served_model=model.served_model)

        if not reply.tool_calls:
            why = (f"the model's reply was {reply.status}" if reply.status != "ok"
                   else "the model stopped without calling finish")
            env = AnswerEnvelope(run_id=run_id, status="error" if reply.status != "ok" else "insufficient",
                                 path="loop", trace=_trace(log.events(run_id)),
                                 reason=why + (f": {reply.error}" if reply.error else ""))
            return _close(log, run_id, env, "done")


def resume(log: RunLog, run_id: str, answers: dict[str, Any] | list[Any] | str) -> None:
    """Give a paused run the caller's answers. Drive it again afterwards.

    The answers become the result of the ``ask_caller`` call that paused the
    run, so the model sees them exactly where it asked.
    """
    run = log.run(run_id)
    if run["state"] != "needs_clarification":
        raise ValueError(f"run {run_id} is {run['state']}, not waiting for a clarification")
    asked = [e for e in log.events(run_id) if e.type == "clarification" and e.payload.get("phase") == "asked"]
    call_id = asked[-1].payload["call_id"]
    log.append(run_id, "clarification", {"phase": "answered", "call_id": call_id, "answers": answers})
    log.append(run_id, "tool_result", {"id": call_id, "name": "ask_caller",
                                       "content": {"answers": answers}, "seconds": 0.0})
    log.set_state(run_id, "running", why="the caller answered")


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #


class RegistryModel:
    """A registry model, its identity verified by token id before first use."""

    def __init__(self, spec: Any, **chat_kwargs: Any) -> None:
        from utils.llm.registry import require_identity

        ident = require_identity(spec)
        self.spec = spec
        self.served_model = f"{spec.name}/{ident.last_token_id}"
        self.chat_kwargs = chat_kwargs

    def __call__(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ModelReply:
        from utils.llm.toolcalls import chat

        return chat(self.spec, messages, tools, **self.chat_kwargs)


__all__ = ["ASK_CALLER_SPEC", "EXIT_TOOLS", "FINISH_SPEC", "Model", "RegistryModel", "Tool", "ToolBox",
           "drive", "resume", "start"]
