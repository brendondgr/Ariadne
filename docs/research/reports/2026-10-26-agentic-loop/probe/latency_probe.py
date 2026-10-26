"""Time one controller-style call on the local relay: card + question -> one typed tool call.

Conditions: thinking off (budget 0), budget 512, budget 2048, and a pick-from-menu call.
Prints prompt/completion tokens, wall seconds and whether a tool call came back.
"""
import json
import sys
import time
import urllib.request

BASE = "http://localhost:9090/v1/chat/completions"
CARD = json.load(open(sys.argv[1]))
desc = CARD["entity_descriptions"]
card_text = "Source: attack (Neo4j)\nLabels:\n" + "\n".join(
    f"- {k}: {v}" for k, v in desc["nodes"].items()) + "\nRelations:\n" + "\n".join(
    f"- {k}: {v}" for k, v in desc["relationships"].items())

RELS = CARD["relationship_types"]
LABELS = CARD["node_labels"]
TOOLS = [{"type": "function", "function": {
    "name": "expand", "description": "Follow one relation from an anchor node.",
    "parameters": {"type": "object", "properties": {
        "anchor_id": {"type": "string"},
        "relation": {"type": "string", "enum": RELS},
        "direction": {"type": "string", "enum": ["out", "in"]},
        "target_label": {"type": "string", "enum": LABELS}},
        "required": ["anchor_id", "relation", "direction", "target_label"]}}}]
QUESTION = "How do I defend against T1176?"
OBS = ("resolve('T1176') -> T1176 (Technique) 'Browser Extensions'. "
       "describe(T1176) relation counts: MITIGATES/in 2, DETECTS/in 1, USES/in 34, SUBTECHNIQUE_OF/in 0.")


def call(messages, budget, tools=True, max_tokens=4096):
    body = {"model": "default-model", "messages": messages, "max_tokens": max_tokens, "temperature": 0}
    if tools:
        body["tools"] = TOOLS
    if budget is not None:
        body["chat_template_kwargs"] = {"thinking_budget": budget, "enable_thinking": budget > 0}
    req = urllib.request.Request(BASE, json.dumps(body).encode(), {"content-type": "application/json"})
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=600) as r:
        out = json.load(r)
    dt = time.monotonic() - t0
    msg = out["choices"][0]["message"]
    u = out.get("usage", {})
    tc = msg.get("tool_calls") or []
    return dt, u.get("prompt_tokens"), u.get("completion_tokens"), tc, (msg.get("content") or "")[:120], out.get("model")


sys_msg = {"role": "system", "content": "You answer questions over knowledge graphs by calling tools. " + card_text}
user_msg = {"role": "user", "content": f"Question: {QUESTION}\nObservation so far: {OBS}\nMake the next tool call."}
menu = {"role": "user", "content": (
    f"Question: {QUESTION}\n{OBS}\nWhich relation from T1176 answers the question? "
    "Reply with one option only: A) MITIGATES/in B) DETECTS/in C) USES/in D) none")}

runs = [("tool call, thinking off", [sys_msg, user_msg], 0, True),
        ("tool call, budget 512", [sys_msg, user_msg], 512, True),
        ("tool call, budget 2048", [sys_msg, user_msg], 2048, True),
        ("menu pick, thinking off", [sys_msg, menu], 0, False)]
for name, msgs, budget, tools in runs:
    for i in range(3):
        dt, pt, ct, tc, text, model = call(msgs, budget, tools)
        args = tc[0]["function"]["arguments"] if tc else text
        print(f"{name:26s} run{i}: {dt:6.2f}s prompt={pt} completion={ct} model={model} -> {args[:110]!r}", flush=True)
