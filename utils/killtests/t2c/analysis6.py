"""EXP-2026-11-006: kill rule (part C), B1 and A1, plus the exploratory checks.

    KILLTESTS_EXPERIMENT=exp006 uv run python -m utils.killtests.t2c.analysis6

Pre-registered: the part-C kill rule (H1–H3), B1 (typed3 >= typed2 + 0.10 on part B) and A1
(typed3 >= typed2 - 0.02 on part A). Everything else is exploratory and post hoc:

- **lenient rescoring** of parts B and C (the EXP-2026-11-005 ``strict`` / ``set`` / ``set_proj``
  rules, applied identically to every arm; typed requests scored on their Cypher compilation);
- **where typed misses come from** on part C: replies cut off at the token cap, invalid requests,
  and valid requests that return the wrong rows, the last split by whether the gold uses a
  feature v3 has no operator for (``analysis.features``) or returns more than one aggregate;
- **inside coverage**: accuracy on the questions where the typed reply was a valid request,
  beside free Cypher on the same questions.
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from ..stages import atomic_write_json
from ..t1.execute import run_cypher, run_gremlin
from .analysis import features
from .run import OUT, REPAIR, Bench
from .sensitivity import rows_of, score

assert os.environ.get("KILLTESTS_EXPERIMENT") == "exp006", "set KILLTESTS_EXPERIMENT=exp006"

from ..config import REPO  # noqa: E402

EXP = REPO / "docs/research/experiments/EXP-2026-11-006-typed-v3-three-benchmarks"
ARMS = ("cypher-3shot", "gremlin-3shot", "typed2-3shot", "typed3-3shot", REPAIR)
#: EXP-2026-11-005 part A, Qwen at the server default reasoning_effort=xhigh (A2 comparison).
QWEN_XHIGH_A = {"free-cypher-3shot": 0.905, "free-gremlin-3shot": 0.655, "typed2-3shot-cypher": 0.905}
_AGG = re.compile(r"\b(count|sum|avg|min|max|collect)\s*\(", re.I)


def load(part: str, what: str) -> dict:
    return json.loads((OUT / f"{part}-{what}.json").read_text())


def er(arms: dict, k: str) -> float:
    return arms[k]["exact_records"]


def verdict_c(sc: dict) -> dict:
    per = {}
    for tag, b in sc["by_model"].items():
        a, d = b["arms"], b["diffs"]
        tc, tg = er(a, "typed3-3shot-cypher"), er(a, "typed3-3shot-gremlin")
        fc, fg = er(a, "free-cypher-3shot"), er(a, "free-gremlin-3shot")
        per[tag] = {
            "typed3_3shot_cypher": tc, "typed3_3shot_gremlin": tg,
            "free_cypher_3shot": fc, "free_gremlin_3shot": fg,
            "H1_backend_independent": abs(tc - tg) <= 0.02 + 1e-9,
            "H2_beats_free_gremlin": tg - fg >= 0.10 - 1e-9,
            "H3_not_worse_than_free_cypher": tc >= fc - 0.05 - 1e-9,
            "ci_typed3_gremlin_minus_free_gremlin": d["typed3-3shot-gremlin_minus_free-gremlin-3shot"]["ci95"],
            "ci_typed3_cypher_minus_free_cypher": d["typed3-3shot-cypher_minus_free-cypher-3shot"]["ci95"],
            "typed2": {k: er(a, f"typed2-3shot-{k}") for k in ("cypher", "gremlin")},
            "repair": {k: er(a, f"{REPAIR}-{k}") for k in ("cypher", "gremlin")},
        }
    killed = any(not v["H2_beats_free_gremlin"] for v in per.values()) or \
        all(not v["H3_not_worse_than_free_cypher"] for v in per.values())
    return {"rule": "killed if H2 fails for any model or H3 fails for every model (3-shot); H1 reported",
            "inputs": per, "verdict": "killed" if killed else "survives",
            "H1_holds_all": all(v["H1_backend_independent"] for v in per.values())}


def expectations(a: dict, b: dict) -> dict:
    out = {"B": {}, "A": {}}
    for tag, blk in b["by_model"].items():
        x = blk["arms"]
        t3, t2 = er(x, "typed3-3shot-cypher"), er(x, "typed2-3shot-cypher")
        tg, fg, fc = er(x, "typed3-3shot-gremlin"), er(x, "free-gremlin-3shot"), er(x, "free-cypher-3shot")
        out["B"][tag] = {"typed3": t3, "typed2": t2, "B1_typed3_ge_typed2_plus_010": t3 - t2 >= 0.10 - 1e-9,
                         "ci_typed3_minus_typed2": blk["diffs"]["typed3-3shot-cypher_minus_typed2-3shot-cypher"]["ci95"],
                         "free_cypher": fc, "free_gremlin": fg, "typed3_gremlin": tg,
                         "B2_H2": tg - fg >= 0.10 - 1e-9, "B2_H3": t3 >= fc - 0.05 - 1e-9}
    for tag, blk in a["by_model"].items():
        x = blk["arms"]
        t3, t2 = er(x, "typed3-3shot-cypher"), er(x, "typed2-3shot-cypher")
        row = {"typed3": t3, "typed2": t2, "A1_typed3_ge_typed2_minus_002": t3 >= t2 - 0.02 - 1e-9,
               "free_cypher": er(x, "free-cypher-3shot"), "free_gremlin": er(x, "free-gremlin-3shot"),
               "backends_agree_typed3": blk["status"]["typed3-3shot"]["backends_agree"]}
        if tag.startswith("qwen"):
            row["A2_qwen_xhigh_exp005"] = QWEN_XHIGH_A
        out["A"][tag] = row
    return out


def rescore(part: str) -> tuple[dict, dict]:
    """Re-execute every saved query of ``part`` and score it strict / set / set_proj."""
    from utils.config import load_env

    load_env()
    b = Bench(part)
    gold = {q["qid"]: q for q in b.gold}
    ex = load(part, "execute")["executions"]
    tags = sorted({k.split("|")[2] for k in ex})
    gold_rows = {qid: rows_of(run_cypher(b.clients(q["graph"])[0], q["gold_cypher"])) for qid, q in gold.items()}
    none = {"strict": False, "set": False, "set_proj": False}

    def one(key: str):
        qid, arm, _ = key.split("|")
        e, q = ex[key], gold[qid]
        drv, gc = b.clients(q["graph"])
        if arm.startswith("typed"):
            query, lang = e.get("cypher"), "cypher"
        else:
            query, lang = e.get("query"), arm.split("-")[0]
        if not query or e.get("status") != "ok":
            return key, none
        try:
            raw = run_cypher(drv, query) if lang == "cypher" else run_gremlin(gc, query)
        except Exception:  # noqa: BLE001
            return key, none
        return key, score(rows_of(raw), gold_rows[qid])

    keys = [k for k in ex if k.split("|")[1] in ARMS]
    with ThreadPoolExecutor(8) as pool:
        res = dict(pool.map(one, keys))
    out = {}
    for tag in tags:
        blk = {}
        for arm in ARMS:
            ks = [f"{qid}|{arm}|{tag}" for qid in gold]
            blk[arm] = {m: round(sum(res[k][m] for k in ks) / len(ks), 4) for m in ("strict", "set", "set_proj")}
            orig = sum(bool(ex[k].get("cypher_ok") if arm.startswith("typed") else ex[k].get("correct")) for k in ks)
            blk[arm]["strict_matches_preregistered"] = orig == sum(res[k]["strict"] for k in ks)
        out[tag] = blk
    return out, res


def miss_sources(part: str, lenient: dict) -> dict:
    """Where typed3 (3-shot, Cypher backend) loses to free Cypher, by question."""
    b = Bench(part)
    gold = {q["qid"]: q for q in b.gold}
    ex = load(part, "execute")["executions"]
    gen = load(part, "generate")["generations"]
    out = {}
    for tag in sorted({k.split("|")[2] for k in ex}):
        c, feats, inside = Counter(), Counter(), Counter()
        for qid, q in gold.items():
            k, kf = f"{qid}|typed3-3shot|{tag}", f"{qid}|cypher-3shot|{tag}"
            t, fc = ex[k], bool(ex[kf].get("correct"))
            if t["status"] == "ok":
                inside["n"] += 1
                inside["typed3_right"] += bool(t.get("cypher_ok"))
                inside["free_cypher_right"] += fc
            if not fc or t.get("cypher_ok"):
                continue
            if t["status"] == "unparseable":
                c["cut_off_at_cap" if gen[k].get("finish_reason") == "length" else "unparseable_other"] += 1
            elif t["status"] == "invalid":
                c["invalid_request"] += 1
            else:
                f = features(q["gold_cypher"])
                multi = len(_AGG.findall(q["gold_cypher"])) >= 2
                if lenient.get(k, {}).get("set_proj"):
                    c["valid_right_rows_other_columns"] += 1
                elif f or multi:
                    c["valid_wrong_gold_uses_gap_feature"] += 1
                    feats.update(f)
                else:
                    c["valid_wrong_no_gap_feature"] += 1
        out[tag] = {"typed3_missed_free_cypher_right": sum(c.values()), "sources": dict(c),
                    "gap_features": dict(feats.most_common()),
                    "inside_coverage": {**inside, "typed3_acc": round(inside["typed3_right"] / max(inside["n"], 1), 3),
                                        "free_cypher_acc_same_questions": round(inside["free_cypher_right"] / max(inside["n"], 1), 3)}}
    n = len(gold)
    out["benchmark"] = {"n": n, "gold_uses_gap_feature_or_several_aggregates": sum(
        bool(features(q["gold_cypher"]) or len(_AGG.findall(q["gold_cypher"])) >= 2) for q in gold.values())}
    return out


def main() -> int:
    a, b, c = (load(p, "score") for p in "ABC")
    vc, exp = verdict_c(c), expectations(a, b)
    data = EXP / "data"
    data.mkdir(parents=True, exist_ok=True)
    sens, misses = {}, {}
    for part in "BC":
        s, per_key = rescore(part)
        sens[part] = s
        atomic_write_json(OUT / f"{part}-sensitivity-per-key.json", per_key)
        misses[part] = miss_sources(part, per_key)

    summary = {}
    for part, sc in (("A", a), ("B", b), ("C", c)):
        for tag, blk in sc["by_model"].items():
            t = tag.replace("-", "_").replace(".", "")
            arms, diffs = blk["arms"], blk["diffs"]
            for arm, name in (("typed3-3shot-cypher", "typed3_3shot"), ("typed2-3shot-cypher", "typed2_3shot"),
                              ("free-cypher-3shot", "free_cypher_3shot"), ("free-gremlin-3shot", "free_gremlin_3shot")):
                summary[f"{part}_exact_records_{name}_{t}"] = round(arms[arm]["exact_records"], 3)
            summary[f"{part}_typed3_3shot_gremlin_minus_free_gremlin_3shot_{t}"] = round(
                diffs["typed3-3shot-gremlin_minus_free-gremlin-3shot"]["diff"], 3)
            summary[f"{part}_typed3_3shot_cypher_minus_free_cypher_3shot_{t}"] = round(
                diffs["typed3-3shot-cypher_minus_free-cypher-3shot"]["diff"], 3)
    summary["C_typed3_3shot_gremlin_minus_free_gremlin_3shot_min"] = min(
        v for k, v in summary.items() if k.startswith("C_typed3_3shot_gremlin_minus"))
    for part, sc in (("A", a), ("B", b), ("C", c)):
        summary[f"{part}_backends_agree_typed3"] = round(min(
            blk["status"][x]["backends_agree"] for blk in sc["by_model"].values() for x in blk["status"]
            if x.startswith("typed3")), 4)
    ann = data / "expressibility-sample.json"  # written by hand after the run (post hoc)
    if ann.exists():
        j = json.loads(ann.read_text())
        summary["C_expressible_share_sample"] = round(len(j["expressible"]) / j["n"], 3)
    for part in "BC":
        for tag, blk in sens[part].items():
            t = tag.replace("-", "_").replace(".", "")
            for arm, name in (("typed3-3shot", "typed3_3shot"), ("cypher-3shot", "free_cypher_3shot"),
                              ("gremlin-3shot", "free_gremlin_3shot")):
                summary[f"{part}_set_proj_{name}_{t}"] = blk[arm]["set_proj"]
    atomic_write_json(data / "metrics.json", {"summary": summary, "A": a, "B": b, "C": c})
    atomic_write_json(data / "killrule.json", {"C": vc, **exp})
    atomic_write_json(data / "sensitivity.json", {"note": __doc__.split("\n\n")[2], "by_part": sens})
    atomic_write_json(data / "miss-sources.json", misses)
    print(json.dumps({"C": vc, **exp, "sensitivity": sens, "misses": misses}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
