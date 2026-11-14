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

Format v3: numbers stored as text (card type ``float_text``) go through ``asNumber()`` wherever
they are compared, sorted or aggregated; a list's length is ``properties(p).count()`` on a vertex
(multi-valued) and ``values(p).count(local)`` on an edge (one list value).
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


def _filter(f: dict, ptype: str | None = None, edge: bool = False) -> str:
    """Steps that keep an element satisfying filter ``f`` (``ptype``: the card type of its property)."""
    op = f["op"]
    if f.get("part") == "size":
        p = lit(f["prop"])
        size = f"__.values({p}).count(local)" if edge else f"__.properties({p}).count()"
        return f".has({p}).where({size}.is({_P[op]}({int(f['value'])})))"
    if ptype == "float_text" and op in _P:
        p = lit(f["prop"])
        return f".where(__.values({p}).asNumber(GType.DOUBLE).is({_P[op]}({lit(f['value'])})))"
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


def _ptype(card: Card | None, label: str, prop: str | None) -> str | None:
    return card.prop_type(label, prop) if card and prop else None


def _none(req: dict, card: Card | None) -> str:
    """``.not(...)`` for the request's ``none`` edge, applied at ``n``."""
    nodes, e = req["nodes"], req["none"][0]
    far = req["_none_far"]
    t = lit(e["type"])
    out_dir = e["from"] == "n"
    ptypes = (card.rel_props(e["type"], nodes[e["from"]]["label"], nodes[e["to"]]["label"]) if card else None) or {}
    flt = "".join(_filter(f, ptypes.get(f.get("prop", "")), edge=True) for f in e.get("filters") or [])
    if flt:
        step = (f"__.outE({t}){flt}.inV()" if out_dir else f"__.inE({t}){flt}.outV()")
    else:
        step = f"__.out({t})" if out_dir else f"__.in({t})"
    step += _node_steps(nodes[far]) + "".join(_filter(f, _ptype(card, nodes[far]["label"], f.get("prop")))
                                             for f in req.get("where") or [] if f["var"] == far)
    return f".not({step})"


def _refs(req: dict) -> str:
    out = ""
    for f in req.get("where") or []:
        if f.get("ref") is not None:
            out += (f".where({lit(f['var'])}, {_P[f['op']]}({lit(f['ref']['var'])}))"
                    f".by({lit(f['prop'])}).by({lit(f['ref']['prop'])})")
    return out


def _match(req: dict, edges: list[dict], keep: frozenset = frozenset(), card: Card | None = None) -> str:
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
    far = req.get("_none_far")
    wh = [f for f in req.get("where") or [] if f["var"] != far]
    vs = pattern_vars(edges) or ["n"]
    start = next((v for v in vs if nodes[v].get("name") is not None), "n")

    def bind(v: str) -> str:
        return (_node_steps(nodes[v])
                + "".join(_filter(f, _ptype(card, nodes[v]["label"], f.get("prop"))) for f in wh
                          if f["var"] == v and f.get("ref") is None)
                + f".as({lit(v)})")

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
        eptypes = (card.rel_props(e["type"], nodes[e["from"]]["label"], nodes[e["to"]]["label"]) if card else None) or {}
        flt = "".join(_filter(f, eptypes.get(f.get("prop", "")), edge=True) for f in e.get("filters") or [])
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
    for v in ["n"] + [f["var"] for f in wh] + [f["ref"]["var"] for f in wh if f.get("ref")]:
        if v not in known:  # a filtered, referenced or subject node not in any edge
            out += f".V(){bind(v)}"
            known.add(v)
    for x in range(len(labelled)):
        for y in range(x + 1, len(labelled)):
            if labelled[x][0] == labelled[y][0]:
                out += f".where({labelled[x][1]}, neq({labelled[y][1]}))"
    out += _refs(req)
    if req.get("none"):
        out += ".select('n')" + _none(req, card)
    return out


def _subjects(req: dict, card: Card | None = None) -> str:
    """A traversal emitting each distinct subject vertex ``n`` once."""
    edges = req.get("edges") or []
    if req.get("any_of"):
        arms = [f"__.V(){_match(req, edges + br, card=card)}.select('n')" for br in req["any_of"]]
        return f"g.inject(0).union({', '.join(arms)}).dedup()"
    return f"g.V(){_match(req, edges, card=card)}.select('n').dedup()"


def _value(p: str) -> str:
    return f"__.choose(__.has({p}), __.values({p}).fold(), __.constant(null))"


_FN = {"max": "max", "min": "min", "avg": "mean", "sum": "sum"}


def _fold_agg(ans: dict) -> str:
    """Steps from a folded list of ``of`` values (or elements, for count) to the group's value."""
    if ans["fn"] == "count":
        return ".count(local)"
    if ans["fn"] == "sum":
        return ".coalesce(__.unfold().sum(), __.constant(0))"
    return f".coalesce(__.unfold().{_FN[ans['fn']]}(), __.constant(null))"


def _per(req: dict, card: Card, key: str) -> str:
    """``per``: a stream of {a: n's key, b: value}, then having / order / limit."""
    nodes, ans = req["nodes"], req["answer"]
    of = ans["of"]
    edges = req.get("edges") or []
    opt = req.get("optional") or []
    vals = ""
    if ans["fn"] != "count":
        vals = f".values({lit(ans['prop'])})" + (".asNumber(GType.DOUBLE)" if ans.get("_numtext") else "")
    if opt and (of == opt[0].get("var") or (of in (opt[0]["from"], opt[0]["to"]) and of not in pattern_vars(edges))):
        e = opt[0]
        t = lit(e["type"])
        out_dir = e["from"] == "n"
        other = e["to"] if out_dir else e["from"]
        ptypes = card.rel_props(e["type"], nodes[e["from"]]["label"], nodes[e["to"]]["label"]) or {}
        flt = "".join(_filter(f, ptypes.get(f.get("prop", "")), edge=True) for f in e.get("filters") or [])
        if of == e.get("var"):  # the edges themselves
            step = (f"__.outE({t}){flt}.where(__.inV(){_node_steps(nodes[other])})" if out_dir
                    else f"__.inE({t}){flt}.where(__.outV(){_node_steps(nodes[other])})")
        else:
            step = ((f"__.outE({t}){flt}.inV()" if out_dir else f"__.inE({t}){flt}.outV()") if flt
                    else (f"__.out({t})" if out_dir else f"__.in({t})")) + _node_steps(nodes[other])
        stream = (f"{_subjects(req, card)}.project('a', 'b').by({key})"
                  f".by({step}.dedup(){vals}.fold(){_fold_agg(ans)})")
    else:
        keep = frozenset([of]) if ans.get("_edge") else frozenset()
        stream = (f"g.V(){_match(req, edges, keep, card)}.select('n', {lit(of)}).dedup()"
                  f".group().by(__.select('n')).by(__.select({lit(of)}){vals}.fold()).unfold()"
                  f".project('a', 'b').by(__.select(keys).values({key})).by(__.select(values){_fold_agg(ans)})")
    h = ans.get("having")
    if h:
        stream += f".where(__.select('b').is({_P[h['op']]}({lit(h['value'])})))"
    if ans.get("order"):
        nonnull = "__.unfold().not(__.select('b').is(eq(null)))"
        nulls = "__.unfold().where(__.select('b').is(eq(null))).order().by(__.select('a'), asc)"
        d = ans["order"]
        ordered = f"{nonnull}.order().by(__.select('b'), {d}).by(__.select('a'), asc)"
        arms = f"{nulls}, {ordered}" if d == "desc" else f"{ordered}, {nulls}"
        stream += f".fold().union({arms})"
        if ans.get("limit"):
            stream += f".limit({int(ans['limit'])})"
    return stream


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

    if kind == "per":
        return Compiled(_per(req, card, key))

    if kind == "aggregate" and (ans.get("var") or "n") != "n":
        v = ans["var"]
        fn = {"max": "max", "min": "min", "avg": "mean", "sum": "sum"}[ans["fn"]]
        post = "year_null" if ans.get("part") == "year" else ("agg_zero" if fn == "sum" else "agg_null")
        num = ".asNumber(GType.DOUBLE)" if ans.get("_numtext") else ""
        return Compiled(f"g.V(){_match(req, req.get('edges') or [], frozenset([v]), card)}.select({lit(v)}).dedup()"
                        f".values({p}){num}.{fn}()", post=post)
    s = _subjects(req, card)
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
        num = ".asNumber(GType.DOUBLE)" if ans.get("_numtext") else ""
        return Compiled(f"{s}.values({p}){num}.{fn}()", post=post)
    if kind == "top":
        props = ans.get("props") or []
        sortkey = f"__.values({p}).asNumber(GType.DOUBLE)" if ans.get("_numtext") else p
        if props:
            cols = ", ".join(lit(f"c{i}") for i in range(len(props) + 1))
            emit = f".project({cols}).by({key})" + "".join(f".by({_value(lit(x))})" for x in props)
        else:
            emit = f".values({key})"
        if ans.get("limit"):
            # Cypher's order: a missing value sorts after every value ascending and
            # before every value descending; ties by the key, ascending.
            k = int(ans["limit"])
            if ans["order"] == "desc":
                arms = f"__.unfold().hasNot({p}).order().by({key}, asc), __.unfold().has({p}).order().by({sortkey}, desc).by({key}, asc)"
            else:
                arms = f"__.unfold().has({p}).order().by({sortkey}, asc).by({key}, asc), __.unfold().hasNot({p}).order().by({key}, asc)"
            return Compiled(f"{s}.fold().union({arms}).limit({k}){emit}")
        return Compiled(f"{s}{emit}")
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
