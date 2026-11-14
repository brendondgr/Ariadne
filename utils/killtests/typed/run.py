"""The typed arm of T1 (EXP-2026-11-004): stages generate -> execute -> score.

Same 200 questions as EXP-2026-11-003 (its recorded ``t1/gold`` stage), same relay,
temperature and token budget. Each reply is parsed, validated against the graph's
card, compiled to Cypher and to Gremlin, and both run on the T1 stores. An
unparseable or invalid request is wrong on both backends; there is no repair turn,
as the free arms had none.

    uv run python -m utils.killtests.typed.run default-model default-model-2

Scores are paired with the free arms of the same served model, read from that
model's EXP-2026-11-003 run folder (``FREE_RUNS``).
"""

from __future__ import annotations

import json
import os
import random
import sys
import threading
import time
from collections import Counter
from pathlib import Path

from ..config import REPO, get
from ..relay import RelayClient
from ..stages import Stage, atomic_write_json
from ..t1 import load as L
from ..t1.execute import normalise, run_cypher, run_gremlin
from ..t1.run import _paired_ci
from .cypher import compile_cypher
from .gremlin import compile_gremlin, finish
from .prompts import ARMS, extract_request, messages
from .request import Card, InvalidRequest, validate

BASE = REPO / "logs" / "killtests-2026-11"
OUT = BASE / "typed"
#: served-model tag -> the free-arm run of the same weights (EXP-2026-11-003).
FREE_RUNS = {
    "gemma4-31b": BASE / "t1-models" / "gemma4-31b__via_default-model" / "t1",
    "qwen38-27b": BASE / "t1-models" / "qwen38-27b__via_default-model-2" / "t1",
    "swift15-flashnext": BASE / "t1",
}
#: the last token id of a reply identifies the tokenizer family (see scripts/killtests_t1_model.py).
STOP_IDS = {106: "gemma4-31b", 248046: "qwen38-27b"}


def identify(relay: RelayClient, alias: str) -> dict:
    import urllib.request

    req = urllib.request.Request(
        relay.base_url + "/chat/completions",
        data=json.dumps({"model": alias, "max_tokens": 2048, "return_token_ids": True,
                         "messages": [{"role": "user", "content": "Reply with the word ok."}]}).encode(),
        headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as resp:  # noqa: S310
        env = json.loads(resp.read().decode())
    ids = env["choices"][0].get("token_ids") or []
    last = ids[-1] if ids else None
    return {"alias": alias, "envelope_model": env.get("model"), "last_token_id": last,
            "model": STOP_IDS.get(last, env.get("model")), "fingerprint": env.get("system_fingerprint")}


def stage_generate(cfg, out: Path, gold: dict, models: dict[str, str]) -> dict:
    st = Stage(out, "generate")
    if st.done:
        return st.load()
    relay = RelayClient(cfg.relay_url, max_tokens=cfg.relay_max_tokens)
    jobs = [(f"{q['qid']}|{arm}|{tag}", (q, arm, alias)) for q in gold["questions"] for arm in ARMS
            for alias, tag in models.items()]

    def one(x):
        q, arm, alias = x
        c = relay.complete(alias, messages(arm, q["graph"], q["nl_question"]), temperature=0.0)
        return {"raw": c.text[-6000:], "served_model": c.served_model, "finish_reason": c.finish_reason,
                "usage": c.usage, "latency_s": c.latency_s}

    res = st.map(jobs, one, workers=cfg.relay_concurrency * len(models))
    st.finish({"generations": res, "models": models})
    return st.load()


def stage_execute(cfg, out: Path, gold: dict, gen: dict) -> dict:
    st = Stage(out, "execute")
    if st.done:
        return st.load()
    local = threading.local()
    golds = {q["qid"]: q for q in gold["questions"]}
    cards = {g: Card(g) for g in L.TEST_GRAPHS}

    def one(key: str) -> dict:
        if not hasattr(local, "drv"):
            local.drv = L._neo4j_driver(cfg)
            local.gc = L._gremlin_client(cfg)
        qid = key.split("|")[0]
        q = golds[qid]
        g = gen["generations"][key]
        res: dict = {}
        if "error" in g:
            return {"status": "generation_error", "cypher_ok": False, "gremlin_ok": False, "detail": g["error"]}
        try:
            req = extract_request(g["raw"])
        except (ValueError, json.JSONDecodeError) as exc:
            return {"status": "unparseable", "cypher_ok": False, "gremlin_ok": False, "detail": str(exc)[:200]}
        res["request"] = req
        try:
            validate(req, cards[q["graph"]])
        except InvalidRequest as exc:
            return {**res, "status": "invalid", "cypher_ok": False, "gremlin_ok": False, "detail": str(exc)[:300]}
        except Exception as exc:  # noqa: BLE001 - malformed shapes the validator did not anticipate
            return {**res, "status": "invalid", "cypher_ok": False, "gremlin_ok": False,
                    "detail": f"{type(exc).__name__}: {exc}"[:300]}
        want = {tuple(k): v for k, v in q["_gold_norm"]}
        cy = compile_cypher(req, cards[q["graph"]])
        gr = compile_gremlin(req, cards[q["graph"]])
        res.update(status="ok", cypher=cy, gremlin=gr.script)
        for be in ("cypher", "gremlin"):
            t = time.time()
            try:
                rows = run_cypher(local.drv, cy) if be == "cypher" else finish(run_gremlin(local.gc, gr.script), gr.post)
                res[f"{be}_ok"] = dict(normalise(rows)) == want
                res[f"{be}_rows"] = len(rows)
            except Exception as exc:  # noqa: BLE001
                res[f"{be}_ok"] = False
                res[f"{be}_err"] = f"{type(exc).__name__}: {exc}"[:300]
            res[f"{be}_s"] = round(time.time() - t, 3)
        return res

    r = st.map([(k, k) for k in gen["generations"]], one, workers=8)
    st.finish({"executions": r})
    return st.load()


def _free(tag: str) -> dict | None:
    d = FREE_RUNS.get(tag)
    if not d or not (d / "execute.json").exists():
        return None
    ex = json.loads((d / "execute.json").read_text())["executions"]
    out: dict[str, dict[str, bool]] = {}
    for k, v in ex.items():
        qid, arm, _alias = k.split("|")
        out.setdefault(arm, {})[qid] = bool(v.get("correct"))
    return out


def stage_score(cfg, out: Path, gold: dict, gen: dict, ex: dict) -> dict:
    st = Stage(out, "score")
    if st.done:
        return st.load()
    qs = gold["questions"]
    cat = {q["qid"]: q["from_template"]["match_category"] for q in qs}
    rng = random.Random(cfg.seed + 23)
    res: dict = {"by_model": {}, "served_models": dict(Counter(g.get("served_model")
                                                              for g in gen["generations"].values()))}
    for alias, tag in gen["models"].items():
        block: dict = {"alias": alias, "arms": {}, "vs_free": {}}
        vec: dict[str, list[int]] = {}
        for arm in ARMS:
            outs = [ex["executions"].get(f"{q['qid']}|{arm}|{tag}") or {"status": "missing"} for q in qs]
            for be in ("cypher", "gremlin"):
                v = [int(bool(o.get(f"{be}_ok"))) for o in outs]
                vec[f"{arm}-{be}"] = v
                block["arms"][f"{arm}-{be}"] = {
                    "n": len(v), "exact_records": sum(v) / len(v),
                    "by_category": {c: sum(x for x, q in zip(v, qs) if cat[q["qid"]] == c)
                                    / max(1, sum(1 for q in qs if cat[q["qid"]] == c)) for c in sorted(set(cat.values()))},
                }
            block["arms"][arm] = {"status": dict(Counter(o.get("status") for o in outs)),
                                  "backends_agree": sum(o.get("cypher_ok") == o.get("gremlin_ok") for o in outs) / len(outs)}
        free = _free(tag)
        if free:
            for fa in ("cypher-0shot", "cypher-3shot", "gremlin-0shot", "gremlin-3shot"):
                vec[f"free-{fa}"] = [int(free.get(fa, {}).get(q["qid"], False)) for q in qs]
                block["arms"][f"free-{fa}"] = {"exact_records": sum(vec[f"free-{fa}"]) / len(qs)}
            for shots in ("0shot", "3shot"):
                for be in ("cypher", "gremlin"):
                    for fa in ("cypher", "gremlin"):
                        a, b = vec[f"free-{fa}-{shots}"], vec[f"typed-{shots}-{be}"]
                        block["vs_free"][f"typed-{shots}-{be}_minus_free-{fa}-{shots}"] = {
                            "diff": (sum(b) - sum(a)) / len(a), "ci95": _paired_ci(a, b, rng)}
        res["by_model"][tag] = block
    st.finish(res)
    return st.load()


def main(argv: list[str] | None = None) -> int:
    from utils.config import load_env

    load_env()
    aliases = (argv if argv is not None else sys.argv[1:]) or ["default-model", "default-model-2"]
    cfg = get()
    out = Path(os.environ.get("KILLTESTS_TYPED_OUT", OUT))
    out.mkdir(parents=True, exist_ok=True)
    gold = json.loads((BASE / "t1" / "gold.json").read_text())
    relay = RelayClient(cfg.relay_url, max_tokens=cfg.relay_max_tokens)
    hdr_path = out / "run_header.json"
    if hdr_path.exists():
        hdr = json.loads(hdr_path.read_text())
    else:
        ids = [identify(relay, a) for a in aliases]
        hdr = {"started_at": time.time(), "identities": ids, "concurrency_per_model": cfg.relay_concurrency,
               "max_tokens": cfg.relay_max_tokens, "n_questions": len(gold["questions"])}
        atomic_write_json(hdr_path, hdr)
    models = {i["alias"]: i["model"] for i in hdr["identities"]}
    if os.environ.get("KILLTESTS_TYPED_SMOKE"):
        gold = {**gold, "questions": gold["questions"][: int(os.environ["KILLTESTS_TYPED_SMOKE"])]}
    gen = stage_generate(cfg, out, gold, models)
    ex = stage_execute(cfg, out, gold, gen)
    sc = stage_score(cfg, out, gold, gen, ex)
    for tag, b in sc["by_model"].items():
        line = "  ".join(f"{k} {v['exact_records']:.3f}" for k, v in b["arms"].items() if "exact_records" in v)
        print(tag, line, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
