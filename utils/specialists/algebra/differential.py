"""Phase E: run compiled operator trees on both engines and compare them (EXP-2026-11-021).

Semantics: ``docs/era-2-expansion/operator-algebra.md``. Three parts:

- **Running.** :class:`Engines` holds a Neo4j driver and a Gremlin client for the
  verification pair (bolt 5480, ws 6480) and runs one :class:`Compiled` on
  either. A compiled query returns one envelope record, read with ``finish``.
  The measured stores (5456, 6455) are refused.
- **Comparing.** :func:`compare` says whether two :class:`Result` objects agree:
  node sets by stored id, every value exactly, and only ``sum``/``avg`` floats
  within a relative 1e-9 (S11). Row order counts, since every list has a
  deterministic order (S8).
- **Generating.** :func:`generate` draws, from a card and the values actually
  stored, every operator instance the card allows (each operator × label ×
  relationship × direction) plus ``n`` seeded random compositions.

    uv run python -m utils.specialists.algebra.differential --seed 20261120 --random 3000 --out DIR

writes ``instances.jsonl`` (one row per instance) and ``summary.json`` (counts,
disagreements, coverage per (operator, label)).
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import math
import os
import random
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from .aggregate import Aggregate
from .base import Anchors, Common, Cond, Count, Describe, Expand, Hop, Intersect, Nodes, Scan, Values, Walk
from .compiled import Backend, Compiled, Result, finish
from .edges import Having, Union_
from .filters import Where
from .groupby import GroupBy
from .ir import OPERATOR_OF, to_dict
from .path import Reach, Shortest
from .rank import Rank
from .typescan import TypeScan
from .validate import InvalidOp, allowed_ops, check
from .verify import Verify

NEO4J_URI = os.environ.get("ALGEBRA_VERIFY_NEO4J_URI", "bolt://localhost:5480")
GREMLIN_URI = os.environ.get("ALGEBRA_VERIFY_GREMLIN_URI", "ws://localhost:6480/gremlin")
MEASURED = ("5456", "6455")
#: S11: the only tolerance anywhere, on float sums and averages.
REL_TOL = 1e-9
TIMEOUT_MS = 60_000


# --------------------------------------------------------------------------- #
# Running
# --------------------------------------------------------------------------- #


def reachable(uri: str, timeout: float = 1.5) -> bool:
    import socket
    from urllib.parse import urlparse

    u = urlparse(uri)
    try:
        with socket.create_connection((u.hostname or "localhost", u.port or 7687), timeout=timeout):
            return True
    except OSError:
        return False


def stores_up() -> bool:
    return reachable(NEO4J_URI) and reachable(GREMLIN_URI)


class Engines:
    """The verification pair: one Neo4j driver, one Gremlin client."""

    def __init__(self, neo4j_uri: str = NEO4J_URI, gremlin_uri: str = GREMLIN_URI, timeout_ms: int = TIMEOUT_MS):
        for uri in (neo4j_uri, gremlin_uri):
            if any(f":{p}" in uri for p in MEASURED):
                raise SystemExit(f"refusing a measured store: {uri}")
        from gremlin_python.driver import client as gclient
        from gremlin_python.driver.serializer import GraphSONSerializersV3d0
        from neo4j import GraphDatabase

        from utils.config import load_env

        load_env()
        self.timeout_ms = timeout_ms
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(os.environ.get("NEO4J_USER", "neo4j"),
                                                            os.environ.get("NEO4J_PASSWORD", "")),
                                           notifications_min_severity="OFF")
        self.client = gclient.Client(gremlin_uri, "g", message_serializer=GraphSONSerializersV3d0())

    def close(self) -> None:
        self.driver.close()
        self.client.close()

    def neo4j_raw(self, text: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        from neo4j import Query

        with self.driver.session() as s:
            return [r.data() for r in s.run(Query(text, timeout=self.timeout_ms / 1000), params or {})]

    def gremlin_raw(self, text: str, params: dict[str, Any] | None = None) -> list[Any]:
        return self.client.submit(text, params or {},
                                  request_options={"evaluationTimeout": self.timeout_ms}).all().result()

    def run(self, compiled: Compiled, backend: str) -> Result:
        raw = self.neo4j_raw(compiled.text, compiled.params) if backend == "cypher" else \
            self.gremlin_raw(compiled.text, compiled.params)
        return finish(raw, compiled)


def compile_on(node: Any, backend: Backend) -> Compiled:
    from utils.specialists.cypher.compile import compile_cypher
    from utils.specialists.gremlin.compile import compile_gremlin

    return (compile_cypher if backend.name == "cypher" else compile_gremlin)(node, backend)


# --------------------------------------------------------------------------- #
# Comparing
# --------------------------------------------------------------------------- #


def _float_close(a: Any, b: Any) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if a == b:
            return True
        return math.isclose(float(a), float(b), rel_tol=REL_TOL, abs_tol=0.0)
    return a == b


def _exact(a: Any, b: Any) -> bool:
    """Exact, but an int and the float it equals are one number (5 == 5.0)."""
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_exact(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(_exact(x, y) for x, y in zip(a, b))
    return a == b


def tolerant_fn(node: Any) -> bool:
    """Whether S11's tolerance applies: a float ``sum``/``avg`` aggregate or group value."""
    return isinstance(node, (Aggregate, GroupBy)) and node.fn in ("sum", "avg")


def compare(a: Result, b: Result, tolerant: bool = False) -> list[str]:
    """Every way ``a`` and ``b`` differ; empty when they agree."""
    out: list[str] = []
    same = _float_close if tolerant else _exact
    for f in ("kind", "total", "complete", "partial"):
        if not _exact(getattr(a, f), getattr(b, f)):
            out.append(f"{f}: {getattr(a, f)!r} != {getattr(b, f)!r}")
    if not same(a.value, b.value) and not (a.value is None and b.value is None):
        out.append(f"value: {a.value!r} != {b.value!r}")
    if not _exact(a.info, b.info):
        out.append(f"info: {_short(a.info)} != {_short(b.info)}")
    if len(a.rows) != len(b.rows):
        out.append(f"rows: {len(a.rows)} != {len(b.rows)}")
    ids_a = [r.get("id") for r in a.rows]
    ids_b = [r.get("id") for r in b.rows]
    if ids_a != ids_b:
        if sorted(map(str, ids_a)) == sorted(map(str, ids_b)):
            out.append("rows: same ids, different order")
        else:
            out.append(f"row ids differ: only-a {sorted(set(map(str, ids_a)) - set(map(str, ids_b)))[:5]} "
                       f"only-b {sorted(set(map(str, ids_b)) - set(map(str, ids_a)))[:5]}")
    else:
        for i, (ra, rb) in enumerate(zip(a.rows, b.rows)):
            if ra.keys() != rb.keys():
                out.append(f"row {i} columns {sorted(ra)} != {sorted(rb)}")
                break
            bad = [k for k in ra if not (same(ra[k], rb[k]) if k == "value" else _exact(ra[k], rb[k]))]
            if bad:
                out.append(f"row {i} ({ra.get('id')}) {bad[0]}: {_short(ra[bad[0]])} != {_short(rb[bad[0]])}")
                break
    return out


def _short(x: Any, n: int = 200) -> str:
    s = repr(x)
    return s if len(s) <= n else s[:n] + "…"


def result_dict(r: Result | None) -> Any:
    return None if r is None else dataclasses.asdict(r)


# --------------------------------------------------------------------------- #
# The combined card
# --------------------------------------------------------------------------- #


def combined_card(data_dir: str | Path = "data", datasets: tuple[str, ...] = ("attack", "capec")) -> Any:
    """One CardModel covering ``datasets``: both are loaded in both engines.

    Labels present in several cards (``Mitigation``) take the union of their
    properties; a property typed differently in two cards is an error.
    """
    from utils.agent.catalog import CardModel, LabelModel, RelationModel, _build_options, load_all

    cats, _ = load_all(data_dir, live=False)
    models = [cats[d].model if hasattr(cats[d], "model") else cats[d]._model for d in datasets]
    labels: dict[str, LabelModel] = {}
    rels: dict[str, RelationModel] = {}
    for m in models:
        for name, lab in m.labels.items():
            cur = labels.setdefault(name, LabelModel(name, lab.gloss, lab.key, {}))
            for p, pm in lab.properties.items():
                if p in cur.properties and cur.properties[p].vtype != pm.vtype:
                    raise ValueError(f"{name}.{p} typed {cur.properties[p].vtype} and {pm.vtype}")
                cur.properties.setdefault(p, pm)
        for name, rel in m.relations.items():
            if name in rels:
                raise ValueError(f"relationship {name} in two cards")
            rels[name] = dataclasses.replace(rel)
    model = CardModel("+".join(datasets), "combined", "neo4j+gremlin", labels, rels,
                      min(m.max_depth for m in models), "combined")
    _build_options(model, {})
    return model


#: Neo4j ``valueType`` -> card value type, for relationship properties read from the store.
_EDGE_TYPES = {"STRING NOT NULL": "string", "FLOAT NOT NULL": "number", "INTEGER NOT NULL": "integer",
               "BOOLEAN NOT NULL": "boolean", "LIST<STRING NOT NULL> NOT NULL": "list"}


def with_stored_edge_props(card: Any, engines: "Engines") -> dict[str, list[str]]:
    """Give ``card``'s relationships the properties the store holds on them (differential only).

    Neither card declares a relationship property, so O7a (edge filters) cannot run on
    real data through the card. The store reload of 2026-11-20 writes edge properties in
    both engines (ATT&CK: ``relationship_type``, ``stix_type``, ``phase_name``,
    ``log_source_names``; CAPEC: ``step``). This reads each relationship's property keys
    and one value type from Neo4j and adds them to the card, so the generator can draw
    edge filters from stored values. ``id`` and long text (``SKIP_PROPS``) are left out;
    a key with more than one value type is left out. Returns relation -> added names.
    """
    from utils.agent.catalog import PropertyModel

    rows = engines.neo4j_raw("MATCH ()-[r]->() UNWIND keys(r) AS k "
                             "RETURN type(r) AS rel, k, collect(DISTINCT valueType(r[k])) AS types")
    added: dict[str, list[str]] = {}
    for r in rows:
        rel, k, types = r["rel"], r["k"], r["types"]
        if rel not in card.relations or k == "id" or k in SKIP_PROPS or len(types) != 1:
            continue
        vtype = _EDGE_TYPES.get(types[0])
        if vtype is None:
            continue
        card.relations[rel].properties[k] = PropertyModel(k, vtype, vtype)
        added.setdefault(rel, []).append(k)
    return {k: sorted(v) for k, v in sorted(added.items())}


# --------------------------------------------------------------------------- #
# Generating
# --------------------------------------------------------------------------- #

#: Properties never used as filter/aggregate parameters: long free text, or
#: stored differently by the two loaders by design (``properties_json``).
SKIP_PROPS = frozenset({"description", "properties_json", "summary", "objective"})
MAX_VALUES = 40


@dataclasses.dataclass
class Instance:
    """One generated operator tree with where it came from."""

    iid: str
    family: str  # "card" or "random"
    operator: str  # O1..O8 or base op name
    labels: tuple[str, ...]
    node: Any


class Sampler:
    """Property values actually present in the store, read once from Neo4j."""

    def __init__(self, engines: Engines, card: Any, rng: random.Random):
        self.engines, self.card, self.rng = engines, card, rng
        self._ids: dict[str, list[str]] = {}
        self._vals: dict[tuple[str, str], list[Any]] = {}
        self._linked: dict[tuple[str, str, str, str], list[str]] = {}

    def ids(self, label: str) -> list[str]:
        if label not in self._ids:
            rows = self.engines.neo4j_raw(f"MATCH (n:`{label}`) RETURN n.id AS id ORDER BY id")
            self._ids[label] = [r["id"] for r in rows]
        return self._ids[label]

    def linked_ids(self, label: str, relation: str, direction: str, target: str) -> list[str]:
        """Ids of ``label`` nodes that have at least one ``relation``/``direction`` edge to ``target``."""
        key = (label, relation, direction, target)
        if key not in self._linked:
            pat = f"(n:`{label}`)-[:`{relation}`]->(m:`{target}`)" if direction == "out" else \
                f"(n:`{label}`)<-[:`{relation}`]-(m:`{target}`)"
            rows = self.engines.neo4j_raw(f"MATCH {pat} RETURN DISTINCT n.id AS id ORDER BY id")
            self._linked[key] = [r["id"] for r in rows]
        return self._linked[key]

    def values(self, label: str, prop: str) -> list[Any]:
        """Present values of ``prop`` on ``label`` (list elements for a list), sorted, at most MAX_VALUES."""
        key = (label, prop)
        if key not in self._vals:
            vtype = self.card.labels[label].properties[prop].vtype
            if vtype == "list":
                q = f"MATCH (n:`{label}`) WHERE n.`{prop}` IS NOT NULL UNWIND n.`{prop}` AS v RETURN DISTINCT v"
            else:
                q = f"MATCH (n:`{label}`) WHERE n.`{prop}` IS NOT NULL RETURN DISTINCT n.`{prop}` AS v"
            vals = [r["v"] for r in self.engines.neo4j_raw(q)]
            vals = sorted({v for v in vals if isinstance(v, (str, int, float, bool))}, key=lambda v: (str(type(v)), v))
            if len(vals) > MAX_VALUES:
                vals = sorted(self.rng.sample(vals, MAX_VALUES), key=lambda v: (str(type(v)), v))
            self._vals[key] = vals
        return self._vals[key]

    def edge_values(self, relation: str, prop: str) -> list[Any]:
        """Present values of a relationship property (list elements for a list), as ``values``."""
        key = ("@" + relation, prop)
        if key not in self._vals:
            vtype = self.card.relations[relation].properties[prop].vtype
            unwind = f"UNWIND r.`{prop}` AS v" if vtype == "list" else f"WITH r.`{prop}` AS v"
            q = f"MATCH ()-[r:`{relation}`]->() WHERE r.`{prop}` IS NOT NULL {unwind} RETURN DISTINCT v"
            vals = [r["v"] for r in self.engines.neo4j_raw(q)]
            vals = sorted({v for v in vals if isinstance(v, (str, int, float, bool))}, key=lambda v: (str(type(v)), v))
            if len(vals) > MAX_VALUES:
                vals = sorted(self.rng.sample(vals, MAX_VALUES), key=lambda v: (str(type(v)), v))
            self._vals[key] = vals
        return self._vals[key]

    def pick(self, seq: list[Any]) -> Any:
        return seq[self.rng.randrange(len(seq))] if seq else None


def _props(card: Any, label: str) -> list[tuple[str, str]]:
    return [(p, pm.vtype) for p, pm in sorted(card.labels[label].properties.items()) if p not in SKIP_PROPS]


def cond_for(s: Sampler, label: str, prop: str, vtype: str, op: str, vals: list[Any] | None = None) -> Cond | None:
    """A condition with a value drawn from the store (``vals``, else ``label``'s values of
    ``prop``), or ``None`` when none fits."""
    vals = s.values(label, prop) if vals is None else vals
    if op in ("present", "missing"):
        return Cond(prop, op)
    if not vals:
        return None
    v = s.pick(vals)
    if op == "size":
        return Cond(prop, "size", s.rng.choice([0, 1, 2, 3]), s.rng.choice(["=", "<>", "<", ">", "<=", ">="]))
    if op in ("contains", "not_contains"):
        return Cond(prop, op, str(v))
    if op in ("before", "after", "between", "year"):
        dates = sorted(str(x)[:10] for x in vals if isinstance(x, str) and _iso(x))
        if not dates:
            return None
        if op == "year":
            return Cond(prop, "year", int(s.pick(dates)[:4]), s.rng.choice(["=", "<", ">=", "<>"]))
        if op == "between":
            a, b = sorted([s.pick(dates), s.pick(dates)])
            return Cond(prop, "between", (a, b))
        return Cond(prop, op, s.pick(dates))
    if op in ("starts_with", "ends_with", "contains_text"):
        if not isinstance(v, str) or not v:
            return None
        i = s.rng.randrange(len(v))
        j = min(len(v), i + s.rng.randrange(1, 6))
        frag = v[:j - i] if op == "starts_with" else v[-(j - i):] if op == "ends_with" else v[i:j]
        return Cond(prop, op, frag)
    if vtype == "boolean":
        return Cond(prop, op, bool(v))
    if vtype in ("integer", "number", "number_text"):
        try:
            return Cond(prop, op, float(v) if vtype == "number" else int(float(v)))
        except (TypeError, ValueError):
            return None
    if vtype in ("date", "datetime") and isinstance(v, str):
        return Cond(prop, op, v[:10])
    return Cond(prop, op, str(v))


def _iso(x: str) -> bool:
    import re

    return bool(re.match(r"^\d{4}-\d{2}-\d{2}", x))


def _hops_from(card: Any, label: str) -> list[Hop]:
    return [Hop(o.relation, o.direction, o.target) for o in card.options(label)]


def _repeating(card: Any, label: str) -> list[Hop]:
    return [Hop(o.relation, o.direction, o.target) for o in card.options(label) if o.target == label]


def card_instances(card: Any, s: Sampler) -> list[Instance]:
    """Every instance the card allows, one per (operator × label × relationship × direction ×
    property × op) cell, with parameters drawn from the store."""
    out: list[Instance] = []
    n = 0

    def add(op: str, labels: Iterable[str], node: Any) -> None:
        nonlocal n
        n += 1
        out.append(Instance(f"c{n:05d}", "card", op, tuple(labels), node))

    rng = s.rng
    for label in sorted(card.labels):
        ids = s.ids(label)
        if not ids:
            continue
        anchors = Anchors(tuple(sorted(rng.sample(ids, min(3, len(ids))))), label)
        one = Anchors((s.pick(ids),), label)
        # today's operations
        add("scan", [label], Nodes(Scan(label)))
        add("describe", [label], Describe(Anchors((s.pick(ids), "no-such-id:" + label), label)))
        add("count", [label], Count(Scan(label)))
        for hop in _hops_from(card, label):
            linked = s.linked_ids(label, hop.relation, hop.direction, hop.target)
            a = Anchors(tuple(sorted(rng.sample(linked, min(3, len(linked))))) or anchors.ids, label) if linked \
                else anchors
            add("expand", [label], Expand(Walk(a, (hop,))))
            add("count", [label], Count(Walk(a, (hop,))))
            add("expand", [label], Expand(Walk(a, (Hop(hop.relation, hop.direction, ""),))))
            if hop.target == label:
                for d in (2, 3):
                    add("expand", [label], Expand(Walk(a, (hop,), d)))
            # second hop
            for hop2 in _hops_from(card, hop.target)[:4]:
                add("expand", [label], Expand(Walk(a, (hop, hop2))))
            # O3 rank by walk, O6 groupby, O7d absence / having, O4 verify
            add("O3", [label], Rank(Scan(label), rng.choice(["asc", "desc"]), rng.choice([1, 3, 10]), by_walk=(hop,)))
            add("O6", [label], GroupBy(Scan(label), (hop,), "count", having=rng.choice([None, (">", 0), ("=", 0)]),
                                       order=rng.choice([None, "desc", "asc"]), k=None))
            add("O7d", [label], Having(Scan(label), hop, False))
            add("O7d", [label], Having(Scan(label), hop, True))
            if linked:
                src = s.pick(linked)
                tgt = s.engines.neo4j_raw(
                    f"MATCH (n {{id:$id}}){'-' if hop.direction == 'out' else '<-'}[:`{hop.relation}`]"
                    f"{'->' if hop.direction == 'out' else '-'}(m:`{hop.target}`) RETURN m.id AS id ORDER BY id LIMIT 1",
                    {"id": src})
                if tgt:
                    add("O4", [label], Verify(Anchors((src,), label), Anchors((tgt[0]["id"],), hop.target),
                                              hop.relation, hop.direction))
                    add("O4", [label], Verify(Anchors((src,), label), Anchors((tgt[0]["id"],), hop.target)))
                add("O4", [label], Verify(Anchors((src,), label), Anchors((s.pick(s.ids(hop.target)),), hop.target)))
            add("O8", [label], Reach(one, ((hop.relation, hop.direction),), rng.choice([1, 2, 3])))
        if len(ids) >= 2:
            add("common", [label], Common(Anchors(tuple(sorted(rng.sample(ids, 2))), label)))
        # today's common: anchors of different kinds (the label's node and a neighbour's neighbour)
        for hop in _hops_from(card, label)[:1]:
            other = [x for x in s.ids(hop.target) if x not in ids]
            if other:
                add("common", [label], Common(Anchors((s.pick(ids), s.pick(other)))))
        for hop in _repeating(card, label)[:2]:
            add("O8", [label], Reach(one, ((hop.relation, hop.direction),), rng.choice([4, 6])))
        if len(ids) >= 2:
            b = rng.sample(ids, 2)
            add("O8", [label], Shortest(Anchors((b[0],), label), Anchors((b[1],), label), (), 3))
        # O1 / O5 / O2 / O3 per property and op
        for prop, vtype in _props(card, label):
            for op in allowed_ops(vtype):
                c = cond_for(s, label, prop, vtype, op)
                if c is None:
                    continue
                add("O1", [label], Where(Scan(label), (c,)))
                add("O5", [label], TypeScan(label, (c,)))
            add("values", [label], Values(Scan(label), prop))
            add("O2", [label], Aggregate(Scan(label), "count_values", prop))
            if vtype in ("integer", "number", "number_text"):
                for fn in ("sum", "avg", "min", "max", "median"):
                    add("O2", [label], Aggregate(Scan(label), fn, prop))
            if vtype in ("integer", "number", "number_text", "date", "datetime", "string"):
                for fn in ("min", "max"):
                    add("O2", [label], Aggregate(Scan(label), fn, prop))
                add("O3", [label], Rank(Scan(label), rng.choice(["asc", "desc"]), rng.choice([1, 3, 10]), prop=prop))
        add("O2", [label], Aggregate(Scan(label), "count"))
        # O7c union of two walks from the label
        hops = _hops_from(card, label)
        if len(hops) >= 2:
            add("O7c", [label], Union_((Walk(anchors, (hops[0],)), Walk(anchors, (hops[1],)))))
        else:
            add("O7c", [label], Union_((Scan(label), anchors)))
    # O7a: edge filters on the relationship properties the store holds (see
    # ``with_stored_edge_props``), one per (relationship, direction from its source label,
    # property, op), with values drawn from the stored edges.
    for label in sorted(card.labels):
        ids = s.ids(label)
        if not ids:
            continue
        for hop in _hops_from(card, label):
            props = card.relations[hop.relation].properties
            if hop.direction != "out" or not props:
                continue
            linked = s.linked_ids(label, hop.relation, hop.direction, hop.target)
            if not linked:
                continue
            a = Anchors(tuple(sorted(rng.sample(linked, min(5, len(linked))))), label)
            for prop, pm in sorted(props.items()):
                if prop in SKIP_PROPS:
                    continue
                vals = s.edge_values(hop.relation, prop)
                for op in allowed_ops(pm.vtype):
                    c = cond_for(s, label, prop, pm.vtype, op, vals)
                    if c is None:
                        continue
                    eh = Hop(hop.relation, hop.direction, hop.target, (c,))
                    add("O7a", [label, hop.target], Expand(Walk(a, (eh,))))
                    if op in ("=", "contains", "present"):
                        add("O7a", [label, hop.target], Count(Walk(Scan(label), (eh,))))
                        add("O7a", [label, hop.target], Having(Scan(label), eh, False))
    return out


def random_instance(card: Any, s: Sampler, i: int) -> Instance | None:
    """One random composition: a node set built from 1-3 operators, then a result operator."""
    rng = s.rng
    label = rng.choice(sorted(card.labels))
    ids = s.ids(label)
    if not ids:
        return None

    def base_set(lab: str) -> tuple[Any, frozenset[str]]:
        lids = s.ids(lab)
        r = rng.random()
        if r < 0.35 or not lids:
            return Scan(lab), frozenset([lab])
        if r < 0.55:
            props = _props(card, lab)
            conds = []
            for _ in range(rng.choice([1, 1, 2])):
                if not props:
                    break
                p, vt = rng.choice(props)
                c = cond_for(s, lab, p, vt, rng.choice(allowed_ops(vt)))
                if c is not None:
                    conds.append(c)
            return (TypeScan(lab, tuple(conds)) if conds else Scan(lab)), frozenset([lab])
        a = Anchors(tuple(sorted(rng.sample(lids, min(len(lids), rng.choice([1, 2, 5]))))), lab)
        return a, frozenset([lab])

    node, labels = base_set(label)
    for _ in range(rng.choice([0, 1, 1, 2])):
        cur = rng.choice(sorted(labels))
        r = rng.random()
        hops = _hops_from(card, cur)
        if r < 0.45 and hops:
            h = rng.choice(hops)
            if rng.random() < 0.2:
                h = Hop(h.relation, h.direction, "")
            last = ()
            tgt = h.target or None
            if tgt and rng.random() < 0.3:
                props = _props(card, tgt)
                if props:
                    p, vt = rng.choice(props)
                    c = cond_for(s, tgt, p, vt, rng.choice(allowed_ops(vt)))
                    last = (c,) if c else ()
            depth = 1
            if h.target == cur and rng.random() < 0.4 and not isinstance(node, Scan):
                depth = rng.choice([2, 3])
            cand = Walk(node, (h,), depth, last)
        elif r < 0.65:
            props = _props(card, cur)
            if not props:
                continue
            p, vt = rng.choice(props)
            c = cond_for(s, cur, p, vt, rng.choice(allowed_ops(vt)))
            if c is None:
                continue
            cand = Where(node, (c,))
        elif r < 0.8 and hops:
            h = rng.choice(hops)
            conds = ()
            if rng.random() < 0.4:
                props = _props(card, h.target)
                if props:
                    p, vt = rng.choice(props)
                    c = cond_for(s, h.target, p, vt, rng.choice(allowed_ops(vt)))
                    conds = (c,) if c else ()
            cand = Having(node, h, rng.random() < 0.5, conds)
        elif r < 0.9:
            other, _ = base_set(cur)
            cand = rng.choice([Union_((node, other)), Intersect((node, other))])
        else:
            cand = Reach(node, (), rng.choice([1, 2]))
        try:
            labels = check(cand, card)
        except InvalidOp:
            continue
        node = cand
    # result operator
    r = rng.random()
    cur = sorted(labels)
    lab = rng.choice(cur)
    props = [(p, vt) for p, vt in _props(card, lab) if all(p in card.labels[x].properties for x in cur)]
    if r < 0.3:
        res = Nodes(node, tuple(p for p, _ in rng.sample(props, min(2, len(props)))) if props and rng.random() < 0.3 else ())
    elif r < 0.45:
        res = Count(node)
    elif r < 0.6 and props:
        p, vt = rng.choice(props)
        fns = ["count_values"] + (["sum", "avg", "median", "min", "max"] if vt in ("integer", "number", "number_text")
                                  else ["min", "max"] if vt in ("date", "datetime", "string") else [])
        res = Aggregate(node, rng.choice(fns), p) if rng.random() < 0.85 else Aggregate(node, "count")
    elif r < 0.75:
        hops = [h for x in cur for h in _hops_from(card, x)]
        orderable = [(p, vt) for p, vt in props if vt in ("integer", "number", "number_text", "date", "string")]
        if hops and (rng.random() < 0.5 or not orderable):
            res = Rank(node, rng.choice(["asc", "desc"]), rng.choice([1, 2, 5, 20]), by_walk=(rng.choice(hops),))
        elif orderable:
            res = Rank(node, rng.choice(["asc", "desc"]), rng.choice([1, 2, 5, 20]), prop=rng.choice(orderable)[0])
        else:
            res = Count(node)
    elif r < 0.9:
        hops = [h for x in cur for h in _hops_from(card, x)]
        if not hops:
            res = Count(node)
        else:
            h = rng.choice(hops)
            tprops = _props(card, h.target) if h.target else []
            fn, prop = "count", None
            if tprops and rng.random() < 0.4:
                p, vt = rng.choice(tprops)
                if vt in ("integer", "number", "number_text"):
                    fn, prop = rng.choice(["sum", "avg", "min", "max", "median"]), p
                elif vt in ("date", "string"):
                    fn, prop = rng.choice(["min", "max"]), p
            end = ()
            if tprops and rng.random() < 0.3:
                p, vt = rng.choice(tprops)
                c = cond_for(s, h.target, p, vt, rng.choice(allowed_ops(vt)))
                end = (c,) if c else ()
            order = rng.choice([None, "asc", "desc"])
            res = GroupBy(node, (h,), fn, prop, having=rng.choice([None, None, (">", 0), ("=", 0), ("<=", 2)]),
                          order=order, k=rng.choice([None, 3]) if order else None, end_conds=end)
    else:
        res = Values(node, rng.choice(props)[0], rng.random() < 0.3) if props else Count(node)
    try:
        check(res, card)
    except InvalidOp:
        return None
    return Instance(f"r{i:05d}", "random", _op_name(res), tuple(sorted(labels)), res)


def _op_name(node: Any) -> str:
    n = OPERATOR_OF.get(type(node).__name__, 0)
    if n:
        return f"O{n}" if n != 7 else ("O7c" if isinstance(node, Union_) else "O7d")
    return type(node).__name__.lower()


def generate(card: Any, s: Sampler, n_random: int) -> list[Instance]:
    out = card_instances(card, s)
    i, tries = 0, 0
    while i < n_random and tries < n_random * 20:
        tries += 1
        inst = random_instance(card, s, i + 1)
        if inst is not None:
            out.append(inst)
            i += 1
    return out


def operators_in(node: Any) -> set[str]:
    """Coverage cells: the operator names a tree uses (O1..O8, plus today's)."""
    out: set[str] = set()

    def walk(x: Any) -> None:
        if dataclasses.is_dataclass(x) and not isinstance(x, type):
            name = type(x).__name__
            n = OPERATOR_OF.get(name)
            if n is not None:
                if n == 0:
                    out.add(name.lower())
                elif n == 7:
                    out.add("O7c" if name == "Union_" else "O7d")
                else:
                    out.add(f"O{n}")
            if name == "Hop" and x.edge_conds:
                out.add("O7a")
            if name == "Cond" and x.op in ("before", "after", "between", "year"):
                out.add("O7b")
            for f in dataclasses.fields(x):
                walk(getattr(x, f.name))
        elif isinstance(x, (tuple, list)):
            for y in x:
                walk(y)

    walk(node)
    return out


# --------------------------------------------------------------------------- #
# Running a batch
# --------------------------------------------------------------------------- #


def known_issue(node: Any, card: Any) -> str | None:  # noqa: ARG001 - kept for the report's shape
    """A reason this instance cannot agree that the semantics document states, or ``None``.

    There is none today. Two tags existed in Phase E, part 1, and both are retired:

    - ``walk_edge_reuse`` (a hop followed by the same relationship back): amendment 4
      makes every walk node-acyclic on both backends.
    - ``list_encoding`` (Gremlin stored lists as JSON text, Neo4j as lists): amendment 4
      and the store reload (2026-11-20) store string lists as list values in both, and
      no empty list.

    Every disagreement and one-sided error now counts.
    """
    return None


def run_instance(engines: Engines, inst: Instance, card: Any, row_cap: int = 1000) -> dict[str, Any]:
    row: dict[str, Any] = {"iid": inst.iid, "family": inst.family, "operator": inst.operator,
                           "labels": list(inst.labels), "ops": sorted(operators_in(inst.node)),
                           "tree": to_dict(inst.node)}
    results: dict[str, Any] = {}
    for bname, backend in (("cypher", Backend.cypher(card, row_cap=row_cap)),
                           ("gremlin", Backend.gremlin(card, row_cap=row_cap))):
        t0 = time.time()
        try:
            c = compile_on(inst.node, backend)
        except Exception as exc:  # noqa: BLE001 - a refusal is recorded
            results[bname] = {"compile_error": f"{type(exc).__name__}: {exc}"[:400]}
            continue
        try:
            r = engines.run(c, bname)
            results[bname] = {"result": r, "ms": round((time.time() - t0) * 1000)}
        except Exception as exc:  # noqa: BLE001
            results[bname] = {"run_error": f"{type(exc).__name__}: {exc}"[:600], "query": c.text[:2000],
                              "params": c.params}
    cy, gr = results["cypher"], results["gremlin"]
    if "result" in cy and "result" in gr:
        diffs = compare(cy["result"], gr["result"], tolerant_fn(inst.node))
        row["status"] = "agree" if not diffs else "disagree"
        row["diffs"] = diffs
        row["total"] = cy["result"].total
        row["value"] = cy["result"].value if not isinstance(cy["result"].value, (list, dict)) else None
        if diffs:
            row["cypher"] = _trim(result_dict(cy["result"]))
            row["gremlin"] = _trim(result_dict(gr["result"]))
    else:
        errs = {k: v for k, v in (("cypher", cy), ("gremlin", gr)) if "result" not in v}
        kinds = {k: ("compile_error" if "compile_error" in v else "run_error") for k, v in errs.items()}
        if len(errs) == 2 and all(k == "compile_error" for k in kinds.values()) and \
                cy["compile_error"].split(":")[0] == gr["compile_error"].split(":")[0]:
            row["status"] = "both_refused"
        else:
            row["status"] = "error"
        row["errors"] = {k: {kk: vv for kk, vv in v.items() if kk != "result"} for k, v in errs.items()}
    row["ms"] = {k: v.get("ms") for k, v in results.items()}
    row["known"] = known_issue(inst.node, card) if row["status"] in ("disagree", "error") else None
    return row


def _trim(d: Any) -> Any:
    if isinstance(d, dict) and "rows" in d:
        d = dict(d)
        d["rows"] = d["rows"][:20]
    return json.loads(json.dumps(d, default=str))


def coverage(rows: list[dict[str, Any]], card: Any, cells: Iterable[tuple[str, str]]) -> dict[str, Any]:
    """Which applicable (operator, label) cells ran on both engines without error."""
    ran: dict[tuple[str, str], int] = Counter()
    for r in rows:
        if r["status"] not in ("agree", "disagree"):
            continue
        for op in r["ops"]:
            for lab in r["labels"]:
                ran[(op, lab)] += 1
    cells = sorted(set(cells))
    missing = [c for c in cells if not ran.get(c)]
    return {"applicable": len(cells), "exercised": len(cells) - len(missing),
            "share": round((len(cells) - len(missing)) / len(cells), 4) if cells else 1.0,
            "missing": [list(c) for c in missing],
            "per_cell": {f"{op}|{lab}": ran.get((op, lab), 0) for op, lab in cells}}


#: Operators whose applicability does not depend on the label's relationships or properties.
ALWAYS = ("scan", "describe", "count", "nodes", "O1", "O2", "O5", "O7c", "O8")


def applicable_cells(card: Any) -> list[tuple[str, str]]:
    """(operator, label) cells the card allows. O7a (edge filters) applies to a label with
    a relationship that has a property (only after ``with_stored_edge_props``: neither
    card declares one); O7b (time) needs an ISO-shaped property value."""
    cells = []
    for lab in sorted(card.labels):
        ops = set(ALWAYS)
        if card.options(lab):
            ops |= {"expand", "walk", "O3", "O4", "O6", "O7d"}
        if any(pm.vtype in ("string", "date") for pm in card.labels[lab].properties.values()):
            ops.add("O3")
        if len(card.labels) > 0:
            ops.add("common")
        cells += [(op, lab) for op in ops]
        if any(p in ("created", "modified", "first_seen", "last_seen") for p in card.labels[lab].properties):
            cells.append(("O7b", lab))
        if any(card.relations[o.relation].properties for o in card.options(lab)):
            cells.append(("O7a", lab))
    return cells


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--seed", type=int, default=20261120)
    ap.add_argument("--random", type=int, default=3000)
    ap.add_argument("--out", required=True)
    ap.add_argument("--row-cap", type=int, default=1000)
    ap.add_argument("--limit", type=int, default=0, help="run only the first N instances (debugging)")
    ap.add_argument("--only", default="", help="comma-separated instance ids to run")
    ap.add_argument("--no-edge-props", dest="edge_props", action="store_false",
                    help="do not add the store's relationship properties to the card (no O7a on real data)")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if not stores_up():
        print("verification stores unreachable", file=sys.stderr)
        return 2
    rng = random.Random(a.seed)
    engines = Engines()
    card = combined_card()
    edge_props = with_stored_edge_props(card, engines) if a.edge_props else {}
    s = Sampler(engines, card, rng)
    t0 = time.time()
    insts = generate(card, s, a.random)
    if a.only:
        keep = set(a.only.split(","))
        insts = [i for i in insts if i.iid in keep]
    if a.limit:
        insts = insts[: a.limit]
    rows = []
    with open(out / "instances.jsonl", "w") as fh:
        for k, inst in enumerate(insts):
            row = run_instance(engines, inst, card, a.row_cap)
            rows.append(row)
            fh.write(json.dumps(row, default=str, sort_keys=True) + "\n")
            if (k + 1) % 250 == 0:
                print(f"{k + 1}/{len(insts)} {Counter(r['status'] for r in rows)}", file=sys.stderr, flush=True)
    engines.close()
    status = Counter(r["status"] for r in rows)
    by_op: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        by_op[r["operator"]][r["status"]] += 1
    cov = coverage(rows, card, applicable_cells(card))
    summary = {
        "seed": a.seed, "random": a.random, "row_cap": a.row_cap, "instances": len(rows),
        "card_instances": sum(1 for r in rows if r["family"] == "card"),
        "random_instances": sum(1 for r in rows if r["family"] == "random"),
        "status": dict(status), "disagreements": status.get("disagree", 0), "errors": status.get("error", 0),
        "unexplained_disagreements": sum(1 for r in rows if r["status"] == "disagree" and not r.get("known")),
        "unexplained_errors": sum(1 for r in rows if r["status"] == "error" and not r.get("known")),
        "known_issues": dict(Counter(f"{r['status']}:{r['known']}" for r in rows if r.get("known"))),
        "by_operator": {k: dict(v) for k, v in sorted(by_op.items())},
        "disagreeing_ids": [r["iid"] for r in rows if r["status"] == "disagree"],
        "error_ids": [r["iid"] for r in rows if r["status"] == "error"],
        "coverage": {k: v for k, v in cov.items() if k != "per_cell"}, "coverage_cells": cov["per_cell"],
        "tolerance": {"relative": REL_TOL, "applies_to": "sum/avg aggregate and group values"},
        "edge_props_from_store": edge_props,
        "neo4j_uri": NEO4J_URI, "gremlin_uri": GREMLIN_URI, "seconds": round(time.time() - t0, 1),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: summary[k] for k in ("instances", "status", "disagreements", "errors",
                                               "unexplained_disagreements", "unexplained_errors", "known_issues")}
                     | {"coverage": summary["coverage"]["share"]}))
    return 0 if not summary["unexplained_disagreements"] and not summary["unexplained_errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
