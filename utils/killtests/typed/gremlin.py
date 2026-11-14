"""Compile a validated typed request to one Gremlin script (TinkerGraph mirror).

Semantics are fixed in ``request.py``. The mirror stores ``date`` properties as
ISO ``YYYY-MM-DD`` strings, so date comparisons are string comparisons and a
year comparison becomes a range of strings; ``list[str]`` properties are
multi-valued, so ``has(k, v)`` means "contains".

Patterns compile to a walk from one node (see :func:`_match`); each traverser's
path labels are one binding of the pattern, the way a Cypher ``MATCH`` binds. Two results need a small, declared post-step
(``Compiled.post``), applied by :func:`finish`: an aggregate over nothing is one
null row (zero for ``sum``), and a year aggregate takes the year of the extreme
date.
"""

from __future__ import annotations

from dataclasses import dataclass

from .request import Card, pattern_vars

_P = {"=": "eq", "<>": "neq", "<": "lt", ">": "gt", "<=": "lte", ">=": "gte"}
_TEXT = {"starts_with": "startingWith", "ends_with": "endingWith", "contains_text": "containing"}


@dataclass(frozen=True)
class Compiled:
    script: str
    post: str | None = None  # None | "agg_null" | "agg_zero" | "year_null" | "one_or_null"


def lit(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    return "'" + str(v).replace("\\", "\\\\").replace("'", "\\'") + "'"


def _year_range(op: str, y: int) -> str:
    a, b = lit(f"{y:04d}-01-01"), lit(f"{y + 1:04d}-01-01")
    return {"=": f"between({a}, {b})", "<>": f"lt({a}).or(gte({b}))", "<": f"lt({a})",
            "<=": f"lt({b})", ">": f"gte({b})", ">=": f"gte({a})"}[op]


def _filter(f: dict) -> str:
    """Steps that keep an element satisfying filter ``f``."""
    op = f["op"]
    if op == "current":
        return f".has({lit(f['start'])}).hasNot({lit(f['end'])})"
    if op == "during":
        y = int(f["year"])
        return f".has({lit(f['start'])}, lte({y})).or(__.has({lit(f['end'])}, gte({y})), __.hasNot({lit(f['end'])}))"
    p = lit(f["prop"])
    if op == "contains":
        return f".has({p}, {lit(f['value'])})"
    if op == "not_contains":
        return f".has({p}).not(__.has({p}, {lit(f['value'])}))"
    if op in _TEXT:
        return f".has({p}, {_TEXT[op]}({lit(f['value'])}))"
    if f.get("part") == "year":
        return f".has({p}, {_year_range(op, int(f['value']))})"
    return f".has({p}, {_P[op]}({lit(f['value'])}))"


def _node_steps(spec: dict) -> str:
    s = f".hasLabel({lit(spec['label'])})"
    if spec.get("name") is not None:
        s += f".has({lit(spec.get('_key', 'name'))}, {lit(spec['name'])})"
    return s


def _match(req: dict, edges: list[dict], keep: frozenset = frozenset()) -> str:
    """Steps after ``g.V()`` that walk the pattern; each traverser is one match.

    The walk starts at a named node if there is one (else ``n``) and takes each
    relationship from a node it has already reached, so every traverser's path
    labels are one complete binding of the pattern, as in a Cypher ``MATCH``:

    - a relationship back to a node already reached checks it is the same node
      (``where(eq(..))``), which covers cycles such as two relationships to one node;
    - relationships of the same type must be different edges (relationship
      uniqueness), checked at the end.

    (``match()`` is not used: in TinkerPop 3.8.0 it returns nothing or a
    ClassCastException on some cyclic patterns with edge labels.)
    """
    nodes = req["nodes"]
    wh = req.get("where") or []
    vs = pattern_vars(edges) or ["n"]
    start = next((v for v in vs if nodes[v].get("name") is not None), "n")

    def bind(v: str) -> str:
        return _node_steps(nodes[v]) + "".join(_filter(f) for f in wh if f["var"] == v) + f".as({lit(v)})"

    by_type: dict[str, int] = {}
    for e in edges:
        by_type[e["type"]] = by_type.get(e["type"], 0) + 1
    out = bind(start)
    at, known = start, {start}
    todo = list(enumerate(edges))
    labelled: list[tuple[str, str]] = []
    while todo:
        k = next((k for k, (_, e) in enumerate(todo) if e["from"] in known or e["to"] in known), None)
        if k is None:  # a part of the pattern not connected to what is reached: a cross product
            i, e = todo.pop(0)
            out += f".V(){bind(e['from'])}"
            at = e["from"]
            known.add(at)
            todo.insert(0, (i, e))
            continue
        i, e = todo.pop(k)
        forward = e["from"] in known
        src, dst = (e["from"], e["to"]) if forward else (e["to"], e["from"])
        if at != src:
            out += f".select({lit(src)})"
        t = lit(e["type"])
        flt = "".join(_filter(f) for f in e.get("filters") or [])
        if flt or by_type[e["type"]] > 1 or e.get("var") in keep:
            rv = lit(e.get("var") or f"_e{i}")
            labelled.append((e["type"], rv))
            out += (f".outE({t}){flt}.as({rv}).inV()" if forward else f".inE({t}){flt}.as({rv}).outV()")
        else:
            out += f".out({t})" if forward else f".in({t})"
        if dst in known:
            out += f".where(eq({lit(dst)}))"
        else:
            out += bind(dst)
            known.add(dst)
        at = dst
    for v in ["n"] + [f["var"] for f in wh]:  # a filtered or subject node not in any edge
        if v not in known:
            out += f".V(){bind(v)}"
            known.add(v)
    for x in range(len(labelled)):
        for y in range(x + 1, len(labelled)):
            if labelled[x][0] == labelled[y][0]:
                out += f".where({labelled[x][1]}, neq({labelled[y][1]}))"
    return out


def _subjects(req: dict) -> str:
    """A traversal emitting each distinct subject vertex ``n`` once."""
    edges = req.get("edges") or []
    if req.get("any_of"):
        arms = [f"__.V(){_match(req, edges + br)}.select('n')" for br in req["any_of"]]
        return f"g.inject(0).union({', '.join(arms)}).dedup()"
    if not edges:
        steps = _node_steps(req["nodes"]["n"]) + "".join(_filter(f) for f in req.get("where") or [] if f["var"] == "n")
        return f"g.V(){steps}.dedup()"
    return f"g.V(){_match(req, edges)}.select('n').dedup()"


def _value(p: str) -> str:
    return f"__.choose(__.has({p}), __.values({p}).fold(), __.constant(null))"


def compile_gremlin(req: dict, card: Card) -> Compiled:
    nodes, ans = req["nodes"], req["answer"]
    kind = ans["kind"]
    p = lit(ans["prop"]) if ans.get("prop") else None
    key = lit(nodes["n"].get("_key", "name"))

    if kind == "compare":
        o = ans["other"]
        head = (f"g.V(){_node_steps(nodes['n'])}.as('n').V(){_node_steps(nodes[o])}.as({lit(o)})")
        t = ans["test"]
        if t == "which_greater":
            return Compiled(f"{head}.choose(__.where('n', gt({lit(o)})).by({p}), "
                            f"__.select('n').values({key}), __.select({lit(o)}).values({lit(nodes[o].get('_key', 'name'))}))")
        if t == "equal":
            return Compiled(f"{head}.choose(__.select('n').has({p}).select({lit(o)}).has({p}), "
                            f"__.choose(__.where('n', eq({lit(o)})).by({p}), __.constant(true), __.constant(false)), "
                            f"__.constant(null))")
        return Compiled(f"{head}.choose(__.select('n').has({p}).select({lit(o)}).has({p}), "
                        f"__.select('n').values({p}).as('_x').select({lit(o)}).values({p}).as('_y').math('_x - _y'), "
                        f"__.constant(null))")

    if kind == "count_per":
        of = ans["of"]
        edges = req.get("edges") or []
        opt = req.get("optional") or []
        if opt and of in (opt[0]["from"], opt[0]["to"]) and of not in pattern_vars(edges):
            e = opt[0]
            t = lit(e["type"])
            out = e["from"] == "n"
            if e.get("filters"):
                step = (f"__.outE({t})" if out else f"__.inE({t})") + "".join(_filter(f) for f in e["filters"]) \
                    + (".inV()" if out else ".outV()")
            else:
                step = f"__.out({t})" if out else f"__.in({t})"
            step += _node_steps(nodes[of])
            return Compiled(f"{_subjects(req)}.project('a', 'b').by({key}).by({step}.dedup().count())")
        return Compiled(f"g.V(){_match(req, edges)}.select('n', {lit(of)}).dedup()"
                        f".group().by(__.select('n')).by(__.count()).unfold()"
                        f".project('a', 'b').by(__.select(keys).values({key})).by(__.select(values))")

    if kind == "aggregate" and (ans.get("var") or "n") != "n":
        v = ans["var"]
        fn = {"max": "max", "min": "min", "avg": "mean", "sum": "sum"}[ans["fn"]]
        post = "year_null" if ans.get("part") == "year" else ("agg_zero" if fn == "sum" else "agg_null")
        return Compiled(f"g.V(){_match(req, req.get('edges') or [], frozenset([v]))}.select({lit(v)}).dedup()"
                        f".values({p}).{fn}()", post=post)
    s = _subjects(req)
    if kind == "names":
        return Compiled(f"{s}.values({key})")
    if kind == "names_with":
        cols = ", ".join(lit(f"c{i}") for i in range(len(ans["props"]) + 1))
        bys = f".by({key})" + "".join(f".by({_value(lit(x))})" for x in ans["props"])
        return Compiled(f"{s}.project({cols}){bys}")
    if kind == "values":
        return Compiled(f"{s}.project('a').by({_value(p)})" + (".dedup()" if ans.get("distinct") else ""))
    if kind == "list_items":
        return Compiled(f"{s}.values({p}).dedup()")
    if kind == "count":
        return Compiled(f"{s}.count()")
    if kind == "count_values":
        return Compiled(f"{s}.has({p}).project('a').by(__.values({p}).fold()).dedup().count()")
    if kind == "aggregate":
        fn = {"max": "max", "min": "min", "avg": "mean", "sum": "sum"}[ans["fn"]]
        post = "year_null" if ans.get("part") == "year" else ("agg_zero" if fn == "sum" else "agg_null")
        return Compiled(f"{s}.values({p}).{fn}()", post=post)
    if kind == "top":
        if ans.get("limit"):
            # Cypher's order: a missing value sorts after every value ascending and
            # before every value descending.
            k = int(ans["limit"])
            if ans["order"] == "desc":
                arms = f"__.unfold().hasNot({p}), __.unfold().has({p}).order().by({p}, desc)"
            else:
                arms = f"__.unfold().has({p}).order().by({p}, asc), __.unfold().hasNot({p})"
            return Compiled(f"{s}.fold().union({arms}).limit({k}).values({key})")
        return Compiled(f"{s}.values({key})")
    raise ValueError(f"unknown answer kind {kind}")


def _year(v):
    if v is None:
        return None
    s = str(v)
    neg = s.startswith("-")
    y = int(s[1:].split("-")[0]) if neg else int(s.split("-")[0])
    return -y if neg else y


def finish(rows: list, post: str | None) -> list:
    """Apply a compiled script's declared post-step to its raw result rows."""
    rows = [r for r in rows]
    if post is None:
        return rows
    empty = not rows or all(r is None for r in rows)
    if post == "agg_null" or post == "one_or_null":
        return [None] if empty else rows
    if post == "agg_zero":
        return [0] if empty else rows
    if post == "year_null":
        return [None] if empty else [_year(rows[0])]
    raise ValueError(post)
