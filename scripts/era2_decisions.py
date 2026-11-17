#!/usr/bin/env python3
"""EXP-2026-11-013: which decisions can small models own (Era 2, Step 7).

    uv run python scripts/era2_decisions.py build --phase A --out <exp>/data
    uv run python scripts/era2_decisions.py run   --data <exp>/data --arms qwen_prob,pplx,d3,qwen_reason [--decisions D4,D2,D3]
    uv run python scripts/era2_decisions.py score --data <exp>/data

``build`` writes ``items.jsonl``. ``run`` appends one record per (item, arm,
order) to ``runs/<arm>.jsonl`` and resumes where it stopped. The baseline
answers in the first order only. ``score`` writes ``metrics.json`` and
``tables/roles.md``.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from utils.decision import score as S  # noqa: E402
from utils.decision.items import Item  # noqa: E402

CONCURRENCY = {"qwen_reason": 8, "qwen_prob": 8, "pplx": 8, "d3": 4}
# decision -> role cap: the Phase C small tests can earn at most "gate" (PROTOCOL, role rule)
CAP = {d: "gate" for d in ("D1", "D5", "D6", "D7", "D8", "D9", "D10", "D12")}


def backend_for_factory():
    import era2_card_bank as B
    from utils.specialists.gremlin.normalizer import public_member_id

    bes, closers = B.backends()
    pub = {"attack": (lambda i: i), "capec": public_member_id}
    return (lambda ds: (bes[ds], pub[ds])), closers


def used_anchors() -> set[str]:
    from utils.killtests.t3.generate import excluded_anchors

    out = set(excluded_anchors())
    for p in (REPO / "docs/evaluation/banks").glob("card-*/bank.json"):
        for q in json.loads(p.read_text())["questions"]:
            cg = q["card_gen"]
            out |= {cg.get("anchor")} | set((cg.get("readings") or {}) if cg.get("ambiguity") == "entity" else ())
            if cg.get("other_anchor"):
                out.add(cg["other_anchor"])
    out.discard(None)
    return out


def load_items(data: Path) -> list[Item]:
    return [Item.from_json(json.loads(line)) for line in (data / "items.jsonl").open()]


def cmd_build(out: Path, phase: str) -> None:
    from utils.decision.items import grounding_items, relation_items, tuning_questions
    from utils.specialists.schema import get_registry

    out.mkdir(parents=True, exist_ok=True)
    qs = tuning_questions()
    items: list[Item] = []
    report: dict = {"phase": phase, "tuning_questions": len(qs)}
    if phase == "A":
        d4 = relation_items(qs, get_registry())
        g, recall = grounding_items(qs)
        items = d4 + g
        report["bm25_recall_at_8"] = recall
    elif phase in ("B", "C"):
        from utils.decision import items_bc as BC

        sys.path.insert(0, str(REPO / "scripts"))
        backend_for, (drv, cli) = backend_for_factory()
        try:
            reg = get_registry()
            if phase == "B":
                items = BC.exit_items(qs, reg, backend_for, used_anchors())
            else:
                items = (BC.d1_items(qs) + BC.d7_items(qs, reg, backend_for) + BC.d9_items(qs, reg, backend_for)
                         + BC.d8_items(qs, reg) + BC.d10_items(backend_for) + BC.d6_items(qs) + BC.d12_items()
                         + BC.d5_items())
        finally:
            cli.close()
            drv.close()
    path = out / "items.jsonl"
    old = [json.loads(line) for line in path.open()] if path.exists() else []
    keep = [o for o in old if o["decision"] not in {i.decision for i in items}]
    with open(path, "w") as fh:
        for o in keep:
            fh.write(json.dumps(o, ensure_ascii=False) + "\n")
        for it in items:
            fh.write(json.dumps(it.to_json(), ensure_ascii=False) + "\n")
    by = defaultdict(int)
    for it in items:
        by[it.decision] += 1
    report["items"] = dict(by)
    (out / f"build-{phase}.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))


def make_arm(name: str):
    from utils.decision import clients as C

    if name in ("qwen_reason", "qwen_prob"):
        from utils.llm.registry import load, require_identity

        spec = load().default
        ident = require_identity(spec)
        arm = C.QwenReason(spec) if name == "qwen_reason" else C.QwenProb(spec)
        return arm, {"model": spec.name, "identity_token": ident.last_token_id}
    if name == "pplx":
        h = json.loads(__import__("urllib.request").request.urlopen("http://127.0.0.1:7500/health", timeout=10).read())
        return C.Pplx(), {"model": h.get("served_model_name"), "protocol": h.get("protocol", {}).get("version")}
    if name == "d3":
        return C.D3(), {"model": "d3-lite"}
    raise ValueError(name)


def cmd_run(data: Path, arms: list[str], decisions: set[str] | None) -> None:
    items = [i for i in load_items(data) if not decisions or i.decision in decisions]
    (data / "runs").mkdir(exist_ok=True)
    for name in arms:
        arm, ident = make_arm(name)
        path = data / "runs" / f"{name}.jsonl"
        done = set()
        if path.exists():
            for line in path.open():
                r = json.loads(line)
                if r.get("top") is not None or r.get("error"):
                    done.add((r["item"], r["order"]))
        jobs = []
        for it in items:
            orders = it.orders()
            for oi, order in enumerate(orders[:1] if name == "qwen_reason" else orders):
                if (it.id, oi) not in done:
                    jobs.append((it, oi, order))
        lock = threading.Lock()
        t0 = time.time()
        print(f"{name}: {len(jobs)} calls to make ({ident})", flush=True)

        def one(job):
            it, oi, order = job
            try:
                d = arm(it, order)
                rec = {"item": it.id, "arm": name, "order": oi, "probs": d.probs, "top": d.top, "ms": round(d.ms, 1),
                       "meta": d.meta, "identity": ident}
            except Exception as exc:  # noqa: BLE001 - recorded, scored as no answer
                rec = {"item": it.id, "arm": name, "order": oi, "probs": {}, "top": None, "ms": None,
                       "error": f"{type(exc).__name__}: {exc}"[:300], "identity": ident}
            with lock, open(path, "a") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            return rec

        with ThreadPoolExecutor(CONCURRENCY[name]) as ex:
            for n, _ in enumerate(ex.map(one, jobs), 1):
                if n % 100 == 0:
                    print(f"  {name}: {n}/{len(jobs)} in {time.time() - t0:.0f}s", flush=True)
        print(f"{name}: done in {time.time() - t0:.0f}s", flush=True)
        if name == "d3":
            from utils.decision.clients import unload_d3

            unload_d3()


def _records(data: Path) -> dict[str, dict[tuple[str, int], dict]]:
    out: dict[str, dict] = {}
    for p in sorted((data / "runs").glob("*.jsonl")):
        recs = {}
        for line in p.open():
            r = json.loads(line)
            recs[(r["item"], r["order"])] = r           # last write wins (a resumed retry)
        out[p.stem] = recs
    return out


ROLE_POPULATION = {
    "D4": lambda it: it.gold == "none" or it.tags.get("real_options", 0) >= 2,
}


def cmd_score(data: Path) -> None:
    # An item with a single option decides nothing (D4 "none" variants of one-relation labels): dropped
    # for every arm alike (ISSUES 2026-11-16).
    items = [it for it in load_items(data) if len(it.options) >= 2]
    recs = _records(data)
    by_dec: dict[str, list[Item]] = defaultdict(list)
    for it in items:
        by_dec[it.decision].append(it)
    # D2 and D3 are one decision for roles (grounding with "none of these").
    role_sets = {"D4": ["D4"], "D2+D3": ["D2", "D3"], **{d: [d] for d in by_dec if d not in ("D4", "D2", "D3")}}
    metrics: dict = {"decisions": {}}
    lines = ["# Roles: decision × model (EXP-2026-11-013)", "",
             "| Decision | Model | n | Accuracy | Wrong at 90 / 70 / 50% | Threshold transfer: coverage, wrong (median; p90) | Flip | AUROC | ECE | Median ms | Role |",
             "|---|---|---:|---:|---|---|---:|---:|---:|---:|---|"]
    for rname, decs in role_sets.items():
        pop = [it for d in decs for it in by_dec.get(d, [])]
        if not pop:
            continue
        rule = ROLE_POPULATION.get(rname, lambda it: True)
        role_pop = [it for it in pop if rule(it)]
        base = recs.get("qwen_reason", {})
        base_rows = [(base.get((it.id, 0), {}).get("top"), 1.0, it.gold) for it in role_pop]
        base_acc = S.accuracy(base_rows)
        dm: dict = {"n_items": len(pop), "n_role_population": len(role_pop), "arms": {}}
        for arm in ("qwen_reason", "qwen_prob", "pplx", "d3"):
            r = recs.get(arm)
            if not r:
                continue
            if not any((it.id, 0) in r for it in pop):
                continue                      # this arm has not answered this decision
            rows_all = []
            by_stratum: dict[str, list] = defaultdict(list)
            strat_groups: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
            groups: dict[str, list] = defaultdict(list)
            for it in pop:
                rec = r.get((it.id, 0))
                if rec is None:
                    continue
                p, c = S.top_of(rec.get("probs") or {})
                row = (p, c, it.gold)
                rows_all.append(row)
                by_stratum[it.stratum].append(row)
                strat_groups[it.stratum][it.group].append(row)
                if rule(it):
                    groups[it.group].append(row)
            role_rows = [x for g in groups.values() for x in g]
            first = {it.id: (r.get((it.id, 0)) or {}).get("top") for it in role_pop}
            second = {it.id: (r.get((it.id, 1)) or {}).get("top") for it in role_pop if (it.id, 1) in r}
            flip = S.flip_rate(first, second) if arm != "qwen_reason" else None
            agree = S.flip_rate(first, {it.id: base.get((it.id, 0), {}).get("top") for it in role_pop})
            am = {
                "n": len(rows_all), "accuracy": S.accuracy(rows_all),
                "accuracy_role_population": S.accuracy(role_rows),
                "accuracy_by_stratum": {k: [S.accuracy(v), len(v)] for k, v in sorted(by_stratum.items())},
                "none": S.none_pr(rows_all),
                "errors": sum(1 for it in pop if (r.get((it.id, 0)) or {}).get("error")),
                "latency": S.latency([x["ms"] for x in r.values() if x.get("ms") and x["item"] in {i.id for i in pop}]),
                "agreement_with_baseline": None if agree is None else round(1 - agree, 4),
            }
            if arm != "qwen_reason":
                t = S.transfer(groups)
                au = S.auroc(role_rows)
                am.update({"ece": S.ece(role_rows), "auroc": au, "flip": flip,
                           "wrong_at": {str(c): S.wrong_at_coverage(role_rows, c) for c in (0.9, 0.7, 0.5)},
                           "transfer": t,
                           # split by anchor within the stratum, as for the whole population
                           "transfer_by_stratum": {k: S.transfer(dict(strat_groups[k]), splits=200)
                                                   for k, v in sorted(by_stratum.items()) if len(v) >= 20},
                           "role": S.role(t, flip, au, am["accuracy_role_population"], base_acc,
                                          cap=CAP.get(rname))})
            else:
                am["role"] = "baseline"
            dm["arms"][arm] = am
            w = am.get("wrong_at", {})
            t = am.get("transfer", {})
            lines.append(
                f"| {rname} | {arm} | {am['n']} | {am['accuracy']} | "
                + (f"{w.get('0.9')} / {w.get('0.7')} / {w.get('0.5')}" if w else "—") + " | "
                + (f"{t.get('coverage_median')}, {t.get('wrong_median')} ({t.get('wrong_p90')})" if t else "—")
                + f" | {am.get('flip', '—')} | {am.get('auroc', '—')} | {am.get('ece', '—')} | "
                f"{am['latency']['median_ms']} | {am['role']} |")
        # The size-matched control: accept only when the three probability arms agree.
        if all(a in recs for a in ("qwen_prob", "pplx", "d3")):
            acc_n, wrong_n = 0, 0
            for it in role_pop:
                tops = {recs[a].get((it.id, 0), {}).get("top") for a in ("qwen_prob", "pplx", "d3")}
                if len(tops) == 1 and None not in tops:
                    acc_n += 1
                    wrong_n += next(iter(tops)) != it.gold
            dm["agreement_gate"] = {"coverage": round(acc_n / len(role_pop), 4) if role_pop else None,
                                    "wrong": round(wrong_n / acc_n, 4) if acc_n else None}
        metrics["decisions"][rname] = dm
    if (data / "latency.json").is_file():          # the sequential probe (cmd_latency), when taken
        metrics["latency_sequential"] = json.loads((data / "latency.json").read_text())
    (data / "metrics.json").write_text(json.dumps(metrics, indent=1))
    tdir = data.parent / "tables"
    tdir.mkdir(exist_ok=True)
    (tdir / "roles.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    for k, v in metrics["decisions"].items():
        if "agreement_gate" in v:
            print(k, "agreement gate", v["agreement_gate"])


def cmd_latency(data: Path, arms: list[str], n: int = 40) -> None:
    """Single, sequential calls on a seeded sample of items (the protocol's latency measure)."""
    from utils.decision.items import _h

    items = sorted(load_items(data), key=lambda it: _h(20261116, "latency", it.id))
    items = [it for it in items if len(it.options) >= 2][:n]
    out = {}
    for name in arms:
        arm, ident = make_arm(name)
        ms = []
        for it in items[: (n // 2 if name == "qwen_reason" else n)]:
            try:
                ms.append(arm(it, it.orders()[0]).ms)
            except Exception:  # noqa: BLE001 - a failed call has no latency
                continue
        out[name] = {**S.latency(ms), "n": len(ms), "identity": ident}
        print(name, out[name], flush=True)
        if name == "d3":
            from utils.decision.clients import unload_d3

            unload_d3()
    (data / "latency.json").write_text(json.dumps(out, indent=1))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "run", "score", "latency"])
    ap.add_argument("--out", type=Path)
    ap.add_argument("--data", type=Path)
    ap.add_argument("--phase", default="A")
    ap.add_argument("--arms", default="qwen_prob,pplx,d3,qwen_reason")
    ap.add_argument("--decisions", default="")
    a = ap.parse_args(argv)
    if a.cmd == "build":
        cmd_build(a.out, a.phase)
    elif a.cmd == "run":
        cmd_run(a.data, a.arms.split(","), set(filter(None, a.decisions.split(","))) or None)
    elif a.cmd == "latency":
        cmd_latency(a.data, a.arms.split(","))
    else:
        cmd_score(a.data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
