"""Compile the operator algebra to Gremlin (TinkerPop 3.8).

Two parts:

- :func:`compile_typed_walk` is today's typed-step walk (``expand``/``count``),
  moved here from ``GremlinQueryBuilder._typed_step`` unchanged: the builder
  keeps its guards, its describe/scan/common dispatch and the store rule that
  decides whether the step's filter can run, and hands this the walk, the seeds,
  the traversal budget, the row limit and that decision. Its output is
  byte-identical to before (Phase D's snapshot check).
- :func:`compile_gremlin` compiles every class of the algebra
  (``utils.specialists.algebra.ir.OPS``) with the meaning fixed in
  ``docs/era-2-expansion/operator-algebra.md``.

Every user value is a binding (a Groovy variable in the script), never text in
the script, so no value is ever escaped into the query (Groovy rejects ``'\\ '``,
which is what ``re.escape`` produces for a space). Identifiers are checked
against ``compiled.SAFE_IDENT`` and spliced in single quotes.
"""

from __future__ import annotations

from typing import Any

from utils.graph_loader.stores.gremlin import gremlin_edge_label
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


def compile_typed_walk(walk: Walk, seed_ids: Any, budget: int, lim: int,
                       filter_ok: bool) -> tuple[str, dict[str, Any]]:
    """Today's typed-step walk: the query text and its parameters.

    Each hop is ``out``/``in`` of the store's edge label for the card relation,
    then ``hasLabel`` of the hop's target. The full path is one ``union``
    branch; shorter prefixes (the intermediates) are added while the
    traversal-step ``budget`` allows, full path first. ``filter_ok`` is the
    builder's store rule for the walk's one ``=`` filter (``walk.last_conds``).
    The rows carry ``generic_walk``'s ``select("ap","nbr")`` shape.
    """
    from .builder import _safe_gremlin_ident, _walk_candidate_ids

    hops = list(walk.hops)
    depth = max(1, int(walk.depth or 1))

    def _hop(h: Hop, repeat: bool) -> str:
        edge = gremlin_edge_label(_safe_gremlin_ident(h.relation, "relationship type"))
        way = "in" if h.direction == "in" else "out"
        # An empty target keeps every label the hop reaches.
        target = (f'.hasLabel("{_safe_gremlin_ident(h.target, "target label")}")'
                  if h.target else "")
        if repeat:
            return f'repeat(__.{way}("{edge}")).times({depth}).emit(){target}'
        return f'{way}("{edge}"){target}'

    repeat = len(hops) == 1 and depth > 1
    branches = [".".join(_hop(h, repeat) for h in hops)]
    spent = 1 if repeat else len(hops)
    for i in range(len(hops) - 1, 0, -1):
        if spent + i > budget:
            break
        branches.append(".".join(_hop(h, False) for h in hops[:i]))
        spent += i
    ids = _walk_candidate_ids(seed_ids)
    params: dict[str, Any] = {"ids": ids}
    scope = ""
    if walk.last_conds and hops[-1].target and filter_ok:
        cond = walk.last_conds[0]
        label = hops[-1].target
        scope = (f'.or(__.not(__.hasLabel("{_safe_gremlin_ident(label, "filter label")}")), '
                 f'__.has("{_safe_gremlin_ident(cond.prop, "property")}", filterValue))')
        params["filterValue"] = cond.value
    union = ", ".join(f"__.{b}" for b in branches)
    query = (
        'g.V().has("id", within(ids)).as("ap")'
        f".union({union}){scope}.as(\"nbr\")"
        f'.select("ap","nbr").by(elementMap()).limit({lim})'
    )
    return query, params


# --- Task 2: every class of the algebra ----------------------------------------
#
# A node set compiles to a *fragment*: steps that, applied to one traverser,
# emit the set's vertices once each (S1). A fragment starts with ``.V()`` (or a
# ``.union(...)`` of fragments), so it composes after ``g``, inside ``__``, or
# after a ``fold()`` that has reduced the stream to one traverser. Sets another
# set must test against (intersect, a ``Having`` target) are gathered first with
# ``aggregate`` and read with ``where(within(key))``.

_DATE_TYPES = ("date", "datetime")
_P = {"=": "eq", "<>": "neq", "<": "lt", ">": "gt", "<=": "lte", ">=": "gte"}
_TEXT = {"starts_with": "startingWith", "ends_with": "endingWith", "contains_text": "containing"}
_NODE_SETS = (Anchors, Scan, FromStep, Walk, Intersect, Where, Union_, Having, TypeScan, Reach)
_FALSE = ".not(__.identity())"


def _q(name: str, kind: str) -> str:
    return f"'{safe_ident(name, kind)}'"


def _guess_type(c: Cond) -> str:
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
    from utils.specialists.cypher.compile import _anchors_in as walk

    return walk(node)


class _Gremlin:
    def __init__(self, backend: Backend) -> None:
        self.b = backend
        self.p = Params(backend)
        self.n = 0
        self.rels_used: dict[str, str] = {}

    def key(self, prefix: str) -> str:
        self.n += 1
        return f"{prefix}{self.n}"

    def param(self, value: Any) -> str:
        return self.p.add(value)

    def rel(self, relation: str) -> str:
        name = self.b.rel(relation)
        self.rels_used[name] = relation
        return f"'{name}'"

    def label(self, label: str) -> str:
        return f".hasLabel({_q(label, 'label')})" if label else ""

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

    # -- conditions (S4, S5, S6): steps that keep an element meeting ``c``
    def cond(self, c: Cond, vtype: str | None) -> str:
        p = _q(c.prop, "property")
        vt = vtype or _guess_type(c)
        op = c.op
        # Amendment 4: an empty list is missing. A list (or a property of unknown type)
        # is present only when ``values(p).unfold()`` yields an element; a scalar
        # (a string included) unfolds to itself, so this is ``has(p)`` for scalars.
        has = f".where(__.values({p}).unfold())"
        listy = vtype in (None, "list")
        if op == "present":
            if vt == "number_text":
                return f".has({p}, TextP.regex({self.param(NUMBER_REGEX)}))"
            return has if listy else f".has({p})"
        if op == "missing":
            if vt == "number_text":
                return f".not(__.has({p}, TextP.regex({self.param(NUMBER_REGEX)})))"
            return f".not(__.values({p}).unfold())" if listy else f".hasNot({p})"
        if op == "size":
            return f"{has}.where(__.values({p}).unfold().count().is({_P[c.cmp]}({self.param(int(c.value))})))"
        if op == "contains":
            return f".where(__.values({p}).unfold().is(eq({self.param(c.value)})))"
        if op == "not_contains":
            return f"{has}.not(__.values({p}).unfold().is(eq({self.param(c.value)})))"
        if op in _TEXT:
            return f".has({p}, TextP.{_TEXT[op]}({self.param(c.value)}))"
        if op in ("before", "after", "between", "year") or vt in _DATE_TYPES:
            return self.date_cond(p, c)
        if op not in _P:
            raise ValueError(f"unknown condition op {op!r}")
        if vt == "number_text":
            return (f".where(__.values({p}).is(TextP.regex({self.param(NUMBER_REGEX)}))"
                    f".asNumber(GType.DOUBLE).is({_P[op]}({self.param(c.value)})))")
        return f".has({p}, {_P[op]}({self.param(c.value)}))"

    def date_cond(self, p: str, c: Cond) -> str:
        """S6 on the stored text: ISO-shaped values only, compared on their ``YYYY-MM-DD`` prefix.

        For an ISO value ``s`` and a day ``d`` (10 characters), ``s[:10] < d`` iff
        ``s < d``, and ``s[:10] = d`` iff ``s`` starts with ``d``; the other
        comparisons follow. ``year`` compares ``s[:4]`` the same way.
        """
        iso = f".has({p}, TextP.regex({self.param(ISO_REGEX)}))"
        lt = lambda d: f"lt({self.param(d)})"  # noqa: E731
        starts = lambda d: f"__.has({p}, TextP.startingWith({self.param(d)}))"  # noqa: E731
        op = {"before": "<", "after": ">"}.get(c.op, c.op)
        if op == "year":
            return iso + self.year(p, c.cmp, int(c.value), starts)
        if op == "between":
            lo, hi = str(c.value[0])[:10], str(c.value[1])[:10]
            return f"{iso}.has({p}, gte({self.param(lo)})).or(__.has({p}, {lt(hi)}), {starts(hi)})"
        d = str(c.value)[:10]
        return iso + {
            "=": f".where({starts(d)})",
            "<>": f".not({starts(d)})",
            "<": f".has({p}, {lt(d)})",
            "<=": f".or(__.has({p}, {lt(d)}), {starts(d)})",
            ">": f".has({p}, gt({self.param(d)})).not({starts(d)})",
            ">=": f".has({p}, gte({self.param(d)}))",
        }[op]

    def year(self, p: str, cmp: str, n: int, starts: Any) -> str:
        """``int(s[:4]) <cmp> n`` for ISO ``s`` (a four-digit year, 0000-9999) as string tests."""
        y = lambda k: f"{k:04d}"  # noqa: E731
        if cmp == "=":
            return f".where({starts(y(n))})" if 0 <= n <= 9999 else _FALSE
        if cmp == "<>":
            return f".not({starts(y(n))})" if 0 <= n <= 9999 else ""
        if cmp == "<":
            return _FALSE if n <= 0 else ("" if n > 9999 else f".has({p}, lt({self.param(y(n))}))")
        if cmp == "<=":
            return _FALSE if n < 0 else ("" if n >= 9999 else f".has({p}, lt({self.param(y(n + 1))}))")
        if cmp == ">":
            return _FALSE if n >= 9999 else ("" if n < 0 else f".has({p}, gte({self.param(y(n + 1))}))")
        if cmp == ">=":
            return "" if n <= 0 else (_FALSE if n > 9999 else f".has({p}, gte({self.param(y(n))}))")
        raise ValueError(f"unknown comparison {cmp!r}")

    def conds(self, conds: tuple[Cond, ...], labels: Any) -> str:
        return "".join(self.cond(c, self.b.prop_type(labels, c.prop)) for c in conds)

    def edge_conds(self, hop: Hop) -> str:
        return "".join(self.cond(c, self.b.edge_prop_type(hop.relation, c.prop)) for c in hop.edge_conds)

    def value(self, prop: str, vtype: str | None, *, day: bool = True) -> tuple[str, str]:
        """``(filter, value)`` steps: the property as a value; ``number_text`` as its number,
        a date as its ISO day; an element without a usable value is filtered out."""
        p = _q(prop, "property")
        if vtype == "number_text":
            return f".has({p}, TextP.regex({self.param(NUMBER_REGEX)}))", f".values({p}).asNumber(GType.DOUBLE)"
        if vtype in _DATE_TYPES and day:
            return f".has({p}, TextP.regex({self.param(ISO_REGEX)}))", f".values({p}).substring(0, 10)"
        if vtype == "list":  # amendment 4: an empty list is missing
            return f".where(__.values({p}).unfold())", f".values({p})"
        return f".has({p})", f".values({p})"

    # -- walks
    def hop(self, h: Hop, *, label: bool = True, edges: bool = False) -> str:
        """One hop. ``edges`` keeps the edge in the path (for paths and edge filters)."""
        r = self.rel(h.relation)
        ec = self.edge_conds(h)
        if ec or edges:
            step = (f".inE({r}){ec}.outV()" if h.direction == "in" else f".outE({r}){ec}.inV()")
        else:
            step = f".in({r})" if h.direction == "in" else f".out({r})"
        return step + (self.label(h.target) if label else "")

    def hops(self, hops: tuple[Hop, ...]) -> str:
        return "".join(self.hop(h) for h in hops)

    @staticmethod
    def acyclic(start: str) -> str:
        """Amendment 4 for a repeated hop: no vertex twice since the walk's start ``start``
        (an ``as`` label), the start included, so a self-loop never returns it."""
        return f".simplePath().from('{start}')"

    def walk(self, start: str, hops: tuple[Hop, ...]) -> str:
        """``hops`` from the vertex labelled ``start``, keeping only node-acyclic walks
        (amendment 4: no vertex twice, the start included).

        Explicit and pairwise, as in Cypher: each vertex reached is ``neq`` every vertex
        before it, each named by an ``as`` label. This needs labelled paths only, not
        full path tracking (``simplePath``), which stops the server from bulking
        traversers and made a reach from a ``Having`` start time out (EXP-2026-11-021).
        """
        seen, out = [start], ""
        for i, h in enumerate(hops):
            out += self.hop(h) + "".join(f".where(neq('{x}'))" for x in seen)
            if i < len(hops) - 1:
                seen.append(self.key("n"))
                out += f".as('{seen[-1]}')"
        return out

    def path_step(self, rels: tuple[tuple[str, str], ...], edges: bool) -> str:
        """One step along any of ``rels`` (each ``(relation, out|in|both)``)."""
        if not rels:
            rels = tuple((r, "both") for r in (self.b.card.relations if self.b.card is not None else ()))
        if not rels:
            return ".bothE().otherV()" if edges else ".both()"
        arms = []
        by_dir: dict[str, list[str]] = {}
        for rel, d in rels:
            by_dir.setdefault(d, [])
            name = self.rel(rel)
            if name not in by_dir[d]:
                by_dir[d].append(name)
        for d, names in by_dir.items():
            ns = ", ".join(names)
            if edges:
                arms.append({"out": f".outE({ns}).inV()", "in": f".inE({ns}).outV()",
                             "both": f".bothE({ns}).otherV()"}[d])
            else:
                arms.append({"out": f".out({ns})", "in": f".in({ns})", "both": f".both({ns})"}[d])
        if len(arms) == 1:
            return arms[0]
        return ".union(" + ", ".join(f"__{a}" for a in arms) + ")"

    def bfs(self, seed: str, rels: tuple[tuple[str, str], ...], depth: int) -> str:
        """Every vertex 1..depth steps from the seed vertices, never a seed (S10).

        Breadth first: ``aggregate`` is a barrier, so each level is complete before
        the next, and a vertex already seen is never expanded again.
        """
        k = self.key("k")
        return (f"{seed}.aggregate('{k}').repeat(__{self.path_step(rels, False)}"
                f".where(without('{k}')).dedup().aggregate('{k}')).emit().times({int(depth)})")

    # -- node sets
    def nodeset(self, node: Any) -> str:
        if isinstance(node, Anchors):
            return f".V().has('id', within({self.param(list(node.ids))})){self.label(node.label)}.dedup()"
        if isinstance(node, Scan):
            return f".V(){self.label(node.label)}"
        if isinstance(node, TypeScan):
            return f".V(){self.label(node.label)}{self.conds(node.conds, frozenset([node.label]))}"
        if isinstance(node, FromStep):
            labels = (".hasLabel(" + ", ".join(_q(lab, "label") for lab in node.labels) + ")") if node.labels else ""
            return f".V().has('id', within({self.p.input(node.step)})){labels}.dedup()"
        if isinstance(node, Walk):
            start = self.nodeset(node.start)
            ends = self.labels_of(node)
            if node.depth > 1:
                h, s = node.hops[0], self.key("s")
                return (f"{start}.as('{s}').repeat(__{self.hop(h, label=False)}{self.acyclic(s)})"
                        f".emit().times({int(node.depth)}){self.label(h.target)}"
                        f"{self.conds(node.last_conds, ends)}.dedup()")
            s = self.key("s")
            return (f"{start}.as('{s}'){self.walk(s, node.hops)}"
                    f"{self.conds(node.last_conds, ends)}.dedup()")
        if isinstance(node, Where):
            return self.nodeset(node.of) + self.conds(node.conds, self.labels_of(node.of))
        if isinstance(node, Intersect):
            pre, tests = "", ""
            for part in node.parts[1:]:
                k = self.key("i")
                pre += f"{self.nodeset(part)}.aggregate('{k}').fold()"
                tests += f".where(within('{k}'))"
            return f"{pre}{self.nodeset(node.parts[0])}{tests}"
        if isinstance(node, Union_):
            return ".union(" + ", ".join(f"__{self.nodeset(part)}" for part in node.parts) + ").dedup()"
        if isinstance(node, Having):
            pre, member = "", ""
            if node.target is not None:
                k = self.key("t")
                pre = f"{self.nodeset(node.target)}.aggregate('{k}').fold()"
                member = f".where(within('{k}'))"
            reach = self.hop_labels(self.labels_of(node.of), (node.hop,))
            # The start label is set inside the child traversal: a parent's label is not
            # visible there (the server reports "Could not locate path from-label").
            # ``filter``, not ``where``: a ``where`` whose traversal starts with ``as`` is
            # a pattern match.
            s = self.key("s")
            test = f"__.as('{s}'){self.walk(s, (node.hop,))}{self.conds(node.target_conds, reach)}{member}"
            return f"{pre}{self.nodeset(node.of)}" + (f".filter({test})" if node.exists else f".not({test})")
        if isinstance(node, Reach):
            return self.reach(node, int(node.depth))
        raise ValueError(f"{type(node).__name__} is not a node set")

    def reach(self, node: Reach, depth: int) -> str:
        """S10's reach, per start node: the nodes 1..depth steps from *that* node along
        acyclic paths, unioned over the start set. A start node is excluded only from
        its own search, so one start reachable from another is kept.

        Breadth first per start: ``barrier()`` completes each level before ``dedup``
        on (start, vertex) keeps the first, shortest arrival, so a vertex is expanded
        once per start, from its least distance. A node reachable by any walk of
        length <= depth is reachable by an acyclic one no longer (S10), so this is
        the acyclic reach without enumerating paths. The start set is one binding
        (``within``), however many ids it holds.
        """
        s, v = self.key("s"), self.key("v")
        return (f"{self.nodeset(node.start)}.as('{s}').repeat(__{self.path_step(node.rels, False)}"
                f".where(neq('{s}')).as('{v}').barrier().dedup('{s}', '{v}'))"
                f".emit().times({int(depth)}).dedup()")

    # -- results
    def name(self) -> str:
        return "__.coalesce(__.values('name'), __.constant(null))"

    def found(self, anchors: list[Anchors]) -> tuple[list[str], list[str]]:
        keys, bys = [], []
        for i, a in enumerate(anchors):
            keys.append(f"'found_{i}'")
            bys.append(f".by(__.V().has('id', within({self.param(list(a.ids))})){self.label(a.label)}"
                       f".values('id').dedup().fold())")
        return keys, bys

    def project(self, head: str, fields: list[tuple[str, str]], anchors: list[Anchors]) -> str:
        """``head`` (one traverser) projected to the envelope ``fields`` plus the anchor check."""
        fkeys, fbys = self.found(anchors)
        keys = [f"'{k}'" for k, _ in fields] + fkeys
        bys = [f".by({b})" for _, b in fields] + fbys
        return f"{head}.project({', '.join(keys)}){''.join(bys)}"

    def envelope(self, frag: str, props: tuple[str, ...], anchors: list[Anchors],
                 beyond: str | None = None) -> str:
        cols = [("id", "'id'"), ("name", self.name())] + [
            (p, f"__.coalesce(__.values({_q(p, 'property')}), __.constant(null))")
            for p in props if p not in ("id", "name")]
        rows = (f"__.unfold().limit({int(self.b.row_cap)}).project({', '.join(repr(c) for c, _ in cols)})"
                + "".join(f".by({b})" for _, b in cols) + ".fold()")
        fields = [("total", "__.count(local)"), ("rows", rows)]
        if beyond is not None:
            fields.append(("total_beyond", f"__{beyond}.count()"))
        return self.project(f"{frag}.order().by('id').fold()", fields, anchors)

    def compiled(self, frag: str, kind: str, post: str | None = None, **meta: Any) -> Compiled:
        self.p.check()
        text = ("g" + frag) if frag.startswith(".V(") else ("g.inject(0)" + frag)
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


def compile_gremlin(node: Any, ctx: Backend | None = None) -> Compiled:
    """Compile one operator tree to one read-only Gremlin script with bindings.

    The script returns one map, the envelope of ``kind``; read it with
    ``compiled.finish``. ``ctx`` defaults to ``Backend.gremlin()`` (no card).
    """
    ctx = ctx or Backend.gremlin()
    if ctx.validate and ctx.card is not None:
        from utils.specialists.algebra.validate import check

        check(node, ctx.card)
    gx = _Gremlin(ctx)
    if isinstance(node, _NODE_SETS):
        node = Nodes(node)
    anchors = _anchors_in(node)
    meta_anchors = [list(a.ids) for a in anchors]

    if isinstance(node, Nodes):
        props = tuple(node.props)
        if isinstance(node.of, Reach):
            frag = gx.nodeset(node.of)
            beyond = gx.reach(node.of, int(node.of.depth) + 1)
            return gx.compiled(gx.envelope(frag, props, anchors, beyond), "nodes", props=props,
                               anchors=meta_anchors)
        return gx.compiled(gx.envelope(gx.nodeset(node.of), props, anchors), "nodes", props=props,
                           anchors=meta_anchors)

    if isinstance(node, Expand):
        w = node.walk
        start = gx.nodeset(w.start)
        ends = gx.labels_of(w)
        if w.depth > 1:
            h, s = w.hops[0], gx.key("s")
            # Amendment 3: every repetition count 1..depth is a prefix; keep each acyclic
            # walk's end that meets the walk's conditions (as the Cypher compiler does).
            frag = (f"{start}.as('{s}').repeat(__{gx.hop(h, label=False)}{gx.acyclic(s)})"
                    f".emit().times({int(w.depth)}){gx.label(h.target)}{gx.conds(w.last_conds, ends)}"
                    f".dedup()")
        else:
            # Amendment 3: the end nodes of every prefix of the hops, whether or not the
            # walk continues from them; the walk's conditions apply to the full walk only.
            # Amendment 4: each arm keeps only walks that visit no vertex twice.
            s = gx.key("s")
            arms = [f"__{gx.walk(s, w.hops[:i])}" + (gx.conds(w.last_conds, ends) if i == len(w.hops) else "")
                    for i in range(1, len(w.hops) + 1)]
            body = arms[0][2:] if len(arms) == 1 else f".union({', '.join(arms)})"
            frag = f"{start}.as('{s}'){body}.dedup()"
        return gx.compiled(gx.envelope(frag, (), anchors), "nodes", props=(), anchors=meta_anchors)

    if isinstance(node, Describe):
        a = node.anchors
        frag = (f".V().has('id', within({gx.param(list(a.ids))})){gx.label(a.label)}.dedup().order().by('id')"
                f".project('id', 'name', 'properties').by('id').by({gx.name()}).by(__.elementMap()).fold()"
                f".project('rows').by()")
        return gx.compiled(frag, "describe", anchors=[list(a.ids)])

    if isinstance(node, Common):
        a = node.anchors
        ids = list(dict.fromkeys(a.ids))
        pid, lab = gx.param(ids), gx.label(a.label)
        frag = (f".V().has('id', within({pid})){lab}.both().dedup()"
                f".where(__.both().has('id', within({pid})){lab}.values('id').dedup().count()"
                f".is(eq({gx.param(len(ids))})))")
        return gx.compiled(gx.envelope(frag, (), anchors), "nodes", props=(), anchors=meta_anchors)

    if isinstance(node, Count) or (isinstance(node, Aggregate) and node.fn == "count"):
        frag = gx.project(f"{gx.nodeset(node.of)}.fold()", [("value", "__.count(local)")], anchors)
        return gx.compiled(frag, "count", anchors=meta_anchors)

    if isinstance(node, Values):
        vt = gx.b.prop_type(gx.labels_of(node.of), node.prop)
        _, val = gx.value(node.prop, vt, day=False)
        flt = gx.cond(Cond(node.prop, "present"), vt)  # amendment 4: an empty list is missing
        lacking = gx.cond(Cond(node.prop, "missing"), vt)
        dedup = ".dedup().by(__.select('value'))" if node.distinct else ""
        kept = f"__.unfold(){flt}.project('id', 'value').by('id').by(__{val}){dedup}"
        fields = [("rows", f"{kept}.limit({int(gx.b.row_cap)}).fold()"), ("total", f"{kept}.count()"),
                  ("lacking", f"__.unfold(){lacking}.count()")]
        frag = gx.project(f"{gx.nodeset(node.of)}.order().by('id').fold()", fields, anchors)
        return gx.compiled(frag, "values", anchors=meta_anchors)

    if isinstance(node, Aggregate):
        vt = gx.b.prop_type(gx.labels_of(node.of), node.prop)
        flt, val = gx.value(node.prop, vt)
        stream = f"{gx.nodeset(node.of)}{flt}{val}"
        if node.fn == "count_values":
            return gx.compiled(gx.project(f"{stream}.dedup().fold()", [("value", "__.count(local)")], anchors),
                               "count", anchors=meta_anchors)
        if node.fn == "median":
            return gx.compiled(gx.project(f"{stream}.fold()", [("value", "__.identity()")], anchors),
                               "aggregate", "median", anchors=meta_anchors)
        fn = {"sum": "sum", "avg": "mean", "min": "min", "max": "max"}[node.fn]
        empty = "0" if node.fn == "sum" else "null"
        value = f"__.coalesce(__.unfold().{fn}(), __.constant({empty}))"
        return gx.compiled(gx.project(f"{stream}.fold()", [("value", value)], anchors), "aggregate",
                           anchors=meta_anchors)

    if isinstance(node, Rank):
        s = gx.key("s")
        if node.prop is not None:
            vt = gx.b.prop_type(gx.labels_of(node.of), node.prop)
            flt, val = gx.value(node.prop, vt)
            key = f"__.coalesce(__{flt}{val}, __.constant(null))"
        else:
            key = f"__.as('{s}'){gx.walk(s, node.by_walk)}.dedup().count()"
        head = (f"{gx.nodeset(node.of)}.project('id', 'name', 'value').by('id').by({gx.name()}).by({key})"
                f".order().by(__.select('id')).fold()")
        return gx.compiled(gx.project(head, [("rows", "__.identity()")], anchors), "rank", "rank",
                           order=node.order, k=int(node.k), drop_missing=node.prop is not None,
                           anchors=meta_anchors)

    if isinstance(node, GroupBy):
        ends = gx.hop_labels(gx.labels_of(node.members), node.hops)
        s = gx.key("s")
        walk = f"__.as('{s}'){gx.walk(s, node.hops)}{gx.conds(node.end_conds, ends)}.dedup()"
        if node.fn == "count":
            agg = f"{walk}.count()"
        else:
            flt, val = gx.value(node.prop, gx.b.prop_type(ends, node.prop))
            if node.fn == "median":
                agg = f"{walk}{flt}{val}.fold()"
            else:
                fn = {"sum": "sum", "avg": "mean", "min": "min", "max": "max"}[node.fn]
                empty = "0" if node.fn == "sum" else "null"
                agg = f"{walk}{flt}{val}.fold().coalesce(__.unfold().{fn}(), __.constant({empty}))"
        head = (f"{gx.nodeset(node.members)}.project('id', 'name', 'value')"
                f".by('id').by({gx.name()}).by({agg})"
                f".order().by(__.select('id')).fold()")
        return gx.compiled(gx.project(head, [("rows", "__.identity()")], anchors), "groupby", "group",
                           fn=node.fn, having=list(node.having) if node.having else None, order=node.order,
                           k=node.k, anchors=meta_anchors)

    if isinstance(node, Verify):
        a, b = node.a, node.b
        pa, pb = gx.param(list(a.ids)), gx.param(list(b.ids))
        va = f"__.V().has('id', within({pa})){gx.label(a.label)}"
        vb_test = f"has('id', within({pb})){gx.label(b.label)}"
        if node.relation is not None:
            r, d = gx.rel(node.relation), node.direction or "both"
        else:
            r, d = _any_rel(gx, a.label, b.label), "both"
        edge = {"out": f".outE({r})", "in": f".inE({r})", "both": f".bothE({r})"}[d]
        witness = (f"{va}{edge}.where(__.otherV().{vb_test}).dedup()"
                   f".project('relation', 'direction', 'properties').by(__.label())"
                   f".by(__.choose(__.outV().has('id', within({pa})), __.constant('out'), __.constant('in')))"
                   f".by(__.valueMap()).fold()")
        frag = (f".project('a_found', 'b_found', 'witness').by({va}.count())"
                f".by(__.V().{vb_test}.count()).by({witness})")
        return gx.compiled(frag, "verify", anchors=[list(a.ids), list(b.ids)])

    if isinstance(node, Shortest):
        a, b, d = node.a, node.b, int(node.depth)
        pa, pb = gx.param(list(a.ids)), gx.param(list(b.ids))
        seed = f".V().has('id', within({pa})){gx.label(a.label)}"
        at_b = f"has('id', within({pb})){gx.label(b.label)}"
        s, k = gx.key("s"), gx.key("k")
        # Backward from b first: ``kb<r>`` holds every vertex within r steps of b
        # (against the walk's direction), r = 0..d-1. A vertex at step j of a path that
        # ends at b within d steps is within d-j of b, so a traverser outside
        # ``kb<d-j>`` is dropped: no shortest path is lost, and the forward search no
        # longer fans out across the whole graph at the last levels (a Group-to-Group
        # search at depth 3 timed out without it, EXP-2026-11-021).
        back = [gx.key("kb") for _ in range(d)]
        rev = tuple((r, {"out": "in", "in": "out"}.get(dr, dr)) for r, dr in node.rels)
        pre = f"__.V().{at_b}.aggregate('{back[0]}')" + "".join(
            f".union(__.identity(), __{gx.path_step(rev, False)}).dedup().aggregate('{back[r]}')" for r in range(1, d))
        # Then forward, level by level (unrolled, d <= 10): a traverser at b stays; every
        # other one steps, and is kept when its vertex is unseen and still within reach of
        # b. The barrier comes before the level is marked seen, so every minimum-length
        # path survives and nothing longer reaches b.
        step = gx.path_step(node.rels, True)
        levels = "".join(
            f".union(__.{at_b}, __.not(__.{at_b}){step}.where(without('{k}')).where(within('{back[d - j]}')))"
            f".barrier().aggregate('{k}')" for j in range(1, d + 1))
        paths = (f"{pre}.fold(){seed}.as('{s}').aggregate('{k}'){levels}"
                 f".{at_b}.path().from('{s}').by('id').by(__.label()).fold()")
        frag = (f".project('a_found', 'b_found', 'paths', 'total_within', 'total_beyond')"
                f".by(__{seed}.count()).by(__.V().{at_b}.count()).by({paths})"
                f".by(__{gx.bfs(seed, node.rels, d)}.count()).by(__{gx.bfs(seed, node.rels, d + 1)}.count())")
        return gx.compiled(frag, "shortest", "shortest", depth=d, anchors=[list(a.ids), list(b.ids)])

    raise ValueError(f"{type(node).__name__} is not an operator of the algebra")


def _any_rel(gx: _Gremlin, la: str, lb: str) -> str:
    """Verify without a relation: any card relationship between the two labels (either way)."""
    card = gx.b.card
    if card is None:
        return ""
    names = [name for name, r in card.relations.items()
             if not la or not lb or any((s, o) in ((la, lb), (lb, la)) for s, o in r.patterns)]
    return ", ".join(dict.fromkeys(gx.rel(n) for n in names))
