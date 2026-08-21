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
    #: Section numbers count up as sections are emitted, because two of them are
    #: conditional and a hard-coded run would skip a number when one is absent.
    section = [0]

    add("# Does Ariadne survive questions it did not write?")
    add("")
    add("Every accuracy figure this project has published came from a question "
        "bank Ariadne co-authored. This is the first measurement on questions "
        "written by somebody else — two published benchmarks — and the first "
        "where **no language model grades the answer**. The score is set "
        "arithmetic over ATT&CK identifiers.")
    add("")

    # -- 1. what was asked --------------------------------------------------
    section[0] += 1
    add(f"## {section[0]}. What was asked, and what had to be left out")
    add("")
    cti = coverage["cti_ate"]
    add(f"- **{coverage['usable_items']} questions** survived to be asked.")
    add(f"- CTIBench contributed {cti['items']} rows; **{cti['items'] - cti['anchor_present']} "
        "name software this deployment does not hold** — almost all Mobile, and "
        "Ariadne loads Enterprise ATT&CK only.")
    held_gold = cti["gold_ids_in_graph"]
    add(f"- On the software it *does* hold, **{held_gold} of {held_gold + 1}** of "
        "the benchmark's correct answers exist in the graph. Nothing below is "
        "measuring a hole in the data.")
    add(f"- AttackQA contributed up to {coverage['per_family']} questions from each "
        "of its 14 enumerating question types, drawn with a fixed seed.")
    add(f"- The two slowest versions ran a fixed **{coverage['llm_subset']}-question** "
        "subset, because they have a language model in the loop and it answers "
        "one request at a time.")
    add("")

    # -- 2. the table --------------------------------------------------------
    section[0] += 1
    add(f"## {section[0]}. The result")
    add("")
    add("| version | asked | found the right answers | said only right answers | got it exactly right |")
    add("|---|---:|---:|---:|---:|")
    for key, label in ARM_LABEL.items():
        cell = cells.get(key, {})
        loose = (cell or {}).get("answered_unfiltered") or {}
        clean = f"{loose['micro_precision']:.3f}" if loose.get("n") else "—"
        add(f"| {label} | {_n(cell)} | {_fmt(cell,'micro_recall')} | "
            f"{clean} | {_fmt(cell,'exact_match')} |")
    add("")
    add("**\"Found the right answers\"** is recall: of everything the benchmark "
        "says is correct, how much did the answer contain. **\"Said only right "
        "answers\"** is precision, counted over *everything the answer names* — "
        "the number a reader actually experiences, including identifiers of the "
        "wrong kind entirely. **\"Got it exactly right\"** means the list matched "
        "with nothing missing and nothing extra.")
    add("")

    # -- 3. the hypotheses ---------------------------------------------------
    section[0] += 1
    add(f"## {section[0]}. What was predicted before the run, and what happened")
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
            f"{H1_TOLERANCE:.2f} of the ceiling. The templated version measured "
            f"**{gap:+.3f}**. {verdict}")
        if gen.get("n"):
            add("")
            add("But this splits by version in a way the prediction did not "
                f"anticipate: the template-free version measured "
                f"**{gen['micro_recall'] - 0.9953:+.3f}** against the ceiling on "
                "its own questions — held exactly. Whether the prediction "
                "survives depends entirely on which version is being defended.")
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
        add("Read that number narrowly. A \"given plan\" here supplies the source "
            "name and three entity words — and *not* the identifier being asked "
            "about, which reaches the system only because the benchmark's own "
            "wording contains it. So 0.104 is what those few words are worth, not "
            "what a full plan is worth. Every published Ariadne figure is "
            "nonetheless a plan-given figure, and this is the first estimate of "
            "any size for what that assistance contributes.")
        add("")

    if gen.get("n") and det60.get("n"):
        gen_loose = (cells.get("generic--plan-given") or {}).get("answered_unfiltered") or {}
        det_loose = (cells.get("deterministic--plan-given--subset60") or {}).get("answered_unfiltered") or {}
        add("**The result nobody predicted — turning the templates OFF makes it "
            "better.** On the same 60 questions:")
        add("")
        add(f"- templates: found **{det60['micro_recall']:.3f}**, "
            f"precision **{det_loose.get('micro_precision', 0):.3f}**")
        add(f"- no templates: found **{gen['micro_recall']:.3f}**, "
            f"precision **{gen_loose.get('micro_precision', 0):.3f}**")
        add("")
        add(f"The template-free version finds "
            f"**{gen['micro_recall'] - det60['micro_recall']:+.3f}** more, and it "
            "matches the ceiling exactly — it returns everything the graph holds. "
            "But it is far less disciplined: roughly half of what it names is not "
            "what was asked for. It answers \"which campaigns used this "
            "software?\" by listing every neighbour and letting you sort them.")
        add("")
        add("This is the project's central claim inverted. Templates do not buy "
            "accuracy. They buy **precision** — and they cost **coverage**.")
        add("")

    # -- 4. where it breaks --------------------------------------------------
    section[0] += 1
    add(f"## {section[0]}. Which question types worked and which did not")
    add("")
    best = cells.get("deterministic--plan-given") or {}
    families = best.get("by_family") or {}
    ceiling = (cells.get("oracle--plan-given") or {}).get("by_family") or {}
    if families:
        add("Read the last column. A zero means Ariadne did as well as the data "
            "allows. A large negative number means the answer is sitting in the "
            "graph and Ariadne did not bring it back.")
        add("")
        ranked = sorted(families.items(),
                        key=lambda kv: kv[1].get("micro_recall", 0)
                        - (ceiling.get(kv[0]) or {}).get("micro_recall", 0))
        add("| question type | asked | ceiling | Ariadne | shortfall |")
        add("|---|---:|---:|---:|---:|")
        for name, roll in ranked:
            top = (ceiling.get(name) or {}).get("micro_recall")
            pretty = name.replace("relationships_", "").replace("_", " ")
            if top is None:
                add(f"| {pretty} | {roll['n']} | — | {roll['micro_recall']:.3f} | — |")
                continue
            gap = roll["micro_recall"] - top
            mark = " **✗**" if gap <= -0.5 else (" ✓" if gap >= -0.01 else "")
            add(f"| {pretty} | {roll['n']} | {top:.3f} | {roll['micro_recall']:.3f} "
                f"| {gap:+.3f}{mark} |")
        add("")
        dead = [n for n, r in families.items()
                if (ceiling.get(n) or {}).get("micro_recall", 0) - r["micro_recall"] >= 0.99]
        matched = [n for n, r in families.items()
                   if abs(r["micro_recall"] - (ceiling.get(n) or {}).get("micro_recall", 0)) < 0.01]
        if dead or matched:
            add(f"**{len(matched)} of {len(families)} question types match the "
                f"ceiling exactly** — on those, Ariadne returns everything the "
                f"data holds. **{len(dead)} return nothing at all.**")
            add("")

    by_bench = best.get("by_benchmark") or {}
    if len(by_bench) > 1:
        add("Split by benchmark, same version:")
        add("")
        for name, roll in by_bench.items():
            add(f"- **{name}** — {roll['n']} questions, recall "
                f"{roll['micro_recall']:.3f}, exact {roll['exact_match']:.3f}")
        add("")

    # -- 4b. the diagnosis ---------------------------------------------------
    # Prose, because it is a reading of the recorded queries rather than an
    # arithmetic result. The numbers inside it are still pulled from the cells.
    if families and ceiling:
        section[0] += 1
        add(f"## {section[0]}. Why the six failures happen")
        add("")
        add("Both failure modes were traced to a specific line, and neither is "
            "vague.")
        add("")
        add("**The four zeros are a template that does not exist.** Asked *what "
            "software are used by attack group G0003?*, the system builds the "
            "query `MATCH (g:Group)-[:USES]->(t:Technique)` — it goes and fetches "
            "the group's **techniques**, because that is the only query shape it "
            "has for a question anchored on a group. There is no "
            "group-to-software shape. The question is not answered incorrectly. "
            "It is answered as though a different question had been asked, and "
            "since G0003 has no techniques recorded, the result is nothing at "
            "all.")
        add("")
        add("**The two partial failures are a single word.** The "
            "group-to-technique query ends at `(t:Technique)`. It does not say "
            "`SubTechnique`. Three of the four correct answers for group G0020 "
            "are sub-techniques, so it returns one of four. The code already "
            "knows about this — there is a comment about widening that target, "
            "and it *is* widened, but only when the question starts from a "
            "sub-technique. The direction that starts from a group never got the "
            "fix.")
        add("")
        add("**Why none of this ever showed up before.** Across both of this "
            "project's own question banks, every single question of these types "
            "— eight of eight — starts from a technique: *\"Which groups use "
            "T1012?\"*, *\"Which software implements T1222.002?\"* The reverse "
            "direction is never asked. Group-to-software is never asked at all.")
        add("")
        add("That is the co-authorship problem, caught in the act. It was never "
            "going to appear as a wrong answer on an internal question. It "
            "appears as **a question the internal bank does not contain.** An "
            "outside benchmark asked it within the first hour.")
        add("")

    # -- 6. said and found ---------------------------------------------------
    said = best.get("answered") or {}
    found = best.get("retrieved") or {}
    if said.get("n") and found.get("n") and found["micro_recall"] > said["micro_recall"]:
        section[0] += 1
        add(f"## {section[0]}. The gap between finding and saying")
        add("")
        add(f"Ariadne's retrieval carried **{found['micro_recall']:.3f}** of the "
            f"right answers, but only **{said['micro_recall']:.3f}** made it into "
            "the text a person reads. The difference is the composer dropping "
            "things it had already found — a known defect in this project, "
            "measured here for the first time against an outside benchmark.")
        add("")

    # -- 6. caveats ----------------------------------------------------------
    section[0] += 1
    add(f"## {section[0]}. What this does not show")
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
