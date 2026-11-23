"""Assemble EXP-2026-11-022's data/metrics.json from the measured files (Step 9 close, Amendment 5).

The Stage 3 chain never completed: off-B and core+ext were not sat, so the Phase H count gates and
the final confidence bar cannot be computed. What exists is gathered here as measured:
off-A, the two core sittings (each against off-A), and the three proving sets. Run from the repo root.
"""
import json
from pathlib import Path

G = Path("docs/evaluation/experiments/algebra-exposure-2026-11-20")
H = G / "phase-h"
OUT = Path("docs/research/experiments/EXP-2026-11-022-era2-algebra-exposure/data/metrics.json")
ARMS = ("T-lazy", "T-full", "T-lazy-G")


def arm_row(a):
    v, d, p = a.get("variants", {}), a.get("dev", {}), a.get("probe") or {}
    ps = p.get("by_switch") or {}
    return {"variants_exact": v.get("exact"), "variants_cw": v.get("confidently_wrong"), "variants_n": v.get("n"),
            "dev_kept": d.get("kept"), "dev_lost": d.get("lost"), "dev_cw": d.get("confidently_wrong"),
            "probe_core_exact": (ps.get("core") or {}).get("exact"), "probe_core_n": (ps.get("core") or {}).get("n"),
            "probe_ext_exact": (ps.get("extended") or {}).get("exact"), "probe_ext_n": (ps.get("extended") or {}).get("n")}


def sitting(path, name):
    d = json.load(open(path))["sittings"][name]
    return {arm: arm_row(d[arm]) for arm in ARMS if arm in d}


s2 = json.load(open(H / "core-superseded-2/metrics-stop-check.json"))
conf = s2["confidence"]["core"]
out = {
    "status": "closed without the final bar: the stop rule fired on both core sittings and the two "
              "further fix rounds (Amendments 4 and 5) failed their proving bars; off-B and core+ext were not sat",
    "sittings": {
        "off-A (f7b908ab)": sitting(H / "metrics-offA.json", "off-A"),
        "core-1 (f7b908ab, superseded)": sitting(H / "metrics-core.json", "core"),
        "core-2 (fix round 4, 840f20da, superseded)": sitting(H / "core-superseded-2/metrics-stop-check.json", "core"),
    },
    "stop_rule_core_2": s2["stop_rule"],
    "confidence_core_2_vs_offA_provisional": {
        arm: {"confident": c["confident"], "confident_amendment2": c["confident_amendment2"],
              **{k: {x: c[k][x] for x in ("estimate", "lo", "hi")} for k in
                 ("variants_exact", "variants_cw", "dev_lost", "dev_cw", "probe_core", "probe_extended")}}
        for arm, c in conf["arms"].items()},
    "bar": conf["bar"],
    "proving_sets": {n: json.load(open(G / n / "score.json")) for n in ("fix4-small", "fix5-small", "fix6-small")},
    "decision": {"ARIADNE_ALGEBRA_CORE": "off", "ARIADNE_ALGEBRA_EXTENDED": "off"},
}
OUT.write_text(json.dumps(out, indent=1) + "\n")
for k, v in out["sittings"].items():
    for arm, r in v.items():
        print(k, arm, r)
print(json.dumps(out["confidence_core_2_vs_offA_provisional"]["T-lazy-G"]))
