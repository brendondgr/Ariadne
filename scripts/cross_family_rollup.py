#!/usr/bin/env python3
"""Roll up EXP-2026-09-006: does the August ordering survive a change of family?

Reads the judgment sidecars, which are authoritative. The run's state files are
bookkeeping and are deliberately not consulted here -- a roll-up that trusts a
process's own account of itself cannot detect the case where the process was
wrong about what it did.

Three disciplines, each of which has already cost this project a wrong number:

* **Positions are averaged per case before cases are averaged.** An arm that
  lost a judgment in one pass would otherwise be scored on a different
  denominator from the arms it is being compared against.
* **Dropout is reported, never absorbed.** A cell with fewer judgments than
  answers names the missing cases. An earlier ``.cross`` pass failed on exactly
  the three lowest-scoring ``llm_query`` answers and read 0.24 high for it.
* **Ties are not flips.** Two arms the reference never ranked cannot reverse,
  and reporting a sort's tie-break as a reversal invents a finding.

    uv run python scripts/cross_family_rollup.py
"""

from __future__ import annotations

import argparse
import json
import sys
from itertools import combinations
from pathlib import Path
from statistics import fmean, pstdev

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

RUNS = REPO / "docs/evaluation/experiments"
EXP = REPO / "docs/research/experiments/EXP-2026-09-006-cross-family-august-regrade"

#: A grader is a *set* of passes, not one pass. Counterbalanced positions are
#: averaged inside the grader; the five qwen sessions from EXP-2026-08-021 are
#: one grader observed five times.
GRADERS: dict[str, tuple[str, ...]] = {
    "gemma4-31B-mtp": (".g31", ".g31p2"),
    "qwen38-27B-v2 (new, composerfix)": (".q38b", ".q38bp2"),
    "qwen38-27B-v2 (EXP-2026-08-021)": (".qwen38", ".qwen38r2", ".qwen38r3",
                                        ".qwen38r4", ".qwen38r5"),
    "UNIDENTIFIED (August)": ("",),
    # C-022's reported figures came from the `.c015` pass, not the base pass,
    # so the base pass has no generic_composed/merged cells at all. Naming it
    # separately keeps "the figure on record" distinct from "the base pass".
    "UNIDENTIFIED (August, .c015)": (".c015",),
}

BANKS = ("bank20260819", "bank20260820")
BANK_ARMS = ("deterministic", "generic", "generic_composed", "gold_loop_llm",
             "llm_query", "merged")


def answers(root: str, arm: str) -> set[str]:
    adir = RUNS / root / arm / "answers"
    if not adir.is_dir():
        return set()
    out = set()
    for p in adir.glob("*.json"):
        if ".judgment" in p.name:
            continue
        try:
            out.add(json.loads(p.read_text())["id"])
        except (json.JSONDecodeError, KeyError, OSError):
            continue
    return out


def cell(root: str, arm: str, suffixes: tuple[str, ...]) -> dict:
    """Per-case mean correctness across a grader's passes."""
    adir = RUNS / root / arm / "answers"
    per_case: dict[str, list[float]] = {}
    for suffix in suffixes:
        want = f".judgment{suffix}.json"
        for p in adir.glob(f"*{want}"):
            # ``*.judgment.json`` would otherwise also match ``.judgment.g31.json``
            if not p.name.endswith(want):
                continue
            try:
                payload = json.loads(p.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            score = payload.get("correctness")
            cid = payload.get("case_id")
            if score is None or cid is None:
                continue
            per_case.setdefault(cid, []).append(float(score))
    have = answers(root, arm)
    means = {c: fmean(v) for c, v in per_case.items()}
    missing = sorted(have - set(means))
    # A grader with no spread cannot measure a contrast: it returns 0 by
    # construction, whatever is true. gemma4-31B-mtp scores 119/119 of the
    # catalogue answers at exactly 1.0, so its C-021 gap of 0.0000 is a
    # statement about the grader's resolution near the ceiling, not about
    # co-authorship bias. This is computed rather than spotted by eye.
    flat = [v for vs in per_case.values() for v in vs]
    at_ceiling = sum(1 for v in flat if v >= 1.0)
    return {
        "n_answers": len(have),
        "n_cases": len(means),
        "missing_cases": missing,
        "complete": not missing and bool(have),
        "mean": round(fmean(means.values()), 4) if means else None,
        "per_case": means,
        "passes": len(suffixes),
        "sd": round(pstdev(flat), 4) if len(flat) > 1 else None,
        "at_ceiling": at_ceiling,
        "n_judgments": len(flat),
        "frac_at_ceiling": round(at_ceiling / len(flat), 4) if flat else None,
        # No resolution left to detect a difference with.
        "saturated": bool(flat) and at_ceiling == len(flat),
    }


def paired_delta(a: dict, b: dict) -> dict | None:
    """Paired difference a - b, with the contrast's sensitivity stated.

    Saturation is not all-or-nothing for a *contrast*. If one side sits at the
    ceiling and the other does not, the grader can still detect the unsaturated
    side falling below -- but cannot detect it rising above, because there is no
    headroom on the saturated side. That is **one-sided sensitivity**, and a
    margin measured through it is a lower bound in one direction only. Reporting
    it as a symmetric estimate would overstate what the instrument can see.
    """
    common = sorted(set(a["per_case"]) & set(b["per_case"]))
    if not common:
        return None
    d = [a["per_case"][c] - b["per_case"][c] for c in common]
    if a["saturated"] and b["saturated"]:
        sensitivity = "none — both sides at ceiling"
    elif a["saturated"]:
        sensitivity = "one-sided — can only detect b below a"
    elif b["saturated"]:
        sensitivity = "one-sided — can only detect a below b"
    else:
        sensitivity = "two-sided"
    return {"n": len(common), "mean": round(fmean(d), 4),
            "sd": round(pstdev(d), 4) if len(d) > 1 else None,
            "dropped": len(set(a["per_case"]) ^ set(b["per_case"])),
            "sensitivity": sensitivity}


def ordering(cells: dict[str, dict]) -> tuple[list[str], list[tuple[str, str]]]:
    usable = {k: v for k, v in cells.items() if v["mean"] is not None}
    order = sorted(usable, key=lambda k: -usable[k]["mean"])
    ties = [(x, y) for x, y in combinations(usable, 2)
            if abs(usable[x]["mean"] - usable[y]["mean"]) < 1e-9]
    return order, ties


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=EXP / "data" / "rollup.json")
    args = ap.parse_args()

    report: dict = {"graders": {k: list(v) for k, v in GRADERS.items()},
                    "banks": {}, "c021": {}, "dropout": [], "verdicts": {}}

    # --- the two blind banks: ordering under each grader ---------------------
    for bank in BANKS:
        report["banks"][bank] = {}
        for gname, suffixes in GRADERS.items():
            cells = {arm: cell(bank, arm, suffixes) for arm in BANK_ARMS}
            for arm, c in cells.items():
                if not c["complete"] and c["n_cases"]:
                    report["dropout"].append(
                        {"grader": gname, "root": bank, "arm": arm,
                         "missing": c["missing_cases"]})
            order, ties = ordering(cells)
            report["banks"][bank][gname] = {
                "means": {a: c["mean"] for a, c in cells.items()},
                "n_cases": {a: c["n_cases"] for a, c in cells.items()},
                "order": order,
                "ties": ties,
                "c012_deterministic_minus_llm_query":
                    paired_delta(cells["deterministic"], cells["llm_query"]),
                "c022_federated_minus_merged":
                    paired_delta(cells["generic_composed"], cells["merged"]),
            }

    # --- C-021: catalogue (120) against blind (30), same arm ------------------
    for gname, suffixes in GRADERS.items():
        cat = cell("composerfix-dev", "deterministic", suffixes)
        blind = cell("composerfix-holdout", "deterministic", suffixes)
        for root, c in (("composerfix-dev", cat), ("composerfix-holdout", blind)):
            if not c["complete"] and c["n_cases"]:
                report["dropout"].append({"grader": gname, "root": root,
                                          "arm": "deterministic",
                                          "missing": c["missing_cases"]})
        report["c021"][gname] = {
            "catalogue_mean": cat["mean"], "catalogue_n": cat["n_cases"],
            "blind_mean": blind["mean"], "blind_n": blind["n_cases"],
            "catalogue_sd": cat["sd"], "blind_sd": blind["sd"],
            "catalogue_frac_at_ceiling": cat["frac_at_ceiling"],
            "blind_frac_at_ceiling": blind["frac_at_ceiling"],
            # A saturated grader reports gap 0.0000 whatever is true. Reporting
            # that as evidence the gap is zero would be the single most
            # misleading sentence available from this experiment.
            "can_measure_the_gap": not (cat["saturated"] and blind["saturated"]),
            # Unpaired by construction: different questions. That IS the claim.
            "gap": (round(cat["mean"] - blind["mean"], 4)
                    if cat["mean"] is not None and blind["mean"] is not None else None),
        }

    # --- adjudication against the pre-registered hypotheses -------------------
    ref = "qwen38-27B-v2 (EXP-2026-08-021)"
    new = "gemma4-31B-mtp"
    reversals = []
    for bank, by_grader in report["banks"].items():
        a, b = by_grader.get(ref, {}), by_grader.get(new, {})
        if not a.get("order") or not b.get("order"):
            continue
        tied = {x for pair in a.get("ties", []) for x in pair}
        # Only arms BOTH graders actually scored can reverse. While a pass is
        # still in flight the candidate has fewer arms, and ranking against an
        # arm it has not graded would invent a reversal out of an absence.
        shared = [m for m in a["order"] if m not in tied and m in b["order"]]
        report["banks"][bank].setdefault("_comparable_arms", {})[new] = shared
        for x, y in combinations(shared, 2):
            if b["order"].index(x) > b["order"].index(y):
                reversals.append({"bank": bank, "pair": [x, y]})
    report["verdicts"]["H1_arm_order_reversals"] = len(reversals)
    report["verdicts"]["H1_reversal_detail"] = reversals

    flips = []
    for bank, by_grader in report["banks"].items():
        for key in ("c012_deterministic_minus_llm_query",
                    "c022_federated_minus_merged"):
            a, b = by_grader.get(ref, {}).get(key), by_grader.get(new, {}).get(key)
            if (a and b and b.get("sensitivity") == "two-sided"
                    and (a["mean"] > 0) != (b["mean"] > 0)):
                flips.append({"bank": bank, "contrast": key,
                              "reference": a["mean"], "candidate": b["mean"]})
    c021_ref = report["c021"].get("qwen38-27B-v2 (new, composerfix)", {}).get("gap")
    c021_new = report["c021"].get(new, {}).get("gap")
    # A saturated grader cannot flip a sign, because it never had one. Counting
    # its 0.0000 as a sign flip would manufacture the experiment's headline out
    # of an instrument with no resolution left.
    gemma_can_measure = report["c021"].get(new, {}).get("can_measure_the_gap", True)
    if (c021_ref is not None and c021_new is not None and gemma_can_measure
            and (c021_ref > 0) != (c021_new > 0)):
        flips.append({"contrast": "c021_catalogue_minus_blind",
                      "reference": c021_ref, "candidate": c021_new})
    report["verdicts"]["H2_gemma_can_measure_c021"] = gemma_can_measure
    report["verdicts"]["H2_c021_gap_qwen"] = c021_ref
    report["verdicts"]["H2_c021_gap_gemma"] = c021_new
    report["verdicts"]["contrast_sign_flips"] = len(flips)
    report["verdicts"]["flip_detail"] = flips

    offs = []
    for bank, by_grader in report["banks"].items():
        for arm in BANK_ARMS:
            a = cell(bank, arm, GRADERS[ref])
            b = cell(bank, arm, GRADERS[new])
            d = paired_delta(b, a)
            if d:
                offs.append(abs(d["mean"]))
    report["verdicts"]["H4_between_family_mean_abs_offset"] = (
        round(fmean(offs), 4) if offs else None)
    report["verdicts"]["H4_within_family_sd_reference"] = "0.0036-0.0249 (EXP-2026-08-021)"

    # H5 was predicted as "disagreement concentrates on the weak arm". Report the
    # per-cell spread that claim rests on, so it is adjudicated on numbers.
    sat = []
    for bank in BANKS:
        for arm in BANK_ARMS:
            for gname in (ref, new):
                c = cell(bank, arm, GRADERS[gname])
                if c["n_judgments"]:
                    sat.append({"bank": bank, "arm": arm, "grader": gname,
                                "sd": c["sd"], "frac_at_ceiling": c["frac_at_ceiling"],
                                "saturated": c["saturated"]})
    report["verdicts"]["H5_saturation_by_cell"] = sat
    report["verdicts"]["H5_saturated_cells"] = sum(1 for x in sat if x["saturated"])

    args.out.parent.mkdir(parents=True, exist_ok=True)
    slim = json.loads(json.dumps(report))
    for bank in slim["banks"].values():
        pass
    args.out.write_text(json.dumps(report, indent=1, default=str) + "\n")

    # --- print ---------------------------------------------------------------
    for bank, by_grader in report["banks"].items():
        print(f"\n=== {bank} ===")
        arms = BANK_ARMS
        print(f"  {'grader':34} " + " ".join(f"{a[:11]:>11}" for a in arms))
        for gname in GRADERS:
            m = by_grader.get(gname, {}).get("means", {})
            if not any(v is not None for v in m.values()):
                continue
            print(f"  {gname:34} " + " ".join(
                f"{(m.get(a) if m.get(a) is not None else float('nan')):>11.4f}" for a in arms))
        for gname in GRADERS:
            o = by_grader.get(gname, {}).get("order")
            if o:
                print(f"    order [{gname}]: {' > '.join(o)}")

    print("\n=== C-021 catalogue (120) vs blind (30), deterministic ===")
    for gname, v in report["c021"].items():
        if v["catalogue_mean"] is None and v["blind_mean"] is None:
            continue
        cat = f"{v['catalogue_mean']:.4f}" if v["catalogue_mean"] is not None else "  —   "
        bl = f"{v['blind_mean']:.4f}" if v["blind_mean"] is not None else "  —   "
        gap = f"{v['gap']:+.4f}" if v["gap"] is not None else "  —   "
        print(f"  {gname:34} catalogue {cat} (n={v['catalogue_n']})"
              f"  blind {bl} (n={v['blind_n']})  gap {gap}   [incomplete]"
              if v["gap"] is None else
              f"  {gname:34} catalogue {cat} (n={v['catalogue_n']})"
              f"  blind {bl} (n={v['blind_n']})  gap {gap}"
              + ("" if v.get("can_measure_the_gap", True)
                 else "   *** SATURATED — cannot measure this gap ***"))

    print("\n=== verdicts ===")
    for k, v in report["verdicts"].items():
        if k.endswith("_detail") or k.endswith("_by_cell"):
            continue
        print(f"  {k:42} {v}")
    if report["dropout"]:
        print("\n=== dropout (excluded from paired stats, reported here) ===")
        for d in report["dropout"]:
            print(f"  {d['grader']:34} {d['root']}/{d['arm']}: {d['missing']}")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
