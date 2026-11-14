"""Prompts for the second benchmark: one schema block per graph, rendered from its card and shared
by every arm, with the free arms' per-store note and the same three worked examples as in T1.
"""

from __future__ import annotations

from ..t1.prompts import schema_block
from ..t1.shots import SHOTS

FREE_ARMS = ("cypher-0shot", "cypher-3shot", "gremlin-0shot", "gremlin-3shot")

_NOTE = {
    "cypher": ("The database is Neo4j. `date` and `datetime` properties are Neo4j temporal values; "
               "`list[str]` properties are lists."),
    "gremlin": ("The database is Apache TinkerPop (TinkerGraph) queried with Gremlin (Groovy script syntax), "
                "traversal source `g`. Vertex labels and edge labels are as listed. `date` properties are ISO-8601 "
                "strings 'YYYY-MM-DD' and `datetime` properties ISO-8601 strings; `list[str]` properties are "
                "multi-valued vertex properties (one value per element, so has('k', 'x') matches any element). "
                "Relationship properties are edge properties."),
}


def card_block(cd: dict) -> str:
    lines = [f"Graph: {cd['name']}", "Node labels and properties (the key property, which identifies a node by "
                                     "name, is marked *):"]
    for e in cd["entities"]:
        props = ", ".join(f"{k}{'*' if k == e['key'] else ''}: {t}" for k, t in e["properties"].items())
        lines.append(f"- {e['label']}: {props or '(none)'}")
    lines.append("Relationships (source label -[type]-> target label):")
    for r in cd["relations"]:
        props = ", ".join(f"{k}: {t}" for k, t in (r.get("properties") or {}).items())
        lines.append(f"- ({r['subj_label']})-[:{r['label']}]->({r['obj_label']})" + (f" with {props}" if props else ""))
    return "\n".join(lines)


def free_messages(arm: str, block: str, question: str) -> list[dict]:
    """The T1 free-arm prompt with ``block`` as the target graph's schema."""
    lang, shots = arm.split("-")
    lang_name = "Cypher" if lang == "cypher" else "Gremlin"
    system = (f"You translate questions about a property graph into a single read-only {lang_name} query. "
              f"Reply with the query only, in one ```{lang} fenced block. Return exactly the values the "
              f"question asks for.")
    user = f"{_NOTE[lang]}\n\n"
    if shots == "3shot":
        user += ("Worked examples on a DIFFERENT graph (same store conventions):\n"
                 f"{schema_block('terrorist_attack')}\n\n")
        for s in SHOTS:
            user += f"Question: {s['question']}\n```{lang}\n{s[lang]}\n```\n\n"
        user += "Now the graph you must query:\n"
    user += f"{block}\n\nQuestion: {question}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
