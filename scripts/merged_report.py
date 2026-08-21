#!/usr/bin/env python3
"""Turn EXP-2026-08-009's state file into something a person can read.

Plain language throughout. Every figure is computed from `state.json` and the
judgment files on disk; nothing is transcribed by hand, and a phase that did not
run says so rather than showing a zero.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

ARM_NAMES = {
    "merged": "ONE database holding both catalogues",
    "generic_composed": "TWO databases, everything else identical",
    "generic": "Two databases, no templates, answer written by a language model",
    "deterministic": "Two databases, pre-written templates",
}

#: The pair that isolates the architecture. Everything else in these two is the
#: same code with the same flags; only the number of stores differs.
COMPARISON = ("merged", "generic_composed")

BANK_NAMES = {
    "bank20260819": "question set 1",
    "bank20260820": "question set 2",
}


def _cells(state: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    """(arm, bank) -> roll-up, recomputed from the judgment files on disk.

    The phase result carries a roll-up too, but it is a snapshot from the moment
    that phase ended. A case regraded afterwards — the oversized ones need a
    third attempt at a larger budget — lands on disk and never reaches the
    cached copy, so a report built from the cache silently keeps saying n=29.
    The phases are read only to learn which cells exist.
    """
    from scripts.overnight_sweep import roll_up

    experiments = REPO / "docs" / "evaluation" / "experiments"
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for phase in state["phases"]:
        if phase.get("status") != "ok" or "judge" not in phase["name"]:
            continue
        result = phase.get("result") or {}
        arm, bank = result.get("arm"), result.get("bank")
        if not arm or not bank:
            continue
        roll = roll_up(experiments / bank, arm, suffix=".c015")
        if roll.get("n"):
            out[(arm, bank)] = roll
    return out


def write_report(out_dir: Path) -> Path:
    state = json.loads((out_dir / "state.json").read_text())
    cells = _cells(state)
    banks = [b for b in BANK_NAMES if any(k[1] == b for k in cells)]
    lines: list[str] = []
    add = lines.append

    add("# Is it worth keeping the two databases apart?")
    add("")
    # A phase carrying no status yet is the one currently running — which,
    # while this function executes, is always the phase that writes this
    # report. Counting it as a failure made every report announce a failure it
    # had itself caused.
    finished = [p for p in state["phases"] if p.get("status")]
    failed = [p for p in finished if p["status"] != "ok"]
    add(f"**Run started** {state.get('started')} · "
        f"**phases** {len(state['phases'])}, {len(failed)} failed")
    add("")
    add("The project's pitch is that keeping MITRE ATT&CK and MITRE CAPEC in two "
        "separate databases, each spoken to in its own language, is worth the "
        "extra complexity. Nobody had ever checked, because the alternative — "
        "pour both into one database and ask it one question — had never been "
        "built. It has now.")
    add("")

    # -- 1. the comparison --------------------------------------------------
    add("## 1. The comparison")
    add("")
    add("Every row below answered **the same questions**, with **the same plan**, "
        "and was graded by **the same grader in the same session**.")
    add("")
    add("**Read the first two rows against each other and ignore the rest.** They "
        "are the same code with the same settings; the only difference is how "
        "many databases sit behind them, and neither has a language model in it, "
        "so neither wanders between runs. The third row disables the templates "
        "*and* hands the writing to a language model — it is the study's "
        "strongest version, but comparing it with the first row would be "
        "comparing two things at once.")
    add("")
    if cells:
        header = "| version | " + " | ".join(BANK_NAMES[b] for b in banks) + " |"
        add(header)
        add("|---|" + "---:|" * len(banks))
        for arm, label in ARM_NAMES.items():
            row = [label]
            for bank in banks:
                roll = cells.get((arm, bank))
                if not roll:
                    row.append("_did not run_")
                    continue
                lo, hi = roll["correctness"]["ci95"]
                row.append(f"**{roll['correctness']['mean']:.4f}** ({lo:.3f}–{hi:.3f})")
            add("| " + " | ".join(row) + " |")
        add("")
        add("Figures are judged correctness from 0 to 1, with a 95% confidence "
            "range over the 30 questions in each set.")
        add("")

        merged_vs = []
        for bank in banks:
            m, g = cells.get((COMPARISON[0], bank)), cells.get((COMPARISON[1], bank))
            if m and g:
                merged_vs.append((bank, m["correctness"]["mean"] - g["correctness"]["mean"]))
        if merged_vs:
            add("**Merging minus federating, on the like-for-like comparison:**")
            add("")
            for bank, delta in merged_vs:
                add(f"- {BANK_NAMES[bank]}: **{delta:+.4f}**")
            add("")
            worst = max(abs(d) for _, d in merged_vs)
            if worst < 0.0050:
                add("Every difference is smaller than the grader's own run-to-run "
                    "spread of 0.0050, measured earlier by grading one fixed set "
                    "of answers three times. On this evidence the two "
                    "architectures are **not distinguishable on correctness**.")
            else:
                add("At least one difference is larger than the grader's own "
                    "spread of 0.0050. That does not by itself make it real — 30 "
                    "questions is small — but it is not noise in the grader.")
            add("")

    # -- 2. what else separates them ---------------------------------------
    add("## 2. What separates them apart from the score")
    add("")
    if cells:
        add("| version | set | made something up | declined | declined with proof |")
        add("|---|---|---:|---:|---:|")
        for arm, label in ARM_NAMES.items():
            for bank in banks:
                roll = cells.get((arm, bank))
                if not roll:
                    continue
                add(f"| {label} | {BANK_NAMES[bank]} | "
                    f"{roll['answers_with_hallucination']} | {roll['abstained']} | "
                    f"{roll['abstention_carries_query']} |")
        add("")
        add("*\"Made something up\"* counts answers containing at least one "
            "statement the grader could not find in the retrieved evidence. "
            "*\"Declined with proof\"* counts refusals that carried the query "
            "that justified refusing.")
        add("")

    # -- 3. the caveat that has to travel ----------------------------------
    add("## 3. The advantage the merged version gets, stated plainly")
    add("")
    add("Two identifier reconciliations happen when the merged database is built, "
        "and they are the reason it can answer cross-source questions at all.")
    add("")
    add("- CAPEC entries get the public identifier ATT&CK entries already carry.")
    add("- CAPEC's ATT&CK mapping entries store `1027.001` where ATT&CK stores "
        "`T1027.001`; the merged build reconciles the two.")
    add("")
    add("Both are things the two-database system already does **in code, at "
        "query time**. Moving them into the data is the merged design's own "
        "argument for itself — reconcile once at load rather than at every "
        "query — so this is the merged condition rather than a thumb on the "
        "scale. One consequence does favour the merged version and must be "
        "reported with any result: in one database the next step of a "
        "cross-catalogue question is reachable without leaving the engine, so "
        "the merged version can follow a link that the two-database version "
        "retrieves and cannot act on. That is a real property of the "
        "architecture, not an artifact of this harness.")
    add("")

    # -- 4. what ran --------------------------------------------------------
    add("## 4. What ran")
    add("")
    add("| phase | what it did | result | time |")
    add("|---|---|---|---:|")
    for p in state["phases"]:
        status = {"ok": "ok", None: "_running_"}.get(
            p.get("status"), f"**{p.get('status')}**")
        add(f"| `{p['name']}` | {p['description']} | {status} | {p.get('wall_s', 0):.0f}s |")
    add("")
    for p in failed:
        add(f"**`{p['name']}` failed:** `{p.get('error')}`")
        add("")

    # -- 5. caveats ---------------------------------------------------------
    add("## 5. Things that would make these numbers wrong")
    add("")
    add("1. **Thirty questions per set.** A difference of a few hundredths is "
        "noise at that size.")
    add("2. **The grader is a language model.** It is the same one used for "
        "every other figure in the study, and it graded every cell here in one "
        "session, so it cancels out of the comparison — but it has never been "
        "checked against a human.")
    add("3. **Every question names an entity.** Nothing here measures the "
        "open-ended regime, where the two designs might differ most.")
    add("4. **One run per cell.** The merged and templated versions are "
        "reproducible; the no-templates version has a language model in the "
        "loop and would vary if re-run.")
    add("")

    path = out_dir / "REPORT.md"
    path.write_text("\n".join(lines) + "\n")
    (out_dir / "metrics.json").write_text(json.dumps({
        "cells": {f"{arm}/{bank}": roll for (arm, bank), roll in cells.items()},
    }, indent=2) + "\n")
    return path


if __name__ == "__main__":
    import sys

    print(write_report(Path(sys.argv[1])))
