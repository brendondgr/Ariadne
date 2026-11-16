#!/usr/bin/env python3
"""EXP-2026-11-012: questions generated from the ATT&CK and CAPEC cards alone (Era 2, Step 6).

    uv run python scripts/era2_card_bank.py --out <experiment>/data [--banks docs/evaluation/banks] [--small]

Generates, validates and writes the banks:
- gold re-executed in keyset mode for every answerable, insufficient and ambiguous reading;
- tuning and held-out splits checked for shared anchors;
- the automatic leak audit re-run on the final synonym and schema questions;
- banks written per dataset x decision step x split, held-out ones marked sealed and hashed;
- a 50-question review sheet for a person (fluency, and whether ambiguous ones really are).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from utils.specialists.evalset import card_generator as CG  # noqa: E402

BANK_NAME = "card-2026-11-16"


def writer_for(spec, temperature: float = 0.7):
    from utils.llm.toolcalls import chat

    def w(system: str, user: str) -> str:
        r = chat(spec, [{"role": "system", "content": system}, {"role": "user", "content": user}],
                 temperature=temperature)
        return r.text or ""
    return w


def backends():
    from gremlin_python.driver import client as gc
    from neo4j import GraphDatabase

    from utils.agent.exact import CypherBackend, GremlinBackend
    from utils.config import load_env
    from utils.specialists.config import SpecialistConfig

    load_env()
    sc = SpecialistConfig.from_env()
    drv = GraphDatabase.driver(sc.endpoint_for("neo4j", "attack"), auth=(sc.neo4j_user, sc.neo4j_password))
    cli = gc.Client(sc.endpoint_for("gremlin", "capec"), "g")
    return {"attack": CypherBackend(drv, id_props=("attack_id", "id")),
            "capec": GremlinBackend(cli, id_props=("id",))}, (drv, cli)


def regold(q: dict, backend, public) -> bool:
    """Re-execute a question's gold in keyset mode (a second fetch path) and compare."""
    from utils.agent.exact import SetSpec, fetch

    cg = q["card_gen"]

    def ids(spec):
        return sorted(public(i) for i in fetch(backend, spec, mode="keyset", page_size=50).ids)

    if cg["kind"] == "out_of_coverage":
        return True
    if cg["kind"] == "ambiguous":
        for key, want in (cg.get("readings") or {}).items():
            if cg.get("ambiguity") == "relation":
                _ds, label, rel, direction, target = key.split("|")
                got = ids(SetSpec((cg["anchor_storage"],), rel, direction, target, label))
            else:
                s, info = cg["slot"], cg["readings_storage"][key]
                if not want:
                    continue       # a candidate whose label lacks the facet reads as empty by construction
                got = ids(SetSpec((info["storage"],), s["rel"], s["direction"], s["target"], info["label"]))
            if got != sorted(want):
                return False
        return True
    s = cg["slot"]
    return ids(SetSpec((cg["anchor_storage"],), s["rel"], s["direction"], s["target"], s["label"])) == \
        sorted(cg["gold_ids"])


def review_sheet(questions: list[dict], n: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    by = defaultdict(list)
    for q in questions:
        by[(q["card_gen"]["kind"], q["card_gen"]["tier"])].append(q)
    picks = []
    keys = sorted(by)
    while len(picks) < n and any(by.values()):
        for k in keys:
            if by[k] and len(picks) < n:
                picks.append(by[k].pop(rng.randrange(len(by[k]))))
    return [{"n": i + 1, "id": q["id"], "dataset": q["task"]["source"], "kind": q["card_gen"]["kind"],
             "tier": q["card_gen"]["tier"], "question": q["question"],
             "readings": q["card_gen"].get("clarification", {}).get("options") if q["card_gen"]["kind"] == "ambiguous" else None}
            for i, q in enumerate(picks)]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--banks", default=None, help="write banks under this dir (omit for a dry run)")
    ap.add_argument("--small", action="store_true")
    a = ap.parse_args(argv)
    from utils.killtests.t3.generate import excluded_anchors
    from utils.llm.registry import load, require_identity
    from utils.specialists.schema import get_registry
    from utils.specialists.schema.namesearch import index_for

    spec = load().default
    ident = require_identity(spec)
    w = writer_for(spec)
    bes, closers = backends()
    registry = get_registry()
    exclude = frozenset(excluded_anchors())
    cfg = CG.GenConfig(exclude=exclude, workers=32)
    if a.small:
        cfg = CG.GenConfig(exclude=exclude, workers=32, anchors_per_slot=1, ambiguous=4, out_of_coverage=4,
                           insufficient=4)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    report: dict = {"model": f"{spec.name}/{ident.last_token_id}", "config": {k: v for k, v in vars(cfg).items()
                                                                               if k != "exclude"},
                    "excluded_anchors": len(exclude), "datasets": {}}
    allq: list[dict] = []
    for ds in ("attack", "capec"):
        card = json.loads((REPO / "data/source_cards" / f"{ds}.json").read_text())
        ix = index_for(ds)
        t = time.time()
        from utils.specialists.gremlin.normalizer import public_member_id
        public = public_member_id if ds == "capec" else (lambda i: i)
        g = CG.generate(card, registry, bes[ds], w, cfg, rare=lambda wd, ix=ix: ix.token_df(wd) <= 0.01,
                        public=public)
        regolds = [regold(q, bes[ds], public) for q in g.questions]
        qs = g.questions
        counts = Counter((q["card_gen"]["kind"], q["card_gen"]["tier"], q["split"]) for q in qs)
        report["datasets"][ds] = {
            "seconds": round(time.time() - t, 1), "questions": len(qs), "notes": g.notes,
            "dropped": dict(g.dropped),
            "gold_reexecuted_match": f"{sum(regolds)}/{len(regolds)}",
            "split_overlap": sorted(CG.split_overlap(qs)),
            "leak_audit": CG.leak_audit(card, qs),
            "by_kind": dict(Counter(q["card_gen"]["kind"] for q in qs)),
            "by_tier_answerable": dict(Counter(q["card_gen"]["tier"] for q in qs if q["card_gen"]["kind"] == "answerable")),
            "by_split": dict(Counter(q["split"] for q in qs)),
            "by_decision": dict(Counter(q["card_gen"]["decision"] for q in qs)),
            "cells": {"|".join(k): v for k, v in sorted(counts.items())},
            "gold_sizes": {"median": sorted(len(q["card_gen"]["gold_ids"]) for q in qs if q["card_gen"]["kind"] == "answerable")[
                len([1 for q in qs if q["card_gen"]["kind"] == "answerable"]) // 2] if qs else None},
        }
        allq += qs
        print(ds, json.dumps({k: v for k, v in report["datasets"][ds].items() if k not in ("cells", "leak_audit")}))
    report["global_split_overlap"] = sorted(CG.split_overlap(allq))
    report["total_questions"] = len(allq)
    sheet = review_sheet(allq, 50, 20261116)
    (out / "review-sheet.json").write_text(json.dumps(sheet, indent=1))
    lines = ["# Review sheet: 50 generated questions", "",
             "For each: is it fluent English an analyst might ask (yes/no)? For ambiguous ones: is it really ambiguous between the listed readings (yes/no)?", "",
             "| # | Dataset | Kind | Tier | Question | Readings | Fluent? | Truly ambiguous? |", "|---|---|---|---|---|---|---|---|"]
    for r in sheet:
        rd = "; ".join(o["label"] for o in r["readings"]) if r["readings"] else ""
        lines.append(f"| {r['n']} | {r['dataset']} | {r['kind']} | {r['tier']} | {r['question'].replace('|', '/')} | {rd} | | |")
    (out / "review-sheet.md").write_text("\n".join(lines) + "\n")
    if a.banks:
        meta = {"generator": "utils/specialists/evalset/card_generator.py", "model": report["model"],
                "created": "2026-11-16", "seed": cfg.seed}
        report["banks"] = CG.write_banks(allq, Path(a.banks), BANK_NAME, meta)
    (out / "card_bank.json").write_text(json.dumps(report, indent=1, default=str))
    with open(out / "questions.jsonl", "w") as fh:
        for q in allq:
            fh.write(json.dumps(q, ensure_ascii=False) + "\n")
    drv, cli = closers
    cli.close()
    drv.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
