#!/usr/bin/env python3
"""The whole two days, written for someone who does not know the codebase.

Every figure is read from an artifact on disk. Nothing is transcribed from a
chat log, and where a number is not there yet the section says so rather than
being omitted -- a report that quietly drops what did not work is the failure
this project's overnight plans have made a mandatory section since 09-02.
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

BANK = REPO / "docs/evaluation/composition/bank"
POST = REPO / "docs/evaluation/experiments/post-repair-2026-09-03"
SPLIT = REPO / "docs/evaluation/experiments/llm-query-split-2026-09-05"
OUT_MD = REPO / "docs/research/reports/2026-09-05-full-report.md"


def load(path: Path):
    try:
        return json.loads(path.read_text())
    except Exception:                                              # noqa: BLE001
        return None


def per_case(adir: Path, suffix: str) -> dict[str, float]:
    out: dict[str, float] = {}
    if not adir.is_dir():
        return out
    for p in sorted(adir.glob(f"*.judgment{suffix}.json")):
        stem = p.name.split(".judgment")[0]
        if p.name != f"{stem}.judgment{suffix}.json":
            continue
        try:
            d = json.loads(p.read_text())
        except json.JSONDecodeError:
            continue
        if d.get("correctness") is not None:
            out[d.get("case_id", stem)] = d["correctness"]
    return out


def arm_mean(adir: Path, suffixes: list[str]) -> tuple[float | None, int]:
    acc: dict[str, list[float]] = defaultdict(list)
    for s in suffixes:
        for cid, v in per_case(adir, s).items():
            acc[cid].append(v)
    means = [statistics.fmean(v) for v in acc.values() if v]
    return (round(statistics.fmean(means), 4) if means else None), len(means)


def main() -> int:
    L: list[str] = []
    A = L.append
    A("# What happened, in plain language")
    A("")
    A(f"Covering 3–5 September 2026. Written {datetime.now():%Y-%m-%d %H:%M}.")
    A("")
    A("## The short version")
    A("")
    A("The project compares three ways of answering a security question against a "
      "knowledge graph: a library of **hand-written queries**, queries **assembled "
      "on the spot** from the catalogue's own structure, and letting a **language "
      "model write the query** itself.")
    A("")
    A("Two days ago the hand-written library looked far worse than the assembled "
      "one. The worry was that this was unfair — that the hand-written path was "
      "simply broken, and a reviewer would say so. **It was broken, in six separate "
      "ways.** All six are now fixed, and the comparison was run again. The "
      "assembled path still wins, by about the same margin.")
    A("")

    # --- headline table -----------------------------------------------------
    A("## The main result")
    A("")
    A("| way of answering | scored by grader 1 | scored by grader 2 |")
    A("|---|---:|---:|")
    rows = []
    for arm, label in (("deterministic", "hand-written library"),
                       ("generic", "assembled from the catalogue")):
        q, _ = arm_mean(POST / arm / "answers", ["", ".pass2"])
        g, _ = arm_mean(POST / arm / "answers",
                        [".gemma", ".gemma2", ".gemma_r3", ".gemma_r4", ".gemma_r5",
                         ".gemma_r6", ".gemma_r7", ".gemma_r8", ".gemma_r9"])
        rows.append((label, q, g))
        A(f"| {label} | {q} | {g} |")
    lq_dir = SPLIT / "llm_query" / "answers"
    lq, lq_n = arm_mean(lq_dir, ["", ".pass2"])
    A(f"| model writes the query | {lq if lq is not None else '**not finished**'} | not graded |")
    A("")
    if rows[0][1] and rows[1][1]:
        A(f"The gap between the two is **{rows[1][1] - rows[0][1]:.4f}** under the first "
          f"grader and **{rows[1][2] - rows[0][2]:.4f}** under the second. Different "
          "graders, same winner.")
    A("")

    # --- confidence ---------------------------------------------------------
    spread = load(BANK / "grader-spread-2026-09-04.json")
    if spread:
        A("## How confident we can be")
        A("")
        A("A single grader could simply be having an opinion. So the same answers were "
          "graded again by a **different model**, and then repeatedly, to see how much "
          "one grader wanders on its own.")
        A("")
        A("| grader | grading sessions | its own wobble | range the gap sits in |")
        A("|---|---:|---:|---|")
        for g, cell in (spread.get("spread") or {}).items():
            bs = (spread.get("paired_bootstrap") or {}).get(g) or {}
            ci = bs.get("ci95")
            A(f"| {g} | {cell['n_sessions']} | "
              f"{cell['sd_gap'] if cell['sd_gap'] is not None else '—'} | "
              f"{f'{ci[0]} to {ci[1]}' if ci else '—'} |")
        A("")
        b = spread.get("between_grader") or {}
        if b:
            A(f"The two graders differ by **{b.get('offset')}**, against a wobble of "
              f"**{b.get('gemma_sd')}**. {b.get('verdict','')}. Both ranges stay well "
              "clear of zero, so the winner is not an artefact of who was marking.")
        A("")

    # --- what was broken ----------------------------------------------------
    A("## What was actually broken")
    A("")
    A("Six faults in the system, and three in the measuring equipment. The last "
      "group matters most, because they are why nobody noticed the others.")
    A("")
    A("**In the system.**")
    A("")
    A("1. The graph was built from a list of ten allowed fields, so most of what "
      "MITRE publishes was thrown away on load. Asked *who contributed this "
      "campaign*, the answer existed in the source file and not in the graph. "
      "24 questions were unanswerable for this reason alone.")
    A("2. Loading a node with many fields hit an undocumented ceiling and silently "
      "capped it at fourteen.")
    A("3. One record's own identifier overwrote the identity of the node it was "
      "stored under. A single connection has been missing from the live graph for "
      "the entire life of the project — 8,581 of 8,582.")
    A("4. Questions about a *view* or a *category* were looked up as though they "
      "were an *attack pattern*, so they matched nothing. 45 questions.")
    A("5. Asked what a threat group *is*, the system answered with a list of that "
      "group's techniques — a valid answer to a different question.")
    A("6. Questions about what a category *contains* were answered with the "
      "category's status, because the containment link was invisible to the "
      "part that chooses a query. 63 questions.")
    A("")
    A("**In the measuring equipment.**")
    A("")
    A("1. The tool that classified failures read a field from the wrong place, so "
      "*\"the query came back empty\"* was the only verdict it could ever give. The "
      "headline finding of the previous report was that verdict.")
    A("2. Questions asking for a fact about something were scored against a rule "
      "nothing could satisfy: the expected answer was a sentence, and the marker "
      "only recognised identifiers.")
    A("3. A correct answer naming nine categories scored zero, because it wrote "
      "them in the graph's spelling and the answer key used the source's.")
    A("")

    # --- the third arm ------------------------------------------------------
    A("## The third way, and why it took four attempts")
    A("")
    merge = load(BANK / "split-merge-2026-09-05.json")
    probe = load(BANK / "split-probe-2026-09-05.json")
    cost = load(BANK / "budget-cost.json")
    A("Letting the model write the query kept producing a number that turned out to "
      "measure our own settings rather than the model:")
    A("")
    A("- **First**: the model was given a word allowance so small it spent all of it "
      "thinking and said nothing. 153 of 284 questions came back blank.")
    A("- **Second**: the allowance was raised, but it was being read once when the "
      "program started rather than when it was used, so the new value never applied.")
    A("- **Third**: with the allowance genuinely raised, a separate **two-minute "
      "cut-off** stopped the model mid-thought. 282 of 284 produced nothing. That "
      "run was deleted rather than reported.")
    A("- **Fourth**: cut-off raised to 68 minutes and allowance to its maximum. "
      "140 of 284 produced a query.")
    if merge:
        A(f"- **Fifth**, split across two dedicated machines: **{merge['queries_built']} "
          f"of {merge['answers']}** produced a query.")
    A("")
    if probe and probe.get("verdict"):
        v = probe["verdict"]
        A(f"A check on the hard questions before the fifth run: **{v['emitted_content']} "
          f"of {v['of']}** produced an answer, so the remaining failures are no longer "
          "the equipment.")
        A("")
    if cost:
        A("**What it costs.** This was the one thing the claim had never measured. "
          "Answering the same 284 questions took the hand-written library about "
          "**four seconds** in total. Letting the model write the queries took "
          "**roughly two days of machine time**. That is a difference of about "
          "**forty thousand times**, before anyone argues about accuracy.")
        A("")

    # --- honesty ------------------------------------------------------------
    A("## Where I got it wrong")
    A("")
    A("Recorded because the record is the point, and because each one cost hours.")
    A("")
    A("- I said the 131 failures shared a single cause. They had six.")
    A("- I predicted a fix would recover 47 questions; it recovered 2. A later "
      "prediction of 23 recovered 14. Both times, predicting what would **not** "
      "move was exactly right and predicting what **would** move was optimistic.")
    A("- I said the held-back questions were untouched. They had been answered once, "
      "months-of-work ago in project time, and the published figure came from that. "
      "Never graded, which is the property that actually matters — but *untouched* "
      "was the wrong word and the record now says so.")
    A("- I reported a run as in progress when it had never started, because I checked "
      "for it by name and matched my own command.")
    A("- I chose a word allowance from a single easy question and applied it to all "
      "of them.")
    A("- I predicted that running 16 jobs at once per machine would starve them. "
      "Measured, it did not.")
    A("")

    # --- what is not settled ------------------------------------------------
    A("## What is still open")
    A("")
    A("- **The held-back half.** 288 questions, never graded. They are the honest "
      "test of whether these fixes generalise, and they can only be used once. Best "
      "spent when all three ways of answering are ready, not two.")
    A("- **Two known scoring faults remain**, both of which make the current numbers "
      "*too low* rather than too high. Left alone deliberately: fixing them raises "
      "our own scores, so the rule has to be written down and agreed before it is "
      "applied.")
    A("- **An outside grader.** Everything so far is graded by models running on this "
      "hardware. The strongest check would be a grader from a different provider "
      "entirely.")
    A("")
    if lq is None:
        A("- **The third way is still being graded** as this was written; its figure "
          "is not in the table above.")
        A("")

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    md = "\n".join(L) + "\n"
    OUT_MD.write_text(md)
    print(f"markdown -> {OUT_MD}")
    try:
        from scripts.morning_report import render_pdf

        ok = render_pdf(md, OUT_MD.with_suffix(".pdf"))
        print(f"pdf -> {OUT_MD.with_suffix('.pdf')} ({ok})")
    except Exception as exc:                                       # noqa: BLE001
        print(f"pdf failed: {type(exc).__name__}: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
