"""One schema block, rendered identically for both languages, and the four arms.

The schema text is the same for Cypher and Gremlin except for one line per
language stating how the store represents dates and list properties. That line
is a fact about the store, not a hint: Neo4j holds ``date`` values, the
TinkerGraph mirror holds ISO strings and multi-valued properties.
"""

from __future__ import annotations

import re

from .load import schema
from .shots import SHOTS

ARMS = ("cypher-0shot", "cypher-3shot", "gremlin-0shot", "gremlin-3shot")


def schema_block(graph: str) -> str:
    s = schema(graph)
    lines = [f"Graph: {graph}", "Node labels and properties (every node also has `name`):"]
    for e in s["entities"]:
        props = ", ".join(f"{k}: {t}" for k, t in (e.get("properties") or {}).items()) or "(name only)"
        lines.append(f"- {e['label']}: {props}")
    lines.append("Relationships (source label -[type]-> target label):")
    for r in s["relations"]:
        props = ", ".join(f"{k}: {t}" for k, t in (r.get("properties") or {}).items())
        lines.append(f"- ({r['subj_label']})-[:{r['label']}]->({r['obj_label']})" + (f" with {props}" if props else ""))
    return "\n".join(lines)


_STORE_NOTE = {
    "cypher": ("The database is Neo4j. `date` properties are Neo4j date values (e.g. n.date.year works); "
               "`list[str]` properties are lists."),
    "gremlin": ("The database is Apache TinkerPop (TinkerGraph) queried with Gremlin (Groovy script syntax), "
                "traversal source `g`. Vertex labels and edge labels are as listed. `date` properties are ISO-8601 "
                "strings 'YYYY-MM-DD'; `list[str]` properties are multi-valued vertex properties (one value per "
                "element, so has('k', 'x') matches any element). Relationship properties are edge properties."),
}


def messages(arm: str, graph: str, question: str) -> list[dict]:
    lang, shots = arm.split("-")
    lang_name = "Cypher" if lang == "cypher" else "Gremlin"
    system = (f"You translate questions about a property graph into a single read-only {lang_name} query. "
              f"Reply with the query only, in one ```{lang} fenced block. Return exactly the values the "
              f"question asks for.")
    user = f"{_STORE_NOTE[lang]}\n\n"
    if shots == "3shot":
        user += ("Worked examples on a DIFFERENT graph (same store conventions):\n"
                 f"{schema_block('terrorist_attack')}\n\n")
        for s in SHOTS:
            user += f"Question: {s['question']}\n```{lang}\n{s[lang]}\n```\n\n"
        user += "Now the graph you must query:\n"
    user += f"{schema_block(graph)}\n\nQuestion: {question}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


_FENCE = re.compile(r"```(?:[a-zA-Z]+)?\s*\n(.*?)```", re.S)


def extract_query(text: str) -> str:
    t = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    m = _FENCE.search(t)
    q = (m.group(1) if m else t).strip()
    return q.rstrip(";").strip()
