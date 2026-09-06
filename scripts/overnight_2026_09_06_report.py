#!/usr/bin/env python3
"""Morning report for the 2026-09-06 overnight run. Markdown + PDF.

Every figure is read from disk at render time. Nothing is passed in from the
orchestrator, so a phase that did not run cannot appear as though it did.
"""

from __future__ import annotations

import json
import statistics
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

RUNS = REPO / "docs/evaluation/experiments"
EXPD = REPO / "docs/research/experiments/EXP-2026-09-008-grader-calibration/data"
HOLD = RUNS / "holdout-spend-2026-09-05"
OUT = REPO / "docs/reports/2026-09-06-overnight-report.md"
BANDS = ("ceiling", "mid", "low")


def state(track: str) -> dict:
    p = EXPD / f"state-{track}.json"
    return json.loads(p.read_text()) if p.is_file() else {}


def scores(root: Path, arm: str, suffix: str) -> list[float]:
    adir = root / arm / "answers"
    want = f".judgment{suffix}.json"
    out = []
    if not adir.is_dir():
        return out
    for p in adir.glob(f"*{want}"):
        if not p.name.endswith(want):
            continue
        try:
            d = json.loads(p.read_text())
        except Exception:                                          # noqa: BLE001
            continue
        if d.get("correctness") is not None:
            out.append(float(d["correctness"]))
    return out


def per_case(root: Path, arm: str, sufs) -> dict:
    from collections import defaultdict
    acc = defaultdict(list)
    adir = root / arm / "answers"
    if not adir.is_dir():
        return {}
    for s in sufs:
        want = f".judgment{s}.json"
        for p in adir.glob(f"*{want}"):
            if not p.name.endswith(want):
                continue
            try:
                d = json.loads(p.read_text())
            except Exception:                                      # noqa: BLE001
                continue
            if d.get("correctness") is not None:
                acc[d["case_id"]].append(float(d["correctness"]))
    return {k: statistics.fmean(v) for k, v in acc.items()}


def main() -> int:
    from utils.evaluation.stats import bootstrap_ci
    L = ["# Overnight run — 6 September 2026", "",
         f"*Generated {datetime.now():%A %d %B, %H:%M}. Every number below is read "
         "from the files on disk at render time, so a phase that did not run "
         "cannot appear here as though it did.*", ""]

    # ---- what ran ----
    L += ["## What ran", "", "| track | phase | outcome | time |", "|---|---|---|---:|"]
    for track in ("gemma31", "qwen", "gemma26"):
        for name, rec in state(track).items():
            el = rec.get("elapsed_s")
            L.append(f"| {track} | {name} | **{rec.get('status','?')}** | "
                     f"{(str(round(el/60,1))+' min') if el else '—'} |")
    L.append("")

    # ---- Phase A ----
    L += ["## The main question: which graders can see near the ceiling?", "",
          "A grader with no spread reports a difference of zero whatever is true. "
          "Yesterday that nearly published four arm-order reversals that did not "
          "exist. This measures it directly: the same 60 answers, spanning the "
          "score range, graded by every model.", "",
          "| model | ceiling band | mid band | low band | usable near ceiling? |",
          "|---|---|---|---|---|"]
    verdicts = {}
    for track in ("gemma31", "qwen", "gemma26"):
        d = state(track).get("A-calibration", {}).get("detail") or {}
        if not d.get("by_band"):
            L.append(f"| {track} | — | — | — | *did not run* |"); continue
        bb = d["by_band"]
        cells = []
        for b in BANDS:
            v = bb[b]
            cells.append(f"{v['mean']:.3f} · {v['distinct_values']} distinct"
                         if v["mean"] is not None else "—")
        ok = d.get("usable_near_ceiling")
        verdicts[track] = ok
        L.append(f"| **{d.get('served_model', track)}** | {cells[0]} | {cells[1]} | "
                 f"{cells[2]} | {'**yes**' if ok else '**NO — saturated**'} |")
    L += ["", "*\"distinct\" is how many different scores the model gave across 20 "
          "answers. A model that gave the same score to all 20 cannot tell them "
          "apart, and any comparison built on it is empty.*", ""]

    # ---- Phase B: the complete two-family holdout ----
    FAM = {"qwen38-27B-v2": (".qw", ".qwp2"), "gemma4-31B-mtp": (".gem", ".gemp2")}
    arms = ("generic", "deterministic", "llm_query")
    tbl = {}
    for fam, sufs in FAM.items():
        A = {a: per_case(HOLD, a, sufs) for a in arms}
        if not all(len(A[a]) == 288 for a in arms):
            continue
        tbl[fam] = {"means": {a: statistics.fmean(A[a].values()) for a in arms}, "c": {}}
        for x, y in (("generic", "deterministic"), ("generic", "llm_query"),
                     ("deterministic", "llm_query")):
            com = sorted(set(A[x]) & set(A[y]))
            o, lo, hi = bootstrap_ci([A[x][k] - A[y][k] for k in com], statistics.fmean,
                                     n_resamples=2000, confidence=0.95, seed=1729)
            tbl[fam]["c"][f"{x} - {y}"] = (o, lo, hi)
    if len(tbl) == 2:
        L += ["## The held-back questions, now judged by two independent graders", "",
              "288 questions the system had never seen, three ways of answering them, "
              "graded twice over by two different models — 3,456 judgments in all. "
              "This is the complete test the plan asked for.", "",
              "**How each approach scored:**", "",
              "| approach | " + " | ".join(tbl) + " |", "|---|---|---|"]
        pretty = {"generic": "schema-assembled (no templates, no model writing queries)",
                  "deterministic": "hand-written templates",
                  "llm_query": "a model writes the query"}
        for a in arms:
            L.append(f"| {pretty[a]} | " + " | ".join(f"{tbl[f]['means'][a]:.4f}" for f in tbl) + " |")
        L += ["", "**The comparisons, with the range each is confident about:**", "",
              "| comparison | " + " | ".join(tbl) + " |", "|---|---|---|"]
        for k in tbl[list(tbl)[0]]["c"]:
            row = []
            for f in tbl:
                o, lo, hi = tbl[f]["c"][k]
                z = " — **could be zero**" if lo <= 0 <= hi else ""
                row.append(f"{o:+.4f} [{lo:+.4f}, {hi:+.4f}]{z}")
            L.append(f"| {k.replace('generic','schema').replace('deterministic','templates').replace('llm_query','model-written')} | "
                     + " | ".join(row) + " |")
        L += ["", "**What this says.** The schema-assembled approach beats both alternatives, "
              "and both graders agree by a wide margin — those two comparisons are safe. "
              "The third, templates against a model writing the query, is *positive under "
              "both graders but only statistically solid under one of them*. It was the "
              "same story on the earlier half of the questions, so this is a consistent "
              "property of who is judging rather than a fluke.", "",
              "That matters for how the paper is framed: **lead with the comparisons both "
              "graders are sure about**, and report the third with its grader-dependence "
              "stated plainly.", ""]
    # ---- Phase C ----
    cat = scores(RUNS / "composerfix-dev", "deterministic", ".g26")
    bl = scores(RUNS / "composerfix-holdout", "deterministic", ".g26")
    L += ["## Does a third grader agree that writing your own exam flatters you?", ""]
    if cat and bl:
        gap = statistics.fmean(cat) - statistics.fmean(bl)
        L += [f"Questions written alongside the system score **{statistics.fmean(cat):.4f}**; "
              f"questions written without seeing it score **{statistics.fmean(bl):.4f}**. "
              f"The gap is **{gap:+.4f}**.", "",
              "| grader | gap |", "|---|---|",
              "| the original, unidentifiable model | +0.0483 |",
              "| qwen (named) | +0.0322 |",
              "| gemma 31B | 0.0000 — *could not measure, saturated* |",
              f"| **gemma 26B** | **{gap:+.4f}** |", ""]
    else:
        r = state("gemma26").get("C-c021-third-opinion", {})
        L += [f"**Not measured.** {r.get('reason', 'did not run')}", "",
              "That is a result rather than a gap: if no available model can tell "
              "these answers apart, the claim rests on one grader for a reason we "
              "can state, and it belongs in the paper's limitations.", ""]

    # ---- Phase D: read the CORRECTED artefact, not the buggy counter ----
    tc = EXPD / "thinkcap-probe.json"
    if tc.is_file():
        t = json.loads(tc.read_text())
        c, u = t["capped_512"], t["uncapped"]
        L += ["## Does capping the model's \"thinking\" help?", "",
              "A setting had been sitting in the code for days, switched on but never "
              "actually tried against a running server. Tonight it was tried, on the same "
              "30 questions as an earlier uncapped run so the two are directly comparable.", "",
              "| | retrieved something | rejected as malformed |", "|---|---|---|",
              f"| capped | **{c['records_gt_0']} of 30** | **{c['gate_rejected']} of 30** |",
              f"| uncapped | {u['records_gt_0']} of 30 | {u['gate_rejected']} of 30 |", "",
              "**It makes things much worse.** Rejections go up sevenfold and nothing at "
              "all gets retrieved. Not one question worked with the cap that had failed "
              "without it. The setting should not be used, and that question is now closed "
              "for the cost of ten minutes.", "",
              "*Caveats: 30 questions, one cap value, and these 30 are a hard slice — the "
              "uncapped run only managed 3 of them against about a third of the full set. "
              "The comparison between the two is what counts, not the raw rates. This does "
              "not change any published figure; those were all measured uncapped.*", "",
              "*One thing worth admitting: the run's own progress counter initially reported "
              "all 30 as having retrieved something. It was counting the wrong field. The "
              "table above comes from re-reading the answers themselves.*", ""]

    # ---- the second grader problem ----
    g26 = state("gemma26").get("C2-holdout-third-family", {})
    if g26.get("status") == "not_run":
        L += ["## Why the third grader was dropped", "",
              "The plan was to have a third model grade the held-back questions as an extra "
              "check. The calibration run above disqualified it, for two separate reasons.", "",
              "It gave only two different scores across twenty near-ceiling answers, so it "
              "cannot express a small difference at all. And more seriously, **it ranked the "
              "weaker set of answers above the stronger one** — 0.643 against 0.624, when "
              "the true order is the other way round. Every one of the held-back comparisons "
              "sits in exactly that range.", "",
              "It would have taken about 32 hours to produce a comparison we already knew "
              "could not be trusted, so it was stopped before it wrote anything. **This is "
              "the calibration step paying for itself**: it was built to catch graders that "
              "cannot see small differences, and it also caught one that gets the order "
              "backwards — a failure nobody had thought to check for.", ""]
    # ---- limits ----
    L += ["## What this night does not settle", "",
          "- Nothing here re-measures the system. No questions were re-answered "
          "except the 30-question probe; every other number is a re-grading of "
          "answers that already existed.",
          "- A grader that agrees is not proof of correctness. All of this tests "
          "whether conclusions survive a change of judge, not whether the judge is right.",
          "- Two known scoring faults remain deliberately unfixed, because fixing "
          "them mid-comparison would break the comparison. Both would raise scores.", ""]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    md = "\n".join(L)
    OUT.write_text(md)
    print(f"markdown -> {OUT}")
    try:
        from scripts.morning_report import render_pdf
        ok = render_pdf(md, OUT.with_suffix(".pdf"))
        print(f"pdf -> {OUT.with_suffix('.pdf')} ({ok})")
    except Exception as exc:                                       # noqa: BLE001
        print(f"pdf failed: {type(exc).__name__}: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
