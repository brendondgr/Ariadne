#!/usr/bin/env python3
"""EXP-2026-11-012 amendment 5: the same questions, worded by a second writer (Era 2, Step 6).

The anchors, gold answers, splits and kinds of the Qwen-worded run are kept; only the text is
rewritten, by a writer that is not the agent's planner model (Q61). Template questions
(relation ambiguity, out of coverage) were never model-written and are copied unchanged.

    uv run python scripts/era2_card_reword.py export   --data <exp>/data --batches 20
    # writer agents read <exp>/data/sonnet/jobs/batch-NN.json, write answers/batch-NN.json
    uv run python scripts/era2_card_reword.py check    --data <exp>/data [--retry-batches 4]
    # retry agents read jobs/retry-NN.json, write answers/retry-NN.json
    uv run python scripts/era2_card_reword.py assemble --data <exp>/data --banks docs/evaluation/banks
    # a blind proxy reader (not the writer's model) reads sonnet/review-sheet.json -> sonnet/proxy-read.json
    uv run python scripts/era2_card_reword.py metrics  --data <exp>/data

Each job carries the same rules the Qwen writer got (``card_generator.question_rules`` and the
reference prompts) and nothing of the Qwen text. ``check`` applies the generator's own checks;
a failing job gets one retry naming the problems, as the Qwen writer did; then it is dropped.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from utils.specialists.evalset import card_generator as CG  # noqa: E402

BANK_NAME = "card-sonnet-2026-11-16"
WRITER = "claude-sonnet-5-5 (medium effort, Claude Code subagents)"
REF_TIERS = ("reworded_name", "description")


def _load(data: Path) -> list[dict]:
    return [json.loads(line) for line in (data / "questions.jsonl").open()]


def _card(ds: str) -> dict:
    return json.loads((REPO / "data/source_cards" / f"{ds}.json").read_text())


def _slot(q: dict) -> CG.Slot:
    return CG.Slot(**q["card_gen"]["slot"])


def _is_template(q: dict) -> bool:
    cg = q["card_gen"]
    return cg["kind"] == "out_of_coverage" or cg.get("ambiguity") == "relation"


def build_jobs(qs: list[dict]) -> list[dict]:
    """One writing job per model-written question, carrying everything the writer may see."""
    import era2_card_bank as B
    from utils.specialists.gremlin.normalizer import public_member_id
    from utils.specialists.schema.namesearch import index_for

    bes, (drv, cli) = B.backends()
    node_cache: dict[tuple[str, str], dict] = {}

    def nodes(ds: str, label: str) -> dict:
        if (ds, label) not in node_cache:
            node_cache[(ds, label)] = {str(n["id"]): n for n in bes[ds].nodes(label)}
        return node_cache[(ds, label)]

    jobs = []
    try:
        for q in qs:
            if _is_template(q):
                continue
            cg, ds = q["card_gen"], q["task"]["source"]
            card, slot, tier = _card(ds), _slot(q), cg["tier"]
            public = public_member_id if ds == "capec" else (lambda i: i)
            job: dict = {"id": q["id"], "dataset": ds, "kind": cg["kind"], "tier": tier}
            if cg["kind"] == "ambiguous":           # entity ambiguity: the shared name, written as-is
                ref = cg["clarification"]["question"].split("'", 1)[1].rsplit("'", 1)[0]
            elif tier in ("identifier", "synonym_relation", "paraphrased_schema"):
                ref = cg["anchor"]
            elif tier == "name":
                ref = str(nodes(ds, slot.label)[cg["anchor_storage"]].get("name") or "")
            else:
                a = cg["anchor_storage"]
                node = nodes(ds, slot.label)[a]
                ix = index_for(ds)
                forb = CG.name_forbidden_words({**node, "id": public(a)}, lambda w, ix=ix: ix.token_df(w) <= 0.01) \
                    + ([a] if a != public(a) else [])
                job["reference_task"] = {
                    "instructions": CG.SYS_REWORD if tier == "reworded_name" else CG.SYS_DESCRIBE,
                    "entry": CG.reference_entry({**node, "id": public(a)}, slot.label),
                    "forbidden": [w for w in forb if w]}
                ref = "{REFERENCE}"
            job["reference"] = None if ref == "{REFERENCE}" else ref
            job["question_instructions"] = CG.SYS_QUESTION
            job["rules"] = CG.question_rules(card, slot, ref, tier)
            jobs.append(job)
    finally:
        cli.close()
        drv.close()
    return jobs


def check_answer(job: dict, ans: dict | None, q: dict) -> list[str]:
    """The generator's own checks, applied to one agent answer."""
    if not ans or not (ans.get("question") or "").strip():
        return ["no answer"]
    text = CG._one_line(ans["question"])
    card, slot, tier = _card(job["dataset"]), _slot(q), job["tier"]
    probs: list[str] = []
    if job.get("reference_task"):
        ref = CG._one_line(ans.get("reference") or "").rstrip(".")
        if not ref:
            return ["no reference written"]
        probs += [f"reference uses forbidden '{w}'" for w in CG.reference_problems(ref, job["reference_task"]["forbidden"])]
        probs += CG.question_problems(card, slot, ref, tier, text, name_forbidden=job["reference_task"]["forbidden"])
    else:
        probs += CG.question_problems(card, slot, job["reference"], tier, text)
    return probs


def _answers(d: Path, prefix: str) -> dict[str, dict]:
    out = {}
    for f in sorted((d / "answers").glob(f"{prefix}-*.json")):
        for a in json.loads(f.read_text()):
            out[a["id"]] = a
    return out


def cmd_export(data: Path, batches: int) -> None:
    qs = _load(data)
    jobs = build_jobs(qs)
    d = data / "sonnet" / "jobs"
    d.mkdir(parents=True, exist_ok=True)
    for i in range(batches):
        part = jobs[i::batches]
        (d / f"batch-{i + 1:02d}.json").write_text(json.dumps(part, indent=1, ensure_ascii=False))
    (data / "sonnet" / "answers").mkdir(exist_ok=True)
    c = Counter((j["dataset"], j["kind"], j["tier"]) for j in jobs)
    print(json.dumps({"jobs": len(jobs), "templates_kept": len(qs) - len(jobs), "batches": batches,
                      "cells": {"|".join(k): v for k, v in sorted(c.items())}}, indent=1))


def cmd_check(data: Path, retry_batches: int) -> None:
    d = data / "sonnet"
    qs = {q["id"]: q for q in _load(data)}
    jobs = {j["id"]: j for f in sorted((d / "jobs").glob("batch-*.json")) for j in json.loads(f.read_text())}
    first, retry = _answers(d, "batch"), _answers(d, "retry")
    status, retry_jobs = {}, []
    for jid, job in jobs.items():
        p1 = check_answer(job, first.get(jid), qs[jid])
        if not p1:
            status[jid] = {"ok": True, "attempts": 1}
            continue
        if jid in retry:
            p2 = check_answer(job, retry[jid], qs[jid])
            status[jid] = {"ok": not p2, "attempts": 2, "problems": [p1, p2]}
        else:
            status[jid] = {"ok": False, "attempts": 1, "problems": [p1]}
            prev = first.get(jid) or {}
            retry_jobs.append({**job, "previous_attempt": {"reference": prev.get("reference"),
                                                           "question": prev.get("question")},
                               "previous_problems": p1})
    (d / "check.json").write_text(json.dumps(status, indent=1))
    if retry_jobs and not retry:
        n = max(1, min(retry_batches, len(retry_jobs)))
        for i in range(n):
            (d / "jobs" / f"retry-{i + 1:02d}.json").write_text(json.dumps(retry_jobs[i::n], indent=1, ensure_ascii=False))
    ok = sum(s["ok"] for s in status.values())
    by = Counter((jobs[j]["dataset"], jobs[j]["tier"], s["ok"]) for j, s in status.items())
    print(json.dumps({"jobs": len(jobs), "answered_first": len(first), "ok": ok,
                      "failing": len(jobs) - ok, "retry_jobs_written": len(retry_jobs) if not retry else 0,
                      "retry_answers": len(retry),
                      "cells": {f"{a}|{b}|{'ok' if c else 'fail'}": v for (a, b, c), v in sorted(by.items())}}, indent=1))


def cmd_assemble(data: Path, banks: Path | None) -> None:
    import era2_card_bank as B
    from utils.specialists.gremlin.normalizer import public_member_id

    d = data / "sonnet"
    status = json.loads((d / "check.json").read_text())
    first, retry = _answers(d, "batch"), _answers(d, "retry")
    out_q = []
    for q in _load(data):
        cg = q["card_gen"]
        if _is_template(q):
            # Amendment 7: template questions in plain words ("attack patterns", not "AttackPattern entries").
            card = _card(q["task"]["source"])
            q["card_gen"]["template_question_raw"] = q["question"]
            q["question"] = q["task"]["text"] = CG.plain_template_text(card, q["question"])
            clar = q["card_gen"].get("clarification")
            if clar:
                clar["question"] = CG.plain_template_text(card, clar["question"].replace(" do you mean?", " entries do you mean?")
                                                          if " entries" not in clar["question"] else clar["question"])
            q["card_gen"]["writer"] = "template"
            out_q.append(q)
            continue
        st = status[q["id"]]
        if not st["ok"]:
            continue
        a = (retry if st["attempts"] == 2 else first)[q["id"]]
        text = CG._one_line(a["question"])
        q["card_gen"]["qwen_question"] = q["question"]
        q["question"] = q["task"]["text"] = text
        q["card_gen"]["writer"] = WRITER
        q["card_gen"]["attempts"] = st["attempts"]
        if a.get("reference") and cg["tier"] in REF_TIERS:
            q["card_gen"]["reference"] = CG._one_line(a["reference"]).rstrip(".")
        out_q.append(q)
    bes, (drv, cli) = B.backends()
    report: dict = {"writer": WRITER, "source_run": "data/questions.jsonl (Qwen-worded, run 4)", "datasets": {}}
    try:
        for ds in ("attack", "capec"):
            card = _card(ds)
            public = public_member_id if ds == "capec" else (lambda i: i)
            qs = [q for q in out_q if q["task"]["source"] == ds]
            regolds = [B.regold(q, bes[ds], public) for q in qs]
            report["datasets"][ds] = {
                "questions": len(qs), "gold_reexecuted_match": f"{sum(regolds)}/{len(regolds)}",
                "split_overlap": sorted(CG.split_overlap(qs)), "leak_audit": CG.leak_audit(card, qs),
                "by_kind": dict(Counter(q["card_gen"]["kind"] for q in qs)),
                "by_writer": dict(Counter(q["card_gen"]["writer"] for q in qs)),
                "by_split": dict(Counter(q["split"] for q in qs)),
                "by_decision": dict(Counter(q["card_gen"]["decision"] for q in qs)),
            }
    finally:
        cli.close()
        drv.close()
    src = {q["id"]: q for q in _load(data)}
    for ds in ("attack", "capec"):
        mine = {jid: st for jid, st in status.items() if src[jid]["task"]["source"] == ds}
        report["datasets"][ds]["dropped"] = dict(Counter(
            f"{src[j]['card_gen']['kind']}:{src[j]['card_gen']['tier']}" for j, st in mine.items() if not st["ok"]))
        report["datasets"][ds]["retried"] = sum(st["attempts"] == 2 for st in mine.values())
    report["global_split_overlap"] = sorted(CG.split_overlap(out_q))
    report["total_questions"] = len(out_q)
    sheet = B.review_sheet(out_q, 50, 20261116)
    (d / "review-sheet.json").write_text(json.dumps(sheet, indent=1))
    lines = ["# Review sheet: 50 questions, Sonnet-worded (PROTOCOL amendments 5-7)", "",
             "For each: is it fluent English an analyst might ask (yes/no)? For ambiguous ones: is it really "
             "ambiguous between the listed readings (yes/no)?", "",
             "| # | Dataset | Kind | Tier | Question | Readings | Fluent? | Truly ambiguous? |",
             "|---|---|---|---|---|---|---|---|"]
    for r in sheet:
        rd = "; ".join(o["label"] for o in r["readings"]) if r["readings"] else ""
        lines.append(f"| {r['n']} | {r['dataset']} | {r['kind']} | {r['tier']} | {r['question'].replace('|', '/')} "
                     f"| {rd} | | |")
    (d / "review-sheet.md").write_text("\n".join(lines) + "\n")
    if banks:
        meta = {"generator": "utils/specialists/evalset/card_generator.py + scripts/era2_card_reword.py",
                "model": WRITER, "created": time.strftime("%Y-%m-%d"), "seed": 20261116,
                "paired_with": "card-2026-11-16 (same ids, Qwen-worded)"}
        report["banks"] = CG.write_banks(out_q, banks, BANK_NAME, meta)
    (d / "card_bank.json").write_text(json.dumps(report, indent=1))
    with open(d / "questions.jsonl", "w") as fh:
        for q in out_q:
            fh.write(json.dumps(q, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "banks"}, indent=1)[:5000])


def cmd_metrics(data: Path) -> None:
    """``data/sonnet/metrics.json``: the paired wording comparison and the proxy read."""
    import re

    d = data / "sonnet"
    cb = json.loads((d / "card_bank.json").read_text())
    qs = [json.loads(line) for line in (d / "questions.jsonl").open()]
    w = [q for q in qs if q["card_gen"]["writer"] != "template"]

    def literal(text: str, q: dict) -> bool:
        return bool(re.search(rf"\b{q['card_gen']['slot']['target']}", text))

    m: dict = {"writer": cb["writer"], "total_questions": len(qs), "rewritten": len(w),
               "templates_plain_rendered": len(qs) - len(w), "datasets": {}}
    for ds, r in cb["datasets"].items():
        m["datasets"][ds] = {k: r[k] for k in ("questions", "gold_reexecuted_match", "by_kind", "by_split",
                                               "by_decision", "dropped", "retried")}
        m["datasets"][ds]["G2_split_overlap"] = len(r["split_overlap"])
        m["datasets"][ds]["G3_leaks"] = len(r["leak_audit"])
    m["G2_global_split_overlap"] = len(cb["global_split_overlap"])
    m["paired_wording"] = {
        "identical_text": sum(q["question"] == q["card_gen"]["qwen_question"] for q in w),
        "schema_label_verbatim": {"qwen": sum(literal(q["card_gen"]["qwen_question"], q) for q in w),
                                  "sonnet": sum(literal(q["question"], q) for q in w)},
        "median_words": {"qwen": sorted(len(q["card_gen"]["qwen_question"].split()) for q in w)[len(w) // 2],
                         "sonnet": sorted(len(q["question"].split()) for q in w)[len(w) // 2]},
    }
    pr = d / "proxy-read.json"
    if pr.exists():
        p = json.loads(pr.read_text())
        items = p["items"]
        amb = [i for i in items if i["kind"] == "ambiguous"]
        m["E2_proxy"] = {"reader": p["reader"], "n": len(items), "fluent": sum(bool(i["fluent"]) for i in items),
                         "ambiguous_truly": f"{sum(bool(i['truly_ambiguous']) for i in amb)}/{len(amb)}",
                         "rejected": [{"n": i["n"], "id": i["id"], "kind": i["kind"], "tier": i["tier"],
                                       "note": i["note"]} for i in items
                                      if not i["fluent"] or (i["kind"] == "ambiguous" and not i["truly_ambiguous"])]}
    if "E2_proxy" in m:
        m["E2_proxy"]["fluent_fraction"] = round(m["E2_proxy"]["fluent"] / m["E2_proxy"]["n"], 4)
    (d / "metrics.json").write_text(json.dumps(m, indent=1))
    # The experiment's data/metrics.json carries these too, under "sonnet" (the manifest reads from it).
    top = data / "metrics.json"
    if top.exists():
        tm = json.loads(top.read_text())
        tm["sonnet"] = m
        top.write_text(json.dumps(tm, indent=1))
    print(json.dumps(m, indent=1))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["export", "check", "assemble", "metrics"])
    ap.add_argument("--data", required=True, type=Path)
    ap.add_argument("--batches", type=int, default=20)
    ap.add_argument("--retry-batches", type=int, default=4)
    ap.add_argument("--banks", type=Path, default=None)
    a = ap.parse_args(argv)
    if a.cmd == "export":
        cmd_export(a.data, a.batches)
    elif a.cmd == "check":
        cmd_check(a.data, a.retry_batches)
    elif a.cmd == "assemble":
        cmd_assemble(a.data, a.banks)
    else:
        cmd_metrics(a.data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
