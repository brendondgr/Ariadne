"""Scoring for EXP-2026-11-014 (imported by ``era2_usability.py score``).

One scoreboard for every treatment, against Step 7's records for the same model on the
same items (PROTOCOL "Metrics"; amendment 1: decision servers only).
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any, Callable

from era2_usability import (ARMS, SEED, Q_GRID, control_items, control_records, decision_group, load_items,
                            records, two_folds)

from utils.decision import score as S
from utils.decision import usability as U
from utils.decision.items import NONE, Item

SPLITS = 200
BOOT = 2000
THETA_GRID = [round(0.05 * i, 2) for i in range(1, 20)]          # 0.05 .. 0.95

Row = tuple[str | None, float, str]                              # (prediction, confidence, gold)


# --------------------------------------------------------------------------- #
# Generic pieces
# --------------------------------------------------------------------------- #

def _splits(groups: list[str]) -> list[tuple[set[str], set[str]]]:
    """The same 200 anchor splits as utils.decision.score.transfer (same seed, same shuffle)."""
    g0 = sorted(groups)
    rng = random.Random(SEED)
    out = []
    for _ in range(SPLITS):
        g = g0[:]
        rng.shuffle(g)
        out.append((set(g[: len(g) // 2]), set(g[len(g) // 2:])))
    return out


def gate_splits(items: list[Item], rows_for: Callable[[set[str]], dict[str, Row]],
                fallback: dict[str, str | None]) -> list[dict[str, float]]:
    """Per split: fit tau on the calibration half, report the test half.

    ``rows_for(calibration_groups)`` returns {item id: row}; a treatment with its own fitted
    parameter (yes/no's theta) fits it on those groups. ``fallback`` is the controller's
    saved answer per item, for the end-to-end figure.
    """
    out = []
    for cal_g, test_g in _splits([it.group for it in items]):
        rows = rows_for(cal_g)
        cal = [rows[it.id] for it in items if it.group in cal_g and it.id in rows]
        test = [(it, rows[it.id]) for it in items if it.group in test_g and it.id in rows]
        if not cal or not test:
            continue
        tau = S.threshold_for(cal)
        acc = [(it, r) for it, r in test if r[1] >= tau]
        wrong = sum(r[0] != r[2] for _, r in acc)
        e2e = sum((r[0] == r[2]) if r[1] >= tau else (fallback.get(it.id) == it.gold) for it, r in test)
        out.append({"coverage": len(acc) / len(test), "wrong": wrong / len(acc) if acc else 0.0,
                    "e2e": e2e / len(test)})
    return out


def summarize_splits(sp: list[dict[str, float]]) -> dict[str, Any]:
    if not sp:
        return {"splits": 0}
    w = sorted(x["wrong"] for x in sp)
    return {"splits": len(sp), "coverage_median": round(median(x["coverage"] for x in sp), 4),
            "wrong_median": round(median(w), 4), "wrong_p90": round(w[int(0.9 * (len(w) - 1))], 4),
            "e2e_median": round(median(x["e2e"] for x in sp), 4)}


def split_diff(a: list[dict], b: list[dict], key: str) -> dict[str, float] | None:
    if len(a) != len(b) or not a:
        return None
    d = sorted(x[key] - y[key] for x, y in zip(a, b))
    return {"median": round(median(d), 4), "lo": round(d[int(0.025 * (len(d) - 1))], 4),
            "hi": round(d[int(0.975 * (len(d) - 1))], 4)}


def boot_diff(items: list[Item], t: dict[str, Row], c: dict[str, Row],
              keep: Callable[[Item], bool] = lambda it: True) -> dict[str, Any] | None:
    """Paired accuracy difference (treatment - control), 95% interval over anchors."""
    its = [it for it in items if keep(it) and it.id in t and it.id in c]
    if not its:
        return None
    by_g: dict[str, list[int]] = defaultdict(list)
    for it in its:
        by_g[it.group].append((t[it.id][0] == it.gold) - (c[it.id][0] == it.gold))
    groups = sorted(by_g)
    point = sum(sum(v) for v in by_g.values()) / len(its)
    rng = random.Random(f"{SEED}|boot")
    sims = []
    for _ in range(BOOT):
        pick = [groups[rng.randrange(len(groups))] for _ in groups]
        n = sum(len(by_g[g]) for g in pick)
        sims.append(sum(sum(by_g[g]) for g in pick) / n)
    sims.sort()
    return {"n": len(its), "diff": round(point, 4), "lo": round(sims[int(0.025 * BOOT)], 4),
            "hi": round(sims[int(0.975 * BOOT) - 1], 4)}


def block(items: list[Item], rows: dict[str, Row], second: dict[str, str | None] | None,
          base_acc: float | None, splits: list[dict]) -> dict[str, Any]:
    r = [rows[it.id] for it in items if it.id in rows]
    offered = [rows[it.id] for it in items if it.id in rows and it.gold != NONE]
    t = summarize_splits(splits)
    flip = (S.flip_rate({i: rows[i][0] for i in rows if i in second}, second) if second else None)
    acc = S.accuracy(r)
    au = S.auroc(r)
    return {"n": len(r), "accuracy": acc, "accuracy_offered": S.accuracy(offered), "none": S.none_pr(r),
            "auroc": au, "ece": S.ece(r), "flip": flip, "transfer": t,
            "role": S.role(t, flip, au, acc, base_acc)}


def choice_rows(recs: dict, prefix: str, items: list[Item], order: int = 0) -> dict[str, Row]:
    out = {}
    for it in items:
        rec = recs.get((prefix + it.id, order))
        if rec and rec.get("probs"):
            p, c = S.top_of(rec["probs"])
            out[it.id] = (p, c, it.gold)
    return out


def choice_tops(recs: dict, prefix: str, items: list[Item], order: int) -> dict[str, str | None]:
    return {it.id: recs[(prefix + it.id, order)].get("top") for it in items
            if (prefix + it.id, order) in recs and recs[(prefix + it.id, order)].get("probs")}


def shared_gloss(it: Item) -> bool:
    if it.gold == NONE:
        return False
    gl = {k: v.split(": ", 1)[-1] for k, v in it.options.items() if k != NONE}
    return sum(v == gl[it.gold] for k, v in gl.items() if k != it.gold) > 0


# --------------------------------------------------------------------------- #
# Yes/no
# --------------------------------------------------------------------------- #

def fit_theta(pairs: list[tuple[dict[str, float], str]]) -> float:
    best, best_acc = THETA_GRID[0], -1.0
    for th in THETA_GRID:
        acc = sum(U.yesno_decide(s, th)[0] == g for s, g in pairs) / len(pairs) if pairs else 0
        if acc > best_acc:
            best, best_acc = th, acc
    return best


def yesno_score(items: list[Item], recs: dict, prefix: str, dec: str) -> tuple[dict, dict, dict, list]:
    s0 = {it.id: recs[(prefix + it.id, 0)]["s"] for it in items
          if (prefix + it.id, 0) in recs and recs[(prefix + it.id, 0)].get("s")}
    s1 = {it.id: recs[(prefix + it.id, 1)]["s"] for it in items
          if (prefix + it.id, 1) in recs and recs[(prefix + it.id, 1)].get("s")}
    its = [it for it in items if it.id in s0]
    a, b = two_folds([it.group for it in its], f"theta|{dec}")
    th_a = fit_theta([(s0[it.id], it.gold) for it in its if it.group in a])
    th_b = fit_theta([(s0[it.id], it.gold) for it in its if it.group in b])
    theta = {it.id: (th_b if it.group in a else th_a) for it in its}
    rows = {}
    for it in its:
        p, c = U.yesno_decide(s0[it.id], theta[it.id])
        rows[it.id] = (p, c, it.gold)
    second = {i: U.yesno_decide(s1[i], theta[i])[0] for i in s1 if i in theta}

    def rows_for(cal_g: set[str]) -> dict[str, Row]:
        th = fit_theta([(s0[it.id], it.gold) for it in its if it.group in cal_g])
        out = {}
        for it in its:
            p, c = U.yesno_decide(s0[it.id], th)
            out[it.id] = (p, c, it.gold)
        return out

    return rows, second, {"theta_fold_a": th_a, "theta_fold_b": th_b}, [rows_for, its]


# --------------------------------------------------------------------------- #
# Shortlist
# --------------------------------------------------------------------------- #

def shortlist_transfer(items: list[Item], recs: dict) -> dict[str, Any]:
    probs = {it.id: recs[(it.id, 0)]["probs"] for it in items if (it.id, 0) in recs and recs[(it.id, 0)].get("probs")}
    its = [it for it in items if it.id in probs and it.gold != NONE]
    rec_, size = [], []
    for cal_g, test_g in _splits([it.group for it in items if it.id in probs]):
        from era2_usability import fit_q

        q = fit_q([(probs[it.id], it.gold) for it in its if it.group in cal_g])
        test = [it for it in its if it.group in test_g]
        if not test:
            continue
        lists = {it.id: U.shortlist_keys(probs[it.id], q) for it in test}
        rec_.append(sum(it.gold in lists[it.id] for it in test) / len(test))
        size.append(sum(len(v) for v in lists.values()) / len(test))
    full = [sum(1 for k in probs[it.id] if k != NONE) for it in its]
    return {"splits": len(rec_), "recall_median": round(median(rec_), 4) if rec_ else None,
            "recall_p10": round(sorted(rec_)[int(0.1 * (len(rec_) - 1))], 4) if rec_ else None,
            "size_median": round(median(size), 3) if size else None,
            "full_menu_mean": round(sum(full) / len(full), 3) if full else None}


# --------------------------------------------------------------------------- #
# The scoreboard
# --------------------------------------------------------------------------- #

def cmd_score(control: Path, data: Path) -> None:
    items = control_items(control)
    by_dec = {d: [it for it in items if decision_group(it) == d] for d in ("D4", "D2+D3")}
    base = control_records(control, "qwen_reason")
    fallback = {it.id: (base.get((it.id, 0)) or {}).get("top") for it in items}
    base_acc = {d: S.accuracy([(fallback[it.id], 1.0, it.gold) for it in its]) for d, its in by_dec.items()}
    runs = data / "runs"
    M: dict[str, Any] = {"base_accuracy_qwen_reason_saved": base_acc, "decisions": {}}

    for dec, its in by_dec.items():
        D: dict[str, Any] = {"n": len(its), "arms": {}}
        for arm in ARMS:
            A: dict[str, Any] = {}
            ctrl = control_records(control, arm)
            c_rows = choice_rows(ctrl, "", its)
            c_split = gate_splits(its, lambda _g, r=c_rows: r, fallback)
            A["control"] = block(its, c_rows, choice_tops(ctrl, "", its, 1), base_acc[dec], c_split)
            if dec == "D4":
                A["control"]["accuracy_shared_gloss"] = S.accuracy([c_rows[i.id] for i in its if shared_gloss(i) and i.id in c_rows])
                A["control"]["accuracy_unique_gloss"] = S.accuracy([c_rows[i.id] for i in its
                                                                    if i.gold != NONE and not shared_gloss(i) and i.id in c_rows])

            def compare(name: str, rows: dict[str, Row], second, splits, sub=None):
                b = block(its, rows, second, base_acc[dec], splits)
                b["vs_control"] = {
                    "accuracy": boot_diff(its, rows, c_rows),
                    "accuracy_offered": boot_diff(its, rows, c_rows, lambda it: it.gold != NONE),
                    "none_recall": boot_diff(its, rows, c_rows, lambda it: it.gold == NONE),
                    "gate_coverage": split_diff(splits, c_split, "coverage"),
                    "gate_wrong": split_diff(splits, c_split, "wrong"),
                    "e2e": split_diff(splits, c_split, "e2e"),
                }
                if dec == "D4":
                    b["vs_control"]["accuracy_shared_gloss"] = boot_diff(its, rows, c_rows, shared_gloss)
                    b["vs_control"]["accuracy_unique_gloss"] = boot_diff(
                        its, rows, c_rows, lambda it: it.gold != NONE and not shared_gloss(it))
                    sh, ac = b["vs_control"]["accuracy_shared_gloss"], b["vs_control"]["accuracy"]
                    if sh and ac and ac["diff"]:
                        # share of the whole-set gain carried by shared-description items (H1)
                        b["vs_control"]["gain_share_shared"] = round(sh["n"] * sh["diff"] / (ac["n"] * ac["diff"]), 4)
                # items a full-set threshold lets through: how often the controller's saved pick is the same
                tau = S.threshold_for([rows[it.id] for it in its if it.id in rows])
                g = [it for it in its if it.id in rows and rows[it.id][1] >= tau]
                b["gated_full_set"] = {"n": len(g), "same_as_controller": round(
                    sum(rows[it.id][0] == fallback[it.id] for it in g) / len(g), 4) if g else None}
                A[name] = b
                return b

            # wording and rule filter (D4, choice)
            if dec == "D4":
                for t, prefix in (("wording", "W:"), ("rulefilter", "R:")):
                    recs = records(runs / t / f"{arm}.jsonl")
                    if not recs:
                        continue
                    rows = choice_rows(recs, prefix, its)
                    second = choice_tops(recs, prefix, its, 1)
                    if t == "rulefilter":                     # unchanged items keep the control answer
                        narrowed = set(rows)
                        rows = {**c_rows, **rows}
                        second = {**choice_tops(ctrl, "", its, 1), **second}
                    sp = gate_splits(its, lambda _g, r=rows: r, fallback)
                    b = compare(t, rows, second, sp)
                    if t == "rulefilter":
                        b["narrowed"] = {
                            "n": len(narrowed),
                            "accuracy": boot_diff(its, rows, c_rows, lambda it: it.id in narrowed),
                            "none_recall": boot_diff(its, rows, c_rows, lambda it: it.id in narrowed and it.gold == NONE),
                            "single_option_accuracy": S.accuracy([rows[i] for i in narrowed
                                                                  if len(load_cache(data, "rulefilter")["R:" + i].options) == 2]),
                        }
            # yes/no and wording x yes/no
            for t, prefix in (("yesno", ""), ("wording_yesno", "W:")):
                if t == "wording_yesno" and dec != "D4":
                    continue
                recs = records(runs / t / f"{arm}.jsonl")
                if not recs:
                    continue
                rows, second, theta, (rows_for, yits) = yesno_score(its, recs, prefix, f"{dec}|{arm}|{t}")
                sp = gate_splits(its, rows_for, fallback)
                b = compare(t, rows, second, sp)
                b["theta"] = theta
            D["arms"][arm] = A

        # shortlist: transfer of q per shortlister; chooser cells against the chooser's full menu
        sl: dict[str, Any] = {}
        for shortlister in ARMS:
            ctrl_s = control_records(control, shortlister)
            sl[shortlister] = {"transfer": shortlist_transfer(its, ctrl_s), "cells": {}}
            s_items = {it.id: it for it in load_cache(data, "shortlist").values()
                       if it.tags.get("shortlister") == shortlister}
            for chooser in ARMS:
                recs = records(runs / "shortlist" / f"{chooser}.jsonl")
                if not recs:
                    continue
                c_rows = choice_rows(control_records(control, chooser), "", its)
                rows = choice_rows(recs, f"S:{shortlister}:", its)
                second = choice_tops(recs, f"S:{shortlister}:", its, 1)
                sizes = [s_items[f"S:{shortlister}:{i}"].tags["shortlist"] for i in rows if f"S:{shortlister}:{i}" in s_items]
                sp = gate_splits(its, lambda _g, r=rows: r, fallback)
                b = block(its, rows, second, base_acc[dec], sp)
                b["vs_full_menu"] = {"accuracy": boot_diff(its, rows, c_rows),
                                     "none_recall": boot_diff(its, rows, c_rows, lambda it: it.gold == NONE)}
                b["gold_kept"] = round(sum(r[2] in s_items[f"S:{shortlister}:{i}"].options for i, r in rows.items())
                                       / len(rows), 4) if rows else None
                b["mean_list_size"] = round(sum(sizes) / len(sizes), 3) if sizes else None
                sl[shortlister]["cells"][chooser] = b
        D["shortlist"] = sl

        # verifier: the verifier's P(yes) against the picker's own confidence, on the picker's real picks
        vr: dict[str, Any] = {}
        v_items = load_cache(data, "verifier")
        for picker in ARMS:
            ctrl_p = control_records(control, picker)
            picks = {}
            for it in its:
                rec = ctrl_p.get((it.id, 0))
                if rec and rec.get("top") and rec["top"] != NONE:
                    picks[it.id] = (rec["top"], S.top_of(rec["probs"])[1], it.gold)
            pits = [it for it in its if it.id in picks]
            own_sp = gate_splits(pits, lambda _g: picks, fallback)
            vr[picker] = {"n_picks": len(pits), "pick_accuracy": S.accuracy(list(picks.values())),
                          "own": {**summarize_splits(own_sp), "auroc": S.auroc(list(picks.values()))}, "by_verifier": {}}
            for verifier in ARMS:
                recs = records(runs / "verifier" / f"{verifier}.jsonl")
                if not recs:
                    continue
                vrows, v1 = {}, {}
                for it in pits:
                    vid = f"V:{picker}:{it.id}"
                    if vid not in v_items:
                        continue
                    r0, r1 = recs.get((vid, 0)), recs.get((vid, 1))
                    if r0 and r0.get("probs"):
                        vrows[it.id] = (picks[it.id][0], float(r0["probs"].get("yes", 0.0)), it.gold)
                    if r0 and r1 and r0.get("top") and r1.get("top"):
                        v1[it.id] = r0["top"] != r1["top"]
                sp = gate_splits(pits, lambda _g, r=vrows: r, fallback)
                minrows = {i: (vrows[i][0], min(vrows[i][1], picks[i][1]), vrows[i][2]) for i in vrows}
                sp_min = gate_splits(pits, lambda _g, r=minrows: r, fallback)
                vr[picker]["by_verifier"][verifier] = {
                    **summarize_splits(sp), "auroc": S.auroc(list(vrows.values())),
                    "verdict_flip": round(sum(v1.values()) / len(v1), 4) if v1 else None,
                    "coverage_vs_own": split_diff(sp, own_sp, "coverage"),
                    "wrong_vs_own": split_diff(sp, own_sp, "wrong"),
                    "min_of_both": summarize_splits(sp_min),
                    "catches_wrong": round(sum(r[1] < 0.5 for r in vrows.values() if r[0] != r[2])
                                           / max(1, sum(r[0] != r[2] for r in vrows.values())), 4),
                    "rejects_right": round(sum(r[1] < 0.5 for r in vrows.values() if r[0] == r[2])
                                           / max(1, sum(r[0] == r[2] for r in vrows.values())), 4),
                }
        D["verifier"] = vr
        M["decisions"][dec] = D

    if (data / "drift.json").is_file():
        M["drift"] = {k: {kk: vv for kk, vv in v.items() if kk != "rows"}
                      for k, v in json.loads((data / "drift.json").read_text()).items()}
    if (data / "latency.json").is_file():
        M["latency_sequential"] = json.loads((data / "latency.json").read_text())
    # yes/no diagnostics: does P(yes) follow the content, or the answer position?
    diag: dict[str, Any] = {}
    for arm in ARMS:
        by_order: dict[int, list[float]] = {0: [], 1: []}
        spread: list[float] = []
        for r in records(runs / "yesno" / f"{arm}.jsonl").values():
            v = list(r["s"].values())
            by_order[r["order"]] += v
            if len(v) > 1:
                spread.append(max(v) - min(v))
        if spread:
            diag[arm] = {"mean_p_yes_yes_first": round(sum(by_order[0]) / len(by_order[0]), 4),
                         "mean_p_yes_no_first": round(sum(by_order[1]) / len(by_order[1]), 4),
                         "median_within_item_spread": round(median(spread), 4), "n_requests": len(spread)}
    M["yesno_diagnostics"] = diag
    (data / "metrics.json").write_text(json.dumps(M, indent=1))
    write_tables(M, data.parent / "tables")
    print((data.parent / "tables" / "scoreboard.md").read_text())


_CACHE: dict[str, dict[str, Item]] = {}


def load_cache(data: Path, name: str) -> dict[str, Item]:
    if name not in _CACHE:
        _CACHE[name] = {it.id: it for it in load_items(data / f"{name}.jsonl")}
    return _CACHE[name]


def _ci(d: dict | None) -> str:
    return "—" if not d else f"{d['diff']:+.3f} [{d['lo']:+.3f}, {d['hi']:+.3f}]"


def _sci(d: dict | None) -> str:
    return "—" if not d else f"{d['median']:+.3f} [{d['lo']:+.3f}, {d['hi']:+.3f}]"


def write_tables(M: dict, tdir: Path) -> None:
    tdir.mkdir(exist_ok=True)
    L = ["# Scoreboard (EXP-2026-11-014)", "",
         "Differences are treatment minus control, same model and items: accuracy with a 95% interval over",
         "anchors; gate coverage as the median per-split difference with the 2.5–97.5 percentile range.", "",
         "| Decision | Model | Treatment | Accuracy | Δ accuracy | Δ offered | Δ none recall | None recall | Gate: coverage, wrong (p90) | Δ gate coverage | End-to-end | Flip | Role |",
         "|---|---|---|---:|---|---|---|---:|---|---|---:|---:|---|"]
    for dec, D in M["decisions"].items():
        for arm, A in D["arms"].items():
            for t, b in A.items():
                tr = b["transfer"]
                v = b.get("vs_control", {})
                L.append(f"| {dec} | {arm} | {t} | {b['accuracy']} | {_ci(v.get('accuracy'))} | "
                         f"{_ci(v.get('accuracy_offered'))} | {_ci(v.get('none_recall'))} | {b['none']['recall']} | "
                         f"{tr.get('coverage_median')}, {tr.get('wrong_median')} ({tr.get('wrong_p90')}) | "
                         f"{_sci(v.get('gate_coverage'))} | {tr.get('e2e_median')} | {b['flip']} | {b['role']} |")
    L += ["", "## Wording on D4: shared against unique gold description", "",
          "| Model | Control shared | Control unique | Δ shared | Δ unique |", "|---|---:|---:|---|---|"]
    for arm, A in M["decisions"]["D4"]["arms"].items():
        w = A.get("wording", {}).get("vs_control", {})
        L.append(f"| {arm} | {A['control'].get('accuracy_shared_gloss')} | {A['control'].get('accuracy_unique_gloss')} | "
                 f"{_ci(w.get('accuracy_shared_gloss'))} | {_ci(w.get('accuracy_unique_gloss'))} |")
    L += ["", "## Rule filter, narrowed items only", "",
          "| Model | n | Δ accuracy | Δ none recall | Accuracy, one real option left |", "|---|---:|---|---|---:|"]
    for arm, A in M["decisions"]["D4"]["arms"].items():
        n = A.get("rulefilter", {}).get("narrowed")
        if n:
            L.append(f"| {arm} | {n['n']} | {_ci(n['accuracy'])} | {_ci(n['none_recall'])} | {n['single_option_accuracy']} |")
    L += ["", "## Shortlist", "",
          "| Decision | Shortlister | Test recall (median; p10) | List size (median) | Full menu | Chooser | Gold kept | Accuracy | Δ vs full menu | Δ none recall | Gate: coverage, wrong | Role |",
          "|---|---|---|---:|---:|---|---:|---:|---|---|---|---|"]
    for dec, D in M["decisions"].items():
        for s, x in D["shortlist"].items():
            tr = x["transfer"]
            for c, b in x["cells"].items():
                t = b["transfer"]
                L.append(f"| {dec} | {s} | {tr['recall_median']}; {tr['recall_p10']} | {tr['size_median']} | "
                         f"{tr['full_menu_mean']} | {c} | {b['gold_kept']} | {b['accuracy']} | "
                         f"{_ci(b['vs_full_menu']['accuracy'])} | {_ci(b['vs_full_menu']['none_recall'])} | "
                         f"{t.get('coverage_median')}, {t.get('wrong_median')} | {b['role']} |")
    L += ["", "## Verifier: the verifier's P(yes) against the picker's own confidence, on the picker's real picks", "",
          "| Decision | Picker | Picks | Pick accuracy | Own gate: coverage, wrong (p90) | Verifier | Verifier gate: coverage, wrong (p90) | Δ coverage vs own | Catches wrong | Rejects right | AUROC own / verifier |",
          "|---|---|---:|---:|---|---|---|---|---:|---:|---|"]
    for dec, D in M["decisions"].items():
        for p, x in D["verifier"].items():
            o = x["own"]
            for v, b in x["by_verifier"].items():
                L.append(f"| {dec} | {p} | {x['n_picks']} | {x['pick_accuracy']} | {o.get('coverage_median')}, "
                         f"{o.get('wrong_median')} ({o.get('wrong_p90')}) | {v} | {b.get('coverage_median')}, "
                         f"{b.get('wrong_median')} ({b.get('wrong_p90')}) | {_sci(b['coverage_vs_own'])} | "
                         f"{b['catches_wrong']} | {b['rejects_right']} | {o.get('auroc')} / {b['auroc']} |")
    (tdir / "scoreboard.md").write_text("\n".join(L) + "\n")


__all__ = ["cmd_score"]
