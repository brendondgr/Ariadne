"""Mirror each Text2Cypher demo graph from its Neo4j into its own Gremlin server, and build its card.

Each graph has its own pair of stores (``t2c-<graph>-neo4j`` on bolt ``550N``, ``t2c-<graph>-gremlin``
on ``650N``), loaded from Neo4j's dump in ``data/external/text2cypher/dumps/<graph>/neo4j.dump``.

**Mirror typing** (the same rule as the CypherBench mirror): strings, numbers and booleans as
they are; string lists as multi-valued properties; ``Date`` as ``YYYY-MM-DD`` and ``DateTime``
as Neo4j's ISO string; ``Point`` properties are dropped from both the mirror and the card, so no
arm is told about them.

**Card:** labels and relationship patterns read from the data (``MATCH (a)-[r]->(b)``), property
types from ``db.schema.*TypeProperties``. Each label's key property is the first present of ``name``, ``title``,
``<label>Name``, ``companyName``, ``<label>ID``; else any ``...Name``, else any ``...ID`` / ``id``,
else the first string property alphabetically. Chosen from the schema alone.

    uv run python -m utils.killtests.t2c.load        # mirror all three graphs, check parity, write cards
"""

from __future__ import annotations

import json
import os
import random
from pathlib import Path

from ..config import REPO
from ..stages import atomic_write_json

GRAPHS = {"movies": 1, "northwind": 2, "fincen": 3}
OUT = REPO / "logs" / "killtests-2026-11" / "t2c"
_TYPES = {"String": "str", "Long": "int", "Double": "float", "Boolean": "bool", "StringArray": "list[str]",
          "Date": "date", "DateTime": "datetime"}


def neo4j_uri(graph: str) -> str:
    return f"bolt://localhost:550{GRAPHS[graph]}"


def gremlin_uri(graph: str) -> str:
    return f"ws://localhost:650{GRAPHS[graph]}/gremlin"


def driver(graph: str):
    from neo4j import GraphDatabase

    return GraphDatabase.driver(neo4j_uri(graph), auth=(os.environ.get("NEO4J_USER", "neo4j"),
                                                        os.environ.get("NEO4J_PASSWORD", "")))


def gclient(graph: str):
    from gremlin_python.driver import client as gc
    from gremlin_python.driver.serializer import GraphSONSerializersV3d0

    return gc.Client(gremlin_uri(graph), "g", message_serializer=GraphSONSerializersV3d0())


def _mirror_value(v):
    if hasattr(v, "iso_format"):
        return v.iso_format()[:10] if type(v).__name__ == "Date" else v.iso_format()
    if type(v).__name__ in ("CartesianPoint", "WGS84Point", "Point"):
        return None
    return v


def _key(props: dict[str, str], label: str = "") -> str:
    strs = sorted(k for k, t in props.items() if t == "str")
    low = label[:1].lower() + label[1:]
    for k in ("name", "title", f"{low}Name", "companyName", f"{low}ID", f"{low}Id"):
        if k in props:
            return k
    for k in strs:
        if k.endswith("Name"):
            return k
    for k in strs:
        if k.endswith("ID") or k.endswith("Id") or k == "id":
            return k
    return strs[0] if strs else "name"


def card(graph: str) -> dict:
    """The graph's schema in the card format ``typed.request.Card`` reads (``raw=``)."""
    with driver(graph) as d, d.session() as s:
        ent: dict[str, dict[str, str]] = {}
        for r in s.run("CALL db.schema.nodeTypeProperties() YIELD nodeLabels, propertyName, propertyTypes "
                       "RETURN nodeLabels, propertyName, propertyTypes"):
            for lab in r["nodeLabels"] or []:
                ent.setdefault(lab, {})
                t = _TYPES.get((r["propertyTypes"] or ["?"])[0])
                if r["propertyName"] and t:
                    ent[lab][r["propertyName"]] = t
        rprops: dict[str, dict[str, str]] = {}
        for r in s.run("CALL db.schema.relTypeProperties() YIELD relType, propertyName, propertyTypes "
                       "RETURN relType, propertyName, propertyTypes"):
            rt = r["relType"].strip(":`")
            rprops.setdefault(rt, {})
            t = _TYPES.get((r["propertyTypes"] or ["?"])[0])
            if r["propertyName"] and t:
                rprops[rt][r["propertyName"]] = t
        pats = s.run("MATCH (a)-[r]->(b) RETURN DISTINCT labels(a)[0] AS s, type(r) AS t, labels(b)[0] AS o "
                     "ORDER BY s, t, o").data()
    return {"name": graph,
            "entities": [{"label": lab, "key": _key(p, lab), "properties": dict(sorted(p.items()))}
                         for lab, p in sorted(ent.items())],
            "relations": [{"label": x["t"], "subj_label": x["s"], "obj_label": x["o"],
                           "properties": dict(sorted(rprops.get(x["t"], {}).items()))} for x in pats]}


_V = """
for (row in rows) {
  def v = graph.addVertex(T.label, row.label, '_eid', row.eid)
  row.single.each { k, val -> v.property(k, val) }
  row.multi.each { k, vals -> vals.each { x -> v.property(VertexProperty.Cardinality.list, k, x) } }
}
'ok'
"""
_E = """
for (row in rows) {
  def a = g.V().has('_eid', row.s).next()
  def b = g.V().has('_eid', row.o).next()
  def e = a.addEdge(row.label, b)
  row.p.each { k, val -> e.property(k, val) }
}
'ok'
"""


def mirror(graph: str) -> dict:
    c = gclient(graph)
    try:
        if c.submit("g.V().count()").all().result(timeout=60)[0] > 0:
            return {"skipped": "gremlin store not empty"}
        c.submit("graph.createIndex('_eid', Vertex.class); 'ok'").all().result(timeout=60)
        with driver(graph) as d, d.session() as s:
            nodes = s.run("MATCH (n) RETURN elementId(n) AS id, labels(n)[0] AS l, properties(n) AS p").data()
            rels = s.run("MATCH (a)-[r]->(b) RETURN elementId(a) AS s, type(r) AS t, elementId(b) AS o, "
                         "properties(r) AS p").data()
        rows = []
        for n in nodes:
            single, multi = {}, {}
            for k, v in n["p"].items():
                if isinstance(v, list):
                    multi[k] = [_mirror_value(x) for x in v if _mirror_value(x) is not None]
                else:
                    mv = _mirror_value(v)
                    if mv is not None:
                        single[k] = mv
            rows.append({"label": n["l"], "eid": n["id"], "single": single, "multi": multi})
        for i in range(0, len(rows), 500):
            c.submit(_V, bindings={"rows": rows[i:i + 500]}).all().result(timeout=600)
        er = [{"s": r["s"], "o": r["o"], "label": r["t"],
               "p": {k: _mirror_value(v) for k, v in r["p"].items() if _mirror_value(v) is not None}} for r in rels]
        for i in range(0, len(er), 1000):
            c.submit(_E, bindings={"rows": er[i:i + 1000]}).all().result(timeout=600)
        return {"nodes": len(rows), "edges": len(er)}
    finally:
        c.close()


def parity(graph: str, sample: int = 50, seed: int = 20261114) -> dict:
    out: dict = {"mismatches": []}
    with driver(graph) as d, d.session() as s:
        out["neo4j_labels"] = {r["l"]: r["c"] for r in s.run("MATCH (n) RETURN labels(n)[0] AS l, count(*) AS c")}
        out["neo4j_rels"] = {r["t"]: r["c"] for r in s.run("MATCH ()-[r]->() RETURN type(r) AS t, count(*) AS c")}
        ids = [r["id"] for r in s.run("MATCH (n) RETURN elementId(n) AS id")]
        pick = random.Random(seed).sample(ids, min(sample, len(ids)))
        neo = {r["id"]: r["p"] for r in s.run("MATCH (n) WHERE elementId(n) IN $ids RETURN elementId(n) AS id, "
                                              "properties(n) AS p", ids=pick)}
    c = gclient(graph)
    try:
        out["gremlin_labels"] = c.submit("g.V().groupCount().by(label)").all().result(timeout=120)[0]
        out["gremlin_rels"] = c.submit("g.E().groupCount().by(label)").all().result(timeout=120)[0]
        for eid in pick:
            gp = c.submit("g.V().has('_eid', eid).valueMap()", bindings={"eid": eid}).all().result(timeout=60)[0]
            gp = {k: (v if len(v) > 1 or isinstance(neo[eid].get(k), list) else v[0]) for k, v in gp.items()
                  if k != "_eid"}
            np_ = {k: _mirror_value(v) if not isinstance(v, list) else [_mirror_value(x) for x in v]
                   for k, v in neo[eid].items() if _mirror_value(v) is not None or isinstance(v, list)}
            for k in set(gp) | set(np_):
                a, b = np_.get(k), gp.get(k)
                same = a == b or (isinstance(a, list) and isinstance(b, list) and sorted(map(str, a)) == sorted(map(str, b))) \
                    or (isinstance(a, float) and isinstance(b, (int, float)) and abs(a - b) < 1e-9)
                if not same:
                    out["mismatches"].append({"id": eid, "key": k, "neo4j": str(a)[:80], "gremlin": str(b)[:80]})
    finally:
        c.close()
    out["labels_equal"] = out["neo4j_labels"] == out["gremlin_labels"]
    out["rels_equal"] = out["neo4j_rels"] == out["gremlin_rels"]
    out["ok"] = out["labels_equal"] and out["rels_equal"] and not out["mismatches"]
    return out


def main() -> int:
    from utils.config import load_env

    load_env()
    OUT.mkdir(parents=True, exist_ok=True)
    res = {}
    for g in GRAPHS:
        m = mirror(g)
        p = parity(g)
        cd = card(g)
        atomic_write_json(OUT / f"card-{g}.json", cd)
        res[g] = {"mirror": m, "parity_ok": p["ok"], "labels_equal": p["labels_equal"], "rels_equal": p["rels_equal"],
                  "mismatches": p["mismatches"][:10], "keys": {e["label"]: e["key"] for e in cd["entities"]}}
    atomic_write_json(OUT / "parity.json", res)
    print(json.dumps(res, indent=1, default=str))
    return 0 if all(r["parity_ok"] for r in res.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
