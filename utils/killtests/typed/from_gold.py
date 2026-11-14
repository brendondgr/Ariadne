"""Convert a CypherBench gold Cypher query into the typed request that means the same.

CypherBench's gold queries come from a fixed set of templates (25 MATCH shapes x 16
RETURN shapes in the training split), so a small parser covers them. Uses:

- **verification:** the compiled request must return the same records as
  CypherBench's ``answer_json`` on the training graphs, in both stores;
- **examples:** the typed arm's three worked examples are the converted shot questions;
- **ceiling (after the run only):** the share of test questions an ideal typed
  request answers exactly, which bounds what the arm can reach.

Raises :class:`Unsupported` for a query outside the templates.
"""

from __future__ import annotations

import re

NAME = r"'((?:[^'\\]|\\.)*)'"
_NODE = re.compile(r"\((\w+)(?::(\w+))?(?:\s*\{name:\s*" + NAME + r"\})?\)")
_REL = re.compile(r"(<-|-)\[(\w+):(\w+)\](->|-)")


class Unsupported(ValueError):
    pass


def _unq(s: str) -> str:
    return re.sub(r"\\(.)", r"\1", s)


def _value(tok: str):
    tok = tok.strip()
    m = re.fullmatch(r"date\(" + NAME + r"\)", tok)
    if m:
        return _unq(m.group(1))
    m = re.fullmatch(NAME, tok)
    if m:
        return _unq(m.group(1))
    if tok in ("true", "false"):
        return tok == "true"
    try:
        return int(tok)
    except ValueError:
        return float(tok)


def _pattern(text: str, nodes: dict) -> list[dict]:
    """Parse comma-separated path patterns into edges, filling ``nodes``."""
    edges = []
    for path in re.split(r",\s*(?=\()", text.strip()):
        pos, prev = 0, None
        while pos < len(path):
            m = _NODE.match(path, pos)
            if not m:
                raise Unsupported(f"cannot parse pattern at: {path[pos:pos + 40]!r}")
            v, label, name = m.group(1), m.group(2), m.group(3)
            spec = nodes.setdefault(v, {})
            if label:
                spec["label"] = label
            if name is not None:
                spec["name"] = _unq(name)
            pos = m.end()
            if prev is not None:
                left, rv, rtype, right = prev_rel
                if left == "-" and right == "->":
                    edges.append({"from": prev, "type": rtype, "to": v, "var": rv})
                elif left == "<-" and right == "-":
                    edges.append({"from": v, "type": rtype, "to": prev, "var": rv})
                else:
                    raise Unsupported("undirected relationship")
            prev = v
            r = _REL.match(path, pos)
            if r:
                prev_rel = (r.group(1), r.group(2), r.group(3), r.group(4))
                pos = r.end()
    return edges


def _edge_where(where: str, edges: list[dict]) -> None:
    m = re.fullmatch(r"(\w+)\.start_year <= (-?\d+) AND \(\1\.end_year >= \2 OR \1\.end_year IS NULL\)", where.strip())
    kind = None
    if m:
        kind = {"op": "during", "year": int(m.group(2)), "start": "start_year", "end": "end_year"}
    m2 = re.fullmatch(r"(\w+)\.start_year IS NOT NULL AND \1\.end_year IS NULL", where.strip())
    if m2:
        m, kind = m2, {"op": "current", "start": "start_year", "end": "end_year"}
    if not kind:
        raise Unsupported(f"edge WHERE: {where!r}")
    for e in edges:
        if e.get("var") == m.group(1):
            e.setdefault("filters", []).append(kind)
            return
    raise Unsupported("edge WHERE names no edge")


_COND = [
    (re.compile(r"NOT " + NAME + r" IN n\.(\w+)"), lambda m: {"prop": m.group(2), "op": "not_contains", "value": _unq(m.group(1))}),
    (re.compile(NAME + r" IN n\.(\w+)"), lambda m: {"prop": m.group(2), "op": "contains", "value": _unq(m.group(1))}),
    (re.compile(r"n\.(\w+)\.year (<>|<=|>=|=|<|>) (-?\d+)"),
     lambda m: {"prop": m.group(1), "op": m.group(2), "value": int(m.group(3)), "part": "year"}),
    (re.compile(r"n\.(\w+) (<>|<=|>=|=|<|>) (.+)"), lambda m: {"prop": m.group(1), "op": m.group(2), "value": _value(m.group(3))}),
]


def _cond(text: str) -> dict:
    for rx, mk in _COND:
        m = rx.fullmatch(text.strip())
        if m:
            return {"var": "n", **mk(m)}
    raise Unsupported(f"condition: {text!r}")


def convert(cypher: str) -> dict:
    q = cypher.strip()
    nodes: dict = {}
    req: dict = {"nodes": nodes}

    m = re.fullmatch(r"MATCH (\(n:\w+ \{name: " + NAME + r"\}\)), (\(m0:\w+ \{name: " + NAME + r"\}\)) RETURN (.+)", q)
    if m:
        _pattern(m.group(1) + ", " + m.group(3), nodes)
        ret = m.group(5)
        for rx, test in ((r"CASE WHEN n\.(\w+) > m0\.\1 THEN n\.name ELSE m0\.name END AS answer", "which_greater"),
                         (r"n\.(\w+) = m0\.\1 AS answer", "equal"), (r"n\.(\w+) - m0\.\1 AS answer", "difference")):
            r = re.fullmatch(rx, ret)
            if r:
                req["answer"] = {"kind": "compare", "other": "m0", "prop": r.group(1), "test": test}
                return req
        raise Unsupported(f"compare RETURN: {ret!r}")

    m = re.fullmatch(r"CALL \{ MATCH (.+?) RETURN n, m0 as m UNION MATCH (.+?) RETURN n, m1 as m \} (WITH .+)", q)
    if m:
        req["edges"] = []
        req["any_of"] = [_pattern(m.group(1), nodes), _pattern(m.group(2), nodes)]
        tail = m.group(3)
    else:
        m = re.fullmatch(r"MATCH (.+?)(?: WHERE (.+?))?(?: OPTIONAL MATCH (.+?))? (WITH .+)", q)
        if not m:
            raise Unsupported(f"MATCH: {q[:80]!r}")
        req["edges"] = _pattern(m.group(1), nodes)
        if m.group(2):
            _edge_where(m.group(2), req["edges"])
        if m.group(3):
            req["optional"] = _pattern(m.group(3), nodes)
        tail = m.group(4)

    r = re.fullmatch(r"WITH n, count\(DISTINCT (\w+)\) AS num RETURN n\.name, num", tail)
    if r:
        req["answer"] = {"kind": "count_per", "of": r.group(1)}
        return _tidy(req)
    r = re.fullmatch(r"WITH DISTINCT n(?: WHERE (.+?))? (RETURN .+|UNWIND .+)", tail)
    if not r:
        raise Unsupported(f"tail: {tail!r}")
    if r.group(1):
        req["where"] = [_cond(r.group(1))]
    ret = r.group(2)
    table = [
        (r"RETURN n\.name", lambda x: {"kind": "names"}),
        (r"RETURN n\.name, n\.(\w+)", lambda x: {"kind": "names_with", "prop": x.group(1)}),
        (r"RETURN DISTINCT n\.(\w+)", lambda x: {"kind": "values", "prop": x.group(1), "distinct": True}),
        (r"RETURN n\.(\w+)", lambda x: {"kind": "values", "prop": x.group(1), "distinct": False}),
        (r"UNWIND n\.(\w+) AS prop RETURN DISTINCT prop", lambda x: {"kind": "list_items", "prop": x.group(1)}),
        (r"RETURN count\((?:DISTINCT )?n\)", lambda x: {"kind": "count"}),
        (r"RETURN count\(DISTINCT n\.(\w+)\)", lambda x: {"kind": "count_values", "prop": x.group(1)}),
        (r"RETURN (max|min|avg|sum)\(n\.(\w+)\.year\)", lambda x: {"kind": "aggregate", "fn": x.group(1), "prop": x.group(2), "part": "year"}),
        (r"RETURN (max|min|avg|sum)\(n\.(\w+)\)", lambda x: {"kind": "aggregate", "fn": x.group(1), "prop": x.group(2)}),
        (r"RETURN n\.name ORDER BY n\.(\w+) (ASC|DESC)(?: LIMIT (\d+))?",
         lambda x: {"kind": "top", "prop": x.group(1), "order": x.group(2).lower(),
                    **({"limit": int(x.group(3))} if x.group(3) else {})}),
    ]
    for rx, mk in table:
        x = re.fullmatch(rx, ret)
        if x:
            req["answer"] = mk(x)
            return _tidy(req)
    raise Unsupported(f"RETURN: {ret!r}")


def _tidy(req: dict) -> dict:
    for k in ("edges", "any_of", "optional", "where"):
        if k in req and not req[k]:
            del req[k]
    return req
