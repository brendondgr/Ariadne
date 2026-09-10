"""Load every number the report shows. Nothing is typed in by hand."""
from __future__ import annotations

import glob
import json
import os
import statistics
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
# Run-local working directory. Every figure in the committed report reads from
# the experiment folders below; this is only a fallback for re-running the
# generator on the machine that produced the runs, before the per-run files were
# rolled up. Set ARIADNE_RUN_SCRATCH to point it somewhere else.
SCRATCH = Path(os.environ.get("ARIADNE_RUN_SCRATCH", REPO / ".run-scratch"))
E14 = REPO / "docs/research/experiments/EXP-2026-09-014-hybrid-rewrite-stage"
E15 = REPO / "docs/research/experiments/EXP-2026-09-015-relation-slot-derivation"
E16 = REPO / "docs/research/experiments/EXP-2026-09-016-arm-cost-and-latency"
TIERS = ("T1", "T2", "T3", "T4", "T5", "T6")


def load(path):
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def cell(doc, tier, key):
    """One metric, whatever shape the harness wrote it in."""
    if not doc:
        return None
    v = (doc.get("tiers") or {}).get(tier, {}).get(key)
    if isinstance(v, dict):
        return v.get("mean", v.get("value"))
    return v


def series(doc, key, tiers=TIERS):
    return [cell(doc, t, key) for t in tiers]


def spread(docs, key, tiers=TIERS):
    """mean and sd across runs, per tier."""
    out = {"mean": [], "sd": [], "n": len(docs)}
    for t in tiers:
        vals = [c for c in (cell(d, t, key) for d in docs) if c is not None]
        out["mean"].append(round(statistics.fmean(vals), 4) if vals else None)
        out["sd"].append(round(statistics.pstdev(vals), 4) if len(vals) > 1 else 0.0)
    return out


def rungs(rows_path):
    """How each question was answered, from the saved rows."""
    rows = load(rows_path)
    if not rows:
        return None
    counts = {"deterministic": 0, "model": 0, "abstain": 0}
    relation_source = {}
    for r in rows:
        rw = r.get("rewrite") or {}
        k = rw.get("rung")
        if k in counts:
            counts[k] += 1
        if k == "model":
            s = ((rw.get("form") or {}).get("sources") or {}).get("relation")
            relation_source[s or "unfilled"] = relation_source.get(s or "unfilled", 0) + 1
    return {"rungs": counts, "relation_source": relation_source}


def refusals(rows_path):
    """Why the stage refused, from the saved rows. Counted, never remembered."""
    rows = load(rows_path)
    if not rows:
        return None
    total = 0
    out_of_range = 0
    relation_unbound = 0
    for r in rows:
        rw = r.get("rewrite") or {}
        if rw.get("rung") != "abstain":
            continue
        total += 1
        why = " ".join(rw.get("rejected") or [])
        if "relation index" in why:
            out_of_range += 1
        if "relation" in why:
            relation_unbound += 1
    return {"total": total, "relation_index_out_of_range": out_of_range,
            "relation_implicated": relation_unbound}


def cost_manifests(root):
    """Per-arm wall clock and tokens from a cost run root."""
    out = {}
    for f in glob.glob(str(Path(root) / "*/manifest.json")):
        d = load(f)
        if not d:
            continue
        walls = sorted(c.get("wall_s") or 0.0 for c in d.get("cases", []))
        out[d.get("arm", Path(f).parent.name)] = {
            "count": d.get("count"),
            "ok": d.get("ok"),
            "workers": d.get("workers"),
            "wall_s_total": d.get("wall_s"),
            "tokens": d.get("tokens") or {},
            "wall_median": round(statistics.median(walls), 3) if walls else None,
            "wall_p95": round(walls[int(len(walls) * 0.95) - 1], 3) if walls else None,
            "records_nonzero": sum(1 for c in d.get("cases", []) if (c.get("records") or 0) > 0),
        }
    return out


def everything():
    a2 = [load(SCRATCH / f"e015/metrics_A2_run{i}.json") for i in (1, 2, 3)]
    a3 = [load(SCRATCH / f"e015/metrics_A3_run{i}.json") for i in (1, 2, 3)]
    return {
        "e14_r0": load(E14 / "data/metrics_R0.json"),
        "e14_r1": load(E14 / "data/metrics_R1.json"),
        "e14_r2": load(E14 / "data/metrics_R2.json"),
        "e14_r3": load(E14 / "data/metrics_R3.json"),
        "a0": load(E15 / "data/metrics_A0.json"),
        "a1": load(E15 / "data/metrics_A1.json"),
        "a2": load(E15 / "data/metrics_A2.json"),
        "a3": load(E15 / "data/metrics_A3.json"),
        "a2_runs": [d for d in a2 if d],
        "a3_runs": [d for d in a3 if d],
        "a4": load(E15 / "data/metrics_A4.json") or load(SCRATCH / "e015/metrics_A4.json"),
        "rescore": load(E15 / "data/slot_rescore.json"),
        "rungs_a2": rungs(REPO / "docs/evaluation/variants-2026-08-29/A2_run1"),
        "refusals_r2": refusals(REPO / "docs/evaluation/variants-2026-08-29/scored_R2_tune.run1.json"),
        "refusals_a2": refusals(REPO / "docs/evaluation/variants-2026-08-29/A2_run1"),
        "rungs_r2": rungs(REPO / "docs/evaluation/variants-2026-08-29/scored_R2_tune.run1.json"),
        "cost_throughput": cost_manifests(SCRATCH / "e016/throughput"),
        "cost_latency": cost_manifests(SCRATCH / "e016/latency"),
    }
