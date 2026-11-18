#!/usr/bin/env python3
"""Exact result sets with exact totals (Era 2, Step 5).

The agent's tools build on *sets*: the neighbours of some anchors over one
relation, in one direction, optionally restricted to one label. This module
fetches such a set **completely**, with its exact total, and says plainly when
a safety ceiling stopped it (``complete=False``, never a silent cut).

Two backends behind one interface:

* :class:`CypherBackend` (Neo4j): the ids are streamed by the driver, so a set
  of a million members is read in fetch-size batches with no server-side cap.
* :class:`GremlinBackend` (TinkerPop): the ids come back in the server's result
  batches.

Two fetch modes, which must agree (a test checks it):

* ``stream`` (default): one query, every id;
* ``keyset``: pages of ``page_size`` ordered ids, each page asking for ids
  greater than the last one seen. Useful where streaming is unavailable, and
  the honest way to page a set without OFFSET drift.

Identifiers: graphs name their ids differently (``eid`` in the kill-test
graphs, ``attack_id``/``id`` in ATT&CK, ``id`` in CAPEC), so each backend takes
an ordered list of id properties and uses the first one a node has.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable

#: The default safety ceiling for one set. Reaching it is a ``complete=False``
#: result with the exact count reported separately, never a silent cut.
DEFAULT_CEILING = 2_000_000
DIRECTIONS = ("out", "in", "both")
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _ident(name: str, what: str) -> str:
    if not _IDENT.match(name or ""):
        raise ValueError(f"unsafe {what} {name!r}")
    return name


@dataclass(frozen=True)
class SetSpec:
    """Which set: the neighbours of ``seeds`` over ``rel`` in ``direction``."""

    seeds: tuple[str, ...]
    rel: str
    direction: str = "out"
    target_label: str | None = None
    seed_label: str | None = None

    def __post_init__(self) -> None:
        if self.direction not in DIRECTIONS:
            raise ValueError(f"direction must be one of {DIRECTIONS}")
        _ident(self.rel, "relationship")
        if self.target_label:
            _ident(self.target_label, "label")
        if self.seed_label:
            _ident(self.seed_label, "label")


@dataclass
class ExactSet:
    """A fetched set: every id (sorted), the exact total, and whether it is complete."""

    ids: list[str]
    total: int
    complete: bool
    query: str
    backend: str
    mode: str
    seconds: float
    pages: int = 1
    ceiling: int = DEFAULT_CEILING
    notes: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Cypher
# --------------------------------------------------------------------------- #


class CypherBackend:
    name = "cypher"

    def __init__(self, driver: Any, *, id_props: tuple[str, ...] = ("eid", "attack_id", "id"),
                 database: str | None = None, timeout_s: float = 60.0) -> None:
        self.driver = driver
        self.id_props = tuple(_ident(p, "id property") for p in id_props)
        self.database = database
        self.timeout_s = timeout_s

    def _id(self, var: str) -> str:
        return "coalesce(" + ", ".join(f"{var}.{p}" for p in self.id_props) + ")"

    def _pattern(self, spec: SetSpec) -> str:
        a = f"(a:{spec.seed_label})" if spec.seed_label else "(a)"
        b = f"(b:{spec.target_label})" if spec.target_label else "(b)"
        r = f"[:{spec.rel}]"
        if spec.direction == "out":
            return f"{a}-{r}->{b}"
        if spec.direction == "in":
            return f"{a}<-{r}-{b}"
        return f"{a}-{r}-{b}"

    def _rows(self, query: str, params: dict[str, Any]) -> Any:
        from neo4j import Query, READ_ACCESS

        # Large fetches: 10,000 records per round trip instead of the driver's 1,000.
        session = self.driver.session(default_access_mode=READ_ACCESS, database=self.database,
                                      fetch_size=10_000)
        try:
            for record in session.run(Query(query, timeout=self.timeout_s), params):
                yield record
        finally:
            session.close()

    def set_query(self, spec: SetSpec, *, after: bool = False, ordered: bool = True) -> str:
        where = f"WHERE {self._id('a')} IN $seeds"
        q = f"MATCH {self._pattern(spec)} {where} WITH DISTINCT {self._id('b')} AS id WHERE id IS NOT NULL"
        if after:
            q += " AND id > $after"
        # Streaming does not need the server to sort: fetch() sorts the ids itself.
        return q + (" RETURN id ORDER BY id" if ordered else " RETURN id") + (" LIMIT $page" if after else "")

    def count(self, spec: SetSpec) -> int:
        q = (f"MATCH {self._pattern(spec)} WHERE {self._id('a')} IN $seeds "
             f"RETURN count(DISTINCT {self._id('b')}) AS n")
        return int(next(iter(self._rows(q, {"seeds": list(spec.seeds)})))["n"])

    def stream(self, spec: SetSpec, ceiling: int) -> tuple[list[str], bool]:
        # One record holding the list (and its exact size): decoding a million
        # separate records costs the Python driver seconds, one list does not.
        q = (f"MATCH {self._pattern(spec)} WHERE {self._id('a')} IN $seeds "
             f"WITH collect(DISTINCT {self._id('b')}) AS ids "
             "RETURN size(ids) AS n, ids[0..$cap] AS ids")
        rec = next(iter(self._rows(q, {"seeds": list(spec.seeds), "cap": ceiling})))
        ids = [str(x) for x in rec["ids"] if x is not None]
        return ids, int(rec["n"]) <= ceiling

    def page(self, spec: SetSpec, after: str | None, size: int) -> list[str]:
        if after is None:
            q = self.set_query(spec) + " LIMIT $page"
            params = {"seeds": list(spec.seeds), "page": size}
        else:
            q = self.set_query(spec, after=True)
            params = {"seeds": list(spec.seeds), "after": after, "page": size}
        return [str(r["id"]) for r in self._rows(q, params)]

    # -- for views and set checks --------------------------------------------

    def describe_ids(self, ids: list[str], props: tuple[str, ...] = ("name",)) -> list[dict[str, Any]]:
        cols = ", ".join(f"n.{_ident(p, 'property')} AS {p}" for p in props)
        q = (f"UNWIND $ids AS i MATCH (n) WHERE {self._id('n')} = i "
             f"RETURN i AS id, labels(n)[0] AS label, {cols}")
        return [dict(r) for r in self._rows(q, {"ids": ids})]

    def facet_counts(self, ids: list[str], prop: str | None) -> dict[str, int]:
        if prop is None:
            q = (f"UNWIND $ids AS i MATCH (n) WHERE {self._id('n')} = i "
                 "RETURN labels(n)[0] AS k, count(*) AS c")
        else:
            q = (f"UNWIND $ids AS i MATCH (n) WHERE {self._id('n')} = i "
                 f"UNWIND (CASE WHEN n.{_ident(prop, 'property')} IS NULL THEN [null] "
                 f"WHEN valueType(n.{prop}) STARTS WITH 'LIST' THEN n.{prop} ELSE [n.{prop}] END) AS v "
                 "RETURN toString(v) AS k, count(*) AS c")
        return {str(r["k"]): int(r["c"]) for r in self._rows(q, {"ids": ids})}

    def anchor_facets(self, seeds: tuple[str, ...]) -> list[dict[str, Any]]:
        """Every (relation, direction, neighbour label, count) at the anchors: the nearest valid options."""
        q = (f"MATCH (a) WHERE {self._id('a')} IN $seeds "
             "MATCH (a)-[r]-(b) RETURN type(r) AS rel, "
             "CASE WHEN startNode(r) = a THEN 'out' ELSE 'in' END AS direction, "
             "labels(b)[0] AS label, count(DISTINCT b) AS n")
        return [dict(r) for r in self._rows(q, {"seeds": list(seeds)})]

    def anchors_found(self, seeds: tuple[str, ...]) -> list[str]:
        q = f"MATCH (a) WHERE {self._id('a')} IN $seeds RETURN DISTINCT {self._id('a')} AS id"
        return [str(r["id"]) for r in self._rows(q, {"seeds": list(seeds)})]

    # -- for the card question generator (Step 6) ----------------------------

    def nodes(self, label: str) -> list[dict[str, Any]]:
        """Every node of ``label``: id, name, description."""
        q = (f"MATCH (n:{_ident(label, 'label')}) RETURN {self._id('n')} AS id, n.name AS name, "
             "n.description AS description")
        return [dict(r) for r in self._rows(q, {}) if r["id"] is not None]

    def degrees(self, label: str, rel: str, direction: str, target_label: str | None) -> dict[str, int]:
        """id -> distinct neighbours over (rel, direction, target_label), zeros included."""
        spec = SetSpec(("x",), rel, direction, target_label, label)
        q = (f"MATCH (a:{_ident(label, 'label')}) OPTIONAL MATCH {self._pattern(spec)} "
             f"RETURN {self._id('a')} AS id, count(DISTINCT b) AS n")
        return {str(r["id"]): int(r["n"]) for r in self._rows(q, {}) if r["id"] is not None}


# --------------------------------------------------------------------------- #
# Gremlin
# --------------------------------------------------------------------------- #


class GremlinBackend:
    name = "gremlin"

    def __init__(self, client: Any, *, id_props: tuple[str, ...] = ("eid", "attack_id", "id"),
                 timeout_s: float = 60.0, edge_label: Callable[[str], str] | None = None) -> None:
        """``edge_label`` maps a card relation name to the stored edge label.

        Ariadne's loader stores every edge as SCREAMING_SNAKE while cards keep the
        source vocabulary (a CamelCase relation becomes CAMEL_CASE in the store): pass
        ``utils.graph_loader.stores.gremlin.gremlin_edge_label`` for such stores, or a
        card-named set over those relations is silently empty. Stores that keep the
        source names (the kill-test loader's mirrors) leave it unset.
        """
        self.client = client
        self.id_props = tuple(_ident(p, "id property") for p in id_props)
        self.timeout_s = timeout_s
        self._edge_label = edge_label

    def _id(self) -> str:
        if len(self.id_props) == 1:
            return f"values('{self.id_props[0]}')"
        return "coalesce(" + ", ".join(f"__.values('{p}')" for p in self.id_props) + ")"

    def _seed_filter(self) -> str:
        if len(self.id_props) == 1:
            return f"has('{self.id_props[0]}', within(seeds))"
        return "or(" + ", ".join(f"__.has('{p}', within(seeds))" for p in self.id_props) + ")"

    def edge_label(self, rel: str) -> str:
        """The stored edge label for a card relation name (identity unless configured)."""
        return self._edge_label(rel) if self._edge_label else rel

    def _walk(self, spec: SetSpec) -> str:
        start = f"g.V().hasLabel('{spec.seed_label}')" if spec.seed_label else "g.V()"
        step = {"out": "out", "in": "in", "both": "both"}[spec.direction]
        q = f"{start}.{self._seed_filter()}.{step}('{self.edge_label(spec.rel)}')"
        if spec.target_label:
            q += f".hasLabel('{spec.target_label}')"
        return q

    def _submit(self, query: str, bindings: dict[str, Any]) -> list[Any]:
        return self.client.submit(query, bindings=bindings).all().result(timeout=self.timeout_s)

    def set_query(self, spec: SetSpec) -> str:
        return self._walk(spec) + f".{self._id()}.dedup().order()"

    def count(self, spec: SetSpec) -> int:
        return int(self._submit(self._walk(spec) + f".{self._id()}.dedup().count()",
                                {"seeds": list(spec.seeds)})[0])

    def stream(self, spec: SetSpec, ceiling: int) -> tuple[list[str], bool]:
        got = self._submit(self.set_query(spec) + ".limit(cap)", {"seeds": list(spec.seeds), "cap": ceiling + 1})
        ids = [str(x) for x in got]
        if len(ids) > ceiling:
            return ids[:ceiling], False
        return ids, True

    def page(self, spec: SetSpec, after: str | None, size: int) -> list[str]:
        q = self._walk(spec) + f".{self._id()}.dedup()"
        params: dict[str, Any] = {"seeds": list(spec.seeds), "size": size}
        if after is not None:
            q += ".is(gt(after))"
            params["after"] = after
        return [str(x) for x in self._submit(q + ".order().limit(size)", params)]

    def describe_ids(self, ids: list[str], props: tuple[str, ...] = ("name",)) -> list[dict[str, Any]]:
        sel = ", ".join(f"'{_ident(p, 'property')}'" for p in props)
        q = (f"g.V().{self._seed_filter()}.project('id', 'label', {sel})"
             f".by({self._id()}).by(label())" + "".join(
                 f".by(coalesce(__.values('{p}'), __.constant('')))" for p in props))
        return [dict(r) for r in self._submit(q, {"seeds": list(ids)})]

    def facet_counts(self, ids: list[str], prop: str | None) -> dict[str, int]:
        if prop is None:
            q = f"g.V().{self._seed_filter()}.groupCount().by(label())"
        else:
            q = (f"g.V().{self._seed_filter()}.groupCount()"
                 f".by(coalesce(__.values('{_ident(prop, 'property')}'), __.constant('None')))")
        got = self._submit(q, {"seeds": list(ids)})
        return {str(k): int(v) for k, v in (got[0] if got else {}).items()}

    def anchor_facets(self, seeds: tuple[str, ...]) -> list[dict[str, Any]]:
        out = []
        for direction, step, edge_end in (("out", "outE", "inV"), ("in", "inE", "outV")):
            q = (f"g.V().{self._seed_filter()}.{step}().as('e').{edge_end}().as('b')"
                 ".select('e', 'b').by(label()).by(label()).groupCount()")
            got = self._submit(q, {"seeds": list(seeds)})
            for k, v in (got[0] if got else {}).items():
                out.append({"rel": k["e"], "direction": direction, "label": k["b"], "n": int(v)})
        return out

    def anchors_found(self, seeds: tuple[str, ...]) -> list[str]:
        return [str(x) for x in self._submit(f"g.V().{self._seed_filter()}.{self._id()}.dedup()",
                                             {"seeds": list(seeds)})]

    # -- for the card question generator (Step 6) ----------------------------

    def nodes(self, label: str) -> list[dict[str, Any]]:
        q = (f"g.V().hasLabel('{_ident(label, 'label')}').project('id', 'name', 'description')"
             f".by({self._id()}).by(coalesce(__.values('name'), __.constant('')))"
             ".by(coalesce(__.values('description'), __.constant('')))")
        return [dict(r) for r in self._submit(q, {})]

    def degrees(self, label: str, rel: str, direction: str, target_label: str | None) -> dict[str, int]:
        step = {"out": "out", "in": "in", "both": "both"}[direction]
        hop = f"__.{step}('{self.edge_label(_ident(rel, 'relationship'))}')"
        if target_label:
            hop += f".hasLabel('{_ident(target_label, 'label')}')"
        q = (f"g.V().hasLabel('{_ident(label, 'label')}').project('id', 'n')"
             f".by({self._id()}).by({hop}.dedup().count())")
        return {str(r["id"]): int(r["n"]) for r in self._submit(q, {})}


Backend = CypherBackend | GremlinBackend


def fetch(backend: Backend, spec: SetSpec, *, mode: str = "stream", page_size: int = 10_000,
          ceiling: int = DEFAULT_CEILING) -> ExactSet:
    """The whole set, its exact total, and whether the ceiling stopped it."""
    started = time.perf_counter()
    notes: list[str] = []
    if mode == "stream":
        ids, complete = backend.stream(spec, ceiling)
        pages = 1
    elif mode == "keyset":
        ids, after, pages, complete = [], None, 0, True
        while True:
            page = backend.page(spec, after, page_size)
            pages += 1
            ids.extend(page)
            if len(ids) > ceiling:
                ids, complete = ids[:ceiling], False
                break
            if len(page) < page_size:
                break
            after = page[-1]
    else:
        raise ValueError("mode must be 'stream' or 'keyset'")
    total = len(ids) if complete else backend.count(spec)
    if not complete:
        notes.append(f"stopped at the ceiling of {ceiling:,}; the set holds {total:,}")
    query = backend.set_query(spec)
    return ExactSet(ids=sorted(ids), total=total, complete=complete, query=query, backend=backend.name,
                    mode=mode, seconds=round(time.perf_counter() - started, 4), pages=pages,
                    ceiling=ceiling, notes=notes)


__all__ = ["DEFAULT_CEILING", "CypherBackend", "ExactSet", "GremlinBackend", "SetSpec", "fetch"]
