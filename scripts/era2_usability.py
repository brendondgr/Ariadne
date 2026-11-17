#!/usr/bin/env python3
"""EXP-2026-11-014: what makes the fast decision models usable (Era 2, between Steps 7 and 8).

Decision servers only (amendment 1): pplx-decider (:7500) and d3-lite (:5107).

    uv run python scripts/era2_usability.py build --control <EXP-013>/data --out <exp>/data
    uv run python scripts/era2_usability.py drift --control <EXP-013>/data --data <exp>/data --arms pplx,d3
    uv run python scripts/era2_usability.py run   --data <exp>/data --treatments wording,... --arms pplx,d3
    uv run python scripts/era2_usability.py score --control <EXP-013>/data --data <exp>/data

``build`` derives every treatment's items from Step 7's items and records (no model call).
``run`` appends one record per (item, arm, order) to ``runs/<treatment>/<arm>.jsonl`` and
resumes where it stopped.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from utils.decision import usability as U  # noqa: E402
from utils.decision.items import NONE, Item, _h  # noqa: E402

SEED = 20261116
ARMS = ("pplx", "d3")
CONCURRENCY = {"pplx": 8, "d3": 4}
CHOICE_TREATMENTS = ("wording", "rulefilter", "shortlist", "verifier")
YESNO_TREATMENTS = ("yesno", "wording_yesno")
Q_GRID = [round(0.50 + 0.01 * i, 2) for i in range(50)]          # 0.50 .. 0.99
SHORTLIST_RECALL = 0.95


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #

def load_items(path: Path) -> list[Item]:
    return [Item.from_json(json.loads(line)) for line in path.open()] if path.is_file() else []


def write_items(path: Path, items: list[Item]) -> None:
    path.write_text("".join(json.dumps(it.to_json(), ensure_ascii=False) + "\n" for it in items))


def records(path: Path) -> dict[tuple[str, int], dict]:
    out: dict[tuple[str, int], dict] = {}
    if path.is_file():
        for line in path.open():
            r = json.loads(line)
            out[(r["item"], r["order"])] = r            # last write wins (a resumed retry)
    return out


def control_records(control: Path, arm: str) -> dict[tuple[str, int], dict]:
    return records(control / "runs" / f"{arm}.jsonl")


def in_role_population(it: Item) -> bool:
    """Step 7's role populations: D4 with 2+ real options or a "none" gold; all of D2 and D3."""
    if len(it.options) < 2:
        return False
    if it.decision == "D4":
        return it.gold == NONE or it.tags.get("real_options", 0) >= 2
    return it.decision in ("D2", "D3")


def decision_group(it: Item) -> str:
    return "D4" if it.decision == "D4" else "D2+D3"


def control_items(control: Path) -> list[Item]:
    return [it for it in load_items(control / "items.jsonl") if in_role_population(it)]


# --------------------------------------------------------------------------- #
# Shortlist fitting (from saved probabilities; no model call)
# --------------------------------------------------------------------------- #

def fit_q(rows: list[tuple[dict[str, float], str]]) -> float:
    """Smallest q whose shortlists keep the gold for >= 0.95 of real-gold rows (1.0 if none does)."""
    real = [(p, g) for p, g in rows if g != NONE]
    for q in Q_GRID:
        if real and sum(g in U.shortlist_keys(p, q) for p, g in real) / len(real) >= SHORTLIST_RECALL:
            return q
    return 1.0


def two_folds(groups: list[str], tag: str) -> tuple[set[str], set[str]]:
    g = sorted(groups)
    random.Random(f"{SEED}|{tag}").shuffle(g)
    return set(g[: len(g) // 2]), set(g[len(g) // 2:])


def shortlist_items(items: list[Item], recs: dict, shortlister: str) -> tuple[list[Item], dict]:
    out, info = [], {}
    by_dec: dict[str, list[Item]] = defaultdict(list)
    for it in items:
        if (it.id, 0) in recs and recs[(it.id, 0)].get("probs"):
            by_dec[decision_group(it)].append(it)
    for dec, its in by_dec.items():
        a, b = two_folds([it.group for it in its], f"crossfit|{dec}")
        rows = {it.id: (recs[(it.id, 0)]["probs"], it.gold) for it in its}
        qa = fit_q([rows[it.id] for it in its if it.group in a])
        qb = fit_q([rows[it.id] for it in its if it.group in b])
        info[dec] = {"q_fold_a": qa, "q_fold_b": qb}
        for it in its:
            q = qb if it.group in a else qa                 # fitted on the other fold
            keep = U.shortlist_keys(rows[it.id][0], q)
            s = U.shortlist_item(it, keep, it.orders()[0])
            out.append(Item(**{**s.to_json(), "id": f"S:{shortlister}:{it.id}",
                               "tags": {**s.tags, "shortlister": shortlister, "parent": it.id, "q": q}}))
    return out, info


# --------------------------------------------------------------------------- #
# build
# --------------------------------------------------------------------------- #

def cmd_build(control: Path, out: Path) -> None:
    items = control_items(control)
    readings = U.load_readings(out / "readings.json")
    keys = U.relation_keys(load_items(control / "items.jsonl"))      # every D4 item, as the brief was written
    problems = U.check_readings(readings, keys)
    assert not problems, problems
    d4 = [it for it in items if it.decision == "D4"]
    wording = [U.wording_item(it, readings) for it in d4]
    rulefilter = [r for it in d4 if (r := U.rulefilter_item(it)) is not None]
    verifier, shortlist, info = [], [], {}
    for picker in ARMS:
        recs = control_records(control, picker)
        for it in items:
            top = (recs.get((it.id, 0)) or {}).get("top")
            if top and top != NONE:
                v = U.verifier_item(it, top)
                verifier.append(Item(**{**v.to_json(), "id": f"V:{picker}:{it.id}",
                                        "tags": {**v.tags, "picker": picker}}))
        s, i = shortlist_items(items, recs, picker)
        shortlist += s
        info[picker] = i
    for name, its in (("wording", wording), ("rulefilter", rulefilter), ("verifier", verifier),
                      ("shortlist", shortlist)):
        write_items(out / f"{name}.jsonl", its)
    summary = {
        "control_items": len(items),
        "by_decision": {d: sum(decision_group(it) == d for it in items) for d in ("D4", "D2+D3")},
        "wording": len(wording), "rulefilter": len(rulefilter),
        "rulefilter_single_option": sum(it.tags["rulefilter_kept"] == 1 for it in rulefilter),
        "verifier": {p: sum(it.tags["picker"] == p for it in verifier) for p in ARMS},
        "shortlist": len(shortlist), "shortlist_q": info,
        "yesno_option_questions": sum(len(it.options) - 1 for it in items),
    }
    (out / "build.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))


# --------------------------------------------------------------------------- #
# run
# --------------------------------------------------------------------------- #

def make_arm(name: str):
    from utils.decision import clients as C

    if name == "pplx":
        import urllib.request

        h = json.loads(urllib.request.urlopen("http://127.0.0.1:7500/health", timeout=10).read())
        return C.Pplx(), {"model": h.get("served_model_name"), "protocol": h.get("protocol", {}).get("version")}
    if name == "d3":
        return C.D3(), {"model": "d3-lite"}
    raise ValueError(f"decision servers only (amendment 1): {name}")


def _run_jobs(path: Path, jobs: list, one, workers: int, label: str) -> None:
    lock = threading.Lock()
    t0 = time.time()
    print(f"{label}: {len(jobs)} requests", flush=True)

    def wrapped(job):
        rec = one(job)
        with lock, open(path, "a") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    with ThreadPoolExecutor(workers) as ex:
        for n, _ in enumerate(ex.map(wrapped, jobs), 1):
            if n % 200 == 0:
                print(f"  {label}: {n}/{len(jobs)} in {time.time() - t0:.0f}s", flush=True)
    print(f"{label}: done in {time.time() - t0:.0f}s", flush=True)


def _done(path: Path) -> set[tuple[str, int]]:
    return {k for k, r in records(path).items() if not r.get("error")}


def run_choice(data: Path, treatment: str, name: str) -> None:
    arm, ident = make_arm(name)
    items = load_items(data / f"{treatment}.jsonl")
    path = data / "runs" / treatment / f"{name}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    done = _done(path)
    jobs = [(it, oi, order) for it in items for oi, order in enumerate(it.orders()) if (it.id, oi) not in done]

    def one(job):
        it, oi, order = job
        try:
            d = arm(it, order)
            return {"item": it.id, "arm": name, "order": oi, "probs": d.probs, "top": d.top, "ms": round(d.ms, 1),
                    "meta": d.meta, "identity": ident}
        except Exception as exc:  # noqa: BLE001 - recorded; a resumed run retries it
            return {"item": it.id, "arm": name, "order": oi, "probs": {}, "top": None, "ms": None,
                    "error": f"{type(exc).__name__}: {exc}"[:300], "identity": ident}

    _run_jobs(path, jobs, one, CONCURRENCY[name], f"{treatment}/{name}")


def run_yesno(data: Path, control: Path, treatment: str, name: str) -> None:
    _, ident = make_arm(name)
    items = control_items(control) if treatment == "yesno" else load_items(data / "wording.jsonl")
    path = data / "runs" / treatment / f"{name}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    done = _done(path)
    jobs = [(it, oi, order) for it in items for oi, order in enumerate(it.orders()) if (it.id, oi) not in done]

    def one(job):
        it, oi, order = job
        try:
            s, ms = U.yesno_batch(name, it, order, yes_first=(oi == 0))
            return {"item": it.id, "arm": name, "order": oi, "s": s, "ms": round(ms, 1), "identity": ident}
        except Exception as exc:  # noqa: BLE001
            return {"item": it.id, "arm": name, "order": oi, "s": {}, "ms": None,
                    "error": f"{type(exc).__name__}: {exc}"[:300], "identity": ident}

    _run_jobs(path, jobs, one, CONCURRENCY[name], f"{treatment}/{name}")


def cmd_run(data: Path, control: Path, treatments: list[str], arms: list[str]) -> None:
    for name in arms:
        for t in treatments:
            if t in CHOICE_TREATMENTS:
                run_choice(data, t, name)
            elif t in YESNO_TREATMENTS:
                run_yesno(data, control, t, name)
            else:
                raise ValueError(t)
        if name == "d3":
            from utils.decision.clients import unload_d3

            unload_d3()


def cmd_drift(data: Path, control: Path, arms: list[str], n: int = 100) -> None:
    items = control_items(control)
    sample = []
    for dec in ("D4", "D2+D3"):
        its = sorted((it for it in items if decision_group(it) == dec), key=lambda it: _h(SEED, "drift", it.id))
        sample += its[:n]
    out = json.loads((data / "drift.json").read_text()) if (data / "drift.json").is_file() else {}
    for name in arms:
        arm, ident = make_arm(name)
        ctrl = control_records(control, name)
        same, rows = 0, []
        for it in sample:
            d = arm(it, it.orders()[0])
            old = (ctrl.get((it.id, 0)) or {}).get("top")
            same += d.top == old
            rows.append({"item": it.id, "now": d.top, "control": old})
        out[name] = {"n": len(sample), "agreement": round(same / len(sample), 4), "identity": ident,
                     "control_kept": same / len(sample) >= 0.97, "rows": rows}
        print(name, out[name]["agreement"], "control kept" if out[name]["control_kept"] else "RE-RUN CONTROL",
              flush=True)
        if name == "d3":
            from utils.decision.clients import unload_d3

            unload_d3()
    (data / "drift.json").write_text(json.dumps(out, indent=1))


def cmd_latency(data: Path, control: Path, arms: list[str], n: int = 40) -> None:
    """Sequential single requests on a seeded sample: one choice call against one batched yes/no call."""
    from utils.decision import score as S

    items = sorted(control_items(control), key=lambda it: _h(SEED, "latency", it.id))[:n]
    out = {}
    for name in arms:
        arm, ident = make_arm(name)
        arm(items[0], items[0].orders()[0])                    # warm-up (d3 loads on first use)
        choice, yesno, qs = [], [], []
        for it in items:
            choice.append(arm(it, it.orders()[0]).ms)
            _, ms = U.yesno_batch(name, it, it.orders()[0], yes_first=True)
            yesno.append(ms)
            qs.append(len(it.options) - 1)
        out[name] = {"choice": S.latency(choice), "yesno_batch": S.latency(yesno), "n": len(items),
                     "mean_questions_per_batch": round(sum(qs) / len(qs), 2), "identity": ident}
        print(name, out[name], flush=True)
        if name == "d3":
            from utils.decision.clients import unload_d3

            unload_d3()
    (data / "latency.json").write_text(json.dumps(out, indent=1))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "drift", "run", "latency", "score"])
    ap.add_argument("--control", type=Path, required=True)
    ap.add_argument("--data", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--arms", default="pplx,d3")
    ap.add_argument("--treatments", default="wording,rulefilter,yesno,wording_yesno,shortlist,verifier")
    a = ap.parse_args(argv)
    if a.cmd == "build":
        cmd_build(a.control, a.out)
    elif a.cmd == "drift":
        cmd_drift(a.data, a.control, a.arms.split(","))
    elif a.cmd == "latency":
        cmd_latency(a.data, a.control, a.arms.split(","))
    elif a.cmd == "run":
        cmd_run(a.data, a.control, a.treatments.split(","), a.arms.split(","))
    else:
        from era2_usability_score import cmd_score  # noqa: PLC0415 - kept apart: long

        cmd_score(a.control, a.data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
