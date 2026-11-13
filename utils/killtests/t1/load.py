"""Load CypherBench graphs into the dedicated T1 stores, and check they agree.

Both stores are loaded from the same ``simplekg`` JSON (CypherBench's own graph
format, Apache-2.0). Typing follows the graph's schema:

- **Neo4j:** ``date`` -> a Neo4j ``date`` (the gold Cypher reads ``n.date.year``),
  ``list[str]`` -> a list, numbers as numbers.
- **Gremlin (TinkerGraph):** ``date`` -> an ISO ``YYYY-MM-DD`` string,
  ``list[str]`` -> a multi-valued (``list`` cardinality) property, so ``has()``
  matches any element, numbers as numbers.

Every vertex and node also carries ``eid`` (CypherBench's entity id) so the two
stores can be compared node by node. ``parity()`` checks node, edge and
per-label counts and the properties of a random sample of nodes.

    uv run python -m utils.killtests.t1.load        # load both, then check parity
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

from ..config import REPO, get

CB = REPO / "data" / "external" / "cypherbench"
GRAPHS = ("flight_accident", "nba", "terrorist_attack")
TEST_GRAPHS = ("flight_accident", "nba")
SHOT_GRAPH = "terrorist_attack"


def kg(graph: str) -> dict:
    with open(CB / "graphs" / "simplekg" / f"{graph}_simplekg.json") as fh:
        return json.load(fh)


def schema(graph: str) -> dict:
    with open(CB / "graphs" / "schemas" / f"{graph}_schema.json") as fh:
        return json.load(fh)


def _neo4j_driver(cfg):
    from neo4j import GraphDatabase

    return GraphDatabase.driver(cfg.t1_neo4j_uri, auth=(cfg.neo4j_user, cfg.neo4j_password))


def _gremlin_client(cfg):
    from gremlin_python.driver import client as gclient
    from gremlin_python.driver.serializer import GraphSONSerializersV3d0

    return gclient.Client(cfg.t1_gremlin_uri, "g", message_serializer=GraphSONSerializersV3d0())


def load_neo4j(cfg, graph: str) -> None:
    d = kg(graph)
    types = {e["label"]: e["properties"] for e in d["schema"]["entities"]}
    with _neo4j_driver(cfg) as drv, drv.session() as s:
        for label in types:
            s.run(f"CREATE INDEX IF NOT EXISTS FOR (n:{label}) ON (n.eid)")
            s.run(f"CREATE INDEX IF NOT EXISTS FOR (n:{label}) ON (n.name)")
        by_label: dict[str, list] = {}
        for e in d["entities"]:
            props = {"eid": e["eid"], "name": e["name"]}
            date_keys = []
            for k, v in e["properties"].items():
                if v is None:
                    continue
                props[k] = v
                if types[e["label"]].get(k) == "date":
                    date_keys.append(k)
            by_label.setdefault(e["label"], []).append({"props": props, "dates": date_keys})
        for label, rows in by_label.items():
            for i in range(0, len(rows), 1000):
                s.run(
                    f"UNWIND $rows AS row CREATE (n:{label}) SET n = row.props "
                    "WITH n, row UNWIND row.dates AS k "
                    "CALL (n, k) { SET n[k] = date(n[k]) }",
                    rows=rows[i:i + 1000])
        by_rel: dict[tuple, list] = {}
        lab = {e["eid"]: e["label"] for e in d["entities"]}
        for r in d["relations"]:
            key = (lab[r["subj_id"]], r["label"], lab[r["obj_id"]])
            by_rel.setdefault(key, []).append({"s": r["subj_id"], "o": r["obj_id"],
                                               "p": {k: v for k, v in r["properties"].items() if v is not None}})
        for (sl, rl, ol), rows in by_rel.items():
            for i in range(0, len(rows), 2000):
                s.run(f"UNWIND $rows AS row MATCH (a:{sl} {{eid: row.s}}), (b:{ol} {{eid: row.o}}) "
                      f"CREATE (a)-[r:{rl}]->(b) SET r = row.p", rows=rows[i:i + 2000])


_V_SCRIPT = """
for (row in rows) {
  def v = graph.addVertex(T.label, row.label, 'eid', row.eid, 'name', row.name)
  for (e in row.single.entrySet()) { v.property(e.key, e.value) }
  for (e in row.multi.entrySet()) { for (x in e.value) { v.property(VertexProperty.Cardinality.list, e.key, x) } }
}
rows.size()
"""

_E_SCRIPT = """
int n = 0
for (row in rows) {
  def a = g.V().has('eid', row.s).next()
  def b = g.V().has('eid', row.o).next()
  def e = a.addEdge(row.label, b)
  for (p in row.p.entrySet()) { e.property(p.key, p.value) }
  n++
}
n
"""


def load_gremlin(cfg, graph: str) -> None:
    d = kg(graph)
    types = {e["label"]: e["properties"] for e in d["schema"]["entities"]}
    c = _gremlin_client(cfg)
    try:
        c.submit("graph.createIndex('eid', Vertex.class); 'ok'").all().result(timeout=60)
        rows = []
        for e in d["entities"]:
            single, multi = {}, {}
            for k, v in e["properties"].items():
                if v is None:
                    continue
                if isinstance(v, list):
                    multi[k] = [x for x in v if x is not None]
                else:
                    single[k] = v
            rows.append({"label": e["label"], "eid": e["eid"], "name": e["name"], "single": single, "multi": multi})
        for i in range(0, len(rows), 500):
            c.submit(_V_SCRIPT, bindings={"rows": rows[i:i + 500]}).all().result(timeout=300)
        erows = [{"s": r["subj_id"], "o": r["obj_id"], "label": r["label"],
                  "p": {k: v for k, v in r["properties"].items() if v is not None}} for r in d["relations"]]
        for i in range(0, len(erows), 1000):
            c.submit(_E_SCRIPT, bindings={"rows": erows[i:i + 1000]}).all().result(timeout=300)
    finally:
        c.close()
    _ = types


def _neo4j_scalar(v):
    if hasattr(v, "iso_format"):
        return v.iso_format()
    return v


def parity(cfg, sample: int = 50, seed: int = 20261113) -> dict:
    """Counts by label and relationship type in both stores, plus a property sample."""
    out: dict = {"neo4j": {}, "gremlin": {}, "mismatches": []}
    with _neo4j_driver(cfg) as drv, drv.session() as s:
        out["neo4j"]["labels"] = {r["l"]: r["c"] for r in s.run(
            "MATCH (n) RETURN head(labels(n)) AS l, count(*) AS c")}
        out["neo4j"]["rels"] = {r["t"]: r["c"] for r in s.run(
            "MATCH ()-[r]->() RETURN type(r) AS t, count(*) AS c")}
        eids = [r["e"] for r in s.run("MATCH (n) RETURN n.eid AS e ORDER BY e")]
        pick = random.Random(seed).sample(eids, min(sample, len(eids)))
        neo_props = {r["e"]: {k: _neo4j_scalar(v) for k, v in r["p"].items()} for r in s.run(
            "MATCH (n) WHERE n.eid IN $ids RETURN n.eid AS e, properties(n) AS p", ids=pick)}
    c = _gremlin_client(cfg)
    try:
        q = lambda s, b=None: c.submit(s, bindings=b or {}).all().result(timeout=120)  # noqa: E731
        out["gremlin"]["labels"] = q("g.V().groupCount().by(label)")[0]
        out["gremlin"]["rels"] = q("g.E().groupCount().by(label)")[0]
        gp = {}
        for row in q("g.V().has('eid', within(ids)).valueMap()", {"ids": pick}):
            e = row["eid"][0]
            gp[e] = {k: (v if len(v) > 1 or k in _multi_keys() else v[0]) for k, v in row.items()}
    finally:
        c.close()
    for e in pick:
        a, b = neo_props.get(e, {}), gp.get(e, {})
        for k in set(a) | set(b):
            va, vb = a.get(k), b.get(k)
            if isinstance(va, list) or isinstance(vb, list):
                same = sorted(map(str, va or [])) == sorted(map(str, vb if isinstance(vb, list) else [vb]))
            else:
                same = (str(va) == str(vb)) or (isinstance(va, float) and isinstance(vb, (int, float)) and abs(va - vb) < 1e-9)
            if not same:
                out["mismatches"].append({"eid": e, "key": k, "neo4j": va, "gremlin": vb})
    out["labels_equal"] = out["neo4j"]["labels"] == out["gremlin"]["labels"]
    out["rels_equal"] = out["neo4j"]["rels"] == out["gremlin"]["rels"]
    out["sampled_nodes"] = len(pick)
    out["ok"] = out["labels_equal"] and out["rels_equal"] and not out["mismatches"]
    return out


def _multi_keys() -> set[str]:
    keys = set()
    for g in GRAPHS:
        for e in schema(g)["entities"]:
            keys.update(k for k, t in (e.get("properties") or {}).items() if str(t).startswith("list"))
    return keys


def counts(cfg) -> dict:
    with _neo4j_driver(cfg) as drv, drv.session() as s:
        n = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
    c = _gremlin_client(cfg)
    try:
        g = c.submit("g.V().count()").all().result(timeout=60)[0]
    finally:
        c.close()
    return {"neo4j_nodes": n, "gremlin_nodes": g}


def main(argv: list[str] | None = None) -> int:
    from utils.config import load_env

    load_env()
    cfg = get()
    argv = argv or sys.argv[1:]
    cur = counts(cfg)
    expected = sum(len(kg(g)["entities"]) for g in GRAPHS)
    if cur["neo4j_nodes"] == 0:
        for g in GRAPHS:
            load_neo4j(cfg, g)
    elif cur["neo4j_nodes"] != expected:
        print(f"neo4j holds {cur['neo4j_nodes']} nodes, expected 0 or {expected}; refusing to load over it")
        return 2
    if cur["gremlin_nodes"] == 0:
        for g in GRAPHS:
            load_gremlin(cfg, g)
    elif cur["gremlin_nodes"] != expected:
        print(f"gremlin holds {cur['gremlin_nodes']} vertices, expected 0 or {expected}; refusing to load over it")
        return 2
    p = parity(cfg)
    out = cfg.out_dir / "t1"
    out.mkdir(parents=True, exist_ok=True)
    (out / "parity.json").write_text(json.dumps(p, indent=1, default=str))
    print(json.dumps({k: p[k] for k in ("ok", "labels_equal", "rels_equal", "sampled_nodes")}),
          "mismatches:", len(p["mismatches"]))
    return 0 if p["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
