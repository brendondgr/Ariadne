"""Verify the two compilers without touching the test graphs.

Two checks, both in a separate pair of stores (``KILLTESTS_VERIFY_NEO4J_URI`` /
``KILLTESTS_VERIFY_GREMLIN_URI``, default ports 5480 / 6480):

1. **Gold** (``--mode gold``): every training question on ``terrorist_attack``
   (the only training graph small enough to load; art, biology and soccer are
   0.4-2.4 GB) is converted to a typed request, compiled to both languages, and
   each backend's records are compared with CypherBench's own ``answer_json``.
   The gold Cypher is run too, so a loader problem is not mistaken for a compiler
   problem.
2. **Differential** (``--mode diff``): random typed requests over the synthetic
   graph in ``fixture.py``; the compiled Cypher and Gremlin must return the same
   records. This covers the shapes terrorist_attack lacks (time filters, two
   relationships to one node, mixed-direction unions).

    uv run python -m utils.killtests.typed.verify --mode gold
    uv run python -m utils.killtests.typed.verify --mode diff --n 3000
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import random
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..config import REPO, get
from ..stages import atomic_write_json
from ..t1 import load as L
from ..t1.execute import normalise, run_cypher, run_gremlin
from .cypher import compile_cypher
from .from_gold import convert
from .gremlin import compile_gremlin, finish
from .request import Card, validate

TRAIN_GRAPHS = ("terrorist_attack",)


def verify_cfg():
    cfg = get()
    return dataclasses.replace(
        cfg,
        t1_neo4j_uri=os.environ.get("KILLTESTS_VERIFY_NEO4J_URI", "bolt://localhost:5480"),
        t1_gremlin_uri=os.environ.get("KILLTESTS_VERIFY_GREMLIN_URI", "ws://localhost:6480/gremlin"))


def ensure_loaded(cfg) -> dict:
    from . import fixture

    fx = fixture.build()
    orig = L.kg
    L.kg = lambda g: fx if g == "fixture" else orig(g)
    graphs = TRAIN_GRAPHS + ("fixture",)
    cur = L.counts(cfg)
    want = sum(len(L.kg(g)["entities"]) for g in graphs)
    if cur["neo4j_nodes"] == 0:
        for g in graphs:
            L.load_neo4j(cfg, g)
    if cur["gremlin_nodes"] == 0:
        for g in graphs:
            L.load_gremlin(cfg, g)
    cur = L.counts(cfg)
    cur["expected"] = want
    if cur["neo4j_nodes"] != want or cur["gremlin_nodes"] != want:
        raise SystemExit(f"verification stores hold {cur}, expected {want} nodes each")
    return cur


def sample(per_cell: int, seed: int = 20261114) -> list[dict]:
    with open(L.CB / "train.json") as fh:
        qs = [q for q in json.load(fh) if q["graph"] in TRAIN_GRAPHS]
    cells: dict[tuple, list] = defaultdict(list)
    for q in qs:
        ft = q["from_template"]
        cells[(q["graph"], ft["match_cypher"], ft["return_pattern_id"])].append(q)
    rng = random.Random(seed)
    out = []
    for k in sorted(cells):
        c = cells[k]
        out.extend(c if len(c) <= per_cell else rng.sample(c, per_cell))
    return out


def main(argv: list[str] | None = None) -> int:
    from utils.config import load_env

    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["gold", "diff"], default="gold")
    ap.add_argument("--n", type=int, default=3000)
    ap.add_argument("--per-cell", type=int, default=100000)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    cfg = verify_cfg()
    counts = ensure_loaded(cfg)
    if args.mode == "diff":
        return differential(cfg, args, counts)
    qs = sample(args.per_cell)
    cards = {g: Card(g) for g in TRAIN_GRAPHS}
    local = threading.local()

    def clients():
        if not hasattr(local, "drv"):
            local.drv = L._neo4j_driver(cfg)
            local.gc = L._gremlin_client(cfg)
        return local.drv, local.gc

    def one(q: dict) -> dict:
        want = normalise(json.loads(q["answer_json"]))
        drv, gc = clients()
        res = {"qid": q["qid"], "graph": q["graph"], "match": q["from_template"]["match_cypher"],
               "ret": q["from_template"]["return_pattern_id"]}
        try:
            res["gold_ok"] = normalise(run_cypher(drv, q["gold_cypher"])) == want
        except Exception as exc:  # noqa: BLE001
            res["gold_ok"], res["gold_err"] = False, str(exc)[:200]
        req = validate(convert(q["gold_cypher"]), cards[q["graph"]])
        cy = compile_cypher(req, cards[q["graph"]])
        gr = compile_gremlin(req, cards[q["graph"]])
        res["cypher"], res["gremlin"] = cy, gr.script
        t = time.time()
        try:
            res["cypher_ok"] = normalise(run_cypher(drv, cy)) == want
        except Exception as exc:  # noqa: BLE001
            res["cypher_ok"], res["cypher_err"] = False, str(exc)[:300]
        res["cypher_s"] = round(time.time() - t, 3)
        t = time.time()
        try:
            got = finish(run_gremlin(gc, gr.script), gr.post)
            res["gremlin_ok"] = normalise(got) == want
            if not res["gremlin_ok"]:
                res["gremlin_got"] = str(got)[:300]
        except Exception as exc:  # noqa: BLE001
            res["gremlin_ok"], res["gremlin_err"] = False, str(exc)[:300]
        res["gremlin_s"] = round(time.time() - t, 3)
        if not res["cypher_ok"] or not res["gremlin_ok"]:
            res["want"] = q["answer_json"][:300]
        return res

    with ThreadPoolExecutor(args.workers) as ex:
        rows = list(ex.map(one, qs))
    n = len(rows)
    summ = {
        "n": n, "store_counts": counts,
        "gold_ok": sum(r["gold_ok"] for r in rows) / n,
        "typed_cypher_ok": sum(r["cypher_ok"] for r in rows) / n,
        "typed_gremlin_ok": sum(r["gremlin_ok"] for r in rows) / n,
        "backends_agree": sum(r["cypher_ok"] == r["gremlin_ok"] for r in rows) / n,
        "among_gold_ok": {
            "n": sum(r["gold_ok"] for r in rows),
            "typed_cypher_ok": sum(r["cypher_ok"] for r in rows if r["gold_ok"]) / max(1, sum(r["gold_ok"] for r in rows)),
            "typed_gremlin_ok": sum(r["gremlin_ok"] for r in rows if r["gold_ok"]) / max(1, sum(r["gold_ok"] for r in rows)),
        },
        "gremlin_s_p95": sorted(r["gremlin_s"] for r in rows)[int(0.95 * n) - 1],
        "fail_cells": Counter(f"{r['match']} | {r['ret']} | cy={r['cypher_ok']} gr={r['gremlin_ok']}"
                              for r in rows if r["gold_ok"] and not (r["cypher_ok"] and r["gremlin_ok"])).most_common(40),
    }
    out = Path(args.out or REPO / "logs/killtests-2026-11/typed-verify/gold.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(out, {"summary": summ, "rows": rows})
    print(json.dumps({k: v for k, v in summ.items() if k != "fail_cells"}, indent=1))
    for k, v in summ["fail_cells"]:
        print(v, k)
    return 0


def differential(cfg, args, counts) -> int:
    from . import fixture

    gen = fixture.Generator(fixture.build())
    card = fixture.card()
    reqs = [validate(gen.request(), card) for _ in range(args.n)]
    local = threading.local()

    def one(req: dict) -> dict:
        if not hasattr(local, "drv"):
            local.drv = L._neo4j_driver(cfg)
            local.gc = L._gremlin_client(cfg)
        cy, gr = compile_cypher(req, card), compile_gremlin(req, card)
        res = {"req": req, "cypher": cy, "gremlin": gr.script}
        try:
            a = run_cypher(local.drv, cy)
        except Exception as exc:  # noqa: BLE001
            return {**res, "ok": False, "err": f"cypher: {exc}"[:300]}
        try:
            b = finish(run_gremlin(local.gc, gr.script), gr.post)
        except Exception as exc:  # noqa: BLE001
            return {**res, "ok": False, "err": f"gremlin: {exc}"[:300]}
        ok = normalise(a) == normalise(b)
        res.update(ok=ok, n_rows=len(a))
        if not ok:
            res.update(cypher_rows=str(a)[:300], gremlin_rows=str(b)[:300])
        return res

    with ThreadPoolExecutor(args.workers) as ex:
        rows = list(ex.map(one, reqs))
    kind = Counter()
    bad = Counter()
    for r in rows:
        k = r["req"]["answer"]["kind"]
        kind[k] += 1
        if not r["ok"]:
            bad[k] += 1
    summ = {"n": len(rows), "store_counts": counts, "agree": sum(r["ok"] for r in rows) / len(rows),
            "nonempty": sum(1 for r in rows if r.get("n_rows")) / len(rows),
            "by_kind": {k: {"n": kind[k], "disagree": bad[k]} for k in sorted(kind)}}
    out = Path(args.out or REPO / "logs/killtests-2026-11/typed-verify/diff.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(out, {"summary": summ, "rows": rows})
    print(json.dumps(summ, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
