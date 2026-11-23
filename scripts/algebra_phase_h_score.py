#!/usr/bin/env python3
"""EXP-2026-11-022 Stage 3 (Phase H) scorer: per sitting and arm, the existing banks, the probe and
the counted-not-gated tallies; then the stop rule and the gates.

    uv run python scripts/algebra_phase_h_score.py \
        --runs docs/evaluation/experiments/algebra-exposure-2026-11-20/phase-h \
        --out docs/research/experiments/EXP-2026-11-022-era2-algebra-exposure/data/metrics.json

Reads ``<runs>/<sitting>/`` as ``data/phase_h.sh`` writes it, for each sitting present
(``off-A``, ``core``, ``core+ext``, ``off-B``).

Per typed arm (T-lazy, T-full: Qwen; T-lazy-G: Gemma):

* **variants** (699 rows, tiers T0-T5): ``exact`` = rows with ``records_exact``;
  ``confidently_wrong`` = ``wrong_entity`` and not ``abstained`` (as EXP-2026-11-018).
* **dev** (284): ``lost`` and ``confidently_wrong`` against the authored answers
  (``era2_catalog_score.dev_summary``). Dev has no "exact"; its exactness measure is ``284 - lost``
  (``kept``), so "exact falls" reads as "lost rises" on dev.
* **probe** (measure half, 115): from ``score-*.json`` (``scripts/algebra_probe_score.py``).
* **counted, not gated**: ``written_id`` coercions; "no confident match" refusals
  (``ambiguous_anchor``); refusals by code; algebra steps per answer.

**Stop rule** (PROTOCOL Stage 3, fixed before the runs), core against off-A, any typed arm, either
bank: confidently wrong rises by more than 5, or exact falls by more than 10 (dev: lost rises by
more than 10).

**Confidence bar** (PROTOCOL Amendments 2-3): paired 95% bootstrap intervals against the mean of
off-A and off-B; decisions use Amendment 3's margins (``BAR``), Amendment 2's are reported.

**Gates** (PROTOCOL "Gates"), per arm and switch-on configuration, each bank:
exact >= min(off-A, off-B) - |off-A - off-B|; confidently wrong <= max(off-A, off-B);
probe exact (per switch group) > off's; ``extended`` stays on only if its probe items gain over
core and its own bank gates hold.
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from era2_catalog_score import (AUTHORED, bootstrap, confidently_wrong_variant, dev_outcome,  # noqa: E402
                                dev_summary, load_dev)

SITTINGS = ("off-A", "core", "core+ext", "off-B")
ARMS = {
    "T-lazy": {"var": "variants/T-lazy.json", "dev": "dev/planned_llm_typed_lazy",
               "probe": "score-probe-planned_llm_typed_lazy.json"},
    "T-full": {"var": "variants/T-full.json", "dev": "dev/planned_llm_typed_full",
               "probe": "score-probe-planned_llm_typed_full.json"},
    "T-lazy-G": {"var": "variants/T-lazy-G.json", "dev": "dev-gemma/planned_llm_typed_lazy",
                 "probe": "score-probe-gemma-planned_llm_typed_lazy.json"},
}
STOP_CW = 5
STOP_EXACT = 10


def _typed_entries(t: Any) -> list[dict[str, Any]]:
    if isinstance(t, dict):
        return [t]
    return [x for x in (t or []) if isinstance(x, dict)]


def _algebra_steps(plan: Any) -> int:
    """Operator steps in one recorded plan (``TypedStep(kind="algebra")``)."""
    steps = plan if isinstance(plan, list) else []
    return sum(1 for s in steps if isinstance(s, dict) and (s.get("step") or {}).get("kind") == "algebra")


def tallies(items: list[tuple[Any, Any]]) -> dict[str, Any]:
    """Coercions, refusals and algebra steps over (``typed`` field, recorded plan) per answer."""
    written = ambiguous = answers_with_algebra = algebra_steps = 0
    codes: Counter[str] = Counter()
    for t, plan in items:
        n_alg = _algebra_steps(plan)
        for e in _typed_entries(t):
            written += sum(1 for c in e.get("coercions") or [] if isinstance(c, dict) and c.get("filled_by") == "written_id")
            for r in e.get("refusals") or []:
                code = (r.get("code") or r.get("error") or "?") if isinstance(r, dict) else str(r)[:40]
                codes[str(code)] += 1
                if "no confident match" in json.dumps(r):
                    ambiguous += 1
        algebra_steps += n_alg
        answers_with_algebra += n_alg > 0
    n = len(items)
    return {"answers": n, "written_id_coercions": written, "no_confident_match_refusals": ambiguous,
            "refusals_by_code": dict(codes.most_common()), "answers_with_algebra": answers_with_algebra,
            "algebra_steps_per_answer": round(algebra_steps / n, 4) if n else None}


def score_sitting(root: Path, authored: dict[str, dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for arm, p in ARMS.items():
        a: dict[str, Any] = {}
        vp = root / p["var"]
        if vp.exists():
            rows = [r for r in json.loads(vp.read_text()) if "records_exact" in r]
            a["variants"] = {"n": len(rows), "exact": sum(bool(r["records_exact"]) for r in rows),
                             "confidently_wrong": sum(confidently_wrong_variant(r) for r in rows),
                             "errors": sum(1 for r in rows if r.get("error"))}
            a["variants_counts"] = tallies([(r.get("typed"), (r.get("planner") or {}).get("plan")) for r in rows])
        dp = root / p["dev"] / "answers"
        if dp.exists():
            dev = load_dev(dp)
            s = dev_summary(dev, authored)
            s["kept"] = s["n"] - s["lost"]
            a["dev"] = s
            a["dev_counts"] = tallies([((x.get("run_meta") or {}).get("typed"), (x.get("run_meta") or {}).get("observed_plan"))
                                    for x in dev.values()])
        pp = root / p["probe"]
        if pp.exists():
            ps = json.loads(pp.read_text())
            a["probe"] = {k: ps[k] for k in ("n", "overall", "by_operator", "by_switch", "by_dataset", "by_source")}
        out[arm] = a
    for extra, key in (("variants/E.json", "E"), ("variants/R.json", "R")):
        vp = root / extra
        if vp.exists():
            rows = [r for r in json.loads(vp.read_text()) if "records_exact" in r]
            out[key] = {"variants": {"n": len(rows), "exact": sum(bool(r["records_exact"]) for r in rows),
                                     "confidently_wrong": sum(confidently_wrong_variant(r) for r in rows)}}
    ep = root / "dev/planned_llm_english/answers"
    if ep.exists():
        out.setdefault("E", {})["dev"] = dev_summary(load_dev(ep), authored)
    return out


def _get(m: dict[str, Any], sit: str, arm: str, bank: str, key: str) -> int | None:
    try:
        return m[sit][arm][bank][key]
    except KeyError:
        return None


def stop_rule(m: dict[str, Any], sit: str = "core") -> dict[str, Any]:
    trips = []
    for arm in ARMS:
        for bank, ex in (("variants", "exact"), ("dev", "kept")):
            o_ex, c_ex = _get(m, "off-A", arm, bank, ex), _get(m, sit, arm, bank, ex)
            o_cw, c_cw = _get(m, "off-A", arm, bank, "confidently_wrong"), _get(m, sit, arm, bank, "confidently_wrong")
            if None in (o_ex, c_ex, o_cw, c_cw):
                trips.append({"arm": arm, "bank": bank, "missing": True})
                continue
            if c_cw - o_cw > STOP_CW:
                trips.append({"arm": arm, "bank": bank, "cw_rise": c_cw - o_cw})
            if o_ex - c_ex > STOP_EXACT:
                trips.append({"arm": arm, "bank": bank, "exact_fall": o_ex - c_ex})
    return {"against": "off-A", "sitting": sit, "stop": bool(trips), "trips": trips}


def gates(m: dict[str, Any]) -> dict[str, Any]:
    if not all(s in m for s in ("off-A", "off-B")):
        return {"complete": False}
    g: dict[str, Any] = {"complete": True, "rows": []}
    for sit in ("core", "core+ext"):
        if sit not in m:
            continue
        for arm in ARMS:
            for bank, ex in (("variants", "exact"), ("dev", "kept")):
                a, b, t = (_get(m, s, arm, bank, ex) for s in ("off-A", "off-B", sit))
                ca, cb, ct = (_get(m, s, arm, bank, "confidently_wrong") for s in ("off-A", "off-B", sit))
                if None in (a, b, t, ca, cb, ct):
                    g["rows"].append({"sitting": sit, "arm": arm, "bank": bank, "missing": True})
                    continue
                bar = min(a, b) - abs(a - b)
                g["rows"].append({"sitting": sit, "arm": arm, "bank": bank, "exact": t, "exact_bar": bar,
                                  "exact_pass": t >= bar, "cw": ct, "cw_bar": max(ca, cb), "cw_pass": ct <= max(ca, cb)})
            for grp in ("core", "extended"):
                try:
                    on = m[sit][arm]["probe"]["by_switch"][grp]["exact"]
                    off = max(m[s][arm]["probe"]["by_switch"][grp]["exact"] for s in ("off-A", "off-B"))
                except KeyError:
                    continue
                g["rows"].append({"sitting": sit, "arm": arm, "bank": f"probe:{grp}", "exact": on, "off_exact": off,
                                  "exact_pass": on > off})
    if "core+ext" in m and "core" in m:
        ext = []
        for arm in ARMS:
            try:
                ext.append(m["core+ext"][arm]["probe"]["by_switch"]["extended"]["exact"]
                           - m["core"][arm]["probe"]["by_switch"]["extended"]["exact"])
            except KeyError:
                pass
        banks_hold = all(r.get("exact_pass") and r.get("cw_pass", True) for r in g["rows"]
                         if r.get("sitting") == "core+ext" and not r["bank"].startswith("probe"))
        g["extended_stays"] = {"probe_gain_per_arm": ext, "gains": bool(ext) and all(d > 0 for d in ext),
                               "banks_hold": banks_hold}
    g["all_bank_gates_pass"] = all(r.get("exact_pass") and r.get("cw_pass", True) for r in g["rows"] if not r.get("missing"))
    return g


# --------------------------------------------------------------------------- #
# PROTOCOL Amendment 2: the confidence bar
# --------------------------------------------------------------------------- #

BAR = {"variants_exact_lo": -0.03, "variants_cw_hi": 0.02, "dev_lost_hi": 8.0, "dev_cw_hi": 3.0, "probe_lo": 0.0}
#: Amendment 2's margins, reported beside the decision bar
BAR_A2 = {"variants_exact_lo": -0.02, "variants_cw_hi": 0.015, "dev_lost_hi": 6.0, "dev_cw_hi": 3.0, "probe_lo": 0.0}


def _var_rows(root: Path, arm: str) -> dict[tuple[str, str, str], dict[str, Any]]:
    p = root / ARMS[arm]["var"]
    if not p.exists():
        return {}
    return {(str(r.get("case_id")), str(r.get("tier")), str(r.get("question"))): r
            for r in json.loads(p.read_text()) if "records_exact" in r}


def _paired_var(on: dict, offs: list[dict], value: Any) -> dict[str, Any]:
    from collections import defaultdict

    by_case: dict[str, list[float]] = defaultdict(list)
    for k, r in on.items():
        if not all(k in o for o in offs):
            continue
        ref = sum(value(o[k]) for o in offs) / len(offs)
        by_case[k[0]].append(value(r) - ref)
    return bootstrap(list(by_case.values()), stat="mean")


def _paired_dev(on: dict, offs: list[dict], authored: dict, key: str) -> dict[str, Any]:
    clusters = []
    for i in sorted(authored):
        ref = sum(float(dev_outcome(o.get(i), authored[i])[key]) for o in offs) / len(offs)
        clusters.append([float(dev_outcome(on.get(i), authored[i])[key]) - ref])
    return bootstrap(clusters, stat="sum")


def _probe_items(root: Path, arm: str) -> dict[str, dict[str, Any]]:
    p = root / ARMS[arm]["probe"]
    if not p.exists():
        return {}
    return {it["id"]: it for it in json.loads(p.read_text()).get("items") or []}


def confidence(runs: Path, sit: str, authored: dict) -> dict[str, Any]:
    """Amendment 2's paired intervals for one switch-on sitting, every typed arm."""
    offs_present = [s for s in ("off-A", "off-B") if (runs / s).exists()]
    out: dict[str, Any] = {"sitting": sit, "off_reference": offs_present,
                           "provisional": offs_present != ["off-A", "off-B"], "bar": BAR, "arms": {}}
    for arm, p in ARMS.items():
        a: dict[str, Any] = {}
        on = _var_rows(runs / sit, arm)
        offs = [_var_rows(runs / s, arm) for s in offs_present]
        if on and all(offs):
            a["variants_exact"] = _paired_var(on, offs, lambda r: float(bool(r["records_exact"])))
            a["variants_cw"] = _paired_var(on, offs, lambda r: float(confidently_wrong_variant(r)))
        dp = runs / sit / p["dev"] / "answers"
        if dp.exists():
            don = load_dev(dp)
            doffs = [load_dev(runs / s / p["dev"] / "answers") for s in offs_present]
            a["dev_lost"] = _paired_dev(don, doffs, authored, "lost")
            a["dev_cw"] = _paired_dev(don, doffs, authored, "confidently_wrong")
        pon = _probe_items(runs / sit, arm)
        poffs = [_probe_items(runs / s, arm) for s in offs_present]
        if pon and all(poffs):
            for grp in ("core", "extended"):
                cl = [[float(it["verdict"] == "exact")
                       - sum(float(o[i]["verdict"] == "exact") for o in poffs) / len(poffs)]
                      for i, it in pon.items() if it.get("switch") == grp and all(i in o for o in poffs)]
                a[f"probe_{grp}"] = bootstrap(cl, stat="mean")
        checks = {
            "variants_exact": (a.get("variants_exact") or {}).get("lo") is not None
                              and a["variants_exact"]["lo"] >= BAR["variants_exact_lo"],
            "variants_cw": (a.get("variants_cw") or {}).get("hi") is not None
                           and a["variants_cw"]["hi"] <= BAR["variants_cw_hi"],
            "dev_lost": (a.get("dev_lost") or {}).get("hi") is not None and a["dev_lost"]["hi"] <= BAR["dev_lost_hi"],
            "dev_cw": (a.get("dev_cw") or {}).get("hi") is not None and a["dev_cw"]["hi"] <= BAR["dev_cw_hi"],
            "probe_core": (a.get("probe_core") or {}).get("lo") is not None and a["probe_core"]["lo"] > BAR["probe_lo"],
        }
        a["checks"] = checks
        a["confident"] = all(checks.values())
        lo = lambda k: (a.get(k) or {}).get("lo")  # noqa: E731
        hi = lambda k: (a.get(k) or {}).get("hi")  # noqa: E731
        a["confident_amendment2"] = bool(
            lo("variants_exact") is not None and lo("variants_exact") >= BAR_A2["variants_exact_lo"]
            and hi("variants_cw") is not None and hi("variants_cw") <= BAR_A2["variants_cw_hi"]
            and hi("dev_lost") is not None and hi("dev_lost") <= BAR_A2["dev_lost_hi"]
            and hi("dev_cw") is not None and hi("dev_cw") <= BAR_A2["dev_cw_hi"] and checks["probe_core"])
        out["arms"][arm] = a
    out["confident"] = bool(out["arms"]) and all(x["confident"] for x in out["arms"].values())
    if sit == "core+ext" and (runs / "core").exists():
        ext = {}
        for arm in ARMS:
            pon, pcore = _probe_items(runs / sit, arm), _probe_items(runs / "core", arm)
            cl = [[float(it["verdict"] == "exact") - float(pcore[i]["verdict"] == "exact")]
                  for i, it in pon.items() if it.get("switch") == "extended" and i in pcore]
            ext[arm] = bootstrap(cl, stat="mean") if cl else None
        out["extended_over_core"] = ext
        out["extended_gains"] = all(v and v["lo"] is not None and v["lo"] > 0 for v in ext.values())
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--authored", default=str(AUTHORED))
    ap.add_argument("--stop-check", default=None, help="print only the stop rule for this sitting against off-A")
    a = ap.parse_args(argv)
    authored = load_dev(Path(a.authored))
    runs = Path(a.runs)
    m = {s: score_sitting(runs / s, authored) for s in SITTINGS if (runs / s).exists()}
    result = {"sittings": m}
    if a.stop_check:
        result["stop_rule"] = stop_rule(m, a.stop_check)
    elif "core" in m and "off-A" in m:
        result["stop_rule"] = stop_rule(m, "core")
    result["gates"] = gates(m)
    result["confidence"] = {sit: confidence(runs, sit, authored) for sit in ("core", "core+ext") if sit in m}
    if a.out:
        Path(a.out).write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    brief = {s: {arm: {k: (v.get("exact", v.get("kept")), v.get("confidently_wrong"))
                       for k, v in d.items() if k in ("variants", "dev")}
                 for arm, d in arms.items()} for s, arms in m.items()}
    print(json.dumps({"brief (exact|kept, cw)": brief, "stop_rule": result.get("stop_rule"),
                      "gates": {k: v for k, v in result["gates"].items() if k != "rows"},
                      "confidence": {s: {"confident": c["confident"], "provisional": c["provisional"],
                                         **{a: {k: (v.get("estimate"), v.get("lo"), v.get("hi"))
                                                for k, v in x.items() if isinstance(v, dict) and "lo" in v}
                                            | {"checks": x["checks"]} for a, x in c["arms"].items()}}
                                     for s, c in result["confidence"].items()}}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
