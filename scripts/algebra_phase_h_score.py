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
from era2_catalog_score import AUTHORED, confidently_wrong_variant, dev_summary, load_dev  # noqa: E402

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
    if a.out:
        Path(a.out).write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    brief = {s: {arm: {k: (v.get("exact", v.get("kept")), v.get("confidently_wrong"))
                       for k, v in d.items() if k in ("variants", "dev")}
                 for arm, d in arms.items()} for s, arms in m.items()}
    print(json.dumps({"brief (exact|kept, cw)": brief, "stop_rule": result.get("stop_rule"),
                      "gates": {k: v for k, v in result["gates"].items() if k != "rows"}}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
