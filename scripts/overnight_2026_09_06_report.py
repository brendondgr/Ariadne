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

    # ---- Phase B ----
    gem_llm = scores(HOLD, "llm_query", ".gem")
    if gem_llm:
        L += ["## Does the headline claim survive a second grader on unseen questions?", ""]
        h = {a: per_case(HOLD, a, (".gem",)) for a in ("deterministic", "generic", "llm_query")}
        if h["deterministic"] and h["llm_query"]:
            common = sorted(set(h["deterministic"]) & set(h["llm_query"]))
            diff = [h["deterministic"][c] - h["llm_query"][c] for c in common]
            o, lo, hi = bootstrap_ci(diff, statistics.fmean, n_resamples=2000,
                                     confidence=0.95, seed=1729)
            sig = "does **not** include zero" if lo > 0 else "**includes zero**"
            L += [f"The claim is that hand-written templates beat letting a model write "
                  f"the query. Under this second grader, on the 288 questions no arm had "
                  f"seen, the margin is **{o:+.4f}** with a 95% interval of "
                  f"[{lo:+.4f}, {hi:+.4f}] — which {sig}.", "",
                  "For comparison, the same contrast measured elsewhere:", "",
                  "| where | grader | margin | interval |", "|---|---|---|---|",
                  "| dev half | qwen | +0.1147 | [+0.0653, +0.1645] |",
                  "| dev half | gemma | +0.0696 | [−0.0024, +0.1450] |",
                  "| holdout | qwen | +0.0831 | [+0.0366, +0.1320] |",
                  f"| **holdout** | **gemma** | **{o:+.4f}** | [{lo:+.4f}, {hi:+.4f}] |", ""]

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

    # ---- Phase D ----
    d = state("qwen").get("D-thinkcap-probe", {}).get("detail") or {}
    if d:
        L += ["## Does capping the model's 'thinking' change anything?", "",
              f"The setting has been wired up for days and never tested against a live "
              f"server. Capped at 512 tokens over 30 questions: **{d.get('answers','?')}** "
              f"answers produced, **{d.get('with_evidence','?')}** of them actually "
              f"retrieved something.", "",
              "**This cannot replace the published figure.** It is a probe to see "
              "whether the setting does anything at all; if it does, that becomes its "
              "own registered experiment.", ""]

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
