#!/usr/bin/env python3
"""EXP-2026-11-011: hub sets of 10^5 and 10^6 members, exact, in Neo4j and Gremlin.

    uv run python scripts/era2_hub_bench.py load      # into the scratch stores era2-hub-* (:5490, :6490)
    uv run python scripts/era2_hub_bench.py bench --out <experiment>/data

The stores are scratch containers started for this measurement; nothing here
touches the project's graphs.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from utils.agent.exact import CypherBackend, GremlinBackend, SetSpec, fetch  # noqa: E402

NEO4J, GREMLIN = "bolt://localhost:5490", "ws://localhost:6490/gremlin"
HUBS = {"H1e5": 100_000, "H1e6": 1_000_000}
#: The project cards' query timeout (task default): the plan's bar for p95.
CARD_TIMEOUT_S = 5.0


def load() -> None:
    from gremlin_python.driver import client as gc
    from neo4j import GraphDatabase

    drv = GraphDatabase.driver(NEO4J, auth=None)
    with drv.session() as s:
        s.run("CREATE INDEX IF NOT EXISTS FOR (n:Hub) ON (n.eid)")
        s.run("CREATE INDEX IF NOT EXISTS FOR (n:Leaf) ON (n.eid)")
        for hub, n in HUBS.items():
            have = s.run("MATCH (:Hub {eid: $h})-[r:LINKS]->() RETURN count(r) AS c", h=hub).single()["c"]
            if have == n:
                print(f"neo4j {hub}: {n} edges present")
                continue
            s.run("MATCH (h:Hub {eid: $h}) DETACH DELETE h", h=hub)
            s.run("MERGE (:Hub {eid: $h})", h=hub)
            t = time.time()
            for lo in range(0, n, 50_000):
                s.run("MATCH (h:Hub {eid: $h}) UNWIND range($lo, $hi - 1) AS i "
                      "CREATE (h)-[:LINKS]->(:Leaf {eid: $h + '-' + apoc_pad(i)})".replace(
                          "apoc_pad(i)", "right('0000000' + toString(i), 7)"),
                      h=hub, lo=lo, hi=min(n, lo + 50_000))
            print(f"neo4j {hub}: loaded {n} edges in {time.time() - t:.0f}s")
    drv.close()

    c = gc.Client(GREMLIN, "g")
    for hub, n in HUBS.items():
        have = c.submit("g.V().has('eid', h).outE('LINKS').count()", bindings={"h": hub}).all().result()[0]
        if have == n:
            print(f"gremlin {hub}: {n} edges present")
            continue
        c.submit("g.V().has('eid', h).drop()", bindings={"h": hub}).all().result()
        c.submit("g.addV('Hub').property('eid', h).iterate()", bindings={"h": hub}).all().result()
        t = time.time()
        for lo in range(0, n, 20_000):
            c.submit("hub = g.V().has('eid', h).next(); "
                     "for (i in lo..<hi) { def v = graph.addVertex(T.label, 'Leaf', 'eid', h + '-' + String.format('%07d', i)); "
                     "hub.addEdge('LINKS', v) }; 'ok'",
                     bindings={"h": hub, "lo": lo, "hi": min(n, lo + 20_000)}).all().result(timeout=600)
        print(f"gremlin {hub}: loaded {n} edges in {time.time() - t:.0f}s")
    c.close()


def bench(out: Path, repeats: int = 20) -> dict:
    from gremlin_python.driver import client as gc
    from neo4j import GraphDatabase

    drv = GraphDatabase.driver(NEO4J, auth=None)
    cli = gc.Client(GREMLIN, "g")
    res: dict = {"card_timeout_s": CARD_TIMEOUT_S, "repeats": repeats, "cells": []}
    for be in (CypherBackend(drv, id_props=("eid",), timeout_s=600), GremlinBackend(cli, id_props=("eid",), timeout_s=600)):
        for hub, n in HUBS.items():
            spec = SetSpec((hub,), "LINKS", "out", "Leaf")
            first = fetch(be, spec)
            ok = first.complete and first.total == n == len(set(first.ids))
            times = [first.seconds] + [fetch(be, spec).seconds for _ in range(repeats - 1)]
            times.sort()
            p95 = times[min(len(times) - 1, int(round(0.95 * len(times))) - 1)]
            cell = {"backend": be.name, "hub": hub, "edges": n, "exact": ok, "total": first.total,
                    "median_s": round(statistics.median(times), 3), "p95_s": round(p95, 3),
                    "within_card_timeout": p95 <= CARD_TIMEOUT_S}
            # paged equals unpaged on the 10^5 hub (10^6 keyset would re-walk the hub per page)
            if n == 100_000:
                k = fetch(be, spec, mode="keyset", page_size=10_000)
                cell["keyset_equals_stream"] = k.ids == first.ids
                cell["keyset_seconds"] = k.seconds
            res["cells"].append(cell)
            print(json.dumps(cell))
    cli.close()
    drv.close()
    out.mkdir(parents=True, exist_ok=True)
    (out / "hubs.json").write_text(json.dumps(res, indent=1))
    return res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("load")
    b = sub.add_parser("bench")
    b.add_argument("--out", required=True)
    b.add_argument("--repeats", type=int, default=20)
    a = ap.parse_args(argv)
    if a.cmd == "load":
        load()
    else:
        bench(Path(a.out), a.repeats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
