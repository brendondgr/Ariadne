"""T3 stages: entities -> reword -> questions -> score -> evaluate.

Real questions are scored by T2's ``candidates`` and ``decide`` stages (the same
candidate construction and the same decider prompt), so T3 runs after T2's
``decide``. Synthetic questions go through the identical scorer here.
"""

from __future__ import annotations

import math
import random
import re
import statistics
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

from .. import candidates
from ..config import KillTestConfig
from ..graph import GraphExecutor
from ..relay import RelayClient
from ..stages import Stage
from ..t2.run import _decide_one
from . import calibrate as C
from . import generate as G

_WORD = re.compile(r"[a-z0-9]+")
_STOP = set("""the a an of to in on for and or is are was were be by with what which who whom how
does do did list show give me tell about this that these those its it any every all from into via
there their them can could would should catalogue entry entries record records entity entities
related linked associated connected through items item details detail overview know need""".split())

# ------------------------------------------------------------------ distance


@lru_cache(maxsize=1)
def vocabulary() -> frozenset[str]:
    v: set[str] = set()
    for ds in candidates.DATASETS:
        for e in candidates.entities(ds).values():
            v.update(_WORD.findall(e.name.lower()))
            v.update(_WORD.findall(e.entity_id.lower()))
        for al in G.aliases(ds).values():
            for a in al:
                v.update(_WORD.findall(a.lower()))
    return frozenset(v)


def distance(text: str) -> float:
    toks = [t for t in _WORD.findall((text or "").lower()) if len(t) >= 3 and t not in _STOP]
    if not toks:
        return 0.0
    voc = vocabulary()
    return sum(1 for t in toks if t not in voc) / len(toks)


# ------------------------------------------------------------------- stages


def stage_entities(cfg: KillTestConfig, out: Path) -> dict:
    st = Stage(out / "t3", "entities")
    if st.done:
        return st.load()
    deg = G.degrees(GraphExecutor())
    ents = G.sample_entities(cfg.t3_entities, cfg.seed, deg)
    st.finish({"entities": [{"entity_id": e.entity_id, "dataset": e.dataset, "label": e.label,
                             "name": e.name, "degree": deg.get(e.entity_id, 0)} for e in ents],
               "by_label": dict(Counter(e.label for e in ents))})
    return st.load()


def stage_reword(cfg: KillTestConfig, out: Path, ents: dict) -> dict:
    st = Stage(out / "t3", "reword")
    if st.done:
        return st.load()
    relay = RelayClient(cfg.relay_url, max_tokens=cfg.relay_max_tokens)
    alias = cfg.relay_models[0]
    jobs = []
    for e in ents["entities"]:
        for tier in ("paraphrase", "description"):
            jobs.append((f"{e['entity_id']}|{tier}", (e["entity_id"], tier)))

    def one(x):
        eid, tier = x
        return G.reword(relay, alias, candidates.entity(eid), tier)

    res = st.map(jobs, one, workers=cfg.relay_concurrency)
    st.finish({"rewordings": res, "alias": alias})
    return st.load()


def stage_questions(cfg: KillTestConfig, out: Path, ents: dict, rw: dict) -> dict:
    st = Stage(out / "t3", "questions")
    if st.done:
        return st.load()
    rng = random.Random(cfg.seed + 3)
    qs, dropped = {}, Counter()
    for e in ents["entities"]:
        ent = candidates.entity(e["entity_id"])
        refs = {"id": ent.entity_id, "name": ent.name}
        for tier in ("paraphrase", "description"):
            r = rw["rewordings"].get(f"{ent.entity_id}|{tier}") or {}
            if r.get("ok") and r.get("text"):
                refs[tier] = r["text"]
            else:
                dropped[tier] += 1
        for tier, ref in refs.items():
            q = G.frame(rng, ent, ref)
            qs[f"{ent.entity_id}|{tier}"] = {"question": q, "gold": ent.entity_id, "tier": tier,
                                            "label": ent.label, "distance": distance(q)}
    st.finish({"questions": qs, "dropped": dict(dropped)})
    return st.load()


def stage_score(cfg: KillTestConfig, out: Path, qs: dict) -> dict:
    st = Stage(out / "t3", "score")
    if st.done:
        return st.load()
    from ..decider import DeciderClient

    dec = DeciderClient(cfg.decider_url)

    def one(q):
        cands = candidates.anchor_candidates(q["question"], cfg.t2_top_anchors)
        d = _decide_one(dec, q["question"], cands, 1.0, anchors_only=True)
        return {"anchor_p": d.get("anchor_p", {}), "none_p": d.get("none_p"),
                "candidates": [c["entity_id"] for c in cands]}

    res = st.map(list(qs["questions"].items()), one, workers=16)
    st.finish({"scores": res})
    return st.load()


# ------------------------------------------------------------------ evaluate


NONE = "none"


def _probs(anchor_p: dict, none_p: float | None) -> dict:
    """The decider's distribution over the full label space: candidates + none."""
    return {**anchor_p, NONE: float(none_p or 0.0)}


def _gold(anchor_p: dict, gold: str) -> str:
    """The right label: the gold entity if it is a candidate, else "none of these"."""
    return gold if gold in anchor_p else NONE


def _row(key: str, probs: dict, gold: str, **extra) -> dict:
    g = _gold({k: v for k, v in probs.items() if k != NONE}, gold)
    return {"key": key, "probs": probs, "gold": g, "gold_entity": gold, "s": 1.0 - probs.get(g, 0.0), **extra}


def _rows_synth(qs: dict, sc: dict) -> list[dict]:
    rows = []
    for k, q in qs["questions"].items():
        s = sc["scores"].get(k)
        if not s or "error" in s:
            continue
        rows.append(_row(k, _probs(s["anchor_p"], s.get("none_p")), q["gold"],
                         tier=q["tier"], distance=q["distance"]))
    return rows


def _rows_real(t2_cand: dict, t2_dec: dict) -> list[dict]:
    rows = []
    for k, item in t2_cand["items"].items():
        if item["tier"] == "T6" or not item["gold_anchor"] or candidates.entity(item["gold_anchor"]) is None:
            continue
        d = t2_dec["decisions"].get(k)
        if not d or "error" in d:
            continue
        rows.append(_row(k, _probs(d.get("anchor_p") or {}, d.get("none_p")), item["gold_anchor"],
                         tier=item["tier"], split=item["split"], distance=distance(item["question"])))
    return rows


def _stratum(d: float, cuts: tuple[float, float]) -> int:
    return 0 if d <= cuts[0] else (1 if d <= cuts[1] else 2)


def _eval(rows: list[dict], q_of) -> dict:
    if not rows:
        return {"n": 0}
    mis = [r["s"] > q_of(r) for r in rows]
    sets = [C.prediction_set(r["probs"], q_of(r)) for r in rows]
    answered = [(r, s) for r, s in zip(rows, sets) if len(s) == 1 and s[0] != NONE]
    full = [len(s) == len(r["probs"]) for r, s in zip(rows, sets)]
    return {
        "n": len(rows),
        "miscoverage": sum(mis) / len(rows),
        "answer_rate": len(answered) / len(rows),
        "abstain_rate": sum(1 for s in sets if s == [NONE]) / len(rows),
        "selective_error": (sum(1 for r, s in answered if s[0] != r["gold_entity"]) / len(answered)) if answered else None,
        "mean_set_size": sum(len(s) for s in sets) / len(rows),
        "full_set_rate": sum(full) / len(rows),
        "gold_absent_rate": sum(1 for r in rows if r["gold"] == NONE) / len(rows),
    }


def _boot(rows: list[dict], q_of, rng: random.Random, n: int = 2000) -> list[float]:
    if not rows:
        return [None, None]
    flags = [r["s"] > q_of(r) for r in rows]
    vals = sorted(sum(flags[rng.randrange(len(flags))] for _ in flags) / len(flags) for _ in range(n))
    return [vals[int(0.025 * n)], vals[int(0.975 * n) - 1]]


def evaluate(cfg: KillTestConfig, synth: list[dict], real: list[dict]) -> dict:
    a = cfg.t3_alpha
    rng = random.Random(cfg.seed + 7)
    ds = sorted(r["distance"] for r in synth)
    cuts = (ds[len(ds) // 3], ds[2 * len(ds) // 3]) if ds else (0.0, 0.0)
    # 30 real labels, drawn from the development bank only; excluded from evaluation.
    dev = [r for r in real if r["split"] == "dev"]
    labelled = rng.sample(dev, min(cfg.t3_spi_labels, len(dev)))
    lab_keys = {r["key"] for r in labelled}
    ev = [r for r in real if r["key"] not in lab_keys]
    s_syn = [r["s"] for r in synth]
    s_lab = [r["s"] for r in labelled]
    q_unw = C.split_quantile(s_syn, a)
    q_str = {k: C.split_quantile([r["s"] for r in synth if _stratum(r["distance"], cuts) == k], a) for k in range(3)}
    q_real = C.split_quantile(s_lab, a)
    q_spi = C.spi_threshold(s_lab, s_syn, a, beta=0.4)
    methods = {
        "onlysynth_unweighted": lambda r: q_unw,
        "onlysynth_stratified": lambda r: q_str[_stratum(r["distance"], cuts)],
        "onlyreal_30": lambda r: q_real,
        "spi_30": lambda r: q_spi,
    }
    res: dict = {"alpha": a, "strata_cuts": cuts, "thresholds": {
        "onlysynth_unweighted": q_unw, "onlysynth_stratified": q_str, "onlyreal_30": q_real, "spi_30": q_spi},
        "n_synthetic": len(synth), "n_real_eval": len(ev), "n_labelled": len(labelled),
        "synthetic_insample": {m: _eval(synth, f) for m, f in methods.items() if m.startswith("onlysynth")},
        "real": {}}
    for m, f in methods.items():
        block = {"pooled": _eval(ev, f), "ci95_miscoverage": _boot(ev, f, rng)}
        for name, sub in (("dev", [r for r in ev if r["split"] == "dev"]),
                          ("confirm", [r for r in ev if r["split"] == "confirm"])):
            block[name] = _eval(sub, f)
        block["by_stratum"] = {k: _eval([r for r in ev if _stratum(r["distance"], cuts) == k], f) for k in range(3)}
        block["by_tier"] = {t: _eval([r for r in ev if r["tier"] == t], f) for t in sorted({r["tier"] for r in ev})}
        res["real"][m] = block
    # 100 redraws of the 30 labels for the label-using methods
    redraw = defaultdict(list)
    for i in range(100):
        r2 = random.Random(cfg.seed + 1000 + i)
        lab = r2.sample(dev, min(cfg.t3_spi_labels, len(dev)))
        lk = {r["key"] for r in lab}
        ev2 = [r for r in real if r["key"] not in lk]
        sl = [r["s"] for r in lab]
        qr, qs_ = C.split_quantile(sl, a), C.spi_threshold(sl, s_syn, a, beta=0.4)
        redraw["onlyreal_30"].append(_eval(ev2, lambda r: qr)["miscoverage"])
        redraw["spi_30"].append(_eval(ev2, lambda r: qs_)["miscoverage"])
    res["redraws"] = {m: {"mean": statistics.mean(v), "sd": statistics.pstdev(v), "n": len(v)} for m, v in redraw.items()}
    res["synthetic_by_tier_accuracy"] = {
        t: sum(1 for r in synth if r["tier"] == t and r["probs"] and max(r["probs"], key=r["probs"].get) == r["gold_entity"])
        / max(1, sum(1 for r in synth if r["tier"] == t)) for t in G.TIERS}
    res["real_by_tier_accuracy"] = {
        t: sum(1 for r in ev if r["tier"] == t and r["probs"] and max(r["probs"], key=r["probs"].get) == r["gold_entity"])
        / max(1, sum(1 for r in ev if r["tier"] == t)) for t in sorted({r["tier"] for r in ev})}
    res["vacuous"] = {m: (max(v.values()) if isinstance(v, dict) else v) >= 1.0
                      for m, v in res["thresholds"].items()}
    res["mean_distance"] = {"synthetic": statistics.mean([r["distance"] for r in synth]) if synth else None,
                            "real": statistics.mean([r["distance"] for r in ev]) if ev else None}
    return res


def stage_evaluate(cfg: KillTestConfig, out: Path, qs: dict, sc: dict, t2_cand: dict, t2_dec: dict) -> dict:
    st = Stage(out / "t3", "evaluate")
    if st.done:
        return st.load()
    res = evaluate(cfg, _rows_synth(qs, sc), _rows_real(t2_cand, t2_dec))
    res["dropped_rewordings"] = qs.get("dropped", {})
    st.finish(res)
    return res


def run(cfg: KillTestConfig, out: Path, t2_cand: dict, t2_dec: dict) -> dict:
    ents = stage_entities(cfg, out)
    rw = stage_reword(cfg, out, ents)
    qs = stage_questions(cfg, out, ents, rw)
    sc = stage_score(cfg, out, qs)
    return stage_evaluate(cfg, out, qs, sc, t2_cand, t2_dec)
