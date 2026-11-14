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
           "count_per", "top", "compare"}
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
    _need("value" in f, f"{where}: missing 'value'")
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
    for i, f in enumerate(req.get("where") or []):
        _need(isinstance(f, dict) and f.get("var") in nodes, f"where[{i}]: var must name a node")
        _check_filter(f, card.labels[nodes[f["var"]]["label"]], f"where[{i}]", edge=False)

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
        var = ans.get("var") or "n"
        _need(var == "n" or not any_of, "an aggregate over another variable cannot be combined with any_of")
        if var in nodes:
            ptypes = card.labels[nodes[var]["label"]]
        else:
            _need(var in edge_vars and edge_vars[var]["edge"] in edges,
                  "answer.var must name a node or an edge var in 'edges' (not in any_of or optional)")
            ptypes = edge_vars[var]["ptypes"]
        _need(ans.get("prop") in ptypes, f"answer.prop must be a property of {var}: {sorted(ptypes)}")
        if ans.get("part") is not None:
            _need(ans["part"] == "year" and ptypes[ans["prop"]] in ("date", "datetime"), "part 'year' needs a date property")
            _need(ans["fn"] in ("max", "min"), "part 'year' supports max and min")
    if kind == "top":
        _need(ans.get("order") in ("asc", "desc"), "answer.order must be asc or desc")
        if ans.get("limit") is not None:
            _need(isinstance(ans["limit"], int) and ans["limit"] > 0, "answer.limit must be a positive integer")
    if kind == "count_per":
        _need(ans.get("of") in nodes and ans["of"] != "n", "answer.of must name a node other than n")
        _need(not any_of, "count_per cannot be combined with any_of")
    if kind == "compare":
        o = ans.get("other")
        _need(o in nodes and o != "n", "answer.other must name a node other than n")
        _need(nodes["n"].get("name") is not None and nodes[o].get("name") is not None,
              "compare needs both nodes named")
        _need(ans.get("test") in TESTS, f"answer.test must be one of {sorted(TESTS)}")
        _need(ans["prop"] in card.labels[nodes[o]["label"]], f"{ans['prop']} is not a property of {nodes[o]['label']}")
        _need(not (edges or any_of or opt), "compare takes two named nodes and no edges")
    used = {"n"}
    for e in edges + [x for br in any_of for x in br] + opt:
        used.update((e["from"], e["to"]))
    if kind == "compare":
        used.add(ans["other"])
    for f in req.get("where") or []:
        used.add(f["var"])
    _need(set(nodes) <= used, f"nodes not connected to anything: {sorted(set(nodes) - used)}")
    if kind == "count_per":
        _need(ans["of"] in used, "answer.of is not in the pattern")
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
