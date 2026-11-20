"""Compile the operator algebra to Cypher (Neo4j).

Two parts:

- :func:`compile_typed_walk` is today's typed-step walk (``expand``/``count``),
  moved here from ``CypherQueryBuilder._typed_step`` unchanged: the builder keeps
  its guards, its describe/scan/common dispatch and its store rule
  (``_typed_filter``), and hands this the walk, the seeds and the bound filter.
  Its output is byte-identical to before (Phase D's snapshot check).
- :func:`compile_cypher` compiles every class of the algebra
  (``utils.specialists.algebra.ir.OPS``) with the meaning fixed in
  ``docs/era-2-expansion/operator-algebra.md``. The result contracts, the
  post-steps and :func:`~utils.specialists.algebra.compiled.finish` are shared
  with the Gremlin compiler (``utils/specialists/algebra/compiled.py``).
"""

from __future__ import annotations

from typing import Any

from utils.specialists.algebra.aggregate import Aggregate
from utils.specialists.algebra.base import (Anchors, Common, Cond, Count, Describe, Expand, FromStep, Hop, Intersect,
                                            Nodes, Scan, Values, Walk)
from utils.specialists.algebra.compiled import (ISO_REGEX, NUMBER_REGEX, Backend, Compiled, Params, safe_ident)
from utils.specialists.algebra.edges import Having, Union_
from utils.specialists.algebra.filters import Where
from utils.specialists.algebra.groupby import GroupBy
from utils.specialists.algebra.path import Reach, Shortest
from utils.specialists.algebra.rank import Rank
from utils.specialists.algebra.typescan import TypeScan
from utils.specialists.algebra.verify import Verify

# --- Task 1: today's typed-step walk, moved from the builder ---------------------


def filter_predicate(bound: Any, var: str) -> str:
    """The Cypher predicate restricting ``var`` to the bound filter.

    Two shapes, because getting it wrong silently matches nothing rather
    than erroring: ``x_mitre_platforms`` holds a list and the question means
    membership; ``Abstraction`` holds a string and it means equality.
    """
    from .builder import _SAFE_PROPERTY_RE, _safe_ident

    if not bound or not var:
        return ""
    _, prop, _, is_list = bound
    safe_prop = _safe_ident(prop, _SAFE_PROPERTY_RE, "property")
    if is_list:
        return f"$filterValue IN coalesce({var}.`{safe_prop}`, [])"
    return f"{var}.`{safe_prop}` = $filterValue"


def compile_typed_walk(walk: Walk, seed_ids: Any, bound: Any) -> tuple[str, dict[str, Any]]:
    """Today's typed-step walk: the query text and its parameters.

    ``walk`` comes from ``from_typed_step`` (no card), ``seed_ids`` are the
    resolved anchors, and ``bound`` is ``CypherQueryBuilder._typed_filter``'s
    ``(label, property, value, is_list)`` or ``None``. Every prefix of the path
    is collected, so an intermediate is retrieved too; rows carry the
    ``generic_neighbors`` column contract.
    """
    from .builder import _SAFE_LABEL_RE, _SAFE_REL_RE, _safe_ident

    hops = list(walk.hops)
    depth = max(1, int(walk.depth or 1))
    blocks: list[str] = []
    collected: list[str] = []
    for i in range(1, len(hops) + 1):
        pattern = []
        for j, hop in enumerate(hops[:i]):
            rel = _safe_ident(hop.relation, _SAFE_REL_RE, "relationship type")
            # An empty target keeps every label the hop reaches.
            target = (":" + _safe_ident(hop.target, _SAFE_LABEL_RE, "target label")
                      if hop.target else "")
            var = f"t{i - 1}" if j == i - 1 else ""
            star = f"*1..{depth}" if len(hops) == 1 and depth > 1 else ""
            if hop.direction == "in":
                pattern.append(f"<-[:{rel}{star}]-({var}{target})")
            else:
                pattern.append(f"-[:{rel}{star}]->({var}{target})")
        terminal = _safe_ident(hops[i - 1].relation, _SAFE_REL_RE, "relationship type")
        where = ""
        if bound is not None and i == len(hops):
            where = f" WHERE {filter_predicate(bound, f't{i - 1}')}"
        carry = ", ".join(["n", *collected])
        blocks.append(
            f"OPTIONAL MATCH (n){''.join(pattern)}{where} "
            f"WITH {carry}, collect(DISTINCT {{m: t{i - 1}, r: '{terminal}'}}) AS k{i - 1}"
        )
        collected.append(f"k{i - 1}")
    query = (
        "MATCH (n) WHERE coalesce(n.attack_id, n.id) IN $ids "
        + " ".join(blocks)
        + f" WITH n, [x IN {' + '.join(collected)} WHERE x.m IS NOT NULL] AS hops "
        "UNWIND (CASE WHEN size(hops) = 0 THEN [{m: null, r: null}] ELSE hops END) AS hop "
        "RETURN coalesce(n.attack_id, n.id) AS anchor_id, n.name AS anchor_name, "
        "labels(n)[0] AS anchor_label, "
        "coalesce(hop.m.attack_id, hop.m.id) AS neighbour_id, "
        "hop.m.name AS neighbour_name, "
        "labels(hop.m)[0] AS neighbour_label, hop.r AS rel_type"
    )
    params: dict[str, Any] = {"ids": list(seed_ids)}
    if bound is not None:
        params["filterValue"] = bound[2]
    return query, params


# --- Task 2: every class of the algebra ----------------------------------------

_DATE_TYPES = ("date", "datetime")
_TEXT_OPS = {"starts_with": "STARTS WITH", "ends_with": "ENDS WITH", "contains_text": "CONTAINS"}
_COMPARE = ("=", "<>", "<", ">", "<=", ">=")
_NODE_SETS = (Anchors, Scan, FromStep, Walk, Intersect, Where, Union_, Having, TypeScan, Reach)


def _guess_type(c: Cond) -> str:
    """A condition's value type when no card says (S5): read from the op and the value."""
    if c.op in ("before", "after", "between", "year"):
        return "date"
    if c.op in ("contains", "not_contains", "size"):
        return "list"
    if isinstance(c.value, bool):
        return "boolean"
    if isinstance(c.value, (int, float)):
        return "number"
    return "string"


def _anchors_in(node: Any) -> list[Anchors]:
    """Every ``Anchors`` in a tree, in order, once each (for S12's ``anchor_not_found``)."""
    import dataclasses

    out: list[Anchors] = []

    def walk(x: Any) -> None:
        if isinstance(x, Anchors):
            if x not in out:
                out.append(x)
        elif dataclasses.is_dataclass(x) and not isinstance(x, type):
            for f in dataclasses.fields(x):
                walk(getattr(x, f.name))
        elif isinstance(x, (tuple, list)):
            for y in x:
                walk(y)

    walk(node)
    return out


class _Cypher:
    """One compilation: parameters, fresh variable names, and the card."""

    def __init__(self, backend: Backend) -> None:
        self.b = backend
        self.p = Params(backend)
        self.n = 0
        self.rels_used: dict[str, str] = {}

    # -- names and values
    def var(self, prefix: str = "v") -> str:
        self.n += 1
        return f"{prefix}{self.n}"

    def param(self, value: Any) -> str:
        return "$" + self.p.add(value)

    def label(self, label: str) -> str:
        return f":{safe_ident(label, 'label')}" if label else ""

    def rel(self, relation: str) -> str:
        name = self.b.rel(relation)
        self.rels_used[name] = relation
        return name

    @staticmethod
    def prop(ref: str, prop: str) -> str:
        return f"{ref}.`{safe_ident(prop, 'property')}`"

    def labels_of(self, node: Any) -> frozenset[str] | None:
        if self.b.card is None:
            return None
        from utils.specialists.algebra.validate import InvalidOp, check

        try:
            return check(node, self.b.card)
        except InvalidOp:
            return None

    def hop_labels(self, start: frozenset[str] | None, hops: tuple[Hop, ...]) -> frozenset[str] | None:
        if self.b.card is None or start is None:
            return None
        from utils.specialists.algebra.validate import InvalidOp, check_hop

        labels = start
        try:
            for h in hops:
                labels = check_hop(self.b.card, labels, h, "hop")
        except InvalidOp:
            return None
        return labels

    # -- conditions (S4, S5, S6)
    def cond(self, ref: str, c: Cond, vtype: str | None) -> str:
        x = self.prop(ref, c.prop)
        vt = vtype or _guess_type(c)
        op = c.op
        nn = f"{x} IS NOT NULL"
        if op == "present":
            return f"coalesce({x} =~ {self.param(NUMBER_REGEX)}, false)" if vt == "number_text" else nn
        if op == "missing":
            return f"NOT coalesce({x} =~ {self.param(NUMBER_REGEX)}, false)" if vt == "number_text" else f"{x} IS NULL"
        if op == "size":
            return f"({nn} AND size({x}) {c.cmp} {self.param(int(c.value))})"
        if op == "contains":
            return f"({nn} AND {self.param(c.value)} IN {x})"
        if op == "not_contains":
            return f"({nn} AND NOT {self.param(c.value)} IN {x})"
        if op in _TEXT_OPS:
            return f"({nn} AND {x} {_TEXT_OPS[op]} {self.param(c.value)})"
        if op in ("before", "after", "between", "year") or vt in _DATE_TYPES:
            iso = f"{x} =~ {self.param(ISO_REGEX)}"
            day = f"substring({x}, 0, 10)"
            if op == "year":
                return f"({nn} AND {iso} AND toInteger(substring({x}, 0, 4)) {c.cmp} {self.param(int(c.value))})"
            if op == "between":
                lo, hi = c.value
                return (f"({nn} AND {iso} AND {day} >= {self.param(str(lo)[:10])} "
                        f"AND {day} <= {self.param(str(hi)[:10])})")
            sym = {"before": "<", "after": ">"}.get(op, op)
            return f"({nn} AND {iso} AND {day} {sym} {self.param(str(c.value)[:10])})"
        if op not in _COMPARE:
            raise ValueError(f"unknown condition op {op!r}")
        if vt == "number_text":
            return f"({nn} AND {x} =~ {self.param(NUMBER_REGEX)} AND toFloat({x}) {op} {self.param(c.value)})"
        return f"({nn} AND {x} {op} {self.param(c.value)})"

    def conds(self, ref: str, conds: tuple[Cond, ...], labels: Any) -> list[str]:
        return [self.cond(ref, c, self.b.prop_type(labels, c.prop)) for c in conds]

    def edge_conds(self, ref: str, hop: Hop) -> list[str]:
        return [self.cond(ref, c, self.b.edge_prop_type(hop.relation, c.prop)) for c in hop.edge_conds]

    def value(self, ref: str, prop: str, vtype: str | None, *, day: bool = True) -> str:
        """A property as a value: ``number_text`` as its number, a date as its ISO day (else null)."""
        x = self.prop(ref, prop)
        if vtype == "number_text":
            return f"CASE WHEN {x} =~ {self.param(NUMBER_REGEX)} THEN toFloat({x}) END"
        if vtype in _DATE_TYPES and day:
            return f"CASE WHEN {x} =~ {self.param(ISO_REGEX)} THEN substring({x}, 0, 10) END"
        return x

    # -- walks
    def arrow(self, hop: Hop, rvar: str = "", star: str = "") -> str:
        r = f"[{rvar}:{self.rel(hop.relation)}{star}]"
        return f"<-{r}-" if hop.direction == "in" else f"-{r}->"

    def chain(self, start: str, hops: tuple[Hop, ...], end: str,
              start_labels: frozenset[str] | None) -> tuple[str, list[str], list[str]]:
        """``(start)-..->(end)`` for ``hops`` (depth 1), with the edge predicates and the
        intermediate variables."""
        pattern, preds, mids = f"({start})", [], []
        for i, h in enumerate(hops):
            rv = self.var("r")
            arrow = self.arrow(h, rv)
            nv = end if i == len(hops) - 1 else self.var("x")
            if i < len(hops) - 1:
                mids.append(nv)
            pattern += f"{arrow}({nv}{self.label(h.target)})"
            preds += self.edge_conds(rv, h)
        return pattern, preds, mids

    def qpp(self, rels: tuple[tuple[str, str], ...]) -> str:
        """A quantified step over ``rels`` (each ``(relation, direction)``) for paths (S10)."""
        if not rels:
            rels = tuple((r, "both") for r in (self.b.card.relations if self.b.card is not None else ()))
        a, r, b = self.var("a"), self.var("r"), self.var("b")
        types = "|".join(dict.fromkeys(self.rel(rel) for rel, _ in rels))
        typed = f":{types}" if types else ""
        dirs = {d for _, d in rels}
        if len(dirs) == 1 and dirs <= {"out", "in", "both"}:
            d = next(iter(dirs))
            arrow = {"out": f"-[{r}{typed}]->", "in": f"<-[{r}{typed}]-", "both": f"-[{r}{typed}]-"}[d]
            return f"(({a}){arrow}({b}))"
        preds = []
        for rel, d in rels:
            t = f"type({r}) = '{self.rel(rel)}'"
            preds.append(t if d == "both" else f"({t} AND {'startNode' if d == 'out' else 'endNode'}({r}) = {a})")
        return f"(({a})-[{r}{typed}]-({b}) WHERE {' OR '.join(preds)})"

    # -- node sets: a clause sequence from nothing, ending with ``WITH DISTINCT var``
    def nodeset(self, node: Any) -> tuple[str, str]:
        v = self.var()
        if isinstance(node, Anchors):
            return (f"MATCH ({v}{self.label(node.label)}) WHERE {v}.id IN {self.param(list(node.ids))} "
                    f"WITH DISTINCT {v}"), v
        if isinstance(node, Scan):
            return f"MATCH ({v}{self.label(node.label)}) WITH DISTINCT {v}", v
        if isinstance(node, TypeScan):
            preds = self.conds(v, node.conds, frozenset([node.label]))
            where = f" WHERE {' AND '.join(preds)}" if preds else ""
            return f"MATCH ({v}{self.label(node.label)}){where} WITH DISTINCT {v}", v
        if isinstance(node, FromStep):
            preds = [f"{v}.id IN ${self.p.input(node.step)}"]
            if node.labels:
                preds.append("(" + " OR ".join(f"{v}{self.label(lab)}" for lab in node.labels) + ")")
            return f"MATCH ({v}) WHERE {' AND '.join(preds)} WITH DISTINCT {v}", v
        if isinstance(node, Walk):
            t, s = self.nodeset(node.start)
            hops = node.hops
            ends = self.labels_of(node)
            if node.depth > 1:
                h, pv = hops[0], self.var("p")
                arrow = self.arrow(h, "", f"*1..{int(node.depth)}")
                e = self.var("e")
                preds = [f"{v} <> {s}"]
                ec = self.edge_conds(e, h)
                if ec:
                    preds.append(f"ALL({e} IN relationships({pv}) WHERE {' AND '.join(ec)})")
                preds += self.conds(v, node.last_conds, ends)
                return (f"{t} MATCH {pv} = ({s}){arrow}({v}{self.label(h.target)}) "
                        f"WHERE {' AND '.join(preds)} WITH DISTINCT {v}"), v
            pattern, preds, _ = self.chain(s, hops, v, self.labels_of(node.start))
            preds += self.conds(v, node.last_conds, ends)
            where = f" WHERE {' AND '.join(preds)}" if preds else ""
            return f"{t} MATCH {pattern}{where} WITH DISTINCT {v}", v
        if isinstance(node, Where):
            t, s = self.nodeset(node.of)
            preds = self.conds(s, node.conds, self.labels_of(node.of))
            return f"{t} WITH {s} WHERE {' AND '.join(preds)}", s
        if isinstance(node, Intersect):
            calls, sets = [], []
            for part in node.parts[1:]:
                t, s = self.nodeset(part)
                c = self.var("c")
                calls.append(f"CALL {{ {t} RETURN collect({s}) AS {c} }}")
                sets.append(c)
            t, s = self.nodeset(node.parts[0])
            keep = ", ".join([v, *sets])
            return (f"{' '.join(calls)} CALL {{ {t} RETURN {s} AS {v} }} WITH {keep} "
                    f"WHERE {' AND '.join(f'{v} IN {c}' for c in sets)} WITH DISTINCT {v}"), v
        if isinstance(node, Union_):
            arms = []
            for part in node.parts:
                t, s = self.nodeset(part)
                arms.append(f"{t} RETURN {s} AS {v}")
            return f"CALL {{ {' UNION '.join(arms)} }} WITH DISTINCT {v}", v
        if isinstance(node, Having):
            pre, keep = "", [v]
            if node.target is not None:
                tt, ts = self.nodeset(node.target)
                tc = self.var("c")
                pre = f"CALL {{ {tt} RETURN collect({ts}) AS {tc} }} "
                keep.append(tc)
            t, s = self.nodeset(node.of)
            m = self.var("m")
            pattern, preds, _ = self.chain(v, (node.hop,), m, None)
            reach = self.hop_labels(self.labels_of(node.of), (node.hop,))
            preds += self.conds(m, node.target_conds, reach)
            if node.target is not None:
                preds.append(f"{m} IN {keep[1]}")
            where = f" WHERE {' AND '.join(preds)}" if preds else ""
            test = f"EXISTS {{ MATCH {pattern}{where} }}"
            return (f"{pre}CALL {{ {t} RETURN {s} AS {v} }} WITH {', '.join(keep)} "
                    f"WHERE {'' if node.exists else 'NOT '}{test} WITH DISTINCT {v}"), v
        if isinstance(node, Reach):
            return f"{self.reach(node, v, int(node.depth))[0]} WITH DISTINCT {v}", v
        raise ValueError(f"{type(node).__name__} is not a node set")

    def reach(self, node: Reach, v: str, depth: int) -> tuple[str, str]:
        """Nodes reachable in 1..depth steps along acyclic paths, never the start (S10).

        A node reachable by any walk of length <= depth from ``s`` (other than ``s``)
        is reachable by an acyclic one no longer, so ``ANY SHORTEST`` per pair is exact.
        Returns the text (rows: ``v`` and its distance ``dist``) and the distance variable.
        """
        t, s = self.nodeset(node.start)
        pv, dist = self.var("p"), self.var("d")
        return (f"{t} MATCH {pv} = ANY SHORTEST ({s}){self.qpp(node.rels)}{{1,{depth}}}({v}) "
                f"WHERE {v} <> {s} WITH {v}, min(length({pv})) AS {dist}"), dist

    # -- the anchor check (S12) and the node-set envelope (S1, S7)
    def found(self, anchors: list[Anchors]) -> tuple[str, str]:
        calls, names = [], []
        for a in anchors:
            x, f = self.var("a"), self.var("f")
            calls.append(f"CALL {{ MATCH ({x}{self.label(a.label)}) WHERE {x}.id IN {self.param(list(a.ids))} "
                         f"RETURN collect(DISTINCT {x}.id) AS {f} }}")
            names.append(f)
        return " ".join(calls), f"[{', '.join(names)}]"

    def envelope(self, text: str, v: str, props: tuple[str, ...], anchors: list[Anchors],
                 dist: str | None = None, depth: int | None = None) -> str:
        """Rows ``id, name, props`` ordered by stored id and capped, with the exact total (S7).

        With ``dist`` (a reach compiled one step past its cap), only nodes within
        ``depth`` are kept and ``partial`` says whether anything lay beyond.
        """
        fields = ["id: x.id", "name: x.name"] + [
            f"`{safe_ident(p, 'property')}`: x.`{p}`" for p in props if p not in ("id", "name")]
        calls, found = self.found(anchors)
        if dist is None:
            head = f"{text} WITH {v} ORDER BY {v}.id WITH collect({v}) AS all_"
            more = ""
        else:
            head = (f"{text} WITH {v}, {dist} ORDER BY {v}.id "
                    f"WITH collect(CASE WHEN {dist} <= {int(depth)} THEN {v} END) AS all_, max({dist}) AS far_")
            more = f", coalesce(far_, 0) > {int(depth)} AS partial"
        if anchors:
            more += f", {found} AS found"
        return " ".join(x for x in (head, calls, f"RETURN size(all_) AS total, "
                                    f"[x IN all_[0..{int(self.b.row_cap)}] | {{{', '.join(fields)}}}] AS rows{more}")
                        if x)

    def tail(self, body: str, outs: list[str], anchors: list[Anchors]) -> str:
        """``body`` ends with ``WITH <outs>`` (one row); add the anchor check and return."""
        calls, found = self.found(anchors)
        ret = ", ".join(outs) + (f", {found} AS found" if anchors else "")
        return " ".join(x for x in (body, calls, f"RETURN {ret}") if x)

    def compiled(self, text: str, kind: str, post: str | None = None, **meta: Any) -> Compiled:
        self.p.check()
        rels = dict(self.rels_used)
        if self.b.card is not None:
            for name in self.b.card.relations:
                try:
                    rels.setdefault(self.b.rel(name), name)
                except ValueError:
                    pass
        meta = {"row_cap": int(self.b.row_cap), "rels": rels, **meta}
        if self.p.inputs:
            meta["inputs"] = dict(self.p.inputs)
        return Compiled(text, dict(self.p.values), kind, post, meta)


def compile_cypher(node: Any, ctx: Backend | None = None) -> Compiled:
    """Compile one operator tree to one read-only Cypher query.

    The query returns one record, the envelope of ``kind``; read it with
    ``compiled.finish``. ``ctx`` defaults to ``Backend.cypher()`` (no card: value
    types are read from each condition's op and value).
    """
    ctx = ctx or Backend.cypher()
    if ctx.validate and ctx.card is not None:
        from utils.specialists.algebra.validate import check

        check(node, ctx.card)
    cx = _Cypher(ctx)
    if isinstance(node, _NODE_SETS):
        node = Nodes(node)
    anchors = [a for a in _anchors_in(node)]
    meta_anchors = [list(a.ids) for a in anchors]

    if isinstance(node, Nodes):
        props = tuple(node.props)
        if isinstance(node.of, Reach):
            v = cx.var()
            d = int(node.of.depth)
            text, dist = cx.reach(node.of, v, d + 1)
            q = cx.envelope(text, v, props, anchors, dist=dist, depth=d)
            return cx.compiled(q, "nodes", props=props, anchors=meta_anchors)
        text, v = cx.nodeset(node.of)
        return cx.compiled(cx.envelope(text, v, props, anchors), "nodes", props=props, anchors=meta_anchors)

    if isinstance(node, Expand):
        w = node.walk
        t, s = cx.nodeset(w.start)
        v = cx.var()
        ends = cx.labels_of(w)
        if w.depth > 1:
            h, pv, e, end = w.hops[0], cx.var("p"), cx.var("e"), cx.var("t")
            arrow = cx.arrow(h, "", f"*1..{int(w.depth)}")
            preds = [f"ALL(i IN range(0, length({pv}) - 1) WHERE NOT nodes({pv})[i] IN nodes({pv})[i + 1..])"]
            ec = cx.edge_conds(e, h)
            if ec:
                preds.append(f"ALL({e} IN relationships({pv}) WHERE {' AND '.join(ec)})")
            preds += cx.conds(end, w.last_conds, ends)
            # Amendment 3: each repetition count 1..depth is a prefix, so the answer is the
            # end node of every acyclic walk of 1..depth steps, filtered by the walk's
            # conditions (eqfilter is on the last hop's label, every repetition). The
            # route nodes are themselves such ends; they are not added unfiltered.
            text = (f"{t} MATCH {pv} = ({s}){arrow}({end}{cx.label(h.target)}) WHERE {' AND '.join(preds)} "
                    f"WITH DISTINCT {end} AS {v}")
        else:
            # Amendment 3: the end nodes of every prefix of the hops, whether or not the
            # walk continues from them; the walk's conditions apply to the full walk only.
            arms = []
            for i in range(1, len(w.hops) + 1):
                end = cx.var("t")
                pattern, preds, _ = cx.chain(s, w.hops[:i], end, cx.labels_of(w.start))
                if i == len(w.hops):
                    preds += cx.conds(end, w.last_conds, ends)
                where = f" WHERE {' AND '.join(preds)}" if preds else ""
                arms.append(f"WITH {s} MATCH {pattern}{where} RETURN {end} AS {v}")
            text = f"{t} CALL {{ {' UNION '.join(arms)} }} WITH DISTINCT {v}"
        return cx.compiled(cx.envelope(text, v, (), anchors), "nodes", props=(), anchors=meta_anchors)

    if isinstance(node, Describe):
        a, v = node.anchors, cx.var()
        q = (f"MATCH ({v}{cx.label(a.label)}) WHERE {v}.id IN {cx.param(list(a.ids))} WITH DISTINCT {v} "
             f"ORDER BY {v}.id RETURN collect({{id: {v}.id, name: {v}.name, properties: properties({v})}}) AS rows")
        return cx.compiled(q, "describe", anchors=[list(a.ids)])

    if isinstance(node, Common):
        a, x, v, c = node.anchors, cx.var("a"), cx.var(), cx.var("c")
        ids = list(dict.fromkeys(a.ids))
        text = (f"MATCH ({x}{cx.label(a.label)})--({v}) WHERE {x}.id IN {cx.param(ids)} "
                f"WITH {v}, count(DISTINCT {x}.id) AS {c} WHERE {c} = {cx.param(len(ids))} WITH DISTINCT {v}")
        return cx.compiled(cx.envelope(text, v, (), anchors), "nodes", props=(), anchors=meta_anchors)

    if isinstance(node, Count) or (isinstance(node, Aggregate) and node.fn == "count"):
        t, v = cx.nodeset(node.of)
        return cx.compiled(cx.tail(f"{t} WITH count(DISTINCT {v}) AS value", ["value"], anchors), "count",
                           anchors=meta_anchors)

    if isinstance(node, Values):
        vt = cx.b.prop_type(cx.labels_of(node.of), node.prop)
        t1, v1 = cx.nodeset(node.of)
        has1 = cx.cond(v1, Cond(node.prop, "present"), vt)
        t2, v2 = cx.nodeset(node.of)
        has2 = cx.cond(v2, Cond(node.prop, "present"), vt)
        val = cx.value(v2, node.prop, vt, day=False)
        if node.distinct:
            rows = (f"WITH {val} AS value, min({v2}.id) AS id ORDER BY id "
                    f"RETURN collect({{id: id, value: value}}) AS all_")
        else:
            rows = f"WITH {v2} ORDER BY {v2}.id RETURN collect({{id: {v2}.id, value: {val}}}) AS all_"
        body = (f"CALL {{ {t1} RETURN count(DISTINCT {v1}) AS n_all, "
                f"count(DISTINCT CASE WHEN {has1} THEN {v1} END) AS n_has }} "
                f"CALL {{ {t2} WITH {v2} WHERE {has2} {rows} }} "
                f"WITH all_[0..{int(cx.b.row_cap)}] AS rows, size(all_) AS total, n_all - n_has AS lacking")
        return cx.compiled(cx.tail(body, ["rows", "total", "lacking"], anchors), "values", anchors=meta_anchors)

    if isinstance(node, Aggregate):
        t, v = cx.nodeset(node.of)
        vt = cx.b.prop_type(cx.labels_of(node.of), node.prop)
        has = cx.cond(v, Cond(node.prop, "present"), vt)
        val = cx.value(v, node.prop, vt)
        if node.fn == "count_values":
            body = f"{t} WITH {v} WHERE {has} WITH count(DISTINCT {val}) AS value"
            return cx.compiled(cx.tail(body, ["value"], anchors), "count", anchors=meta_anchors)
        if node.fn == "median":
            body = f"{t} WITH collect({val}) AS value"
            return cx.compiled(cx.tail(body, ["value"], anchors), "aggregate", "median", anchors=meta_anchors)
        body = f"{t} WITH {node.fn}({val}) AS value"
        return cx.compiled(cx.tail(body, ["value"], anchors), "aggregate", anchors=meta_anchors)

    if isinstance(node, Rank):
        t, v = cx.nodeset(node.of)
        if node.prop is not None:
            vt = cx.b.prop_type(cx.labels_of(node.of), node.prop)
            keyed = f"WITH {v}, {cx.value(v, node.prop, vt)} AS value"
        else:
            m = cx.var("m")
            pattern, preds, _ = cx.chain(v, node.by_walk, m, cx.labels_of(node.of))
            where = f" WHERE {' AND '.join(preds)}" if preds else ""
            keyed = (f"CALL {{ WITH {v} OPTIONAL MATCH {pattern}{where} WITH DISTINCT {m} "
                     f"RETURN count({m}) AS value }}")
        body = (f"{t} {keyed} WITH {v}, value ORDER BY value {'DESC' if node.order == 'desc' else 'ASC'}, {v}.id "
                f"WITH collect({{id: {v}.id, name: {v}.name, value: value}}) AS rows")
        return cx.compiled(cx.tail(body, ["rows"], anchors), "rank", "rank", order=node.order, k=int(node.k),
                           drop_missing=node.prop is not None, anchors=meta_anchors)

    if isinstance(node, GroupBy):
        t, v = cx.nodeset(node.members)
        m = cx.var("m")
        pattern, preds, _ = cx.chain(v, node.hops, m, cx.labels_of(node.members))
        ends = cx.hop_labels(cx.labels_of(node.members), node.hops)
        preds += cx.conds(m, node.end_conds, ends)
        where = f" WHERE {' AND '.join(preds)}" if preds else ""
        if node.fn == "count":
            agg = f"count({m})"
        else:
            val = cx.value(m, node.prop, cx.b.prop_type(ends, node.prop))
            agg = f"collect({val})" if node.fn == "median" else f"{node.fn}({val})"
        body = (f"{t} CALL {{ WITH {v} OPTIONAL MATCH {pattern}{where} WITH DISTINCT {m} RETURN {agg} AS value }} "
                f"WITH {v}, value ORDER BY {v}.id "
                f"WITH collect({{id: {v}.id, name: {v}.name, value: value}}) AS rows")
        return cx.compiled(cx.tail(body, ["rows"], anchors), "groupby", "group", fn=node.fn,
                           having=list(node.having) if node.having else None, order=node.order, k=node.k,
                           anchors=meta_anchors)

    if isinstance(node, Verify):
        a, b = node.a, node.b
        pa, pb = cx.param(list(a.ids)), cx.param(list(b.ids))
        la, lb = cx.label(a.label), cx.label(b.label)
        if node.relation is not None:
            typed = f":{cx.rel(node.relation)}"
            d = node.direction or "both"
        else:
            typed = _any_rel(cx, a.label, b.label)
            d = "both"
        x1, y1, x2, y2, r = cx.var("a"), cx.var("b"), cx.var("a"), cx.var("b"), cx.var("r")
        arrow = {"out": f"-[{r}{typed}]->", "in": f"<-[{r}{typed}]-", "both": f"-[{r}{typed}]-"}[d]
        fa, fb = cx.var("f"), cx.var("f")
        q = (f"CALL {{ MATCH ({x1}{la}) WHERE {x1}.id IN {pa} RETURN count({x1}) > 0 AS {fa} }} "
             f"CALL {{ MATCH ({y1}{lb}) WHERE {y1}.id IN {pb} RETURN count({y1}) > 0 AS {fb} }} "
             f"CALL {{ MATCH ({x2}{la}){arrow}({y2}{lb}) "
             f"WHERE {x2}.id IN {pa} AND {y2}.id IN {pb} "
             f"WITH DISTINCT {x2}, {r} ORDER BY type({r}), {r}.id "
             f"RETURN collect({{relation: type({r}), "
             f"direction: CASE WHEN startNode({r}) = {x2} THEN 'out' ELSE 'in' END, "
             f"properties: properties({r})}}) AS witness }} "
             f"RETURN {fa} AS a_found, {fb} AS b_found, witness")
        return cx.compiled(q, "verify", anchors=[list(a.ids), list(b.ids)])

    if isinstance(node, Shortest):
        a, b, d = node.a, node.b, int(node.depth)
        pa, pb = cx.param(list(a.ids)), cx.param(list(b.ids))
        la, lb = cx.label(a.label), cx.label(b.label)
        x1, y1, x2, y2, x3 = cx.var("a"), cx.var("b"), cx.var("a"), cx.var("b"), cx.var("a")
        z, pv, qv, fa, fb, dist = cx.var("z"), cx.var("p"), cx.var("p"), cx.var("f"), cx.var("f"), cx.var("d")
        q = (f"CALL {{ MATCH ({x1}{la}) WHERE {x1}.id IN {pa} RETURN count({x1}) > 0 AS {fa} }} "
             f"CALL {{ MATCH ({y1}{lb}) WHERE {y1}.id IN {pb} RETURN count({y1}) > 0 AS {fb} }} "
             f"CALL {{ MATCH ({x2}{la}) WHERE {x2}.id IN {pa} MATCH ({y2}{lb}) WHERE {y2}.id IN {pb} "
             f"MATCH {pv} = ALL SHORTEST ({x2}){cx.qpp(node.rels)}{{1,{d}}}({y2}) "
             f"RETURN collect({{nodes: [n IN nodes({pv}) | n.id], rels: [e IN relationships({pv}) | type(e)]}}) "
             f"AS paths }} "
             f"CALL {{ MATCH ({x3}{la}) WHERE {x3}.id IN {pa} "
             f"MATCH {qv} = ANY SHORTEST ({x3}){cx.qpp(node.rels)}{{1,{d + 1}}}({z}) WHERE {z} <> {x3} "
             f"WITH {z}, min(length({qv})) AS {dist} RETURN count(CASE WHEN {dist} > {d} THEN 1 END) > 0 AS beyond }} "
             f"RETURN {fa} AS a_found, {fb} AS b_found, paths, beyond")
        return cx.compiled(q, "shortest", "shortest", depth=d, anchors=[list(a.ids), list(b.ids)])

    raise ValueError(f"{type(node).__name__} is not an operator of the algebra")


def _any_rel(cx: _Cypher, la: str, lb: str) -> str:
    """Verify without a relation: any card relationship between the two labels (either way)."""
    card = cx.b.card
    if card is None:
        return ""
    names = [name for name, r in card.relations.items()
             if not la or not lb or any((s, o) in ((la, lb), (lb, la)) for s, o in r.patterns)]
    names = [cx.rel(n) for n in names]
    return (":" + "|".join(dict.fromkeys(names))) if names else ""
