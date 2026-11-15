#!/usr/bin/env python3
"""Reply repairs: turn what a model actually wrote into what it meant to send.

Era 2, Step 2. Ported from GAIFA's model client (``services/agent/agent/llm.py``),
with one change of policy: **no repair is silent.** Every function here returns
the :class:`RepairEvent` objects describing what it changed, and the caller logs
them. A repaired reply that is scored as if the model had written it cleanly is
how a harness hides a model's real behaviour, and this programme has already
been misled three ways by plausible numbers (see the harness-gotchas record).

What gets repaired, and why each exists:

- **Tool calls written into the text** instead of the ``tool_calls`` field.
  Gemma's own ``<|tool_call>call:name{…}<tool_call|>`` (and ``<call:name{…}</call>``
  from the 26B), Hermes ``<tool_call>{…}</tool_call>``, a known tool's name used
  as a tag, a bare or fenced JSON object naming a known tool, and a reply that is
  nothing but Python-style calls of known tools. The Python form is parsed with
  :mod:`ast` and :func:`ast.literal_eval`; it is never executed.
- **Arguments that are not quite JSON**: Gemma's loose dialect
  (``{key:<|"|>text<|"|>}``), and JSON cut off at the end (vLLM's streaming Gemma
  parser drops the closing ``"}`` of every call but the last). Still invalid after
  both → the call is kept with ``bad_arguments`` and returned to the model with
  the schema; it is never dropped and never guessed.
- **Thinking that arrives inside the text** (``<think>…</think>``, Gemma's
  ``<|channel>thought…<channel|>`` when the server's reasoning parser missed it).
- **Runaway repetition** (the last 300 characters repeated ≥ 10 times in the
  tail): detected here, acted on by the transport.

Everything in this module is pure: no sockets, no clocks, no globals.
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from typing import Any

# --------------------------------------------------------------------------- #
# Repair events
# --------------------------------------------------------------------------- #

#: Every repair kind this module (and the transport) can emit. A test asserts
#: the list is closed, so a new repair cannot be added without being named here.
REPAIR_KINDS = (
    "thinking_split_tag",       # <think>…</think> at the start of the text
    "thinking_split_channel",   # Gemma's <|channel>thought … <channel|>
    "leaked_call_gemma",        # <|tool_call>call:name{…}<tool_call|> / <call:name{…}</call>
    "leaked_call_hermes",       # <tool_call>{…}</tool_call>
    "leaked_call_tag",          # <known_tool>{…}</known_tool>
    "leaked_call_json",         # a bare or fenced JSON object naming a known tool
    "leaked_call_python",       # known_tool(a=1, b='x') — parsed, never run
    "args_loose_json",          # Gemma's {key:<|"|>v<|"|>} dialect
    "args_closed_truncated",    # JSON cut short at the end, closed
    "args_not_object",          # arguments parsed but were not an object
    "args_bad",                 # still invalid after every repair: kept as bad_arguments
    "json_fenced",              # a JSON body taken out of a ``` fence (free-text replies)
    "json_braces",              # a JSON body taken from the first { to the last }
    "content_in_reasoning",     # an unclosed think block: the server filed the whole reply as reasoning
    "empty_retry",              # an empty streamed reply was retried without streaming
    "runaway_retry",            # a degenerate repeating reply was cut and retried
    "runaway_error",            # …and repeated again: an honest error, no answer
    "cut_off_at_cap",           # hit max_tokens with no usable output (not a model error)
)


@dataclass(frozen=True)
class RepairEvent:
    """One change the harness made to a model's reply. Always logged."""

    kind: str
    detail: str = ""
    call_id: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in REPAIR_KINDS:
            raise ValueError(f"unknown repair kind {self.kind!r}; add it to REPAIR_KINDS")

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"kind": self.kind}
        if self.detail:
            out["detail"] = self.detail
        if self.call_id:
            out["call_id"] = self.call_id
        return out


# --------------------------------------------------------------------------- #
# Patterns (from GAIFA, unchanged unless noted)
# --------------------------------------------------------------------------- #

GEMMA_CALL = re.compile(
    r"(?:<\|tool_call\>\s*)?<?(?:call:)?([A-Za-z0-9_.-]+)\s*(\{.*?\})\s*(?:<tool_call\|>|</call>)", re.S
)
HERMES_CALL = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.S)
TAG_CALL = re.compile(r"<([A-Za-z][A-Za-z0-9_]*)>\s*(\{.*?\})\s*</\1>", re.S)
FENCED_OBJECT = re.compile(r"```(?:json|tool_code|tool)?\s*(\{.*?\})\s*```", re.S)
ONE_FENCE = re.compile(r"^```[A-Za-z_]*\s*\n?(.*?)\s*```$", re.S)
CHANNEL_OPEN = re.compile(r"<\|channel\>(?:thought|analysis|final)?\s*")
THINK = re.compile(r"^\s*<(think|thinking)>(.*?)(?:</\1>|$)", re.S)
#: A fenced block whose body is meant to be JSON (free-text replies, e.g. typed requests).
JSON_FENCE = re.compile(r"```(?:json)?\s*\n(.*?)```", re.S)

LOOP_WINDOW, LOOP_SPAN, LOOP_REPEATS = 8000, 300, 10


# --------------------------------------------------------------------------- #
# Runaway detection
# --------------------------------------------------------------------------- #


def looping(text: str) -> bool:
    """The end of ``text`` is one span repeated over and over.

    Needs at least ``LOOP_SPAN * LOOP_REPEATS`` (3,000) characters, and the last
    300 characters occurring ≥ 10 times in the last 8,000. A degenerate
    generation once streamed 23,762 tokens in nine minutes in GAIFA.
    """
    if len(text) < LOOP_SPAN * LOOP_REPEATS:
        return False
    tail = text[-LOOP_WINDOW:]
    return tail.count(tail[-LOOP_SPAN:]) >= LOOP_REPEATS


# --------------------------------------------------------------------------- #
# Thinking
# --------------------------------------------------------------------------- #


def split_thinking(text: str, thinking: str = "") -> tuple[str, str, list[RepairEvent]]:
    """Move thinking that arrived inside ``text`` into ``thinking``.

    Returns ``(thinking, text, events)``. Only markers are acted on: GAIFA's
    heuristic that also moves "planning" paragraphs ("The user wants…") is not
    ported, because it rewrites real output on a guess.
    """
    events: list[RepairEvent] = []
    if not text:
        return thinking, text, events
    if "<channel|>" in text:
        before, _, after = text.rpartition("<channel|>")
        before = CHANNEL_OPEN.sub("", before).strip()
        thinking = (thinking + "\n" + before).strip()
        text = after.strip()
        events.append(RepairEvent("thinking_split_channel", f"{len(before)} chars"))
    elif CHANNEL_OPEN.search(text):
        text = CHANNEL_OPEN.sub("", text)
        events.append(RepairEvent("thinking_split_channel", "stray channel marker removed"))
    m = THINK.match(text)
    if m:
        thinking = (thinking + "\n" + m.group(2).strip()).strip()
        text = text[m.end():].strip()
        events.append(RepairEvent("thinking_split_tag", f"<{m.group(1)}> {len(m.group(2))} chars"))
    return thinking, text, events


# --------------------------------------------------------------------------- #
# JSON repairs
# --------------------------------------------------------------------------- #


def close_json(raw: str) -> dict[str, Any] | None:
    """JSON cut short at the end, closed (open string, objects and arrays).

    Returns ``None`` when the text is not a truncated object (it is complete, or
    its brackets do not nest), so a well-formed-but-invalid body is never
    "repaired" into something else.
    """
    stack: list[str] = []
    in_str = esc = False
    for ch in raw:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]":
            if not stack or stack.pop() != ch:
                return None
    if not stack and not in_str:
        return None
    s = raw + ('"' if in_str else "")
    t = s.rstrip()
    if t.endswith(","):
        s = t[:-1]
    elif t.endswith(":"):
        s = t + " null"
    s += "".join(reversed(stack))
    try:
        v = json.loads(s)
    except ValueError:
        return None
    return v if isinstance(v, dict) else None


def loose_json(raw: str) -> dict[str, Any] | None:
    """Gemma's argument dialect, ``{key:<|"|>text<|"|>,n:3}``, as JSON."""
    s = raw.replace('<|"|>', '"')
    s = re.sub(r'([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:', r'\1"\2":', s)
    try:
        v = json.loads(s)
    except ValueError:
        return None
    return v if isinstance(v, dict) else None


@dataclass(frozen=True)
class ParsedArguments:
    """The outcome of reading one call's arguments.

    ``value`` is ``None`` exactly when ``error`` is set; such a call is kept as a
    ``bad_arguments`` call and sent back to the model with its schema.
    """

    value: dict[str, Any] | None
    error: str | None = None
    events: tuple[RepairEvent, ...] = ()


def parse_arguments(raw: Any, call_id: str | None = None, *, cut_off: bool = False) -> ParsedArguments:
    """``json.loads``, then the loose dialect, then closing truncated JSON.

    ``cut_off`` says the reply stopped at its token cap. Truncated JSON is then
    **not** closed: closing exists for vLLM's streaming parser, which drops the
    closing ``"}`` of a call that was in fact complete. A reply cut off at the
    cap is genuinely incomplete, and closing it yields an object that parses but
    has lost its tail (EXP-2026-11-007: 16 of 16 such "rescues" were missing
    fields or had chopped values).
    """
    if isinstance(raw, dict):
        return ParsedArguments(raw)
    text = (raw or "").strip() if isinstance(raw, str) else json.dumps(raw)
    if not text:
        return ParsedArguments({})
    try:
        v = json.loads(text)
    except ValueError as exc:
        fixed = loose_json(text)
        if fixed is not None:
            return ParsedArguments(fixed, events=(RepairEvent("args_loose_json", "", call_id),))
        fixed = close_json(text)
        if fixed is not None and not cut_off:
            return ParsedArguments(
                fixed, events=(RepairEvent("args_closed_truncated", f"{len(text)} chars", call_id),)
            )
        if fixed is not None:
            err = "arguments were cut off at the token cap; not closed, because the tail is missing"
            return ParsedArguments(None, err, (RepairEvent("args_bad", err, call_id),))
        err = f"arguments aren't valid JSON ({exc.msg} at char {exc.pos})"
        return ParsedArguments(None, err, (RepairEvent("args_bad", err, call_id),))
    if not isinstance(v, dict):
        err = f"arguments must be a JSON object, got {type(v).__name__}"
        return ParsedArguments(None, err, (RepairEvent("args_not_object", err, call_id),))
    return ParsedArguments(v)


@dataclass(frozen=True)
class ExtractedJSON:
    """A JSON object read out of a free-text reply, with how it was found."""

    value: dict[str, Any] | None
    error: str | None = None
    events: tuple[RepairEvent, ...] = ()


def extract_json_object(text: str, *, cut_off: bool = False) -> ExtractedJSON:
    """The JSON object a free-text reply was asked to contain.

    For replies that answer in prose-wrapped JSON rather than through a tool call
    (the kill tests' typed requests, judge verdicts). Strategy, each non-trivial
    step logged:

    1. thinking markers split off;
    2. a ```json fence → its body (``json_fenced``), else the first ``{`` to the
       last ``}`` (``json_braces``), else the whole text;
    3. ``json.loads``, then the loose dialect, then closing truncated JSON --
       unless ``cut_off`` (the reply hit its token cap), see :func:`parse_arguments`.
    """
    _, body, events = split_thinking(text or "")
    events = list(events)
    m = JSON_FENCE.search(body)
    if m:
        candidate = m.group(1).strip()
        events.append(RepairEvent("json_fenced"))
    else:
        stripped = body.strip()
        a, b = stripped.find("{"), stripped.rfind("}")
        if a < 0:
            return ExtractedJSON(None, "no JSON object in the reply", tuple(events))
        # A complete object first: first "{" to last "}", parsed as is or in the
        # loose dialect -- never closed, because closing an inner slice of a
        # truncated reply would silently drop everything after that "}".
        if b > a:
            sliced = stripped[a:b + 1]
            try:
                value = json.loads(sliced)
            except ValueError:
                value = loose_json(sliced)
                if value is not None:
                    events.append(RepairEvent("args_loose_json"))
            if isinstance(value, dict):
                if sliced != stripped:
                    events.append(RepairEvent("json_braces"))
                return ExtractedJSON(value, None, tuple(events))
        # Otherwise the whole tail from the first "{" (a reply cut off at the cap).
        candidate = stripped[a:]
        if candidate != stripped:
            events.append(RepairEvent("json_braces"))
            if "```" in stripped[:a]:
                events.append(RepairEvent("json_fenced", "unterminated fence"))
    parsed = parse_arguments(candidate, cut_off=cut_off)
    events.extend(parsed.events)
    if parsed.value is None:
        return ExtractedJSON(None, parsed.error, tuple(events))
    return ExtractedJSON(parsed.value, None, tuple(events))


# --------------------------------------------------------------------------- #
# Tool calls written into the text
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class LeakedCall:
    """A call recovered from the text; ``arguments`` is the raw argument text."""

    name: str
    arguments: str
    kind: str


def _python_calls(text: str, known: set[str]) -> list[tuple[str, dict[str, Any]]] | None:
    """A reply that is nothing but Python-style calls of known tools.

    E.g. ``count(handle='set:3')`` or ``default_api.count(handle='set:3')``. Only
    keyword arguments with literal values are accepted; anything else → ``None``.
    Parsed with :mod:`ast`; nothing is ever evaluated beyond ``literal_eval``.
    """
    body = text.strip()
    if m := ONE_FENCE.match(body):
        body = m.group(1)
    body = body.strip("`").strip()
    if "(" not in body:
        return None
    try:
        tree = ast.parse(body, mode="exec")
    except SyntaxError:
        return None
    out = []
    for st in tree.body:
        call = st.value if isinstance(st, ast.Expr) else None
        if (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                and call.func.id == "print" and len(call.args) == 1):
            call = call.args[0]
        if not isinstance(call, ast.Call) or call.args:
            return None
        f = call.func
        name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
        if name not in known:
            return None
        args: dict[str, Any] = {}
        for kw in call.keywords:
            if kw.arg is None:
                return None
            try:
                args[kw.arg] = ast.literal_eval(kw.value)
            except (ValueError, SyntaxError):
                return None
        out.append((name, args))
    return out or None


def recover_leaked_calls(text: str, known: set[str]) -> tuple[str, list[LeakedCall]]:
    """Tool calls written into ``text`` → ``(text without them, calls)``.

    Only names in ``known`` count, except inside Gemma's explicit
    ``<|tool_call>`` opener (an unknown name there is still a call, and the
    loop's "unknown tool" error is the right response to it).
    """
    calls: list[LeakedCall] = []
    out = text
    for m in GEMMA_CALL.finditer(text):
        explicit = m.group(0).lstrip().startswith("<|tool_call>")
        if m.group(1) not in known and not explicit:
            continue
        args = loose_json(m.group(2))
        calls.append(LeakedCall(m.group(1), json.dumps(args) if args is not None else m.group(2),
                                "leaked_call_gemma"))
        out = out.replace(m.group(0), "")
    for m in HERMES_CALL.finditer(text):
        try:
            obj = json.loads(m.group(1))
        except ValueError:
            continue
        if isinstance(obj, dict) and obj.get("name"):
            args = obj.get("arguments") or obj.get("parameters") or {}
            calls.append(LeakedCall(str(obj["name"]),
                                    args if isinstance(args, str) else json.dumps(args),
                                    "leaked_call_hermes"))
            out = out.replace(m.group(0), "")
    if not calls:
        for m in TAG_CALL.finditer(text):
            if m.group(1) in known and (args := loose_json(m.group(2))) is not None:
                calls.append(LeakedCall(m.group(1), json.dumps(args), "leaked_call_tag"))
                out = out.replace(m.group(0), "")
    if not calls:
        candidates = [m.group(1) for m in FENCED_OBJECT.finditer(text)]
        stripped = text.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            candidates.append(stripped)
        for c in candidates:
            try:
                obj = json.loads(c)
            except ValueError:
                continue
            if isinstance(obj, dict) and obj.get("name") in known:
                args = obj.get("arguments") or obj.get("parameters") or {}
                calls.append(LeakedCall(str(obj["name"]),
                                        args if isinstance(args, str) else json.dumps(args),
                                        "leaked_call_json"))
                out = out.replace(c, "").replace("```json", "").replace("```", "")
    if not calls and (py := _python_calls(text, known)):
        return "", [LeakedCall(name, json.dumps(args), "leaked_call_python") for name, args in py]
    return out.strip(), calls


__all__ = [
    "REPAIR_KINDS",
    "ExtractedJSON",
    "LeakedCall",
    "ParsedArguments",
    "RepairEvent",
    "close_json",
    "extract_json_object",
    "looping",
    "loose_json",
    "parse_arguments",
    "recover_leaked_calls",
    "split_thinking",
]
