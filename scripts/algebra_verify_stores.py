#!/usr/bin/env python3
"""Load ATT&CK and CAPEC into BOTH engines of the verification pair (Era 2, Step 9, Phase E).

The differential test compares Cypher with Gremlin on the same data. The
measured stores hold one dataset per engine (ATT&CK in Neo4j, CAPEC in Gremlin),
so the verification pair is separate: ``docker/algebra-verify/compose.yml``,
with Neo4j on bolt 5480 and Gremlin on 6480.

This script reuses the loader's stores and records, but **never writes a runtime
manifest and never touches the measured stores**:
- the URIs are the verification pair's, set explicitly;
- the preflight and manifest steps of ``load_backend`` are skipped.

    uv run python scripts/algebra_verify_stores.py load    # wipe both, load both datasets into both
    uv run python scripts/algebra_verify_stores.py counts  # node and edge counts per engine
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
NEO4J_URI = os.environ.get("ALGEBRA_VERIFY_NEO4J_URI", "bolt://localhost:5480")
GREMLIN_URI = os.environ.get("ALGEBRA_VERIFY_GREMLIN_URI", "ws://localhost:6480/gremlin")
DATASETS = ("attack", "capec")
MEASURED = ("5456", "6455")  # the measured stores' ports; refused as a target


def _stores(target, config):
    from utils.graph_loader.stores.gremlin import GremlinGraphStore
    from utils.graph_loader.stores.neo4j import Neo4jGraphStore

    for uri in (NEO4J_URI, GREMLIN_URI):
        if any(f":{p}" in uri for p in MEASURED):
            raise SystemExit(f"refusing to load into a measured store: {uri}")
    return {
        "neo4j": Neo4jGraphStore(uri=NEO4J_URI, user=config.neo4j_user, password=config.neo4j_password,
                                 export_files=target("neo4j").backends["neo4j"].export_files,
                                 batch_size=config.batch_size),
        "gremlin": GremlinGraphStore(uri=GREMLIN_URI,
                                     export_files=target("gremlin").backends["gremlin"].export_files,
                                     batch_size=config.batch_size),
    }


def counts() -> dict:
    from gremlin_python.driver import client as gclient
    from neo4j import GraphDatabase

    from utils.graph_loader.config import LoaderConfig

    cfg = LoaderConfig.from_data_dir()
    d = GraphDatabase.driver(NEO4J_URI, auth=(cfg.neo4j_user, cfg.neo4j_password))
    with d.session() as s:
        n = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        e = s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
    d.close()
    c = gclient.Client(GREMLIN_URI, "g")
    gn = c.submit("g.V().count()").all().result()[0]
    ge = c.submit("g.E().count()").all().result()[0]
    c.close()
    return {"neo4j": {"nodes": n, "edges": e}, "gremlin": {"nodes": gn, "edges": ge}}


def wipe() -> None:
    from gremlin_python.driver import client as gclient
    from neo4j import GraphDatabase

    from utils.graph_loader.config import LoaderConfig

    cfg = LoaderConfig.from_data_dir()
    d = GraphDatabase.driver(NEO4J_URI, auth=(cfg.neo4j_user, cfg.neo4j_password))
    with d.session() as s:
        s.run("MATCH (n) CALL (n) { DETACH DELETE n } IN TRANSACTIONS OF 5000 ROWS").consume()
    d.close()
    c = gclient.Client(GREMLIN_URI, "g")
    c.submit("g.V().drop().iterate()").all().result()
    c.close()


def load() -> dict:
    from utils.graph_loader.config import LoaderConfig
    from utils.graph_loader.loader import _batched, _expected_counts, _load_backend_records
    from utils.graph_loader.registry import resolve_dataset

    cfg = LoaderConfig.from_data_dir()
    wipe()
    report: dict = {"neo4j_uri": NEO4J_URI, "gremlin_uri": GREMLIN_URI, "datasets": {}}
    want = {"nodes": 0, "edges": 0}
    for ds in DATASETS:
        stores = _stores(lambda b, ds=ds: resolve_dataset(ds, b, cfg), cfg)
        entry = {}
        for backend, store in stores.items():
            target = resolve_dataset(ds, backend, cfg)
            nodes, edges = _load_backend_records(target, backend)
            store.connect()
            try:
                store.ensure_schema({k: str(v) for k, v in target.backends[backend].export_files.items()})
                n = sum(store.upsert_nodes(b) for b in _batched(nodes, cfg.batch_size))
                e = sum(store.upsert_edges(b) for b in _batched(edges, cfg.batch_size))
            finally:
                store.close()
            entry[backend] = {"nodes": n, "edges": e, "records": [len(nodes), len(edges)]}
        exp = _expected_counts(resolve_dataset(ds, "neo4j", cfg).manifest)
        entry["expected"] = {"nodes": exp.nodes, "edges": exp.edges}
        want["nodes"] += exp.nodes
        want["edges"] += exp.edges
        report["datasets"][ds] = entry
    got = counts()
    report["counts"] = got
    report["expected_total"] = want
    report["ok"] = all(got[b]["nodes"] == want["nodes"] and got[b]["edges"] == want["edges"] for b in got)
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["load", "counts"])
    a = ap.parse_args(argv)
    from utils.config import load_env

    load_env()
    r = load() if a.cmd == "load" else counts()
    print(json.dumps(r, indent=1, default=str))
    return 0 if r.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
