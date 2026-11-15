"""A scripted model and canned tools for deterministic run-log tests."""

from __future__ import annotations

import json
from typing import Any

from utils.llm.client import RawCompletion
from utils.llm.toolcalls import ModelReply, finalize
from utils.agent.runner import ToolBox

TEAM = {"handle": "set:1", "kind": "Team", "total": 1, "complete": True, "ids": ["team:norway"]}
MATCHES = {"handle": "set:2", "kind": "Match", "total": 3, "complete": True,
           "ids": ["match:1995-06-06", "match:1995-06-10", "match:1995-06-13"]}

RESOLVE_SPEC = {"type": "function", "function": {"name": "resolve_entity", "parameters": {
    "type": "object", "properties": {"text": {"type": "string"}, "label": {"type": "string"}},
    "required": ["text", "label"]}}}
EXPAND_SPEC = {"type": "function", "function": {"name": "expand", "parameters": {
    "type": "object", "properties": {"handle": {"type": "string"}, "relation": {"type": "string"}},
    "required": ["handle", "relation"]}}}


def toolbox() -> ToolBox:
    box = ToolBox()
    box.add(RESOLVE_SPEC, lambda text, label: dict(TEAM) if text == "Norway" else
            {"error": f"no {label} named {text!r}"})
    box.add(EXPAND_SPEC, lambda handle, relation: dict(MATCHES) if handle == "set:1" else
            {"error": f"unknown handle {handle}"})
    return box


#: One step = the calls of one model turn: [(name, args)], or a str for text only.
FOUR_STEPS = [
    [("resolve_entity", {"text": "Norway", "label": "Team"})],
    [("expand", {"handle": "set:1", "relation": "PLAYED_IN"})],
    [("finish", {"answer": "Norway played 3 matches.", "handles": ["set:2"]})],
]


class ScriptedModel:
    """Replies by turn number (the count of assistant messages it has been shown).

    Deterministic across processes, so a run interrupted anywhere and resumed
    sees exactly the replies an uninterrupted run sees.
    """

    served_model = "scripted/0"

    def __init__(self, steps: list[Any]) -> None:
        self.steps = steps
        self.calls = 0

    def __call__(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ModelReply:
        self.calls += 1
        turn = sum(1 for m in messages if m["role"] == "assistant")
        step = self.steps[turn] if turn < len(self.steps) else "I have nothing more to add."
        if isinstance(step, str):
            raw = RawCompletion(content=step, finish_reason="stop")
        else:
            raw = RawCompletion(finish_reason="tool_calls", tool_calls=[
                {"id": f"c{turn}_{i}", "name": n, "arguments": json.dumps(a)} for i, (n, a) in enumerate(step)])
        raw.usage = {"prompt_tokens": sum(len(str(m.get("content"))) for m in messages) // 4,
                     "completion_tokens": 20}
        return finalize(raw, "scripted", {t["function"]["name"] for t in tools})
