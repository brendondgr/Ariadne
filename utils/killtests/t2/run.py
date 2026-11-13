"""T2 stages: candidates -> decide -> execute -> score.

Each stage is resumable and writes ``<out_dir>/t2/<stage>.json``. The decider
is the only model touched, and only by ``t2-decide``; T2-raw and the gold use
no model at all (asserted in tests by counting sockets to :9090 and :7500).
"""

from __future__ import annotations

import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .. import banks, candidates
from ..config import KillTestConfig
from ..decider import NONE_KEY, DeciderClient, keyed
from ..graph import DESCRIBE, GraphExecutor, facet_key, parse_facet
from ..stages import Stage
from . import interpretations as I

# --------------------------------------------------------------------------- items


def items(cfg: KillTestConfig) -> list[banks.Item]:
    its = banks.all_items()
    if cfg.smoke:
        rng = random.Random(cfg.seed)
        by_split: dict[str, list] = defaultdict(list)
        for it in its:
            by_split[(it.split, it.tier)].append(it)
        its = [x for k in sorted(by_split) for x in rng.sample(by_split[k], min(2, len(by_split[k])))]
    return its


# ---------------------------------------------------------------------- candidates


def stage_candidates(cfg: KillTestConfig, out: Path) -> dict:
    st = Stage(out / "t2", "candidates")
    if st.done:
        return st.load()
    its = items(cfg)
    res = st.map([(it.key, it) for it in its],
                 lambda it: candidates.anchor_candidates(it.question, cfg.t2_top_anchors), workers=8)
    result = {"items": {it.key: it.to_dict() for it in its}, "candidates": res}
    st.finish(result)
    return result


# -------------------------------------------------------------------------- decide


def _decide_one(dec: DeciderClient, question: str, cands: list[dict], floor: float, *, anchors_only: bool = False) -> dict:
    if not cands:
        return {"anchor_p": {}, "none_p": 1.0, "facet_p": {}}
    descs = [I.entity_option(c, (candidates.entity(c["entity_id"]) or candidates.Entity("", "", "", "", "")).description)
             for c in cands]
    options, keys = keyed(descs, none_option="none of these entities: the question is about something else")
    ch = dec.choose(f"Question: {question}", "Which entity is this question about?", options)
    anchor_p = {c["entity_id"]: ch.probabilities.get(k, 0.0) for c, k in zip(cands, keys)}
    none_p = ch.probabilities.get(NONE_KEY, 0.0)
    if anchors_only:
        return {"anchor_p": anchor_p, "none_p": none_p, "facet_p": {}, "temperature": ch.temperature}
    top = max(anchor_p, key=anchor_p.get)
    labels = {}
    for c in cands:
        if anchor_p[c["entity_id"]] >= floor or c["entity_id"] == top:
            labels[(c["dataset"], c["label"])] = c
    facet_p: dict[str, dict[str, float]] = {}
    for (ds, label), c in sorted(labels.items()):
        fs = list(I.facets_for(ds, label))
        fdescs = [I.facet_description(ds, label, f) for f in fs]
        fopts, fkeys = keyed(fdescs)
        fch = dec.choose(
            f"Question: {question}\nThe question is about the {label} '{c['name']}'.",
            f"What does the question ask for about this {label}?", fopts)
        facet_p[f"{ds}|{label}"] = {f: fch.probabilities.get(k, 0.0) for f, k in zip(fs, fkeys)}
    return {"anchor_p": anchor_p, "none_p": none_p, "facet_p": facet_p, "temperature": ch.temperature}


def stage_decide(cfg: KillTestConfig, out: Path, cand: dict) -> dict:
    st = Stage(out / "t2", "decide")
    if st.done:
        return st.load()
    dec = DeciderClient(cfg.decider_url)
    pairs = [(k, (cand["items"][k]["question"], v)) for k, v in cand["candidates"].items()]
    res = st.map(pairs, lambda x: _decide_one(dec, x[0], x[1], cfg.t2_filter_floor), workers=16)
    st.finish({"decisions": res, "floor": cfg.t2_filter_floor})
    return st.load()


# ------------------------------------------------------------------ interpretations


def _cap(interps: list[tuple[str, str]], cap: int) -> tuple[list[tuple[str, str]], bool]:
    return (interps[:cap], len(interps) > cap)


def build_interpretations(item: dict, cands: list[dict], dec: dict, floor: float, cap: int) -> dict:
    q = item["question"]
    by_id = {c["entity_id"]: c for c in cands}
    # raw
    raw = [(c["entity_id"], f) for c in cands for f in I.raw_facets(q, c["dataset"], c["label"])]
    raw, raw_capped = _cap(raw, cap)
    guess_raw = []
    if cands:
        c0 = cands[0]
        sup = [f for f in I.facets_for(c0["dataset"], c0["label"]) if I.lexically_supported(q, f)]
        guess_raw = [(c0["entity_id"], sup[0] if sup else DESCRIBE)]
    # filtered
    filt, guess_f = [], []
    ap = dec.get("anchor_p") or {}
    if ap:
        ranked = sorted(ap, key=lambda a: -ap[a])
        for a in ranked:
            if ap[a] < floor:
                continue
            c = by_id[a]
            fp = dec["facet_p"].get(f"{c['dataset']}|{c['label']}", {})
            for f in sorted(fp, key=lambda f: -fp[f]):
                if fp[f] >= floor:
                    filt.append((a, f))
        top = ranked[0]
        if ap[top] >= dec.get("none_p", 0.0):
            c = by_id[top]
            fp = dec["facet_p"].get(f"{c['dataset']}|{c['label']}", {})
            if fp:
                guess_f = [(top, max(fp, key=fp.get))]
    filt, filt_capped = _cap(filt, cap)
    return {"raw": raw, "raw_capped": raw_capped, "filtered": filt, "filtered_capped": filt_capped,
            "guess_raw": guess_raw, "guess_filtered": guess_f}


# ------------------------------------------------------------------------ execute


def gold_facets(item: dict, gx: GraphExecutor | None = None) -> dict:
    """The gold interpretation: facets grouped by direction.

    - An anchor in no store (an invented or deprecated id) makes the item a
      negative: the right behaviour is to abstain.
    - Within one direction the gold answer is the union over the gold target
      labels ("techniques" = Technique + SubTechnique). Two directions (a
      self-relation like ChildOf) are alternatives, settled by the reference
      run's ids when they can be.
    - ``relation_by``: "slot" when the slot gold names a real facet;
      "relation" when only the relation matches (the target is named as the
      other store calls it); "unresolved" otherwise (the reference fallback in
      ``_exec_item`` may still resolve it).
    """
    if item["gold_anchor"] is None:
        return {"by_dir": {}, "resolved": True, "negative": True}
    e = candidates.entity(item["gold_anchor"])
    if e is None:
        return {"by_dir": {}, "resolved": True, "negative": True, "why": "gold anchor in no store"}
    base = {"label": e.label, "dataset": e.dataset, "negative": False}
    if not item["gold_relation"]:
        return {**base, "by_dir": {"describe": [DESCRIBE]}, "resolved": True, "relation_by": "describe"}
    rel_fs = [f for f in I.facets_for(e.dataset, e.label) if f != DESCRIBE
              and parse_facet(f)[0] == item["gold_relation"]]
    fs = [f for f in rel_fs if not item["gold_target_labels"] or parse_facet(f)[2] in item["gold_target_labels"]]
    by = "slot"
    if not fs and rel_fs:
        fs, by = rel_fs, "relation"
    if not fs:
        return {**base, "by_dir": {}, "resolved": False, "relation_by": "unresolved",
                "why": "slot gold relation has no facet for the anchor label"}
    by_dir: dict[str, list[str]] = defaultdict(list)
    for f in fs:
        by_dir[parse_facet(f)[1]].append(f)
    return {**base, "by_dir": dict(by_dir), "resolved": True, "relation_by": by}


def _exec_item(gx: GraphExecutor, item: dict, cands: list[dict], interps: dict, reference_ids: list[str]) -> dict:
    ents = {c["entity_id"]: c for c in cands}
    needed: set[tuple[str, str]] = set()
    for k in ("raw", "filtered", "guess_raw", "guess_filtered"):
        needed.update(tuple(x) for x in interps[k])
    recs: dict[str, list[str]] = {}
    for a, f in sorted(needed):
        c = ents[a]
        recs[f"{a}#{f}"] = list(gx.records(c["dataset"], a, c["label"], f))
    g = gold_facets(item, gx)
    ref = set(reference_ids)
    if not g["resolved"] and not g["negative"] and ref:
        # Reference fallback: the anchor facet whose records best match the
        # recorded reference answer, accepted only at Jaccard >= 0.5.
        best, best_j = None, 0.0
        for f in I.facets_for(g["dataset"], g["label"]):
            if f == DESCRIBE:
                continue
            r = set(gx.records(g["dataset"], item["gold_anchor"], g["label"], f))
            j = len(r & ref) / len(r | ref) if (r | ref) else 0.0
            if j > best_j:
                best, best_j = f, j
        if best and best_j >= 0.5:
            g = {**g, "by_dir": {parse_facet(best)[1]: [best]}, "resolved": True,
                 "relation_by": f"reference (jaccard {best_j:.2f})"}
    answers: dict[str, list[str]] = {}
    for d, fs in g.get("by_dir", {}).items():
        u: set[str] = set()
        for f in fs:
            u.update(gx.records(g["dataset"], item["gold_anchor"], g["label"], f))
        answers[d] = sorted(u)
    if len(answers) > 1 and ref:
        overlap = {d: len(ref & set(v)) for d, v in answers.items()}
        top = max(overlap.values())
        if top > 0:
            answers = {d: v for d, v in answers.items() if overlap[d] == top}
            g = {**g, "by_dir": {d: g["by_dir"][d] for d in answers}}
    return {"records": recs, "gold": {**g, "answers": answers}}


def stage_execute(cfg: KillTestConfig, out: Path, cand: dict, dec: dict) -> dict:
    st = Stage(out / "t2", "execute")
    if st.done:
        return st.load()
    gx = GraphExecutor()
    ref_ids = {it.key: list(it.reference_ids) for it in banks.all_items()}

    def one(key: str) -> dict:
        item = cand["items"][key]
        cands = cand["candidates"][key]
        d = dec["decisions"].get(key) or {}
        if "error" in d:
            raise RuntimeError(f"decide failed: {d['error']}")
        interps = build_interpretations(item, cands, d, cfg.t2_filter_floor, cfg.t2_max_interpretations)
        return {"interps": interps, **_exec_item(gx, item, cands, interps, ref_ids.get(key, []))}

    res = st.map([(k, k) for k in cand["items"]], one, workers=8)
    st.finish({"executed": res, "graph_calls": gx.calls})
    return st.load()


# -------------------------------------------------------------------------- score

POLICIES = ("raw", "filtered")


def gate(records: dict[str, list[str]], interps: list) -> dict:
    groups: dict[tuple, list[str]] = defaultdict(list)
    for a, f in interps:
        r = tuple(records[f"{a}#{f}"])
        if r:
            groups[r].append(f"{a}#{f}")
    if not groups:
        return {"decision": "abstain", "groups": 0, "answer": None}
    if len(groups) == 1:
        ((ans, members),) = groups.items()
        return {"decision": "answer", "groups": 1, "answer": list(ans), "members": members}
    return {"decision": "ask", "groups": len(groups), "answer": None}


def guess(records: dict[str, list[str]], interps: list) -> dict:
    if not interps:
        return {"decision": "abstain", "answer": None}
    a, f = interps[0]
    r = records[f"{a}#{f}"]
    return {"decision": "answer", "answer": list(r)} if r else {"decision": "abstain", "answer": None}


def score_item(item: dict, ex: dict) -> dict:
    recs, interps, gold = ex["records"], ex["interps"], ex["gold"]
    gold_keys = {f"{item['gold_anchor']}#{f}" for fs in gold.get("by_dir", {}).values() for f in fs}
    gold_answers = [tuple(v) for v in gold.get("answers", {}).values()]
    out = {"tier": item["tier"], "split": item["split"], "negative": gold.get("negative", False),
           "gold_resolved": gold.get("resolved", False), "relation_by": gold.get("relation_by"),
           "multi_target": any(len(fs) > 1 for fs in gold.get("by_dir", {}).values())}
    for name in POLICIES:
        ints = [tuple(x) for x in interps[name]]
        g = gate(recs, ints)
        present = any(f"{a}#{f}" in gold_keys for a, f in ints)
        correct = g["decision"] == "answer" and tuple(g["answer"]) in gold_answers
        out[name] = {"decision": g["decision"], "groups": g["groups"], "n_interps": len(ints),
                     "gold_present": present, "correct": correct,
                     "capped": interps.get(f"{name}_capped", False)}
    for name, key in (("guess_raw", "guess_raw"), ("guess_filtered", "guess_filtered")):
        g = guess(recs, [tuple(x) for x in interps[key]])
        out[name] = {"decision": g["decision"],
                     "correct": g["decision"] == "answer" and tuple(g["answer"]) in gold_answers}
    return out


def summarise(scored: dict[str, dict], split: str) -> dict:
    rows = [r for r in scored.values() if r["split"] == split]
    pos = [r for r in rows if not r["negative"] and r["gold_resolved"]]
    neg = [r for r in rows if r["negative"]]
    res: dict[str, Any] = {"n_positive": len(pos), "n_negative": len(neg),
                           "n_gold_unresolved": sum(1 for r in rows if not r["negative"] and not r["gold_resolved"])}
    for pol in (*POLICIES, "guess_raw", "guess_filtered"):
        d = Counter(r[pol]["decision"] for r in pos)
        m = {
            "answer_rate": d["answer"] / len(pos) if pos else None,
            "ask_rate": d["ask"] / len(pos) if pos else None,
            "abstain_rate": d["abstain"] / len(pos) if pos else None,
            "answer_exact": sum(r[pol]["correct"] for r in pos) / len(pos) if pos else None,
            "confident_wrong": sum(1 for r in pos if r[pol]["decision"] == "answer" and not r[pol]["correct"])
            + sum(1 for r in neg if r[pol]["decision"] == "answer"),
            "t6_answered": (sum(1 for r in neg if r[pol]["decision"] == "answer") / len(neg)) if neg else None,
        }
        if pol in POLICIES:
            m["gold_pruned_rate"] = sum(1 for r in pos if not r[pol]["gold_present"]) / len(pos) if pos else None
            m["mean_interps"] = sum(r[pol]["n_interps"] for r in pos) / len(pos) if pos else None
            m["capped"] = sum(1 for r in rows if r[pol]["capped"])
        by_tier = {}
        for t in sorted({r["tier"] for r in pos}):
            tp = [r for r in pos if r["tier"] == t]
            by_tier[t] = {"n": len(tp),
                          "ask_rate": sum(r[pol]["decision"] == "ask" for r in tp) / len(tp),
                          "answer_exact": sum(r[pol]["correct"] for r in tp) / len(tp)}
            if pol in POLICIES:
                by_tier[t]["gold_pruned_rate"] = sum(not r[pol]["gold_present"] for r in tp) / len(tp)
        m["by_tier"] = by_tier
        res[pol] = m
    res["n_multi_target"] = sum(1 for r in pos if r.get("multi_target"))
    res["relation_by"] = dict(Counter(r.get("relation_by") for r in pos))
    return res


def stage_score(cfg: KillTestConfig, out: Path, cand: dict, ex: dict) -> dict:
    st = Stage(out / "t2", "score")
    if st.done:
        return st.load()
    scored = {}
    errors = {}
    for k, item in cand["items"].items():
        e = ex["executed"].get(k)
        if not e or "error" in e:
            errors[k] = (e or {}).get("error", "missing")
            continue
        scored[k] = score_item(item, e)
    result = {"per_item": scored, "errors": errors,
              "summary": {s: summarise(scored, s) for s in ("dev", "confirm")}}
    st.finish(result)
    return result


def run(cfg: KillTestConfig, out: Path) -> dict:
    cand = stage_candidates(cfg, out)
    dec = stage_decide(cfg, out, cand)
    ex = stage_execute(cfg, out, cand, dec)
    return stage_score(cfg, out, cand, ex)
