#!/usr/bin/env python3
"""Run one test over a list of models from one command (Era 2, Step 2).

    from utils.llm.matrix import run_matrix
    rows = run_matrix(["gemma4-31b", "qwen38-27b"], "toolcall-roundtrip", n_questions=2)

**Every row names the model that served it.** Before a model's first call its
identity is probed by token id (:mod:`utils.llm.registry`); a model that fails
the check is *refused* -- one ``refused`` row, no calls. After its last call it
is probed again, and if the model behind the alias changed mid-run every row of
that model is marked ``identity_changed``. Rows never carry an alias alone.

A *test* is a function ``(spec, question) -> list[dict]`` registered in
:data:`TESTS`. Later steps add theirs (the agent loop, the decision models); the
one shipped here is the format round trip the loop depends on.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from utils.llm.registry import (
    IdentityMismatch,
    Registry,
    check_identity,
    load,
)
from utils.llm.toolcalls import chat, tool_result_message
from utils.llm.types import LLMUnavailable

TestFn = Callable[[Any, dict[str, Any]], list[dict[str, Any]]]
TESTS: dict[str, tuple[TestFn, list[dict[str, Any]]]] = {}


def register(name: str, questions: list[dict[str, Any]]) -> Callable[[TestFn], TestFn]:
    def wrap(fn: TestFn) -> TestFn:
        TESTS[name] = (fn, questions)
        return fn
    return wrap


# --------------------------------------------------------------------------- #
# The format round trip: two turns, canned tool results
# --------------------------------------------------------------------------- #

ROUNDTRIP_TOOLS = [
    {"type": "function", "function": {
        "name": "resolve_entity",
        "description": "Find graph nodes whose name matches the text. Returns a handle to the matching set.",
        "parameters": {"type": "object", "properties": {
            "text": {"type": "string", "description": "the name as written in the question"},
            "label": {"type": "string", "enum": ["Team", "Person", "Match", "Tournament"]}},
            "required": ["text", "label"]}}},
    {"type": "function", "function": {
        "name": "expand",
        "description": "Follow one relation from every member of a set. Returns a handle to the result set.",
        "parameters": {"type": "object", "properties": {
            "handle": {"type": "string", "description": "a set handle such as set:1"},
            "relation": {"type": "string", "enum": ["PLAYED_IN", "SCORED_GOAL", "IN_TOURNAMENT"]},
            "direction": {"type": "string", "enum": ["out", "in"]}},
            "required": ["handle", "relation", "direction"]}}},
    {"type": "function", "function": {
        "name": "finish",
        "description": "Give the final answer, citing the set handles it rests on.",
        "parameters": {"type": "object", "properties": {
            "answer": {"type": "string"},
            "handles": {"type": "array", "items": {"type": "string"}}},
            "required": ["answer", "handles"]}}},
]

ROUNDTRIP_SYSTEM = (
    "You answer questions about a football (soccer) graph by calling tools. Each tool returns a "
    "short summary and a set handle (set:N) that later calls can build on. Call finish when you "
    "have the answer."
)

ROUNDTRIP_QUESTIONS = [
    {"qid": "rt1", "question": "How many matches did Norway play?",
     "canned": [
         {"tool": "resolve_entity", "result": {"handle": "set:1", "total": 1, "label": "Team",
                                               "sample": ["Norway"]}},
         {"tool": "expand", "result": {"handle": "set:2", "total": 14, "label": "Match",
                                       "complete": True}},
     ],
     "answer_contains": "14"},
    {"qid": "rt2", "question": "Which tournaments did Mia Hamm score in?",
     "canned": [
         {"tool": "resolve_entity", "result": {"handle": "set:1", "total": 1, "label": "Person",
                                               "sample": ["Mia Hamm"]}},
         {"tool": "expand", "result": {"handle": "set:2", "total": 9, "label": "Match"}},
         {"tool": "expand", "result": {"handle": "set:3", "total": 3, "label": "Tournament",
                                       "sample": ["USA 1999", "Sweden 1995", "China 1991"],
                                       "complete": True}},
     ],
     "answer_contains": "1999"},
]

MAX_ROUNDTRIP_TURNS = 6


@register("toolcall-roundtrip", ROUNDTRIP_QUESTIONS)
def toolcall_roundtrip(spec: Any, q: dict[str, Any]) -> list[dict[str, Any]]:
    """A short tool loop with canned results: does the universal format round-trip?

    Each turn's calls get the next canned result (a call the script did not
    expect gets an error result, as a real tool would). The checks: the model
    called a tool on turn 1, every call named a known tool with readable
    arguments, it cited a handle it was given, and it finished with the answer.
    """
    messages: list[dict[str, Any]] = [{"role": "system", "content": ROUNDTRIP_SYSTEM},
                                      {"role": "user", "content": q["question"]}]
    canned = list(q["canned"])
    known = {t["function"]["name"] for t in ROUNDTRIP_TOOLS}
    given: set[str] = set()
    rows = []
    finished = None
    for turn in range(1, MAX_ROUNDTRIP_TURNS + 1):
        reply = chat(spec, messages, ROUNDTRIP_TOOLS)
        row = {"turn": turn, **reply.as_row()}
        rows.append(row)
        messages.append(reply.assistant_message())
        if not reply.tool_calls:
            break
        for call in reply.tool_calls:
            if call.name == "finish":
                finished = call.arguments or {}
                messages.append(tool_result_message(call.id, {"ok": True}))
                continue
            if call.bad_arguments:
                result: dict[str, Any] = {"error": call.error, "fix": "send arguments as a JSON object"}
            elif call.name not in known:
                result = {"error": f"unknown tool {call.name!r}", "fix": f"use one of {sorted(known)}"}
            elif canned and canned[0]["tool"] == call.name:
                result = canned.pop(0)["result"]
                given.add(result["handle"])
            else:
                result = {"error": f"{call.name} returned no rows for these arguments"}
            messages.append(tool_result_message(call.id, result))
        if finished is not None:
            break
    calls = [c for r in rows for c in r["tool_calls"]]
    cited = set((finished or {}).get("handles") or [])
    checks = {
        "called_on_turn_1": bool(rows and rows[0]["tool_calls"]),
        "all_calls_known": all(c["name"] in known for c in calls),
        "all_arguments_readable": all(c.get("error") is None for c in calls),
        "finished": finished is not None,
        "cited_a_given_handle": bool(cited & given),
        "answer_correct": q["answer_contains"] in str((finished or {}).get("answer", "")),
        "turns": len(rows),
        "repairs": sum(len(r["repairs"]) for r in rows),
    }
    return [{"qid": q["qid"], "turns": rows, "checks": checks}]


# --------------------------------------------------------------------------- #
# The runner
# --------------------------------------------------------------------------- #


@dataclass
class MatrixResult:
    run_id: str
    test: str
    rows: list[dict[str, Any]]

    @property
    def ok(self) -> bool:
        return all(r["status"] == "ran" for r in self.rows)

    def summary(self) -> list[dict[str, Any]]:
        out = []
        for r in self.rows:
            checks = r.get("checks") or {}
            out.append({"model": r["model"], "qid": r.get("qid"), "status": r["status"],
                        "served_by": (r.get("identity_before") or {}).get("last_token_id"),
                        **{k: v for k, v in checks.items()}})
        return out


def run_matrix(models: list[str], test: str, *, n_questions: int | None = None,
               registry: Registry | None = None, recheck: bool = True) -> MatrixResult:
    if test not in TESTS:
        raise KeyError(f"unknown test {test!r}; known: {sorted(TESTS)}")
    fn, questions = TESTS[test]
    questions = questions[:n_questions] if n_questions else questions
    reg = registry or load()
    run_id = time.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6]
    rows: list[dict[str, Any]] = []
    for name in models:
        spec = reg[name]
        base = {"run_id": run_id, "test": test, "model": name, "alias": spec.alias,
                "endpoint": spec.endpoint}
        try:
            before = check_identity(spec)
        except LLMUnavailable as exc:
            rows.append({**base, "status": "unreachable", "error": str(exc)})
            continue
        if before.verified is not True:
            rows.append({**base, "status": "refused", "identity_before": before.as_dict(),
                         "error": before.reason or "identity not verified"})
            continue
        mine = []
        for q in questions:
            try:
                for out in fn(spec, q):
                    mine.append({**base, "status": "ran", "identity_before": before.as_dict(), **out})
            except LLMUnavailable as exc:
                mine.append({**base, "status": "unreachable", "qid": q.get("qid"), "error": str(exc)})
        if recheck:
            after = check_identity(spec)
            for r in mine:
                r["identity_after"] = after.as_dict()
                if after.verified is not True and r["status"] == "ran":
                    r["status"] = "identity_changed"
        rows.extend(mine)
    return MatrixResult(run_id, test, rows)


def write(result: MatrixResult, path) -> None:
    with open(path, "w") as fh:
        for r in result.rows:
            fh.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")


__all__ = ["IdentityMismatch", "MatrixResult", "TESTS", "register", "run_matrix", "write"]
