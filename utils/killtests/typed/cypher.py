"""Compile a validated typed request to one read-only Cypher query (Neo4j).

Semantics are fixed in ``request.py``; this module only spells them in Cypher.
Neo4j holds ``date`` properties as date values, so a date literal compiles to
``date('YYYY-MM-DD')`` and a year comparison to ``.year``.
"""

from __future__ import annotations

from .request import Card, pattern_vars

_OPS = {"=": "=", "<>": "<>", "<": "<", ">": ">", "<=": "<=", ">=": ">="}
_TEXT = {"starts_with": "STARTS WITH", "ends_with": "ENDS WITH", "contains_text": "CONTAINS"}


def lit(v, *, date: bool | str = False) -> str:
    """A Cypher literal; ``date`` is True/"date" for ``date('..')``, "datetime" for ``datetime('..')``."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    s = "'" + str(v).replace("\\", "\\\\").replace("'", "\\'") + "'"
    if date == "datetime":
        return f"datetime({s})"
    return f"date({s})" if date else s


def _q(name: str) -> str:
    return "`" + name.replace("`", "``") + "`"


def _cond(ref_var: str, f: dict, ptype: str | None) -> str:
    op = f["op"]
    if op in ("current", "during"):
        s, e = f"{ref_var}.{_q(f['start'])}", f"{ref_var}.{_q(f['end'])}"
        if op == "current":
            return f"{s} IS NOT NULL AND {e} IS NULL"
        y = int(f["year"])
        return f"{s} <= {y} AND ({e} >= {y} OR {e} IS NULL)"
    ref = f"{ref_var}.{_q(f['prop'])}"
    if op == "contains":
        return f"{lit(f['value'])} IN {ref}"
    if op == "not_contains":
        return f"{ref} IS NOT NULL AND NOT {lit(f['value'])} IN {ref}"
    if op in _TEXT:
        return f"{ref} {_TEXT[op]} {lit(f['value'])}"
    if f.get("part") == "year":
        return f"{ref}.year {_OPS[op]} {int(f['value'])}"
    kind = ptype if ptype in ("date", "datetime") else False
    return f"{ref} IS NOT NULL AND {ref} {_OPS[op]} {lit(f['value'], date=kind)}"


def _node(v: str, spec: dict) -> str:
    key = spec.get("_key", "name")
    name = f" {{{_q(key)}: {lit(spec['name'])}}}" if spec.get("name") is not None else ""
    return f"({v}:{_q(spec['label'])}{name})"


def _match(req: dict, card: Card, edges: list[dict], prefix: str = "MATCH") -> str:
    nodes = req["nodes"]
    vs = pattern_vars(edges)
    for v in ["n"] + [f["var"] for f in req.get("where") or []]:
        if v not in vs:
            vs.append(v)
    parts = [_node(v, nodes[v]) for v in vs]
    conds = []
    for i, e in enumerate(edges):
        rv = e.get("var") or f"_e{i}"
        parts.append(f"({e['from']})-[{rv}:{_q(e['type'])}]->({e['to']})")
        for f in e.get("filters") or []:
            ptypes = card.rel_props(e["type"], nodes[e["from"]]["label"], nodes[e["to"]]["label"]) or {}
            conds.append(_cond(rv, f, ptypes.get(f.get("prop", ""))))
    for f in req.get("where") or []:
        if f["var"] in vs:
            conds.append(_cond(f["var"], f, card.prop_type(nodes[f["var"]]["label"], f["prop"])))
    out = f"{prefix} " + ", ".join(parts)
    if conds:
        out += " WHERE " + " AND ".join(f"({c})" for c in conds)
    return out


def compile_cypher(req: dict, card: Card) -> str:
    nodes, ans = req["nodes"], req["answer"]
    kind = ans["kind"]
    p = _q(ans["prop"]) if ans.get("prop") else None
    key = _q(nodes["n"].get("_key", "name"))
    if kind == "compare":
        o = ans["other"]
        head = f"MATCH {_node('n', nodes['n'])}, {_node(o, nodes[o])}"
        t = ans["test"]
        if t == "which_greater":
            okey = _q(nodes[o].get("_key", "name"))
            return f"{head} RETURN CASE WHEN n.{p} > {o}.{p} THEN n.{key} ELSE {o}.{okey} END AS answer"
        if t == "equal":
            return f"{head} RETURN n.{p} = {o}.{p} AS answer"
        return f"{head} RETURN n.{p} - {o}.{p} AS answer"

    edges = req.get("edges") or []
    if req.get("any_of"):
        branches = [_match(req, card, edges + br) + " RETURN n" for br in req["any_of"]]
        body = "CALL { " + " UNION ".join(branches) + " }"
    else:
        body = _match(req, card, edges)

    if kind == "count_per":
        of = ans["of"]
        opt = req.get("optional") or []
        if opt and of in (opt[0]["from"], opt[0]["to"]) and of not in pattern_vars(edges):
            e = opt[0]
            other = e["to"] if e["from"] == "n" else e["from"]
            rv = e.get("var") or "_o"
            pat = (f"(n)-[{rv}:{_q(e['type'])}]->{_node(other, nodes[other])}" if e["from"] == "n"
                   else f"{_node(other, nodes[other])}-[{rv}:{_q(e['type'])}]->(n)")
            body += f" OPTIONAL MATCH {pat}"
            conds = [_cond(rv, f, None) for f in e.get("filters") or []]
            if conds:
                body += " WHERE " + " AND ".join(f"({c})" for c in conds)
        return f"{body} WITH n, count(DISTINCT {of}) AS num RETURN n.{key}, num"

    if kind == "aggregate" and (ans.get("var") or "n") != "n":
        v = ans["var"]
        ref = f"{v}.{p}.year" if ans.get("part") == "year" else f"{v}.{p}"
        return f"{body} WITH DISTINCT {v} RETURN {ans['fn']}({ref})"
    body += " WITH DISTINCT n"
    if kind == "names":
        return f"{body} RETURN n.{key}"
    if kind == "names_with":
        cols = [f"n.{key} AS c0"] + [f"n.{_q(x)} AS c{i + 1}" for i, x in enumerate(ans["props"])]
        return f"{body} RETURN " + ", ".join(cols)
    if kind == "values":
        return f"{body} RETURN {'DISTINCT ' if ans.get('distinct') else ''}n.{p}"
    if kind == "list_items":
        return f"{body} UNWIND n.{p} AS item RETURN DISTINCT item"
    if kind == "count":
        return f"{body} RETURN count(n)"
    if kind == "count_values":
        return f"{body} RETURN count(DISTINCT n.{p})"
    if kind == "aggregate":
        ref = f"n.{p}.year" if ans.get("part") == "year" else f"n.{p}"
        return f"{body} RETURN {ans['fn']}({ref})"
    if kind == "top":
        order = "DESC" if ans["order"] == "desc" else "ASC"
        if ans.get("limit"):
            return f"{body} RETURN n.{key} ORDER BY n.{p} {order} LIMIT {int(ans['limit'])}"
        return f"{body} RETURN n.{key} ORDER BY n.{p} {order}"
    raise ValueError(f"unknown answer kind {kind}")
