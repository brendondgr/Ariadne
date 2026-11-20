"""What both compilers produce, and the one function that reads their results.

The compilers (``utils/specialists/cypher/compile.py`` and ``gremlin/compile.py``)
turn an operator tree into a :class:`Compiled`: query text, its parameters, the
result contract (``kind``), and at most one declared post-step. Semantics:
``docs/era-2-expansion/operator-algebra.md`` (rule ids S1-S12).

**Raw results.** Every compiled query returns exactly **one** record (a Neo4j
record, or one Gremlin map): an envelope whose keys depend on ``kind``
(``rows``/``total`` for node sets, ``value`` for a count, ``a_found``/``witness``
for verify, ...). :func:`finish` reads that envelope and returns a :class:`Result`
whose ``rows`` use the same column names on both backends (the ``*_COLUMNS``
constants below).

**Post-steps** (``Compiled.post``) are the parts both backends hand to Python, so
that one function gives both the same meaning:

- ``rank``: sort by key then stored id, a missing key last, and cut at ``k``
  keeping every item tied with the k-th (S8);
- ``group``: per group, median (S11), then ``having``, then the same ranking as
  ``rank``, then the row cap (S9's order: values first, ``having`` after);
- ``median``: the median of an aggregate's collected values (S11);
- ``shortest``: keep the distinct paths, cap them, and mark ``partial`` (S10, S7).

Everything else (deduplication, missing-never-matches, dates, ``number_text``,
empty groups, totals) happens inside the query.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

#: Labels, relationship names and property names are spliced into the query
#: text as identifiers (no engine binds them), so each is checked against this.
SAFE_IDENT = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
#: An ISO-8601 date prefix (S6). The same text is a parameter on both backends;
#: it matches under both a full match (Cypher ``=~``) and a search (``TextP.regex``).
ISO_REGEX = r"(?s)^\d{4}-\d{2}-\d{2}.*$"
#: A number written as text (amendment 2). Anything else counts as missing. One
#: regex on both backends, so "parses" means the same thing in each.
NUMBER_REGEX = r"^-?\d+(\.\d+)?([eE][-+]?\d+)?$"

# --- result contracts (the finished rows' columns, the same on both backends) ---
NODE_COLUMNS = ("id", "name")  # plus any requested props
DESCRIBE_COLUMNS = ("id", "name", "properties")
VALUES_COLUMNS = ("id", "value")
SCALAR_COLUMNS = ("value",)
RANK_COLUMNS = ("id", "name", "value")
GROUP_COLUMNS = ("id", "name", "value")
VERIFY_COLUMNS = ("relation", "direction", "properties")
VERIFY_FLAGS = ("a_found", "b_found", "exists")
SHORTEST_COLUMNS = ("path", "rels")

#: Result kinds, one per contract.
KINDS = ("nodes", "describe", "values", "count", "aggregate", "rank", "groupby", "verify", "shortest")
POSTS = ("rank", "group", "median", "shortest")


class UnsafeIdentifier(ValueError):
    """A label, relationship or property name that may not be spliced into a query."""


def safe_ident(value: Any, kind: str) -> str:
    if not isinstance(value, str) or not SAFE_IDENT.match(value):
        raise UnsafeIdentifier(f"unsafe {kind}: {value!r}")
    return value


@dataclass(frozen=True)
class Compiled:
    """One compiled query.

    ``text`` and ``params`` are what runs: every user value is in ``params``.
    ``kind`` names the result contract and ``post`` the declared post-step.
    ``meta`` carries what :func:`finish` needs and the query cannot return:
    the row cap, ``k``, the anchor ids asked for, the backend-to-card
    relationship names, and ``inputs`` (parameter -> earlier step id, for
    ``FromStep``; the runner fills those parameters before running).
    """

    text: str
    params: dict[str, Any]
    kind: str
    post: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class Backend:
    """What a compiler needs to know about the store it compiles for.

    ``rel_name`` turns a card relationship name into the backend's spelling.
    ``max_params`` is the most parameters one query may bind (the stock Gremlin
    server allows 16); ``None`` is unbounded.
    """

    name: str
    rel_name: Callable[[str], str]
    row_cap: int = 1000
    card: Any = None
    max_params: int | None = None
    validate: bool = True

    @classmethod
    def cypher(cls, card: Any = None, *, row_cap: int = 1000, rel_name: Callable[[str], str] | None = None,
               validate: bool = True) -> "Backend":
        return cls("cypher", rel_name or (lambda r: r), row_cap, card, None, validate)

    @classmethod
    def gremlin(cls, card: Any = None, *, row_cap: int = 1000, rel_name: Callable[[str], str] | None = None,
                max_params: int | None = 16, validate: bool = True) -> "Backend":
        if rel_name is None:
            from utils.graph_loader.stores.gremlin import gremlin_edge_label

            rel_name = gremlin_edge_label
        return cls("gremlin", rel_name, row_cap, card, max_params, validate)

    def rel(self, card_name: str) -> str:
        """The backend spelling of a card relationship, checked as an identifier."""
        safe_ident(card_name, "relationship")
        return safe_ident(self.rel_name(card_name), "relationship")

    def prop_type(self, labels: Any, prop: str) -> str | None:
        """The card value type of ``prop`` on ``labels`` (``None``: no card, or unknown)."""
        if self.card is None or not labels:
            return None
        types = {self.card.labels[lab].properties[prop].vtype for lab in labels
                 if lab in self.card.labels and prop in self.card.labels[lab].properties}
        return next(iter(types)) if len(types) == 1 else None

    def edge_prop_type(self, relation: str, prop: str) -> str | None:
        if self.card is None or relation not in self.card.relations:
            return None
        p = self.card.relations[relation].properties.get(prop)
        return p.vtype if p is not None else None


class Params:
    """Parameter names for one query. Equal values share one name, which keeps
    a Gremlin query under the server's binding limit."""

    def __init__(self, backend: Backend) -> None:
        self.backend = backend
        self.values: dict[str, Any] = {}
        self._memo: dict[tuple[str, str], str] = {}
        self.inputs: dict[str, str] = {}

    def add(self, value: Any) -> str:
        if isinstance(value, tuple):
            value = list(value)
        key = (type(value).__name__, repr(value))
        if key not in self._memo:
            name = f"p{len(self.values)}"
            self.values[name] = value
            self._memo[key] = name
        return self._memo[key]

    def input(self, step: str) -> str:
        """A parameter the runner fills with an earlier step's stored ids."""
        name = f"p{len(self.values)}"
        self.values[name] = None
        self.inputs[name] = step
        return name

    def check(self) -> None:
        cap = self.backend.max_params
        if cap is not None and len(self.values) > cap:
            raise ValueError(f"the query needs {len(self.values)} parameters; this backend binds at most {cap}")


# --- finishing -----------------------------------------------------------------

@dataclass
class Result:
    """A finished result: rows in the contract's columns, plus the envelope.

    ``total`` is exact (S7); ``complete`` is false when the rows shown were capped
    or the search hit its depth cap (``partial``). ``info`` holds what some kinds
    add: ``anchor_not_found`` (S12), ``unranked``, ``lacking``, ``a_found``,
    ``b_found``, ``exists``.
    """

    kind: str
    rows: list[dict[str, Any]]
    total: int | None = None
    complete: bool = True
    partial: bool = False
    value: Any = None
    info: dict[str, Any] = field(default_factory=dict)


def _record(raw: Any) -> dict[str, Any]:
    """The one envelope record, from a driver's rows."""
    rows = list(raw) if not isinstance(raw, dict) else [raw]
    if len(rows) != 1:
        raise ValueError(f"expected one envelope record, got {len(rows)}")
    rec = rows[0]
    if hasattr(rec, "data") and callable(rec.data):  # neo4j.Record
        rec = rec.data()
    return dict(rec)


#: Properties a loader writes for its own use, not card properties (§ 1: the algebra
#: sees the card, not the raw storage). Neo4j's loader keeps a ``properties_json``
#: copy of the canonical record; Gremlin has none.
STORE_ONLY_PROPS = frozenset({"properties_json"})


def _str_keys(d: Any) -> dict[str, Any]:
    """A property map without Gremlin's ``T.id``/``T.label`` tokens, store-only keys, or
    empty lists (amendment 4: an empty list is missing, so describe never shows one)."""
    return {k: v for k, v in dict(d or {}).items()
            if isinstance(k, str) and k not in STORE_ONLY_PROPS and not (isinstance(v, (list, tuple)) and not v)}


def median(values: list[Any]) -> Any:
    """S11: the middle value, or the mean of the two middle values; ``None`` for nothing."""
    xs = sorted(v for v in values if v is not None)
    if not xs:
        return None
    mid = len(xs) // 2
    if len(xs) % 2:
        return xs[mid]
    return (xs[mid - 1] + xs[mid]) / 2


def rank_rows(rows: list[dict[str, Any]], order: str, k: int | None) -> list[dict[str, Any]]:
    """S8: order by ``value`` then ``id``; a ``None`` value last in either order; keep ties at ``k``.

    When the k-th item has no value, every item without a value is tied with it.
    """
    have = [r for r in rows if r.get("value") is not None]
    none = sorted((r for r in rows if r.get("value") is None), key=lambda r: str(r.get("id")))
    have.sort(key=lambda r: str(r.get("id")))
    have.sort(key=lambda r: r["value"], reverse=(order == "desc"))
    ordered = have + none
    if k is None or k >= len(ordered):
        return ordered
    cut = ordered[k - 1].get("value")
    return ordered[:k] + [r for r in ordered[k:] if r.get("value") == cut]


def _cmp(op: str, a: Any, b: Any) -> bool:
    if a is None:
        return False
    return {"=": a == b, "<>": a != b, "<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b}[op]


def _back(meta: dict[str, Any], name: Any) -> Any:
    return (meta.get("rels") or {}).get(name, name)


def _not_found(meta: dict[str, Any], found: list[list[str]] | None) -> list[str]:
    out: list[str] = []
    for want, got in zip(meta.get("anchors") or [], found or []):
        have = set(got or [])
        out += [x for x in want if x not in have and x not in out]
    return out


def finish(rows: Any, compiled: Compiled) -> Result:
    """Normalise a compiled query's raw rows into its contract, applying its post-step."""
    rec = _record(rows)
    meta, kind, post = compiled.meta, compiled.kind, compiled.post
    cap = int(meta.get("row_cap", 1000))
    info: dict[str, Any] = {}
    if "found" not in rec and any(k.startswith("found_") for k in rec):  # Gremlin: one key per Anchors
        rec["found"] = [rec.get(f"found_{i}") or [] for i in range(len(meta.get("anchors") or []))]
    if "found" in rec and meta.get("anchors"):
        info["anchor_not_found"] = _not_found(meta, rec.get("found"))

    if kind == "nodes":
        cols = NODE_COLUMNS + tuple(meta.get("props") or ())
        out = [{c: r.get(c) for c in cols} for r in rec.get("rows") or []][:cap]
        total = int(rec.get("total") or 0)
        partial = bool(rec.get("partial")) or (rec.get("total_beyond") is not None
                                               and int(rec["total_beyond"]) > total)
        return Result(kind, out, total, len(out) == total and not partial, partial, info=info)

    if kind == "describe":
        out = [{"id": r.get("id"), "name": r.get("name"), "properties": _str_keys(r.get("properties"))}
               for r in rec.get("rows") or []]
        found = {r["id"] for r in out}
        info["anchor_not_found"] = [x for x in meta.get("anchors", [[]])[0] if x not in found]
        return Result(kind, out, len(out), True, info=info)

    if kind == "values":
        out = [{"id": r.get("id"), "value": r.get("value")} for r in rec.get("rows") or []][:cap]
        total = int(rec.get("total") or 0)
        info["lacking"] = int(rec.get("lacking") or 0)
        return Result(kind, out, total, len(out) == total, info=info)

    if kind in ("count", "aggregate"):
        value = rec.get("value")
        if post == "median":
            value = median(list(value or []))
        elif kind == "count":
            value = int(value or 0)
        return Result(kind, [{"value": value}], 1, True, value=value, info=info)

    if kind == "rank":
        allr = [{c: r.get(c) for c in RANK_COLUMNS} for r in rec.get("rows") or []]
        if meta.get("drop_missing"):
            info["unranked"] = sum(1 for r in allr if r["value"] is None)
            allr = [r for r in allr if r["value"] is not None]
        out = rank_rows(allr, meta["order"], meta["k"])
        return Result(kind, out, len(out), True, info=info)

    if kind == "groupby":
        allr = [{c: r.get(c) for c in GROUP_COLUMNS} for r in rec.get("rows") or []]
        if meta.get("fn") == "median":
            for r in allr:
                r["value"] = median(list(r["value"] or []))
        if meta.get("having"):
            op, val = meta["having"]
            allr = [r for r in allr if _cmp(op, r["value"], val)]
        if meta.get("order"):
            allr = rank_rows(allr, meta["order"], meta.get("k"))
        else:
            allr.sort(key=lambda r: str(r["id"]))
        total = len(allr)
        out = allr[:cap]
        return Result(kind, out, total, len(out) == total, info=info)

    if kind == "verify":
        wit = [{"relation": _back(meta, w.get("relation")), "direction": w.get("direction"),
                "properties": _str_keys(w.get("properties"))} for w in rec.get("witness") or []]
        uniq = []
        for w in wit:
            if w not in uniq:
                uniq.append(w)
        uniq.sort(key=lambda w: (str(w["relation"]), str(w["direction"]), str(w["properties"].get("id"))))
        a_found, b_found = bool(rec.get("a_found")), bool(rec.get("b_found"))
        info.update(a_found=a_found, b_found=b_found, exists=bool(uniq))
        info["anchor_not_found"] = ([] if a_found else list(meta["anchors"][0])) + (
            [] if b_found else list(meta["anchors"][1]))
        out = uniq[:cap]
        return Result(kind, out, len(uniq), len(out) == len(uniq), value=bool(uniq), info=info)

    if kind == "shortest":
        paths = []
        for p in rec.get("paths") or []:
            if isinstance(p, dict):  # Cypher: node ids and relationship names apart
                ids, rels = list(p.get("nodes") or []), [_back(meta, r) for r in p.get("rels") or []]
            else:  # Gremlin: one alternating list
                seq = list(p)
                ids, rels = seq[0::2], [_back(meta, r) for r in seq[1::2]]
            alt: list[Any] = []
            for i, node in enumerate(ids):
                alt.append(node)
                if i < len(rels):
                    alt.append(rels[i])
            row = {"path": alt, "rels": rels}
            if row not in paths:
                paths.append(row)
        paths.sort(key=lambda r: [str(x) for x in r["path"]])
        a_found, b_found = bool(rec.get("a_found")), bool(rec.get("b_found"))
        info.update(a_found=a_found, b_found=b_found)
        info["anchor_not_found"] = ([] if a_found else list(meta["anchors"][0])) + (
            [] if b_found else list(meta["anchors"][1]))
        beyond = bool(rec.get("beyond")) or (rec.get("total_beyond") is not None
                                             and int(rec["total_beyond"]) > int(rec.get("total_within") or 0))
        partial = not paths and beyond
        out = paths[:cap]
        return Result(kind, out, len(paths), len(out) == len(paths) and not partial, partial, info=info)

    raise ValueError(f"unknown result kind {kind!r}")


__all__ = ["Backend", "Compiled", "DESCRIBE_COLUMNS", "GROUP_COLUMNS", "ISO_REGEX", "KINDS", "NODE_COLUMNS",
           "NUMBER_REGEX", "POSTS", "Params", "RANK_COLUMNS", "Result", "SAFE_IDENT", "SCALAR_COLUMNS",
           "SHORTEST_COLUMNS", "UnsafeIdentifier", "VALUES_COLUMNS", "VERIFY_COLUMNS", "VERIFY_FLAGS", "finish",
           "median", "rank_rows", "safe_ident"]
