"""EXP-2026-11-004: the kill rule, applied mechanically, and the post-run ceiling.

    uv run python -m utils.killtests.typed.analysis           # ceiling (after the run), then the verdict

**Ceiling.** Each test question's gold Cypher is converted to a typed request,
compiled to both backends and executed; the share that reproduces the gold rows
bounds what any model filling in the form could reach. Computed only after the
run, with the code frozen at tag ``killtests-typed-run``.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from ..config import REPO, get
from ..stages import Stage, atomic_write_json
from ..t1 import load as L
from ..t1.execute import normalise, run_cypher, run_gremlin
from .cypher import compile_cypher
from .from_gold import Unsupported, convert
from .gremlin import compile_gremlin, finish
from .request import Card, InvalidRequest, validate
from .run import BASE, OUT

EXP = REPO / "docs/research/experiments/EXP-2026-11-004-t1-typed-arm"


def ceiling(cfg, out: Path) -> dict:
    st = Stage(out, "ceiling")
    if st.done:
        return st.load()
    gold = json.loads((BASE / "t1" / "gold.json").read_text())
    cards = {g: Card(g) for g in L.TEST_GRAPHS}
    drv, gc = L._neo4j_driver(cfg), L._gremlin_client(cfg)
    rows = {}
    try:
        for q in gold["questions"]:
            want = {tuple(k): v for k, v in q["_gold_norm"]}
            r: dict = {"category": q["from_template"]["match_category"]}
            try:
                req = validate(convert(q["gold_cypher"]), cards[q["graph"]])
            except (Unsupported, InvalidRequest) as exc:
                rows[q["qid"]] = {**r, "status": "not_expressible", "detail": str(exc)[:200],
                                  "cypher_ok": False, "gremlin_ok": False}
                continue
            r["status"] = "ok"
            for be in ("cypher", "gremlin"):
                try:
                    if be == "cypher":
                        got = run_cypher(drv, compile_cypher(req, cards[q["graph"]]))
                    else:
                        c = compile_gremlin(req, cards[q["graph"]])
                        got = finish(run_gremlin(gc, c.script), c.post)
                    r[f"{be}_ok"] = dict(normalise(got)) == want
                except Exception as exc:  # noqa: BLE001
                    r[f"{be}_ok"], r[f"{be}_err"] = False, str(exc)[:200]
            rows[q["qid"]] = r
    finally:
        drv.close()
        gc.close()
    n = len(rows)
    res = {"n": n, "rows": rows,
           "status": dict(Counter(r["status"] for r in rows.values())),
           "cypher": sum(r["cypher_ok"] for r in rows.values()) / n,
           "gremlin": sum(r["gremlin_ok"] for r in rows.values()) / n,
           "misses_by_category": dict(Counter(r["category"] for r in rows.values()
                                              if not (r["cypher_ok"] and r["gremlin_ok"])))}
    st.finish(res)
    return st.load()


def verdict(score: dict) -> dict:
    per = {}
    for tag, b in score["by_model"].items():
        a = b["arms"]
        tc, tg = a["typed-3shot-cypher"]["exact_records"], a["typed-3shot-gremlin"]["exact_records"]
        fc, fg = a["free-cypher-3shot"]["exact_records"], a["free-gremlin-3shot"]["exact_records"]
        per[tag] = {"typed_3shot_cypher": tc, "typed_3shot_gremlin": tg, "free_cypher_3shot": fc,
                    "free_gremlin_3shot": fg,
                    "H1_backend_independent": abs(tc - tg) <= 0.02 + 1e-9,
                    "H2_beats_free_gremlin": tg - fg >= 0.10 - 1e-9,
                    "H3_not_worse_than_free_cypher": tc >= fc - 0.05 - 1e-9,
                    "ci_typed_gremlin_minus_free_gremlin":
                        b["vs_free"]["typed-3shot-gremlin_minus_free-gremlin-3shot"]["ci95"],
                    "ci_typed_cypher_minus_free_cypher":
                        b["vs_free"]["typed-3shot-cypher_minus_free-cypher-3shot"]["ci95"]}
    killed = any(not v["H2_beats_free_gremlin"] for v in per.values()) or \
        all(not v["H3_not_worse_than_free_cypher"] for v in per.values())
    return {"rule": "killed if H2 (typed-3shot-gremlin >= free-gremlin-3shot + 0.10) fails for any model, "
                    "OR H3 (typed-3shot-cypher >= free-cypher-3shot - 0.05) fails for every model; H1 is "
                    "reported, not part of the rule",
            "inputs": per, "verdict": "killed" if killed else "survives",
            "H1_holds_all": all(v["H1_backend_independent"] for v in per.values())}


def main() -> int:
    from utils.config import load_env

    load_env()
    cfg = get()
    out = OUT
    score = json.loads((out / "score.json").read_text())
    ceil = ceiling(cfg, out)
    v = verdict(score)
    v["ceiling"] = {k: ceil[k] for k in ("n", "status", "cypher", "gremlin", "misses_by_category")}
    data = EXP / "data"
    data.mkdir(parents=True, exist_ok=True)
    atomic_write_json(data / "metrics.json", score)
    atomic_write_json(data / "killrule.json", v)
    atomic_write_json(data / "ceiling.json", {k: ceil[k] for k in ("n", "status", "cypher", "gremlin",
                                                                   "misses_by_category")})
    print(json.dumps({k: v[k] for k in ("verdict", "H1_holds_all", "inputs", "ceiling")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
