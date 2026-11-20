"""The kill-test v3 typed request (``utils/killtests/typed/request.py``) as the internal form.

``from_v3(req, card)`` takes a request already normalised by ``request.validate`` and
returns an operator tree with the same meaning, or raises :class:`NotExpressible` with
a short machine-readable ``reason``. Where a mapping is uncertain it refuses rather
than approximates.

| v3 | Internal form |
|---|---|
| subject ``n`` | ``Scan(label)``; its ``name`` is ``Cond(_key, "=", name)`` (names are key values, not stored ids, so never ``Anchors``); ``where`` on ``n`` joins the same ``Where`` |
| a pattern edge to a child node | ``Having(set, Hop(type, out/in, child label, edge conds), target_conds=child conds, target=child subtree)`` |
| ``any_of`` | ``Union_`` of the whole pattern built once per branch (required edges + that branch) |
| ``none`` | ``Having(..., exists=False, target_conds=far node conds)`` |
| ``names`` / ``names_with`` / ``values`` | ``Nodes`` / ``Nodes(props)`` / ``Values`` |
| ``count`` / ``count_values`` / ``aggregate`` | ``Count`` / ``Aggregate("count_values")`` / ``Aggregate(fn)`` |
| ``top`` with ``limit`` | ``Rank(order, k=limit, prop)`` |
| ``per`` / ``count_per`` over a node down a plain chain from ``n`` (or the optional edge) | ``GroupBy(members, hops, fn, prop, having, order, k)`` |

The pattern must be a tree rooted at ``n``: one path from ``n`` to every other node.
v3 follows Cypher's single-``MATCH`` rule that two relationships in one pattern are
different relationships, which nested ``Having`` cannot say, so two edges of one type
are accepted only when they can never bind the same relationship anyway: one pair of corresponding endpoints is provably two different nodes
(different card labels, or both named with different key values).

A ``per`` follows the tree from ``n`` to ``of``. Every node passed through, and ``of``
itself, must have no ``name``, no ``where`` and no other edges: ``GroupBy`` walks plain
hops and cannot narrow which ends count. Each hop keeps its edge filters.

**Known differences** (``semantic_differences``). The tree is returned anyway:
- ``ties``: v3 ``top`` and ranked ``per`` cut at ``LIMIT`` without ties; ``Rank`` and
  ``GroupBy`` keep every item tied with the k-th (S8).
- ``missing_values``: v3 sorts a missing key as Cypher does (after every value
  ascending, before every value descending), so a ``top`` can return nodes without
  the property; ``Rank`` leaves them out (O3). The same holds for a ranked ``per``
  whose ``avg``/``min``/``max`` is null for a member with nothing.

A ``per`` over a *required* edge cannot show the S9 empty-group difference here: the
members set keeps that edge as ``Having(exists=True)``, so no member has an empty walk.

Refusal reasons: ``compare``, ``list_items``, ``aggregate_other_var``,
``aggregate_year``, ``aggregate_non_numeric``, ``top_without_limit``, ``top_props``,
``rank_type``, ``per_edge``, ``per_not_in_pattern``, ``per_target_filter``, ``ref``,
``edge_time_window``, ``float_text``, ``cond_value_type``,
``name_type``, ``not_tree``, ``same_type_twice``, ``disconnected_var``.
"""

from __future__ import annotations

from typing import Any

from utils.agent.catalog import VALUE_TYPES

from .aggregate import Aggregate
from .base import COMPARE, Cond, Count, Hop, Nodes, Scan, Values
from .edges import Having, Union_
from .filters import Where
from .groupby import GroupBy
from .rank import Rank
from .validate import DATE_TYPES, NUMERIC_TYPES, InvalidOp, check_conds


class NotExpressible(ValueError):
    """A v3 request the internal form cannot say with the same meaning."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason


def _vtype(raw: str | None) -> str:
    return VALUE_TYPES.get(str(raw or "string").lower(), "string")


def _cond(f: dict, ptypes: dict[str, str]) -> Cond:
    """One v3 filter (node ``where`` or edge ``filters``) as a ``Cond``."""
    op = f.get("op")
    if op in ("current", "during"):
        raise NotExpressible("edge_time_window", op)
    if f.get("ref") is not None:
        raise NotExpressible("ref")
    prop, value = f["prop"], f["value"]
    raw = ptypes[prop]
    if raw == "float_text":
        raise NotExpressible("float_text", prop)
    vtype = _vtype(raw)
    if f.get("part") == "size":
        c = Cond(prop, "size", value, cmp=op)
    elif f.get("part") == "year":
        c = Cond(prop, "year", value, cmp=op)
    else:
        c = Cond(prop, op, value)
    try:
        check_conds((c,), lambda p: {vtype} if p == prop else set(), "v3")
    except InvalidOp as exc:
        raise NotExpressible("cond_value_type", str(exc)) from exc
    return c


def _node_conds(req: dict, card: Any, var: str) -> tuple[Cond, ...]:
    spec = req["nodes"][var]
    props = card.labels[spec["label"]]
    out: list[Cond] = []
    if spec.get("name") is not None:
        key = spec["_key"]
        c = Cond(key, "=", spec["name"])
        vtype = _vtype(props.get(key))
        try:
            check_conds((c,), lambda p: {vtype}, "v3.name")
        except InvalidOp as exc:
            raise NotExpressible("name_type", str(exc)) from exc
        out.append(c)
    out += [_cond(f, props) for f in req.get("where") or [] if f["var"] == var]
    return tuple(out)


def _edge_conds(req: dict, card: Any, e: dict) -> tuple[Cond, ...]:
    nodes = req["nodes"]
    ptypes = card.rel_props(e["type"], nodes[e["from"]]["label"], nodes[e["to"]]["label"]) or {}
    return tuple(_cond(f, ptypes) for f in e.get("filters") or [])


def _distinct_nodes(nodes: dict, a: str, b: str) -> bool:
    """True when vars ``a`` and ``b`` can never bind the same node: different card
    labels (a node has one, S2), or both named with different key values."""
    if a == b:
        return False
    sa, sb = nodes[a], nodes[b]
    if sa["label"] != sb["label"]:
        return True
    return sa.get("name") is not None and sb.get("name") is not None and sa["name"] != sb["name"]


def _same_type_safe(nodes: dict, edges: list[dict]) -> None:
    """Refuse two edges of one type unless they can never bind the same relationship.

    Cypher's single ``MATCH`` makes them different relationships; nested ``Having``
    cannot say that. When an endpoint of one provably differs from the matching
    endpoint of the other, they are different relationships anyway, and the rule is
    vacuous.
    """
    for i, e1 in enumerate(edges):
        for e2 in edges[i + 1:]:
            if e1["type"] != e2["type"]:
                continue
            if not (_distinct_nodes(nodes, e1["from"], e2["from"]) or _distinct_nodes(nodes, e1["to"], e2["to"])):
                raise NotExpressible("same_type_twice", e1["type"])


def _tree(edges: list[dict], nodes: dict) -> dict[str, list[tuple[dict, str]]]:
    """``var -> [(edge, child)]`` for a pattern that is a tree rooted at ``n``."""
    _same_type_safe(nodes, edges)
    children: dict[str, list[tuple[dict, str]]] = {"n": []}
    used: set[int] = set()
    frontier = ["n"]
    while frontier:
        v = frontier.pop(0)
        for i, e in enumerate(edges):
            if i in used or v not in (e["from"], e["to"]):
                continue
            if e["from"] == e["to"]:
                raise NotExpressible("not_tree", "a relationship from a node to itself")
            child = e["to"] if e["from"] == v else e["from"]
            if child in children:
                raise NotExpressible("not_tree", "a cycle")
            used.add(i)
            children[v].append((e, child))
            children[child] = []
            frontier.append(child)
    if len(used) != len(edges):
        raise NotExpressible("not_tree", "edges not connected to n")
    return children


def _build(req: dict, card: Any, children: dict, var: str, with_conds: bool = True) -> Any:
    nodes = req["nodes"]
    s: Any = Scan(nodes[var]["label"])
    conds = _node_conds(req, card, var) if with_conds else ()
    if conds:
        s = Where(s, conds)
    for e, child in children[var]:
        hop = Hop(e["type"], "out" if e["from"] == var else "in", nodes[child]["label"], _edge_conds(req, card, e))
        target = _build(req, card, children, child, with_conds=False) if children[child] else None
        s = Having(s, hop, True, _node_conds(req, card, child), target)
    return s


def _core(req: dict, card: Any, edges: list[dict]) -> tuple[Any, dict]:
    children = _tree(edges, req["nodes"])
    far = req.get("_none_far")
    for f in req.get("where") or []:
        if f["var"] not in children and f["var"] != far:
            raise NotExpressible("disconnected_var", f["var"])
    return _build(req, card, children, "n"), children


def _base(req: dict, card: Any) -> tuple[Any, dict]:
    """The subject set (pattern, any_of, none) and the required pattern's tree."""
    for f in req.get("where") or []:
        if f.get("ref") is not None:
            raise NotExpressible("ref")
    edges = req.get("edges") or []
    if req.get("any_of"):  # validate refuses per with any_of, so the tree is not needed after
        s, children = Union_(tuple(_core(req, card, edges + br)[0] for br in req["any_of"])), {}
    else:
        s, children = _core(req, card, edges)
    if req.get("none"):
        e, far = req["none"][0], req["_none_far"]
        nodes = req["nodes"]
        hop = Hop(e["type"], "out" if e["from"] == "n" else "in", nodes[far]["label"], _edge_conds(req, card, e))
        s = Having(s, hop, False, _node_conds(req, card, far))
    return s, children


def _numeric(card: Any, label: str, prop: str, reason: str, ok: tuple[str, ...] = NUMERIC_TYPES) -> None:
    raw = card.labels[label].get(prop)
    if raw == "float_text":
        raise NotExpressible("float_text", prop)
    if _vtype(raw) not in ok:
        raise NotExpressible(reason, f"{prop} is {raw}")


def from_v3(req: dict, card: Any) -> Any:
    """The internal form of a normalised v3 request; raises :class:`NotExpressible`."""
    nodes, ans = req["nodes"], req["answer"]
    kind = ans["kind"]
    if kind in ("compare", "list_items"):
        raise NotExpressible(kind)
    if kind == "aggregate" and (ans.get("var") or "n") != "n":
        raise NotExpressible("aggregate_other_var")
    s, children = _base(req, card)
    nlabel = nodes["n"]["label"]
    if kind == "names":
        return Nodes(s)
    if kind == "names_with":
        return Nodes(s, tuple(ans["props"]))
    if kind == "values":
        return Values(s, ans["prop"], bool(ans.get("distinct")))
    if kind == "count":
        return Count(s)
    if kind == "count_values":
        return Aggregate(s, "count_values", ans["prop"])
    if kind == "aggregate":
        if ans.get("part") is not None:
            raise NotExpressible("aggregate_year")
        fn = ans["fn"]
        _numeric(card, nlabel, ans["prop"], "aggregate_non_numeric",
                 NUMERIC_TYPES if fn in ("sum", "avg") else NUMERIC_TYPES + DATE_TYPES + ("string",))
        return Aggregate(s, fn, ans["prop"])
    if kind == "top":
        if ans.get("limit") is None:
            raise NotExpressible("top_without_limit")
        if ans.get("props"):
            raise NotExpressible("top_props")
        _numeric(card, nlabel, ans["prop"], "rank_type", NUMERIC_TYPES + DATE_TYPES + ("string",))
        return Rank(s, ans["order"], int(ans["limit"]), ans["prop"])
    if kind == "per":
        return _per(req, card, s, children)
    raise NotExpressible("unknown_kind", kind)


def _path(children: dict, of: str) -> list[tuple[dict, str]]:
    """The ``(edge, child)`` steps from ``n`` down the tree to ``of``."""
    for e, child in children["n"]:
        if child == of:
            return [(e, child)]
        sub = _path({**children, "n": children[child]}, of)
        if sub:
            return [(e, child)] + sub
    return []


def _per(req: dict, card: Any, members: Any, children: dict) -> GroupBy:
    nodes, ans = req["nodes"], req["answer"]
    of = ans["of"]
    if ans.get("_edge"):
        raise NotExpressible("per_edge")
    if of in children:
        path = _path(children, of)
        for _, mid in path[:-1]:  # a node passed through must not narrow which ends count
            if len(children[mid]) != 1 or _node_conds(req, card, mid):
                raise NotExpressible("per_target_filter", f"{mid} on the way to {of} has its own filters or edges")
        if children[of]:
            raise NotExpressible("per_target_filter", "the grouped node has further edges")
    else:
        opt = req.get("optional") or []
        if not (opt and of in (opt[0]["from"], opt[0]["to"])):
            raise NotExpressible("per_not_in_pattern")
        path = [(opt[0], of)]
    if _node_conds(req, card, of):
        raise NotExpressible("per_target_filter", "the grouped node has a name or where filter")
    hops, at = [], "n"
    for e, child in path:
        hops.append(Hop(e["type"], "out" if e["from"] == at else "in", nodes[child]["label"], _edge_conds(req, card, e)))
        at = child
    fn, prop = ans["fn"], None
    if fn != "count":
        prop = ans["prop"]
        _numeric(card, nodes[of]["label"], prop, "aggregate_non_numeric")
    having = None
    if ans.get("having") is not None:
        h = ans["having"]
        if h["op"] not in COMPARE:
            raise NotExpressible("having_op", h["op"])
        having = (h["op"], h["value"])
    return GroupBy(members, tuple(hops), fn, prop, having, ans.get("order"), ans.get("limit"))


def semantic_differences(req: dict) -> list[str]:
    """Where a converted tree's answer can differ from v3's, by rule (module docstring)."""
    ans = req["answer"]
    kind = ans["kind"]
    out: list[str] = []
    if kind in ("top", "per") and ans.get("limit") is not None:
        out.append("ties")
    if kind == "top" or (kind == "per" and ans.get("order") and ans.get("fn") in ("avg", "min", "max")):
        out.append("missing_values")
    return out


__all__ = ["NotExpressible", "from_v3", "semantic_differences"]
