"""Compile a validated typed request to one read-only Cypher query (Neo4j).

Semantics are fixed in ``request.py``; this module only spells them in Cypher. Numbers stored as
text (card type ``float_text``) are read through ``toFloat`` wherever they are compared, sorted or
aggregated (format v3).
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
    if f.get("ref") is not None:
        other = f"{f['ref']['var']}.{_q(f['ref']['prop'])}"
        return f"{ref} IS NOT NULL AND {other} IS NOT NULL AND {ref} {_OPS[op]} {other}"
    if f.get("part") == "size":
        return f"{ref} IS NOT NULL AND size({ref}) {_OPS[op]} {int(f['value'])}"
    if ptype == "float_text":
        return f"{ref} IS NOT NULL AND toFloat({ref}) {_OPS[op]} {lit(f['value'])}"
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


def _num(ref: str, numtext: bool) -> str:
    return f"toFloat({ref})" if numtext else ref


def _none(req: dict, card: Card) -> str:
    """``NOT EXISTS { ... }`` for the request's ``none`` edge."""
    nodes, e = req["nodes"], req["none"][0]
    far = req["_none_far"]
    rv = e.get("var") or "_x"
    pat = (f"(n)-[{rv}:{_q(e['type'])}]->{_node(far, nodes[far])}" if e["from"] == "n"
           else f"{_node(far, nodes[far])}-[{rv}:{_q(e['type'])}]->(n)")
    ptypes = card.rel_props(e["type"], nodes[e["from"]]["label"], nodes[e["to"]]["label"]) or {}
    conds = [_cond(rv, f, ptypes.get(f.get("prop", ""))) for f in e.get("filters") or []]
    conds += [_cond(far, f, card.prop_type(nodes[far]["label"], f["prop"])) for f in req.get("where") or []
              if f["var"] == far]
    return f"NOT EXISTS {{ MATCH {pat}" + (" WHERE " + " AND ".join(f"({c})" for c in conds) if conds else "") + " }"


def _match(req: dict, card: Card, edges: list[dict], prefix: str = "MATCH") -> str:
    nodes = req["nodes"]
    far = req.get("_none_far")
    vs = pattern_vars(edges)
    wh = [f for f in req.get("where") or [] if f["var"] != far]
    for v in ["n"] + [f["var"] for f in wh] + [f["ref"]["var"] for f in wh if f.get("ref")]:
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
    for f in wh:
        conds.append(_cond(f["var"], f, card.prop_type(nodes[f["var"]]["label"], f["prop"])))
    if req.get("none"):
        conds.append(_none(req, card))
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

    if kind == "per":
        of = ans["of"]
        opt = req.get("optional") or []
        if opt and (of == opt[0].get("var") or (of in (opt[0]["from"], opt[0]["to"]) and of not in pattern_vars(edges))):
            e = opt[0]
            other = e["to"] if e["from"] == "n" else e["from"]
            rv = e.get("var") or "_o"
            pat = (f"(n)-[{rv}:{_q(e['type'])}]->{_node(other, nodes[other])}" if e["from"] == "n"
                   else f"{_node(other, nodes[other])}-[{rv}:{_q(e['type'])}]->(n)")
            body += f" OPTIONAL MATCH {pat}"
            ptypes = card.rel_props(e["type"], nodes[e["from"]]["label"], nodes[e["to"]]["label"]) or {}
            conds = [_cond(rv, f, ptypes.get(f.get("prop", ""))) for f in e.get("filters") or []]
            if conds:
                body += " WHERE " + " AND ".join(f"({c})" for c in conds)
        if ans["fn"] == "count":
            agg = f"count(DISTINCT {of})"
        else:
            agg = f"{ans['fn']}({_num(f'{of}.{p}', ans.get('_numtext'))})"
        out = f"{body} WITH DISTINCT n, {of} WITH n, {agg} AS num"
        h = ans.get("having")
        if h:
            out += f" WHERE num {_OPS[h['op']]} {lit(h['value'])}"
        out += f" RETURN n.{key}, num"
        if ans.get("order"):
            out += f" ORDER BY num {'DESC' if ans['order'] == 'desc' else 'ASC'}, n.{key} ASC"
            if ans.get("limit"):
                out += f" LIMIT {int(ans['limit'])}"
        return out

    if kind == "aggregate" and (ans.get("var") or "n") != "n":
        v = ans["var"]
        ref = f"{v}.{p}.year" if ans.get("part") == "year" else _num(f"{v}.{p}", ans.get("_numtext"))
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
        ref = f"n.{p}.year" if ans.get("part") == "year" else _num(f"n.{p}", ans.get("_numtext"))
        return f"{body} RETURN {ans['fn']}({ref})"
    if kind == "top":
        order = "DESC" if ans["order"] == "desc" else "ASC"
        cols = ", ".join([f"n.{key} AS c0"] + [f"n.{_q(x)} AS c{i + 1}" for i, x in enumerate(ans.get("props") or [])])
        out = f"{body} RETURN {cols} ORDER BY {_num(f'n.{p}', ans.get('_numtext'))} {order}, n.{key} ASC"
        if ans.get("limit"):
            out += f" LIMIT {int(ans['limit'])}"
        return out
    raise ValueError(f"unknown answer kind {kind}")
