"""EXP-2026-11-005, exploratory (post hoc): how much of part B's result depends on the scorer.

The pre-registered scorer compares row **multisets** with exact columns. Text2Cypher's gold
queries often keep duplicate rows (no DISTINCT) and add columns the question does not ask for
(e.g. the sort value next to a name), while the typed compiler always de-duplicates by entity
and returns the columns the request names. This script re-executes every saved part-B query and
scores it three ways, identically for every arm:

- ``strict``: the pre-registered rule (multiset of rows, values sorted within a row);
- ``set``: duplicates ignored;
- ``set_proj``: duplicates ignored, and when the answer and the gold have different numbers of
  columns, correct if the wider side, projected onto some choice of columns, equals the
  narrower side exactly.

Typed requests are scored on their Cypher compilation (Cypher and Gremlin agreed on every
part-B request). It does not change the verdict.

    uv run python -m utils.killtests.t2c.sensitivity
"""

from __future__ import annotations

import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from itertools import combinations

from ..stages import atomic_write_json
from ..t1.execute import _row_values, canon, run_cypher, run_gremlin
from .analysis import EXP
from .run import OUT, REPAIR, Bench

ARMS = ("cypher-0shot", "cypher-3shot", "gremlin-0shot", "gremlin-3shot", "typed2-0shot", "typed2-3shot", REPAIR)


def rows_of(raw: list) -> list[tuple[str, ...]]:
    return [tuple(canon(v) for v in _row_values(r)) for r in raw]


def score(ans: list[tuple], gold: list[tuple]) -> dict[str, bool]:
    def bag(rows):
        return Counter(tuple(sorted(r)) for r in rows)

    strict = bag(ans) == bag(gold)
    sa, sg = set(bag(ans)), set(bag(gold))
    s = sa == sg
    proj = s
    if not proj and ans and gold:
        wa, wg = len(ans[0]), len(gold[0])
        if wa != wg and all(len(r) == wa for r in ans) and all(len(r) == wg for r in gold):
            wide, narrow = (ans, sg) if wa > wg else (gold, sa)
            k = min(wa, wg)
            for cols in combinations(range(max(wa, wg)), k):
                if {tuple(sorted(r[c] for c in cols)) for r in wide} == narrow:
                    proj = True
                    break
    return {"strict": strict, "set": s, "set_proj": proj}


def main() -> int:
    from utils.config import load_env

    load_env()
    b = Bench("B")
    gold = {q["qid"]: q for q in b.gold}
    ex = json.loads((OUT / "B-execute.json").read_text())["executions"]
    tags = sorted({k.split("|")[2] for k in ex})

    gold_rows = {}
    for qid, q in gold.items():
        drv, _ = b.clients(q["graph"])
        gold_rows[qid] = rows_of(run_cypher(drv, q["gold_cypher"]))

    def one(key: str):
        qid, arm, _tag = key.split("|")
        e, q = ex[key], gold[qid]
        drv, gc = b.clients(q["graph"])
        if arm.startswith("typed2"):
            query, lang = e.get("cypher"), "cypher"
        else:
            query, lang = e.get("query"), arm.split("-")[0]
        if not query or e.get("status") not in ("ok",):
            return key, {"strict": False, "set": False, "set_proj": False}
        try:
            raw = run_cypher(drv, query) if lang == "cypher" else run_gremlin(gc, query)
        except Exception:  # noqa: BLE001
            return key, {"strict": False, "set": False, "set_proj": False}
        return key, score(rows_of(raw), gold_rows[qid])

    keys = [k for k in ex if k.split("|")[1] in ARMS]
    with ThreadPoolExecutor(8) as pool:
        res = dict(pool.map(one, keys))

    out: dict = {"n": len(gold), "note": __doc__.split("\n\n")[1], "by_model": {}}
    for tag in tags:
        blk = {}
        for arm in ARMS:
            ks = [f"{qid}|{arm}|{tag}" for qid in gold]
            blk[arm] = {m: round(sum(res[k][m] for k in ks) / len(ks), 4) for m in ("strict", "set", "set_proj")}
            # consistency with the pre-registered scorer
            orig = sum(bool(ex[k].get("cypher_ok") if arm.startswith("typed2") else ex[k].get("correct")) for k in ks)
            blk[arm]["strict_matches_preregistered"] = orig == sum(res[k]["strict"] for k in ks)
        out["by_model"][tag] = blk
    atomic_write_json(EXP / "data" / "sensitivity.json", out)
    atomic_write_json(OUT / "B-sensitivity-per-key.json", res)
    print(json.dumps(out["by_model"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
