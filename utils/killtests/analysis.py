"""Evaluate each pre-registered kill rule mechanically, and write the numbers.

    uv run python -m utils.killtests.analysis [t1|t2|t3|all]

Reads the stage outputs under the run directory and writes, per experiment:

- ``docs/research/experiments/EXP-.../data/metrics.json`` — the figures;
- ``.../data/killrule.json`` — the rule as written in PROTOCOL.md, the inputs,
  and the verdict (``killed`` / ``survives`` / ``incomplete``).

A rule's verdict is never typed by hand: it is this module's output.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .config import REPO, KillTestConfig, get
from .stages import atomic_write_json

EXP = {
    "t2": REPO / "docs/research/experiments/EXP-2026-11-001-t2-invariance-gate",
    "t3": REPO / "docs/research/experiments/EXP-2026-11-002-t3-synthetic-calibration",
    "t1": REPO / "docs/research/experiments/EXP-2026-11-003-t1-free-query-gap",
}


def _load(p: Path):
    try:
        return json.loads(p.read_text())
    except FileNotFoundError:
        return None


def t2(out: Path) -> dict:
    sc = _load(out / "t2" / "score.json")
    if not sc:
        return {"verdict": "incomplete", "why": "t2/score.json missing"}
    m = sc["summary"]["confirm"]["filtered"]
    killed = m["ask_rate"] > 0.40 or m["gold_pruned_rate"] >= 0.30
    return {
        "rule": "T2-filtered on the confirmation bank: ask_rate > 0.40 OR gold_pruned_rate >= 0.30 -> killed",
        "inputs": {"ask_rate": m["ask_rate"], "gold_pruned_rate": m["gold_pruned_rate"]},
        "verdict": "killed" if killed else "survives",
        "metrics": sc["summary"],
        "errors": len(sc.get("errors") or {}),
    }


def t3(out: Path, alpha: float = 0.10) -> dict:
    ev = _load(out / "t3" / "evaluate.json")
    if not ev:
        return {"verdict": "incomplete", "why": "t3/evaluate.json missing"}
    r = ev["real"]
    mu = r["onlysynth_unweighted"]["pooled"]["miscoverage"]
    ms = r["onlysynth_stratified"]["pooled"]["miscoverage"]
    vac = ev.get("vacuous") or {}
    holds_u = mu <= alpha + 0.02 and not vac.get("onlysynth_unweighted")
    holds_s = ms <= alpha + 0.02 and not vac.get("onlysynth_stratified")
    better = abs(ms - alpha) < abs(mu - alpha)
    killed = (not holds_u and not holds_s) or not better
    return {
        "rule": "killed if neither zero-label variant has miscoverage <= alpha+0.02 (non-vacuous), "
                "OR |miscov(stratified)-alpha| >= |miscov(unweighted)-alpha|",
        "inputs": {"alpha": alpha, "miscoverage_unweighted": mu, "miscoverage_stratified": ms,
                   "vacuous": vac, "stratified_closer": better},
        "verdict": "killed" if killed else "survives",
        "metrics": ev,
    }


def t1(out: Path) -> dict:
    sc = _load(out / "t1" / "score.json")
    if not sc:
        return {"verdict": "incomplete", "why": "t1/score.json missing"}
    per = {}
    for m, b in sc["by_model"].items():
        c3 = b["arms"]["cypher-3shot"]["exact_records"]
        g3 = b["arms"]["gremlin-3shot"]["exact_records"]
        dead = g3 >= c3 - 0.05 and c3 >= 0.80 and g3 >= 0.80
        per[m] = {"cypher_3shot": c3, "gremlin_3shot": g3, "killed": dead}
    killed = bool(per) and all(v["killed"] for v in per.values())
    return {
        "rule": "for every model, 3-shot: gremlin >= cypher - 0.05 AND both >= 0.80 -> killed",
        "inputs": per,
        "verdict": "killed" if killed else "survives",
        "provisional": len(per) < 2,
        "provisional_why": "fewer than two models served; the plan requires several sizes" if len(per) < 2 else None,
        "served_models": sc.get("served_models"),
        "metrics": sc,
    }


FUNCS = {"t1": t1, "t2": t2, "t3": t3}


def write(cfg: KillTestConfig, which: list[str]) -> dict:
    out = cfg.out_dir
    res = {}
    for t in which:
        r = FUNCS[t](out)
        res[t] = r
        if cfg.smoke or r["verdict"] == "incomplete":
            continue
        data = EXP[t] / "data"
        data.mkdir(parents=True, exist_ok=True)
        atomic_write_json(data / "metrics.json", r.get("metrics"))
        atomic_write_json(data / "killrule.json", {k: v for k, v in r.items() if k != "metrics"})
    return res


def main(argv: list[str] | None = None) -> int:
    from utils.config import load_env

    load_env()
    argv = argv if argv is not None else sys.argv[1:]
    which = ["t1", "t2", "t3"] if not argv or argv[0] == "all" else argv
    res = write(get(), which)
    for t, r in res.items():
        print(t, r["verdict"], json.dumps(r.get("inputs"), default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
