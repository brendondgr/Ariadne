"""T1 stages: sample + gold -> generate -> execute -> score.

    gold      CypherBench's reference Cypher, executed on killtests-neo4j; checked
              against CypherBench's own answer_json (a disagreeing question is
              excluded from the sample and recorded)
    generate  every (question, arm, model) through the relay, served model recorded
    execute   every generated query, read-only, 30 s timeout
    score     exact_records by arm x model x category, paired bootstrap CIs
"""

from __future__ import annotations

import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from ..config import KillTestConfig
from ..relay import RelayClient
from ..stages import Stage
from . import load as L
from .execute import normalise, run_cypher, run_gremlin
from .prompts import ARMS, extract_query, messages


def _questions() -> list[dict]:
    with open(L.CB / "test.json") as fh:
        return [q for q in json.load(fh) if q["graph"] in L.TEST_GRAPHS]


def sample(cfg: KillTestConfig, eligible: list[dict]) -> list[dict]:
    per_graph = max(1, cfg.t1_questions // len(L.TEST_GRAPHS))
    rng = random.Random(cfg.seed)
    out = []
    for g in L.TEST_GRAPHS:
        qs = [q for q in eligible if q["graph"] == g]
        by: dict[str, list] = defaultdict(list)
        for q in qs:
            by[q["from_template"]["match_category"]].append(q)
        cats = sorted(by)
        # proportional allocation, at least one per category, total per_graph
        alloc = {c: max(1, round(per_graph * len(by[c]) / len(qs))) for c in cats}
        while sum(alloc.values()) > per_graph:
            c = max(alloc, key=lambda k: (alloc[k], k))
            alloc[c] -= 1
        while sum(alloc.values()) < per_graph:
            c = max(cats, key=lambda k: (len(by[k]) - alloc[k], k))
            alloc[c] += 1
        for c in cats:
            out.extend(rng.sample(by[c], min(alloc[c], len(by[c]))))
    return out


def stage_gold(cfg: KillTestConfig, out: Path) -> dict:
    st = Stage(out / "t1", "gold")
    if st.done:
        return st.load()
    drv = L._neo4j_driver(cfg)
    try:
        eligible, disagree = [], []
        for q in _questions():
            rows = run_cypher(drv, q["gold_cypher"])
            if normalise(rows) == normalise(json.loads(q["answer_json"])):
                eligible.append({**q, "_gold_rows": [list(map(str, r.values())) for r in rows],
                                 "_gold_norm": [[list(k), v] for k, v in normalise(rows).items()]})
            else:
                disagree.append(q["qid"])
    finally:
        drv.close()
    chosen = sample(cfg, eligible)
    st.finish({"questions": [{k: v for k, v in q.items() if k != "_gold_rows"} for q in chosen],
               "excluded_gold_disagrees_with_answer_json": disagree,
               "n_eligible": len(eligible)})
    return st.load()


def _models(cfg: KillTestConfig) -> list[str]:
    relay = RelayClient(cfg.relay_url)
    try:
        healthy = set(relay.healthy_aliases())
    except Exception:  # noqa: BLE001
        healthy = set(cfg.relay_models)
    return [m for m in cfg.relay_models if m in healthy] or list(cfg.relay_models)


def stage_generate(cfg: KillTestConfig, out: Path, gold: dict) -> dict:
    st = Stage(out / "t1", "generate")
    if st.done:
        return st.load()
    relay = RelayClient(cfg.relay_url, max_tokens=cfg.relay_max_tokens)
    models = _models(cfg)
    jobs = [(f"{q['qid']}|{arm}|{m}", (q, arm, m)) for q in gold["questions"] for arm in ARMS for m in models]

    def one(x):
        q, arm, m = x
        c = relay.complete(m, messages(arm, q["graph"], q["nl_question"]), temperature=0.0)
        return {"query": extract_query(c.text), "raw": c.text[-4000:], "served_model": c.served_model,
                "finish_reason": c.finish_reason, "usage": c.usage, "latency_s": c.latency_s}

    res = st.map(jobs, one, workers=cfg.relay_concurrency)
    st.finish({"generations": res, "models": models})
    return st.load()


def stage_execute(cfg: KillTestConfig, out: Path, gold: dict, gen: dict) -> dict:
    st = Stage(out / "t1", "execute")
    if st.done:
        return st.load()
    import threading

    local = threading.local()

    def clients():
        if not hasattr(local, "drv"):
            local.drv = L._neo4j_driver(cfg)
            local.gc = L._gremlin_client(cfg)
        return local.drv, local.gc

    golds = {q["qid"]: q for q in gold["questions"]}

    def one(key: str) -> dict:
        qid, arm, _m = key.split("|")
        g = gen["generations"][key]
        if "error" in g:
            return {"status": "generation_error", "correct": False, "detail": g["error"]}
        query = g["query"]
        if not query:
            return {"status": "empty", "correct": False}
        drv, gc = clients()
        try:
            rows = run_cypher(drv, query) if arm.startswith("cypher") else run_gremlin(gc, query)
        except PermissionError as exc:
            return {"status": "blocked", "correct": False, "detail": str(exc)[:300]}
        except Exception as exc:  # noqa: BLE001
            kind = "timeout" if "timeout" in str(exc).lower() or "Timeout" in type(exc).__name__ else "error"
            return {"status": kind, "correct": False, "detail": f"{type(exc).__name__}: {exc}"[:300]}
        got = normalise(rows)
        want = {tuple(k): v for k, v in golds[qid]["_gold_norm"]}
        return {"status": "ok", "correct": dict(got) == want, "n_rows": len(rows)}

    res = st.map([(k, k) for k in gen["generations"]], one, workers=8)
    st.finish({"executions": res})
    return st.load()


def _paired_ci(a: list[int], b: list[int], rng: random.Random, n: int = 2000) -> list[float]:
    idx = range(len(a))
    diffs = []
    for _ in range(n):
        s = [rng.randrange(len(a)) for _ in idx]
        diffs.append(sum(b[i] - a[i] for i in s) / len(a))
    diffs.sort()
    return [diffs[int(0.025 * n)], diffs[int(0.975 * n) - 1]]


def stage_score(cfg: KillTestConfig, out: Path, gold: dict, gen: dict, ex: dict) -> dict:
    st = Stage(out / "t1", "score")
    if st.done:
        return st.load()
    qs = gold["questions"]
    cat = {q["qid"]: q["from_template"]["match_category"] for q in qs}
    graph = {q["qid"]: q["graph"] for q in qs}
    rng = random.Random(cfg.seed + 11)
    res: dict = {"by_model": {}, "served_models": dict(Counter(g.get("served_model") for g in gen["generations"].values()))}
    for m in gen["models"]:
        block: dict = {"arms": {}}
        vec: dict[str, list[int]] = {}
        for arm in ARMS:
            keys = [f"{q['qid']}|{arm}|{m}" for q in qs]
            outs = [ex["executions"].get(k) or {"status": "missing", "correct": False} for k in keys]
            v = [int(bool(o.get("correct"))) for o in outs]
            vec[arm] = v
            status = Counter(o.get("status") for o in outs)
            block["arms"][arm] = {
                "n": len(v), "exact_records": sum(v) / len(v) if v else None,
                "status": dict(status),
                "by_category": {c: sum(x for x, q in zip(v, qs) if cat[q["qid"]] == c)
                                / max(1, sum(1 for q in qs if cat[q["qid"]] == c)) for c in sorted(set(cat.values()))},
                "by_graph": {g: sum(x for x, q in zip(v, qs) if graph[q["qid"]] == g)
                             / max(1, sum(1 for q in qs if graph[q["qid"]] == g)) for g in L.TEST_GRAPHS},
            }
        for shots in ("0shot", "3shot"):
            a, b = vec[f"cypher-{shots}"], vec[f"gremlin-{shots}"]
            block[f"gremlin_minus_cypher_{shots}"] = {
                "diff": (sum(b) - sum(a)) / len(a) if a else None, "ci95": _paired_ci(a, b, rng) if a else None}
        res["by_model"][m] = block
    st.finish(res)
    return st.load()


def run(cfg: KillTestConfig, out: Path) -> dict:
    gold = stage_gold(cfg, out)
    gen = stage_generate(cfg, out, gold)
    ex = stage_execute(cfg, out, gold, gen)
    return stage_score(cfg, out, gold, ex=ex, gen=gen)
