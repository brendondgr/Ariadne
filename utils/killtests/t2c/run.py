"""EXP-2026-11-005 (default) and EXP-2026-11-006 (``KILLTESTS_EXPERIMENT=exp006``).

EXP-2026-11-006 (format v3): parts A (CypherBench, 200), B (Text2Cypher, 390, the development
benchmark) and C (Mind the Query, 450, held out), each with free Cypher, free Gremlin, typed v2 and
typed v3 at 3 shots, plus ``typed3-3shot-repair``; v3 cards (``cards-v3/``) for B and C.

EXP-2026-11-005: format v2 on CypherBench (part A) and every arm on Text2Cypher (part B).

    uv run --with pyarrow python -m utils.killtests.t2c.run [A|B ...]

Part A: ``typed2-0shot``, ``typed2-3shot`` and ``typed2-3shot-repair`` on the 200 CypherBench
questions of EXP-2026-11-003/-004; the free arms and v1 typed arms are read from those runs.

Part B: the four free arms, the two typed v2 arms and the repair arm on the 390 selected
Text2Cypher questions (``gold.py``), on the three local graphs.

``typed2-3shot-repair``: when a ``typed2-3shot`` reply is unparseable or invalid, one more turn
shows the model the validator's message and asks for a corrected request. Replies that were
valid carry over unchanged. Execution errors are not fed back. This is a secondary arm: the free
arms get no repair turn.
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

from ..config import get
from ..relay import RelayClient
from ..stages import Stage, atomic_write_json
from ..t1 import load as L
from ..t1.execute import normalise, run_cypher, run_gremlin
from ..t1.prompts import extract_query, schema_block
from ..t1.run import _paired_ci
from ..typed.cypher import compile_cypher
from ..typed.gremlin import compile_gremlin, finish
from ..typed.prompts import ARMS_V2, ARMS_V3, extract_request
from ..typed.prompts import messages as typed_messages
from ..typed.request import Card, InvalidRequest, validate
from ..typed.run import BASE, FREE_RUNS, identify
from . import load as T
from .prompts import FREE_ARMS, card_block, free_messages

EXPERIMENT = os.environ.get("KILLTESTS_EXPERIMENT", "exp005")
if EXPERIMENT == "exp006":
    OUT = BASE / "exp006"
    REPAIR_FROM = "typed3-3shot"
    ARMS6 = ("cypher-3shot", "gremlin-3shot", "typed2-3shot", "typed3-3shot")
else:
    OUT = BASE / "exp005"
    REPAIR_FROM = "typed2-3shot"
    ARMS6 = ()
REPAIR = f"{REPAIR_FROM}-repair"
_ = ARMS_V3


class Bench:
    def __init__(self, part: str) -> None:
        self.part = part
        if part == "A":
            self.gold = json.loads((BASE / "t1" / "gold.json").read_text())["questions"]
            self.graphs = list(L.TEST_GRAPHS)
            self.cards = {g: Card(g) for g in self.graphs}
            self.blocks = {g: schema_block(g) for g in self.graphs}
            self.arms = ARMS6 or ARMS_V2
        else:
            src = T.OUT_MTQ if part == "C" else T.OUT
            self.gold = json.loads((src / "gold.json").read_text())["questions"]
            self.graphs = list(T.MTQ if part == "C" else T.GRAPHS)
            cdir = src / "cards-v3" if EXPERIMENT == "exp006" else src
            raw = {g: json.loads((cdir / f"card-{g}.json").read_text()) for g in self.graphs}
            self.cards = {g: Card(g, raw[g]) for g in self.graphs}
            self.blocks = {g: card_block(raw[g]) for g in self.graphs}
            self.arms = ARMS6 or (FREE_ARMS + ARMS_V2)
        self.local = threading.local()

    def clients(self, graph: str):
        k = f"c_{graph}"
        if not hasattr(self.local, k):
            if self.part == "A":
                cfg = get()
                setattr(self.local, k, (L._neo4j_driver(cfg), L._gremlin_client(cfg)))
            else:
                setattr(self.local, k, (T.driver(graph), T.gclient(graph)))
        return getattr(self.local, k)

    def messages(self, arm: str, q: dict) -> list[dict]:
        if arm.startswith("typed"):
            return typed_messages(arm, q["graph"], q["nl_question"], block=self.blocks[q["graph"]])
        return free_messages(arm, self.blocks[q["graph"]], q["nl_question"])


def _parse_validate(raw: str, card: Card):
    try:
        req = extract_request(raw)
    except (ValueError, json.JSONDecodeError) as exc:
        return None, "unparseable", f"no valid JSON request: {exc}"[:300]
    try:
        return validate(req, card), "ok", None
    except InvalidRequest as exc:
        return req, "invalid", str(exc)[:300]
    except Exception as exc:  # noqa: BLE001
        return req, "invalid", f"{type(exc).__name__}: {exc}"[:300]


def effort(tag: str) -> dict:
    """Per-model request extras, e.g. ``KILLTESTS_REASONING_EFFORT='{"qwen38-27b": "medium"}'``.

    Added 2026-11-14 after the protocol was frozen (see ISSUES.md): Qwen's server defaults to
    ``reasoning_effort=xhigh`` and ran out of the 8,192-token budget on part B.
    """
    lvl = json.loads(os.environ.get("KILLTESTS_REASONING_EFFORT") or "{}").get(tag)
    return {"reasoning_effort": lvl} if lvl else {}


def stage_generate(cfg, out: Path, b: Bench, models: dict[str, str]) -> dict:
    st = Stage(out, f"{b.part}-generate")
    if st.done:
        return st.load()
    relay = RelayClient(cfg.relay_url, max_tokens=cfg.relay_max_tokens)
    jobs = [(f"{q['qid']}|{arm}|{tag}", (q, arm, alias)) for q in b.gold for arm in b.arms
            for alias, tag in models.items()]

    def one(x):
        q, arm, alias = x
        ex = effort(models[alias])
        c = relay.complete(alias, b.messages(arm, q), temperature=0.0, extra=ex)
        # reasoning_chars added 2026-11-15 (EXP-2026-11-010): counts replies whose
        # text arrived only in the reasoning channel. Additive; `raw` is unchanged.
        return {"raw": c.text[-6000:], "served_model": c.served_model, "finish_reason": c.finish_reason,
                "usage": c.usage, "latency_s": c.latency_s, "reasoning_chars": len(c.reasoning), **ex}

    res = st.map(jobs, one, workers=cfg.relay_concurrency * len(models))
    st.finish({"generations": res, "models": models})
    return st.load()


def stage_repair(cfg, out: Path, b: Bench, gen: dict) -> dict:
    st = Stage(out, f"{b.part}-repair")
    if st.done:
        return st.load()
    relay = RelayClient(cfg.relay_url, max_tokens=cfg.relay_max_tokens)
    golds = {q["qid"]: q for q in b.gold}
    alias_of = {tag: alias for alias, tag in gen["models"].items()}
    jobs = []
    for k, g in gen["generations"].items():
        qid, arm, tag = k.split("|")
        if arm != REPAIR_FROM or "error" in g:
            continue
        q = golds[qid]
        _, status, msg = _parse_validate(g["raw"], b.cards[q["graph"]])
        if status != "ok":
            jobs.append((f"{qid}|{REPAIR}|{tag}", (q, alias_of[tag], g["raw"], msg)))

    def one(x):
        q, alias, raw, msg = x
        m = b.messages(REPAIR_FROM, q) + [
            {"role": "assistant", "content": raw},
            {"role": "user", "content": f"That request is not valid: {msg}\nReply with a corrected request only, "
                                        "as JSON in one ```json fenced block."}]
        ex = effort(gen["models"][alias])
        c = relay.complete(alias, m, temperature=0.0, extra=ex)
        return {"raw": c.text[-6000:], "served_model": c.served_model, "finish_reason": c.finish_reason,
                "usage": c.usage, "repaired_from": msg, **ex}

    res = st.map(jobs, one, workers=cfg.relay_concurrency * len(gen["models"]))
    st.finish({"generations": res, "n_repaired": len(jobs)})
    return st.load()


def stage_execute(cfg, out: Path, b: Bench, gen: dict, rep: dict) -> dict:
    st = Stage(out, f"{b.part}-execute")
    if st.done:
        return st.load()
    golds = {q["qid"]: q for q in b.gold}
    items = dict(gen["generations"])
    for k, g in gen["generations"].items():
        qid, arm, tag = k.split("|")
        if arm == REPAIR_FROM:
            rk = f"{qid}|{REPAIR}|{tag}"
            items[rk] = rep["generations"].get(rk, g)

    def one(key: str) -> dict:
        qid, arm, _tag = key.split("|")
        q = golds[qid]
        g = items[key]
        want = {tuple(k): v for k, v in q["_gold_norm"]}
        drv, gc = b.clients(q["graph"])
        if "error" in g:
            return {"status": "generation_error", "detail": str(g["error"])[:200], "cypher_ok": False, "gremlin_ok": False}
        if arm.startswith("typed"):
            req, status, msg = _parse_validate(g["raw"], b.cards[q["graph"]])
            res: dict = {"request": req, "status": status, "repaired": "repaired_from" in g}
            if status != "ok":
                return {**res, "detail": msg, "cypher_ok": False, "gremlin_ok": False}
            card = b.cards[q["graph"]]
            plan = {"cypher": compile_cypher(req, card)}
            gr = compile_gremlin(req, card)
            plan["gremlin"] = gr.script
            res.update(cypher=plan["cypher"], gremlin=gr.script)
            for be in ("cypher", "gremlin"):
                t = time.time()
                try:
                    rows = run_cypher(drv, plan[be]) if be == "cypher" else finish(run_gremlin(gc, plan[be]), gr.post)
                    res[f"{be}_ok"] = dict(normalise(rows)) == want
                except Exception as exc:  # noqa: BLE001
                    res[f"{be}_ok"], res[f"{be}_err"] = False, f"{type(exc).__name__}: {exc}"[:300]
                res[f"{be}_s"] = round(time.time() - t, 3)
            return res
        query = extract_query(g["raw"])
        lang = arm.split("-")[0]
        if not query:
            return {"status": "empty", "correct": False}
        try:
            rows = run_cypher(drv, query) if lang == "cypher" else run_gremlin(gc, query)
        except PermissionError as exc:
            return {"status": "blocked", "correct": False, "detail": str(exc)[:200], "query": query[:2000]}
        except Exception as exc:  # noqa: BLE001
            kind = "timeout" if "timeout" in str(exc).lower() else "error"
            return {"status": kind, "correct": False, "detail": f"{type(exc).__name__}: {exc}"[:300], "query": query[:2000]}
        return {"status": "ok", "correct": dict(normalise(rows)) == want, "query": query[:2000]}

    r = st.map([(k, k) for k in items], one, workers=8)
    st.finish({"executions": r})
    return st.load()


def _free_a(tag: str) -> dict[str, dict[str, bool]]:
    d = FREE_RUNS.get(tag)
    out: dict[str, dict[str, bool]] = {}
    if d and (d / "execute.json").exists():
        for k, v in json.loads((d / "execute.json").read_text())["executions"].items():
            qid, arm, _a = k.split("|")
            out.setdefault(f"free-{arm}", {})[qid] = bool(v.get("correct"))
    v1 = BASE / "typed" / "execute.json"
    if v1.exists():
        for k, v in json.loads(v1.read_text())["executions"].items():
            qid, arm, t = k.split("|")
            if t == tag:
                for be in ("cypher", "gremlin"):
                    out.setdefault(f"{arm}-{be}", {})[qid] = bool(v.get(f"{be}_ok"))
    return out


def stage_score(cfg, out: Path, b: Bench, gen: dict, ex: dict) -> dict:
    st = Stage(out, f"{b.part}-score")
    if st.done:
        return st.load()
    qs = b.gold
    rng = random.Random(cfg.seed + 31)
    cat_of = ({q["qid"]: q["from_template"]["match_category"] for q in qs} if b.part == "A"
              else {q["qid"]: q["graph"] for q in qs})
    src_of = {q["qid"]: q.get("data_source", "cypherbench") for q in qs}
    res: dict = {"by_model": {}, "n": len(qs),
                 "served_models": dict(Counter(g.get("served_model") for g in gen["generations"].values()))}
    for alias, tag in gen["models"].items():
        vec: dict[str, list[int]] = {}
        block: dict = {"alias": alias, "arms": {}, "status": {}, "diffs": {}}
        arms_here = list(b.arms) + [REPAIR]
        for arm in arms_here:
            outs = [ex["executions"].get(f"{q['qid']}|{arm}|{tag}") or {"status": "missing"} for q in qs]
            block["status"][arm] = dict(Counter(o.get("status") for o in outs))
            if arm.startswith("typed"):
                block["status"][arm]["backends_agree"] = sum(o.get("cypher_ok") == o.get("gremlin_ok") for o in outs) / len(qs)
                names = [(f"{arm}-cypher", "cypher_ok"), (f"{arm}-gremlin", "gremlin_ok")]
            else:
                names = [(f"free-{arm}", "correct")]
            for name, fld in names:
                v = [int(bool(o.get(fld))) for o in outs]
                vec[name] = v
                block["arms"][name] = {
                    "exact_records": sum(v) / len(v),
                    "by_group": {c: round(sum(x for x, q in zip(v, qs) if cat_of[q["qid"]] == c)
                                          / max(1, sum(1 for q in qs if cat_of[q["qid"]] == c)), 4)
                                 for c in sorted(set(cat_of.values()))},
                    "by_source": {s: round(sum(x for x, q in zip(v, qs) if src_of[q["qid"]] == s)
                                           / max(1, sum(1 for q in qs if src_of[q["qid"]] == s)), 4)
                                  for s in sorted(set(src_of.values()))},
                }
        if b.part == "A" and EXPERIMENT == "exp005":
            for name, d in _free_a(tag).items():
                vec[name] = [int(d.get(q["qid"], False)) for q in qs]
                block["arms"][name] = {"exact_records": sum(vec[name]) / len(qs)}
        for v in ("typed3", "typed2") if EXPERIMENT == "exp006" else ("typed2",):
            for be in ("cypher", "gremlin"):
                t, f = vec.get(f"{v}-3shot-{be}"), vec.get(f"free-{be}-3shot")
                if EXPERIMENT == "exp006" and t and f:
                    for fa in ("cypher", "gremlin"):
                        f = vec.get(f"free-{fa}-3shot")
                        block["diffs"][f"{v}-3shot-{be}_minus_free-{fa}-3shot"] = {
                            "diff": (sum(t) - sum(f)) / len(qs), "ci95": _paired_ci(f, t, rng)}
        if EXPERIMENT == "exp006":
            for be in ("cypher", "gremlin"):
                t, v2 = vec.get(f"typed3-3shot-{be}"), vec.get(f"typed2-3shot-{be}")
                block["diffs"][f"typed3-3shot-{be}_minus_typed2-3shot-{be}"] = {
                    "diff": (sum(t) - sum(v2)) / len(qs), "ci95": _paired_ci(v2, t, rng)}
        for shots in ("0shot", "3shot") if EXPERIMENT == "exp005" else ():
            for be in ("cypher", "gremlin"):
                t = vec.get(f"typed2-{shots}-{be}")
                for fa in ("cypher", "gremlin"):
                    f = vec.get(f"free-{fa}-{shots}")
                    if t and f:
                        block["diffs"][f"typed2-{shots}-{be}_minus_free-{fa}-{shots}"] = {
                            "diff": (sum(t) - sum(f)) / len(qs), "ci95": _paired_ci(f, t, rng)}
                v1 = vec.get(f"typed-{shots}-{be}")
                if t and v1:
                    block["diffs"][f"typed2-{shots}-{be}_minus_typed-{shots}-{be}"] = {
                        "diff": (sum(t) - sum(v1)) / len(qs), "ci95": _paired_ci(v1, t, rng)}
        for be in ("cypher", "gremlin"):
            t, f = vec.get(f"{REPAIR}-{be}"), vec.get(f"free-{be}-3shot")
            if t and f:
                block["diffs"][f"{REPAIR}-{be}_minus_free-{be}-3shot"] = {
                    "diff": (sum(t) - sum(f)) / len(qs), "ci95": _paired_ci(f, t, rng)}
        res["by_model"][tag] = block
    st.finish(res)
    return st.load()


def main(argv: list[str] | None = None) -> int:
    from utils.config import load_env

    load_env()
    parts = (argv if argv is not None else sys.argv[1:]) or ["A", "B"]
    cfg = get()
    out = Path(os.environ.get("KILLTESTS_EXP005_OUT", OUT))
    out.mkdir(parents=True, exist_ok=True)
    relay = RelayClient(cfg.relay_url, max_tokens=cfg.relay_max_tokens)
    hp = out / "run_header.json"
    if hp.exists():
        hdr = json.loads(hp.read_text())
    else:
        hdr = {"started_at": time.time(), "identities": [identify(relay, a) for a in ("default-model", "default-model-2")],
               "concurrency_per_model": cfg.relay_concurrency, "max_tokens": cfg.relay_max_tokens}
        atomic_write_json(hp, hdr)
    models = {i["alias"]: i["model"] for i in hdr["identities"]}
    smoke = int(os.environ.get("KILLTESTS_EXP005_SMOKE", "0"))
    for part in parts:
        b = Bench(part)
        if smoke:
            b.gold = b.gold[:smoke]
        gen = stage_generate(cfg, out, b, models)
        rep = stage_repair(cfg, out, b, gen)
        ex = stage_execute(cfg, out, b, gen, rep)
        sc = stage_score(cfg, out, b, gen, ex)
        for tag, blk in sc["by_model"].items():
            print(part, tag, "  ".join(f"{k} {v['exact_records']:.3f}" for k, v in blk["arms"].items()), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
