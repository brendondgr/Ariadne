"""The typed request: format, semantics, and validation against a graph's card.

A request names a pattern of typed nodes and relationships, optional filters,
and one answer operator. Every label, relationship type and property must exist
in the card (the graph's schema), and every relationship must connect the labels
the card says it connects, in the card's direction. The compilers assume a
request has passed :func:`validate`.

Format (JSON)::

    {
      "nodes":  {"n": {"label": "Player"}, "m0": {"label": "Team", "name": "Houston Rockets"}},
      "edges":  [{"from": "n", "type": "playsFor", "to": "m0", "var": "r0",
                  "filters": [{"op": "during", "year": 2000, "start": "start_year", "end": "end_year"}]}],
      "any_of": [[edge, ...], [edge, ...]],     # optional: n must satisfy at least one branch
      "optional": [edge],                       # optional: at most one, touching n; for count_per
      "where":  [{"var": "n", "prop": "height_cm", "op": ">", "value": 200}],
      "answer": {"kind": "names"}
    }

``n`` is always the subject: the thing the question is about. The answer kinds:

=================  ====================================================================
``names``          the name of each distinct ``n``
``names_with``     name and ``prop`` of each distinct ``n``
``values``         ``prop`` of each distinct ``n`` (``distinct: true`` drops repeats)
``list_items``     the distinct elements of the list property ``prop`` over all ``n``
``count``          how many distinct ``n``
``count_values``   how many distinct non-null values of ``prop`` among the ``n``
``aggregate``      ``fn`` (max, min, avg, sum) of ``prop`` over distinct ``n``;
                   ``part: "year"`` takes the year of a date first
``count_per``      for each ``n``: its name and how many distinct ``of`` it has
``top``            names of ``n`` ordered by ``prop`` (``order`` asc|desc); with ``limit``,
                   only the first ``limit``. Missing values sort as in Cypher (after
                   every value ascending, before every value descending), because
                   CypherBench's gold answers were produced that way
``compare``        two named nodes ``n`` and ``other`` on ``prop``: ``test`` is
                   ``which_greater`` (name of the larger; the other if not larger),
                   ``equal`` (true/false) or ``difference`` (n minus other)
=================  ====================================================================

Matching follows a single Cypher ``MATCH``: two relationships of the same type in
one pattern must be different relationships.

**Format v3 additions (2026-11-14):**

- ``per``: for each ``n``, an aggregate over ``of`` (a node var other than ``n``, or an edge var):
  ``fn`` is ``count`` (distinct ``of``) or ``sum``/``avg``/``max``/``min`` of ``of``'s ``prop``
  (over distinct ``(n, of)`` pairs). Optional ``having`` ``{"op", "value"}`` keeps only groups
  whose value passes; ``order`` (asc|desc) and ``limit`` rank the groups (ties by ``n``'s key,
  ascending; missing values sort as in Cypher). Rows: ``n``'s key and the value.
  ``count_per`` is ``per`` with ``fn: count``.
- ``top`` takes optional ``props``: extra columns of ``n`` next to its key.
- ``optional`` may name an edge written in ``edges`` by its ``var`` (as ``any_of`` may).
- A filter may compare with another property instead of a value: ``"ref": {"var", "prop"}``.
- ``"part": "size"`` compares the length of a list property with an integer.
- ``none``: one edge touching ``n``; ``n`` qualifies only if it has **no** such relationship
  (with that edge's filters and the far node's ``name`` and ``where`` filters).
- Properties typed ``float_text`` in the card (numbers stored as text) compare, sort and aggregate
  as numbers.

Filters (``where`` on nodes, ``filters`` on edges) use ``op`` in ``=, <>, <, >, <=, >=``
(the property must be present and satisfy it), ``contains`` / ``not_contains`` for list
properties (``not_contains`` also requires the property present), and ``part: "year"``
to compare a date's year with an integer. Dates are written ``YYYY-MM-DD``. Edge
filters also allow two time operators over a start/end pair of edge properties:
``current`` (start present, end absent) and ``during`` (start <= year and end absent
or >= year).
"""

from __future__ import annotations

import json
from typing import Any

from ..t1.load import schema

ANSWERS = {"names", "names_with", "values", "list_items", "count", "count_values", "aggregate",
           "count_per", "top", "compare", "per"}
NUMERIC = {"int", "float", "float_text"}
CMP = {"=", "<>", "<", ">", "<=", ">="}
OPS = {"=", "<>", "<", ">", "<=", ">=", "contains", "not_contains", "starts_with", "ends_with", "contains_text"}
TEXT_OPS = {"starts_with", "ends_with", "contains_text"}
AGG = {"max", "min", "avg", "sum"}
TESTS = {"which_greater", "equal", "difference"}


class InvalidRequest(ValueError):
    pass


class Card:
    """A graph's schema as the request validator and the prompt see it.

    Each label has a **key property**: the one a node's ``name`` in a request is
    matched against and the one answers report. In order: the schema entity's
    ``key`` if given; ``name`` for a CypherBench schema (every entity has it though
    the schema omits it; also a raw schema with ``"cypherbench": true``); else
    ``name``, ``title``, or the first string property.
    """

    def __init__(self, graph: str, raw: dict | None = None) -> None:
        s = raw or schema(graph)
        self.graph = graph
        self.labels: dict[str, dict[str, str]] = {}
        self.keys: dict[str, str] = {}
        for e in s["entities"]:
            props = dict(e.get("properties") or {})
            if e.get("key"):
                key = e["key"]
            elif raw is None or raw.get("cypherbench"):
                key = "name"  # CypherBench: every entity has `name`, though the schema omits it
            else:
                key = next((k for k in ("name", "title") if k in props),
                           next((k for k, t in props.items() if t == "str"), "name"))
            if key == "name":
                props.setdefault("name", "str")
            self.labels[e["label"]] = props
            self.keys[e["label"]] = key
        self.rels: dict[str, list[tuple[str, str, dict[str, str]]]] = {}
        for r in s["relations"]:
            self.rels.setdefault(r["label"], []).append((r["subj_label"], r["obj_label"], dict(r.get("properties") or {})))

    def rel_props(self, rtype: str, src: str, dst: str) -> dict[str, str] | None:
        for s, o, p in self.rels.get(rtype, []):
            if s == src and o == dst:
                return p
        return None

    def prop_type(self, label: str, prop: str) -> str | None:
        return self.labels.get(label, {}).get(prop)


def _need(cond: bool, msg: str) -> None:
    if not cond:
        raise InvalidRequest(msg)


def _check_filter(f: dict, ptypes: dict[str, str], where: str, *, edge: bool) -> None:
    _need(isinstance(f, dict), f"{where}: a filter must be an object")
    op = f.get("op")
    if edge and op in ("current", "during"):
        for k in ("start", "end"):
            _need(f.get(k) in ptypes, f"{where}: {op} needs '{k}' naming an edge property, one of {sorted(ptypes)}")
        if op == "during":
            _need(isinstance(f.get("year"), int), f"{where}: during needs an integer 'year'")
        return
    _need(op in OPS, f"{where}: op must be one of {sorted(OPS)}")
    p = f.get("prop")
    _need(p in ptypes, f"{where}: unknown property {p!r}; options {sorted(ptypes)}")
    t = ptypes[p]
    if f.get("ref") is not None:
        _need(not edge, f"{where}: 'ref' is for node filters in 'where'")
        _need(op in CMP, f"{where}: a 'ref' comparison needs op in {sorted(CMP)}")
        _need(isinstance(f["ref"], dict) and f["ref"].get("var") and f["ref"].get("prop"),
              f"{where}: ref must be {{\"var\": <node var>, \"prop\": <property>}}")
        _need("value" not in f, f"{where}: give either 'value' or 'ref', not both")
        _need(t != "float_text", f"{where}: 'ref' does not support numbers stored as text")
        return
    _need("value" in f, f"{where}: missing 'value'")
    if f.get("part") == "size":
        _need(t.startswith("list"), f"{where}: part 'size' needs a list property; {p} is {t}")
        _need(op in CMP and isinstance(f["value"], int) and not isinstance(f["value"], bool),
              f"{where}: a size comparison needs op in {sorted(CMP)} and an integer value")
        return
    if t == "float_text":
        _need(op in CMP and isinstance(f["value"], (int, float)) and not isinstance(f["value"], bool),
              f"{where}: {p} is a number stored as text: use op in {sorted(CMP)} with a numeric value")
        return
    if op in ("contains", "not_contains"):
        _need(t.startswith("list"), f"{where}: {op} needs a list property; {p} is {t}")
    if op in TEXT_OPS:
        _need(t == "str" and isinstance(f["value"], str), f"{where}: {op} needs a string property and a string value")
    if f.get("part") is not None:
        _need(f.get("part") == "year" and t in ("date", "datetime"), f"{where}: part 'year' needs a date property")
        _need(isinstance(f["value"], int), f"{where}: a year comparison needs an integer value")


def validate(req: Any, card: Card) -> dict:
    """Check ``req`` against ``card`` and return its normalised form; raise :class:`InvalidRequest`.

    Normalisation (the compilers read only the normalised form):
    - every node spec gains ``_key``, its label's key property;
    - ``any_of`` entries that are strings name edges in ``edges`` by their ``var``;
      those edges move out of the required pattern into that branch;
    - ``names_with`` with ``prop`` becomes ``props: [prop]``.
    """
    _need(isinstance(req, dict), "the request must be a JSON object")
    req = json.loads(json.dumps(req))
    nodes = req.get("nodes")
    _need(isinstance(nodes, dict) and "n" in nodes, "nodes must be an object that includes 'n'")
    for v, spec in nodes.items():
        _need(isinstance(spec, dict) and spec.get("label") in card.labels,
              f"node {v}: label must be one of {sorted(card.labels)}")
        if spec.get("name") is not None:
            _need(isinstance(spec["name"], (str, int, float)) and not isinstance(spec["name"], bool),
                  f"node {v}: name must be a string")
        spec["_key"] = card.keys[spec["label"]]
        kt = card.labels[spec["label"]].get(spec["_key"], "str")
        if kt in ("int", "float") and isinstance(spec.get("name"), str):
            try:
                spec["name"] = int(spec["name"]) if kt == "int" else float(spec["name"])
            except ValueError as exc:
                raise InvalidRequest(f"node {v}: {spec['label']}'s key {spec['_key']} is a number") from exc

    edges = req.get("edges") or []
    _need(isinstance(edges, list), "edges must be a list")
    any_of = req.get("any_of") or []
    _need(isinstance(any_of, list), "any_of must be a list of edge lists")
    if any_of:
        by_var = {e.get("var"): e for e in edges if isinstance(e, dict) and e.get("var")}
        moved: set[str] = set()
        branches = []
        for i, br in enumerate(any_of):
            br = br if isinstance(br, list) else [br]
            out = []
            for x in br:
                if isinstance(x, str):
                    _need(x in by_var, f"any_of[{i}]: {x!r} names no edge in 'edges' (give the edge a 'var')")
                    out.append(by_var[x])
                    moved.add(x)
                else:
                    out.append(x)
            branches.append(out)
        req["edges"] = edges = [e for e in edges if not (isinstance(e, dict) and e.get("var") in moved)]
        req["any_of"] = any_of = branches
    opt_in = req.get("optional") or []
    if isinstance(opt_in, list) and any(isinstance(x, str) for x in opt_in):
        by_var = {e.get("var"): e for e in edges if isinstance(e, dict) and e.get("var")}
        outs = []
        for x in opt_in:
            if isinstance(x, str):
                _need(x in by_var, f"optional: {x!r} names no edge in 'edges' (give the edge a 'var')")
                outs.append(by_var[x])
            else:
                outs.append(x)
        moved_o = {x for x in opt_in if isinstance(x, str)}
        req["edges"] = edges = [e for e in edges if not (isinstance(e, dict) and e.get("var") in moved_o)]
        req["optional"] = outs
    none_in = req.get("none") or []
    if none_in:
        _need(isinstance(none_in, list) and len(none_in) == 1, "none takes exactly one edge")
        if isinstance(none_in[0], str):
            by_var = {e.get("var"): e for e in edges if isinstance(e, dict) and e.get("var")}
            _need(none_in[0] in by_var, f"none: {none_in[0]!r} names no edge in 'edges'")
            req["none"] = none_in = [by_var[none_in[0]]]
            req["edges"] = edges = [e for e in edges if e is not none_in[0]]
    edge_vars: dict[str, dict] = {}

    def check_edges(es: Any, where: str, scope: set[str]) -> None:
        _need(isinstance(es, list), f"{where} must be a list")
        for i, e in enumerate(es):
            w = f"{where}[{i}]"
            _need(isinstance(e, dict), f"{w}: an edge must be an object")
            a, b, t = e.get("from"), e.get("to"), e.get("type")
            _need(a in nodes and b in nodes, f"{w}: from/to must name nodes in 'nodes'")
            _need(t in card.rels, f"{w}: unknown relationship {t!r}")
            ptypes = card.rel_props(t, nodes[a]["label"], nodes[b]["label"])
            _need(ptypes is not None,
                  f"{w}: {t} does not go from {nodes[a]['label']} to {nodes[b]['label']}; it connects "
                  + ", ".join(f"{s}->{o}" for s, o, _ in card.rels[t]))
            if e.get("var") is not None:
                _need(isinstance(e["var"], str) and e["var"] not in nodes and e["var"] not in scope,
                      f"{w}: edge var {e.get('var')!r} must not repeat a node or another edge in the same pattern")
                scope.add(e["var"])
                edge_vars[e["var"]] = {"edge": e, "ptypes": ptypes}
            for j, f in enumerate(e.get("filters") or []):
                _check_filter(f, ptypes, f"{w}.filters[{j}]", edge=True)

    required: set[str] = set()
    check_edges(edges, "edges", required)
    if any_of:
        _need(len(any_of) >= 2, "any_of needs at least two branches")
        for i, br in enumerate(any_of):
            check_edges(br, f"any_of[{i}]", set(required))
    opt = req.get("optional") or []
    check_edges(opt, "optional", set(required))
    _need(len(opt) <= 1, "at most one optional edge")
    if opt:
        _need("n" in (opt[0]["from"], opt[0]["to"]), "the optional edge must touch n")
    if none_in:
        check_edges(none_in, "none", set(required))
        ne = none_in[0]
        _need("n" in (ne["from"], ne["to"]) and ne["from"] != ne["to"], "the none edge must join n to another node")
        far = ne["to"] if ne["from"] == "n" else ne["from"]
        _need(far not in pattern_vars(edges + [x for br in any_of for x in br] + opt),
              "the none edge's other node must not appear elsewhere in the pattern")
        req["_none_far"] = far
    for i, f in enumerate(req.get("where") or []):
        _need(isinstance(f, dict) and f.get("var") in nodes, f"where[{i}]: var must name a node")
        _check_filter(f, card.labels[nodes[f["var"]]["label"]], f"where[{i}]", edge=False)
        if f.get("ref") is not None:
            rv = f["ref"]["var"]
            _need(rv in nodes, f"where[{i}]: ref.var must name a node")
            _need(f["ref"]["prop"] in card.labels[nodes[rv]["label"]],
                  f"where[{i}]: ref.prop must be a property of {nodes[rv]['label']}")
            _need(none_in == [] or req.get("_none_far") not in (f["var"], rv), f"where[{i}]: ref cannot use the none node")

    ans = req.get("answer")
    _need(isinstance(ans, dict) and ans.get("kind") in ANSWERS, f"answer.kind must be one of {sorted(ANSWERS)}")
    kind = ans["kind"]
    nprops = card.labels[nodes["n"]["label"]]
    if kind == "names_with":
        props = ans.get("props") if ans.get("props") is not None else [ans.get("prop")]
        _need(isinstance(props, list) and props and all(p in nprops for p in props),
              f"answer.props must be properties of {nodes['n']['label']}: {sorted(nprops)}")
        ans["props"] = props
        ans.pop("prop", None)
    if kind in ("values", "list_items", "count_values", "top", "compare"):
        _need(ans.get("prop") in nprops, f"answer.prop must be a property of {nodes['n']['label']}: {sorted(nprops)}")
    if kind == "list_items":
        _need(nprops[ans["prop"]].startswith("list"), "list_items needs a list property")
    if kind == "aggregate":
        _need(ans.get("fn") in AGG, f"answer.fn must be one of {sorted(AGG)}")
        _need(not none_in or (ans.get("var") or "n") == "n", "an aggregate over another variable cannot use none")
        var = ans.get("var") or "n"
        _need(var == "n" or not any_of, "an aggregate over another variable cannot be combined with any_of")
        if var in nodes:
            ptypes = card.labels[nodes[var]["label"]]
        else:
            _need(var in edge_vars and edge_vars[var]["edge"] in edges,
                  "answer.var must name a node or an edge var in 'edges' (not in any_of or optional)")
            ptypes = edge_vars[var]["ptypes"]
        _need(ans.get("prop") in ptypes, f"answer.prop must be a property of {var}: {sorted(ptypes)}")
        ans["_numtext"] = ptypes[ans["prop"]] == "float_text"
        if ans.get("part") is not None:
            _need(ans["part"] == "year" and ptypes[ans["prop"]] in ("date", "datetime"), "part 'year' needs a date property")
            _need(ans["fn"] in ("max", "min"), "part 'year' supports max and min")
    if kind == "top":
        _need(ans.get("order") in ("asc", "desc"), "answer.order must be asc or desc")
        if ans.get("props") is not None:
            _need(isinstance(ans["props"], list) and all(p in nprops for p in ans["props"]),
                  f"answer.props must be properties of {nodes['n']['label']}: {sorted(nprops)}")
        ans["_numtext"] = nprops[ans["prop"]] == "float_text"
        if ans.get("limit") is not None:
            _need(isinstance(ans["limit"], int) and ans["limit"] > 0, "answer.limit must be a positive integer")
    if kind == "count_per":
        _need(ans.get("of") in nodes and ans["of"] != "n", "answer.of must name a node other than n")
        _need(not any_of, "count_per cannot be combined with any_of")
        ans.update(kind="per", fn="count")
        kind = "per"
    elif kind == "per":
        of = ans.get("of")
        _need(not any_of, "per cannot be combined with any_of")
        _need(ans.get("fn") in AGG | {"count"}, f"answer.fn must be one of {sorted(AGG | {'count'})}")
        if of in nodes:
            _need(of != "n", "answer.of must name a node other than n, or an edge var")
            optypes = card.labels[nodes[of]["label"]]
        else:
            _need(of in edge_vars, "answer.of must name a node other than n, or an edge var")
            optypes = edge_vars[of]["ptypes"]
            ans["_edge"] = True
        if ans["fn"] != "count":
            _need(ans.get("prop") in optypes and optypes[ans["prop"]] in NUMERIC,
                  f"answer.prop must be a numeric property of {of}: "
                  f"{sorted(k for k, t in optypes.items() if t in NUMERIC)}")
            ans["_numtext"] = optypes[ans["prop"]] == "float_text"
        if ans.get("having") is not None:
            h = ans["having"]
            _need(isinstance(h, dict) and h.get("op") in CMP and isinstance(h.get("value"), (int, float))
                  and not isinstance(h.get("value"), bool), f"answer.having must be {{op in {sorted(CMP)}, numeric value}}")
        if ans.get("order") is not None:
            _need(ans["order"] in ("asc", "desc"), "answer.order must be asc or desc")
        if ans.get("limit") is not None:
            _need(ans.get("order") is not None, "answer.limit needs answer.order")
            _need(isinstance(ans["limit"], int) and ans["limit"] > 0, "answer.limit must be a positive integer")
    if kind == "compare":
        o = ans.get("other")
        _need(o in nodes and o != "n", "answer.other must name a node other than n")
        _need(nodes["n"].get("name") is not None and nodes[o].get("name") is not None,
              "compare needs both nodes named")
        _need(ans.get("test") in TESTS, f"answer.test must be one of {sorted(TESTS)}")
        _need(ans["prop"] in card.labels[nodes[o]["label"]], f"{ans['prop']} is not a property of {nodes[o]['label']}")
        _need(not (edges or any_of or opt or none_in), "compare takes two named nodes and no edges")
    used = {"n"}
    for e in edges + [x for br in any_of for x in br] + opt:
        used.update((e["from"], e["to"]))
    if kind == "compare":
        used.add(ans["other"])
    for f in req.get("where") or []:
        used.add(f["var"])
        if f.get("ref"):
            used.add(f["ref"]["var"])
    for e in none_in:
        used.update((e["from"], e["to"]))
    _need(set(nodes) <= used, f"nodes not connected to anything: {sorted(set(nodes) - used)}")
    if kind == "per" and not ans.get("_edge"):
        _need(ans["of"] in used and ans["of"] != req.get("_none_far"), "answer.of is not in the pattern")
    if kind == "per" and ans.get("_edge"):
        _need(edge_vars[ans["of"]]["edge"] in edges + opt, "answer.of must be an edge in 'edges' or 'optional'")
    if kind == "aggregate" and (ans.get("var") or "n") in nodes:
        _need((ans.get("var") or "n") in used, "answer.var is not in the pattern")
    return req


def pattern_vars(edges: list[dict]) -> list[str]:
    out: list[str] = []
    for e in edges:
        for v in (e["from"], e["to"]):
            if v not in out:
                out.append(v)
    return out
