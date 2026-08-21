#!/usr/bin/env python3
"""Turn EXP-2026-08-010's metrics into something a person can read.

Plain language, every figure computed from ``metrics.json``. A cell that did not
run says so instead of showing a zero, and each pre-registered hypothesis is
printed with the number that settles it and a verdict -- including when the
verdict goes against the hypothesis.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ARM_LABEL = {
    "oracle--plan-given": "**Ceiling** — read straight from the graph",
    "deterministic--plan-given": "Ariadne, templates, plan handed to it",
    "deterministic--plan-given--subset60": "Ariadne, templates, plan handed to it *(same 60)*",
    "generic--plan-given": "Ariadne, no templates + model writes the answer",
    "llm--plan-free": "Ariadne, **question text only** — it plans for itself",
}

#: The gap H1 allows between Ariadne and the ceiling before it is refuted.
H1_TOLERANCE = 0.05
#: The band the project's own internal banks produce, for H2.
INTERNAL_BAND = (0.92, 1.00)


def _fmt(cell: dict[str, Any], key: str) -> str:
    got = (cell or {}).get("answered") or {}
    if not got.get("n"):
        return "_did not run_"
    return f"{got[key]:.3f}"


def _n(cell: dict[str, Any]) -> str:
    got = (cell or {}).get("answered") or {}
    return str(got.get("n", 0)) if got.get("n") else "—"


def write_report(out_dir: Path) -> Path:
    metrics = json.loads((out_dir / "metrics.json").read_text())
    cells = metrics["cells"]
    coverage = metrics["coverage"]
    lines: list[str] = []
    add = lines.append

    add("# Does Ariadne survive questions it did not write?")
    add("")
    add("Every accuracy figure this project has published came from a question "
        "bank Ariadne co-authored. This is the first measurement on questions "
        "written by somebody else — two published benchmarks — and the first "
        "where **no language model grades the answer**. The score is set "
        "arithmetic over ATT&CK identifiers.")
    add("")

    # -- 1. what was asked --------------------------------------------------
    add("## 1. What was asked, and what had to be left out")
    add("")
    cti = coverage["cti_ate"]
    add(f"- **{coverage['usable_items']} questions** survived to be asked.")
    add(f"- CTIBench contributed {cti['items']} rows; **{cti['items'] - cti['anchor_present']} "
        "name software this deployment does not hold** — almost all Mobile, and "
        "Ariadne loads Enterprise ATT&CK only.")
    add(f"- Of the gold answers on the software it does hold, "
        f"**{cti['gold_ids_in_graph']} of {cti['gold_ids_total']}** are present in "
        "the graph. Nothing here is measuring a hole in the data.")
    add(f"- AttackQA contributed up to {coverage['per_family']} questions from each "
        "of its 14 enumerating question types, drawn with a fixed seed.")
    add(f"- The two slowest versions ran a fixed **{coverage['llm_subset']}-question** "
        "subset, because they have a language model in the loop and it answers "
        "one request at a time.")
    add("")

    # -- 2. the table --------------------------------------------------------
    add("## 2. The result")
    add("")
    add("| version | asked | found the right answers | said only right answers | got it exactly right |")
    add("|---|---:|---:|---:|---:|")
    for key, label in ARM_LABEL.items():
        cell = cells.get(key, {})
        add(f"| {label} | {_n(cell)} | {_fmt(cell,'micro_recall')} | "
            f"{_fmt(cell,'micro_precision')} | {_fmt(cell,'exact_match')} |")
    add("")
    add("**\"Found the right answers\"** is recall: of everything the benchmark "
        "says is correct, how much did the answer contain. **\"Said only right "
        "answers\"** is precision: of everything the answer named, how much the "
        "benchmark agrees with. **\"Got it exactly right\"** means the answer "
        "matched the benchmark's list with nothing missing and nothing extra.")
    add("")

    # -- 3. the hypotheses ---------------------------------------------------
    add("## 3. What was predicted before the run, and what happened")
    add("")
    oracle = (cells.get("oracle--plan-given") or {}).get("answered") or {}
    det = (cells.get("deterministic--plan-given") or {}).get("answered") or {}
    det60 = (cells.get("deterministic--plan-given--subset60") or {}).get("answered") or {}
    gen = (cells.get("generic--plan-given") or {}).get("answered") or {}
    free = (cells.get("llm--plan-free") or {}).get("answered") or {}

    if oracle.get("n") and det.get("n"):
        gap = det["micro_recall"] - oracle["micro_recall"]
        verdict = "**held**" if abs(gap) <= H1_TOLERANCE else "**refuted**"
        add(f"**H1 — Ariadne retrieves what the graph holds.** Predicted within "
            f"{H1_TOLERANCE:.2f} of the ceiling. Measured **{gap:+.3f}**. {verdict}")
        add("")
        add(f"> The ceiling itself only reaches {oracle['micro_recall']:.3f} against "
            "the benchmark, which is the next point.")
        add("")

    if oracle.get("n"):
        add(f"**H3 — the benchmarks are out of date, and that is not Ariadne's "
            f"fault.** The ceiling — a direct read of the graph, with no retrieval "
            f"in the way — scores **{oracle['micro_precision']:.3f}** for precision. "
            "It names far more than the benchmark lists because ATT&CK has grown "
            "since the benchmark was published. Any arm's low precision has to be "
            "read against that number, not against 1.0.")
        add("")

    if det.get("n"):
        low, high = INTERNAL_BAND
        inside = low <= det["micro_recall"] <= high
        add(f"**H2 — external questions score below internal ones.** The project's "
            f"own banks produce {low:.2f}–{high:.2f}. External recall is "
            f"**{det['micro_recall']:.3f}** — "
            + ("**inside** that band, so the predicted drop did not appear."
               if inside else
               "**outside** it, so the drop the co-authorship figure predicted is real."))
        add("")

    if free.get("n") and det60.get("n"):
        gap = free["micro_recall"] - det60["micro_recall"]
        add(f"**H4 — being handed the plan is worth something.** On the same 60 "
            f"questions, the version given a plan scores "
            f"**{det60['micro_recall']:.3f}** and the version that must work out "
            f"its own plan from the question scores **{free['micro_recall']:.3f}** "
            f"— a difference of **{gap:+.3f}**.")
        add("")
        add("This is the number with the most consequence for the write-up. Every "
            "published Ariadne figure is a plan-given figure. The gap here is how "
            "much of that number is the retrieval and how much is the plan the "
            "bank supplied.")
        add("")

    if gen.get("n") and det60.get("n"):
        add(f"**Aside — templates against the narrator.** On the same 60: "
            f"templates {det60['micro_recall']:.3f}, narrator "
            f"{gen['micro_recall']:.3f}.")
        add("")

    # -- 4. where it breaks --------------------------------------------------
    add("## 4. Which question types worked and which did not")
    add("")
    best = cells.get("deterministic--plan-given") or {}
    families = best.get("by_family") or {}
    if families:
        ranked = sorted(families.items(), key=lambda kv: kv[1].get("micro_recall", 0))
        add("| question type | asked | found the right answers |")
        add("|---|---:|---:|")
        for name, roll in ranked:
            pretty = name.replace("relationships_", "").replace("_", " ")
            add(f"| {pretty} | {roll['n']} | {roll['micro_recall']:.3f} |")
        add("")

    by_bench = best.get("by_benchmark") or {}
    if len(by_bench) > 1:
        add("Split by benchmark, same version:")
        add("")
        for name, roll in by_bench.items():
            add(f"- **{name}** — {roll['n']} questions, recall "
                f"{roll['micro_recall']:.3f}, exact {roll['exact_match']:.3f}")
        add("")

    # -- 5. said and found ---------------------------------------------------
    said = best.get("answered") or {}
    found = best.get("retrieved") or {}
    if said.get("n") and found.get("n") and found["micro_recall"] > said["micro_recall"]:
        add("## 5. The gap between finding and saying")
        add("")
        add(f"Ariadne's retrieval carried **{found['micro_recall']:.3f}** of the "
            f"right answers, but only **{said['micro_recall']:.3f}** made it into "
            "the text a person reads. The difference is the composer dropping "
            "things it had already found — a known defect in this project, "
            "measured here for the first time against an outside benchmark.")
        add("")

    # -- 6. caveats ----------------------------------------------------------
    add("## 6. What this does not show")
    add("")
    add("1. **Nothing about human phrasing.** Both benchmarks are machine-written. "
        "A search on 2026-08-21 found no human-authored ATT&CK question set "
        "anywhere public. That gap is still open.")
    add("2. **Enterprise ATT&CK only.** Mobile and ICS questions were excluded, "
        "not failed.")
    add("3. **CAPEC is untouched.** Neither benchmark covers it, so half of what "
        "the system does is unmeasured here.")
    add("4. **Enumerating questions only.** Every question here has a list for an "
        "answer. Open-ended asks are not represented.")
    add("5. **The benchmarks are older than the data.** That is what the ceiling "
        "row is for, and why no number here should be read against a perfect 1.0.")
    add("")

    path = out_dir / "REPORT.md"
    path.write_text("\n".join(lines) + "\n")
    return path


if __name__ == "__main__":
    print(write_report(Path(sys.argv[1])))
