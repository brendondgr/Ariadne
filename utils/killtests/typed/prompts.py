"""Prompts for the typed arms: the same schema block and the same three worked
examples as the free arms, with the request format in place of a query language.

The examples are the free arms' three shot questions, converted from their gold
Cypher by ``from_gold.convert``, so all six arms see the same questions.
"""

from __future__ import annotations

import json
import re

from ..t1.prompts import schema_block
from ..t1.shots import SHOTS
from .from_gold import convert

ARMS = ("typed-0shot", "typed-3shot")

FORMAT = """Write one request object (JSON) that answers the question:

{
  "nodes": {"<var>": {"label": "<node label>", "name": "<exact name, only if the question names it>"}},
  "edges": [{"from": "<var>", "type": "<relationship type>", "to": "<var>", "var": "<optional edge name>",
             "filters": [<edge filter>]}],
  "any_of": [[<edge>, ...], [<edge>, ...]],
  "optional": [<edge>],
  "where": [{"var": "<var>", "prop": "<property>", "op": "<op>", "value": <value>, "part": "year"}],
  "answer": {<answer>}
}

- "n" is required: the node the question asks about. Other variables are free names.
- Every edge follows the direction listed in the schema: "from" is the source label, "to" the target.
- "any_of" (optional): n qualifies if ANY one branch matches ("either ... or ..."). All branches must use n.
- "optional" (optional): one relationship of n that may be absent; use it with "count_per" so that n with
  none are still listed with 0.
- "where" (optional): op is one of = <> < > <= >= (the property must be present), or contains /
  not_contains for list properties. Dates are written "YYYY-MM-DD"; add "part": "year" to compare a
  date's year with an integer.
- Edge filters: the same form without "var", or, for a start/end pair of edge properties,
  {"op": "current", "start": "<start prop>", "end": "<end prop>"} (started and not ended) or
  {"op": "during", "year": <int>, "start": "<start prop>", "end": "<end prop>"} (ongoing in that year).

Answers (n is counted once however many ways it matches):
- {"kind": "names"}: the name of each n
- {"kind": "names_with", "prop": p}: the name and p of each n
- {"kind": "values", "prop": p, "distinct": true|false}: p of each n
- {"kind": "list_items", "prop": p}: the distinct elements of list property p over all n
- {"kind": "count"}: how many n
- {"kind": "count_values", "prop": p}: how many distinct values p takes among the n
- {"kind": "aggregate", "fn": "max"|"min"|"avg"|"sum", "prop": p}: optionally "part": "year" for a date
- {"kind": "count_per", "of": "<var>"}: for each n, its name and how many distinct <var> it has
- {"kind": "top", "prop": p, "order": "asc"|"desc", "limit": k}: names of n sorted by p; "limit" optional
- {"kind": "compare", "other": "<var>", "prop": p, "test": "which_greater"|"equal"|"difference"}:
  two named nodes n and <var>, no edges; which_greater gives the name of the one with the larger p,
  difference gives n's p minus the other's"""


def shot_requests() -> list[dict]:
    return [{"question": s["question"], "request": convert(s["cypher"])} for s in SHOTS]


def messages(arm: str, graph: str, question: str) -> list[dict]:
    system = ("You translate questions about a property graph into a typed request. "
              "Reply with the request only, as JSON in one ```json fenced block.")
    user = FORMAT + "\n\n"
    if arm == "typed-3shot":
        user += f"Worked examples on a DIFFERENT graph:\n{schema_block('terrorist_attack')}\n\n"
        for s in shot_requests():
            user += f"Question: {s['question']}\n```json\n{json.dumps(s['request'])}\n```\n\n"
        user += "Now the graph you must query:\n"
    user += f"{schema_block(graph)}\n\nQuestion: {question}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


_FENCE = re.compile(r"```(?:json)?\s*\n(.*?)```", re.S)


def extract_request(text: str):
    """The JSON request in a reply, or raise ValueError."""
    t = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    m = _FENCE.search(t)
    body = (m.group(1) if m else t).strip()
    if not m:
        a, b = body.find("{"), body.rfind("}")
        if a < 0 or b < a:
            raise ValueError("no JSON object in the reply")
        body = body[a:b + 1]
    return json.loads(body)
