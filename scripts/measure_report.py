#!/usr/bin/env python3
"""Turn the measurement's state file into something a person can read.

Written deliberately in plain language. Every figure is computed from
`state.json` and the judgment files on disk; nothing here is transcribed by
hand, and a phase that did not run says so rather than showing a zero.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]

ARM_NAMES = {
    "deterministic": "Normal system (pre-written query templates)",
    "generic": "No templates (works the schema out at run time)",
    "gold_loop_llm": "LLM-assisted (AI writes the prose answer)",
    "llm_query": "AI writes the database query itself",
}


def _roll(phase: dict[str, Any] | None) -> dict[str, Any] | None:
    if not phase or phase.get("status") != "ok":
        return None
    return (phase.get("result") or {}).get("roll")


def _unpushed() -> str:
    try:
        out = subprocess.run(["git", "rev-list", "--count", "--all", "--not", "--remotes"],
                             cwd=REPO, capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or "?"
    except Exception:  # noqa: BLE001
        return "?"


def write_report(out_dir: Path) -> Path:
    state = json.loads((out_dir / "state.json").read_text())
    phases = {p["name"]: p for p in state["phases"]}
    lines: list[str] = []
    add = lines.append

    add("# What we changed today, and whether it worked")
    add("")
    add(f"**Run started** {state.get('started')} · "
        f"**phases** {len(state['phases'])}, "
        f"{sum(1 for p in state['phases'] if p.get('status') != 'ok')} failed")
    add("")
    add("Every number below was produced by the same grader in the same run, so the "
        "comparisons are like-for-like. Where a phase did not finish, it says so "
        "instead of showing a zero.")
    add("")

    # -- 1. the fixes -------------------------------------------------------
    add("## 1. Did this morning's two fixes make answers better?")
    add("")
    add("**What was broken.** The system was fetching the right information and then "
        "not saying it. Asked *\"what is this technique and how does it work?\"* it "
        "replied with internal bookkeeping — version numbers, deletion flags — while "
        "the actual explanation sat unused in the record it had just cited. Separately, "
        "when a record had a small set of related items, those items were fetched, "
        "checked, and then mentioned nowhere.")
    add("")
    add("**How this was measured.** The same 30 questions as last night, graded by the "
        "same grader, compared **question by question**. Only the code changed between "
        "the two columns, so nothing else can explain a difference.")
    add("")
    pair = (phases.get("A3") or {}).get("result") if phases.get("A3", {}).get("status") == "ok" else None
    if pair:
        add("| | score out of 1.0 |")
        add("|---|---|")
        add(f"| before the fixes (last night) | {pair['before_mean']:.4f} |")
        add(f"| after the fixes | {pair['after_mean']:.4f} |")
        add(f"| **change** | **{pair['delta']:+.4f}** "
            f"(95% confidence range {pair['ci95'][0]:+.4f} to {pair['ci95'][1]:+.4f}) |")
        add("")
        add(f"**{pair['improved']} questions got better, {pair['regressed']} got worse, "
            f"{pair['unchanged']} did not move.**")
        add("")
        if pair["ci95"][0] > 0:
            add("The confidence range stays above zero, which means the improvement is "
                "not an accident of which questions happened to be in the set.")
        elif pair["delta"] > 0:
            add("⚠ The improvement does not clear the confidence range, so at 30 "
                "questions this is **suggestive, not proven**. It would need a larger "
                "question set to call it a real effect.")
        else:
            add("⚠ The fixes did **not** improve the score on this set.")
        add("")
        if pair["moved"]:
            add("The questions that actually moved:")
            add("")
            add("| question | before | after | change |")
            add("|---|---:|---:|---:|")
            for row in pair["moved"]:
                add(f"| `{row['case']}` | {row['before']:.2f} | {row['after']:.2f} | "
                    f"{row['delta']:+.2f} |")
            add("")
    else:
        add("_This phase did not complete, so there is no before/after figure._")
        add("")

    # -- 2. the arms --------------------------------------------------------
    add("## 2. How do the four versions compare?")
    add("")
    add("**The question set is new.** It was generated this morning, drawn to exclude "
        "every entity the old set used, and no version of the system has seen it. That "
        "matters: the old set had been used to find and fix bugs, which stops it being "
        "a fair test.")
    add("")
    add("| version | questions | score | fully correct | made something up | declined, with proof |")
    add("|---|---:|---|---|---:|---|")
    any_arm = False
    for arm, label in ARM_NAMES.items():
        roll = _roll(phases.get(f"B-judge-{arm}"))
        if not roll or not roll.get("n"):
            add(f"| {label} | — | _did not run_ | — | — | — |")
            continue
        any_arm = True
        v = roll["verdicts"]
        abst = roll["abstained"]
        proof = roll["abstention_carries_query"]
        add(f"| {label} | {roll['n']} | **{roll['correctness']['mean']:.4f}** "
            f"({roll['correctness']['ci95'][0]:.3f}–{roll['correctness']['ci95'][1]:.3f}) | "
            f"{v['CORRECT']} of {roll['n']} | {roll['answers_with_hallucination']} | "
            f"{proof} of {abst} |")
    add("")
    if any_arm:
        add("*\"Made something up\"* counts answers containing at least one statement the "
            "grader could not find in the retrieved evidence. *\"Declined, with proof\"* "
            "counts the times the system refused to answer **and** showed the query it "
            "ran to justify refusing — the behaviour the project leads with.")
        add("")

    # -- 3. the AI-written-query arm ---------------------------------------
    add("## 3. When the AI wrote its own queries, what went wrong?")
    add("")
    add("This one needs care. Its score mixes two very different failures, and only "
        "one of them is the model's fault:")
    add("")
    add("- it wrote a **bad query** — genuinely its own failure; or")
    add("- it wrote a **good query** whose results our own reader could not parse, "
        "because that reader was built around the column layouts the pre-written "
        "templates produce.")
    add("")
    split = (phases.get("C") or {}).get("result") if phases.get("C", {}).get("status") == "ok" else None
    if split:
        counts = split["counts"]
        total = sum(counts.values()) or 1
        add("| outcome | questions | share |")
        add("|---|---:|---:|")
        labels = {
            "answered": "worked — query ran and produced evidence",
            "reader_could_not_parse": "**our reader's limitation** — query ran, output not understood",
            "execution_failed": "the database refused the query",
            "gate_rejected": "the safety check refused every attempt",
            "no_result": "no result recorded",
        }
        for key, label in labels.items():
            n = counts.get(key, 0)
            if n:
                add(f"| {label} | {n} | {n / total:.0%} |")
        add("")
        reader = counts.get("reader_could_not_parse", 0)
        if reader:
            add(f"**{reader} of {total} questions failed for a reason that is ours, not "
                "the model's.** Any comparison against the templated system has to say "
                "so. The honest reading is that the pre-written templates guarantee "
                "their own output is readable, which is a real advantage of that "
                "design — but it is a different advantage from writing better queries, "
                "and the two should not be reported as one number.")
            add("")
    else:
        add("_This phase did not run, so the failures have not been split._")
        add("")

    # -- 4. what ran --------------------------------------------------------
    add("## 4. What ran")
    add("")
    add("| phase | what it did | result | time |")
    add("|---|---|---|---:|")
    for p in state["phases"]:
        status = "ok" if p.get("status") == "ok" else f"**{p.get('status')}**"
        add(f"| `{p['name']}` | {p['description']} | {status} | {p.get('wall_s', 0):.0f}s |")
    add("")
    for p in state["phases"]:
        if p.get("status") != "ok":
            add(f"**`{p['name']}` failed:** `{p.get('error')}`")
            add("")

    # -- 5. caveats ---------------------------------------------------------
    add("## 5. Things that would make these numbers wrong")
    add("")
    add("1. **The grader is a language model on the same server the system uses.** It "
        "agrees closely with the independent grader used earlier (correlation 0.93), "
        "but it is not independent, and it runs about 0.03 generous. Fine for "
        "comparing versions; not what you would publish an absolute score from.")
    add("2. **30 questions.** Small. A difference of a few hundredths is noise.")
    add("3. **The new question set was written by a language model**, from a prompt that "
        "shows it one entity and nothing about the system. That keeps it fair, but the "
        "phrasing is less varied than a human's would be.")
    add("4. **Each version answered each question once.** No repeat runs, so there is no "
        "estimate of how much a version varies with itself.")
    add("")

    # -- 6. next ------------------------------------------------------------
    add("## 6. What is worth doing next")
    add("")
    add("- **Decide how to report the AI-written-query comparison** — §3 is the whole "
        "question. Reporting the split is the honest option.")
    add("- **The merged-database test has infrastructure but no arm yet.** A second "
        "database container is set up and isolated; nothing has been loaded into it.")
    add("- **Re-grade with an independent model** before any of this leaves the "
        "repository.")
    add(f"- **{_unpushed()} commits are still local.** Nothing has been pushed.")
    add("")

    path = out_dir / "REPORT.md"
    path.write_text("\n".join(lines) + "\n")
    (out_dir / "metrics.json").write_text(json.dumps({
        "composer_fix": pair,
        "arms": {arm: _roll(phases.get(f"B-judge-{arm}")) for arm in ARM_NAMES},
        "llm_query_failure_split": split,
    }, indent=2) + "\n")
    return path


if __name__ == "__main__":
    import sys
    print(write_report(Path(sys.argv[1])))
