#!/usr/bin/env python3
"""The morning read of the second night, in plain language.

Every figure is computed from `state.json` and the judgment files on disk. A
phase that did not run says so rather than showing a zero, because a partial
night presented as a complete one is the only outcome worse than no night.
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

BANK1_METRICS = REPO / "docs" / "evaluation" / "measure-2026-08-19" / "metrics.json"


def _ok(phases: dict[str, Any], name: str) -> dict[str, Any] | None:
    entry = phases.get(name)
    if not entry or entry.get("status") != "ok":
        return None
    return entry.get("result")


def _roll(phases: dict[str, Any], name: str) -> dict[str, Any] | None:
    result = _ok(phases, name)
    return (result or {}).get("roll") if result else None


def _bank1_arms() -> dict[str, Any]:
    if not BANK1_METRICS.is_file():
        return {}
    return (json.loads(BANK1_METRICS.read_text()).get("arms") or {})


def _unpushed() -> str:
    try:
        out = subprocess.run(["git", "rev-list", "--count", "--all", "--not", "--remotes"],
                             cwd=REPO, capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or "?"
    except Exception:  # noqa: BLE001
        return "?"


def write_report(out_dir: Path) -> Path:  # noqa: C901 — a report is a long list of sections
    state = json.loads((out_dir / "state.json").read_text())
    phases = {p["name"]: p for p in state["phases"]}
    lines: list[str] = []
    add = lines.append

    failed = [p["name"] for p in state["phases"] if p.get("status") != "ok"]
    add("# Second night — hardening yesterday's numbers")
    add("")
    add(f"**Started** {state.get('started')} · **phases** {len(state['phases'])}, "
        f"{len(failed)} failed{(': ' + ', '.join(failed)) if failed else ''}")
    add("")
    add("Yesterday's arm table came from one question set, graded once, by a grader "
        "sharing a server with the system it graded. Nothing was added last night — "
        "the night went at those three weaknesses instead.")
    add("")

    # -- 1. second bank ------------------------------------------------------
    add("## 1. Does the ranking survive a completely different question set?")
    add("")
    bank2 = _ok(phases, "N1")
    if bank2:
        if bank2.get("reused"):
            add(f"Bank 2 was already on disk ({bank2['questions']} questions); it was reused.")
        else:
            overlap = bank2.get("overlap_with_prior_banks") or []
            add(f"A second question set of **{bank2['questions']} questions** was drawn and "
                "written overnight, with every entity used by any earlier set excluded "
                "before drawing.")
            add("")
            if overlap:
                add(f"⚠ **{len(overlap)} entities leaked through the exclusion list**: "
                    f"{', '.join(overlap)}. That is a bug in the generator, not a "
                    "coincidence, and it needs fixing before this set is trusted.")
            else:
                add("**No entity appears in both sets.** The exclusion list did its job, "
                    "which is the first time it has been tested on a real second draw.")
        add("")
    else:
        add("_The second set was not produced, so everything that depended on it was skipped._")
        add("")

    old = _bank1_arms()
    rows = []
    for arm, label in ARM_NAMES.items():
        new = _roll(phases, f"N2-judge-{arm}")
        prev = (old.get(arm) or {})
        rows.append((label, prev.get("correctness", {}).get("mean"), new))
    if any(r[2] for r in rows):
        add("| version | set 1 (yesterday) | set 2 (last night) | change | fully correct | made something up |")
        add("|---|---:|---:|---:|---|---:|")
        for label, before, new in rows:
            if not new or not new.get("n"):
                add(f"| {label} | {before if before is None else f'{before:.4f}'} | "
                    "_did not run_ | — | — | — |")
                continue
            after = new["correctness"]["mean"]
            delta = "—" if before is None else f"{after - before:+.4f}"
            add(f"| {label} | {'—' if before is None else f'{before:.4f}'} | "
                f"**{after:.4f}** | {delta} | {new['verdicts']['CORRECT']} of {new['n']} | "
                f"{new['answers_with_hallucination']} |")
        add("")
        add("**How to read the change column.** These are two different sets of questions, "
            "not a before/after on the same ones, so a small movement means nothing. What "
            "matters is whether the *order* of the rows is the same on both sets. An order "
            "that flips means yesterday's table described one question set rather than the "
            "system.")
        add("")
        ranked_new = [(r[0], r[2]["correctness"]["mean"]) for r in rows if r[2] and r[2].get("n")]
        ranked_old = [(r[0], r[1]) for r in rows if r[1] is not None and r[2] and r[2].get("n")]
        if len(ranked_new) == len(ranked_old) and len(ranked_new) > 1:
            same = [n for n, _ in sorted(ranked_new, key=lambda x: -x[1])] == \
                   [n for n, _ in sorted(ranked_old, key=lambda x: -x[1])]
            add("**The ordering held.**" if same else
                "⚠ **The ordering changed between the two sets.** Yesterday's comparison "
                "table cannot be quoted as-is.")
            add("")

    # -- 2. the query-writing arm, properly funded ---------------------------
    add("## 2. Was the AI-written-query result unfair to the AI?")
    add("")
    add("Yesterday that version scored around half. Three of its failures were the safety "
        "check refusing every attempt — but **two of those three were the model replying "
        "with nothing at all**, having spent its whole word budget thinking. That is our "
        "harness starving it, not a bad query being caught. Last night it ran again with "
        "four times the budget and nothing else changed.")
    add("")
    funded = _roll(phases, "N3-judge")
    base = (_bank1_arms().get("llm_query") or {}).get("correctness", {}).get("mean")
    if funded and funded.get("n"):
        add("| | score | fully correct | made something up |")
        add("|---|---:|---|---:|")
        if base is not None:
            add(f"| original budget | {base:.4f} | — | — |")
        add(f"| **4x budget** | **{funded['correctness']['mean']:.4f}** | "
            f"{funded['verdicts']['CORRECT']} of {funded['n']} | "
            f"{funded['answers_with_hallucination']} |")
        add("")
        if base is not None:
            gap = funded["correctness"]["mean"] - base
            if gap > 0.05:
                add(f"**It moved {gap:+.4f}.** Part of yesterday's gap was our harness. The "
                    "headline comparison should quote this number, not yesterday's.")
            else:
                add(f"**It moved {gap:+.4f} — essentially not at all.** The token budget was "
                    "not what was holding it back, which makes yesterday's figure safe to "
                    "quote and strengthens the comparison rather than weakening it.")
            add("")
    else:
        add("_This did not run._")
        add("")
    split = _ok(phases, "N3-split")
    if split:
        add("Where its questions ended up this time:")
        add("")
        add("| outcome | questions |")
        add("|---|---:|")
        labels = {
            "answered": "worked — query ran and produced evidence",
            "reader_could_not_parse": "**our reader's limitation** — query ran, output not understood",
            "execution_failed": "the database refused the query",
            "gate_rejected": "the safety check refused every attempt",
            "no_result": "no result recorded",
        }
        for key, label in labels.items():
            n = split["counts"].get(key, 0)
            if n:
                add(f"| {label} | {n} |")
        add("")

    # -- 3. self-variance ----------------------------------------------------
    add("## 3. Does the system give the same answer twice?")
    add("")
    add("Every score so far came from running each version **once**. If a version wanders "
        "between runs, differences of a few hundredths between versions are meaningless. "
        "Two extra runs of two versions settle it — and for the templated one this costs "
        "nothing to check, because the answers can simply be compared character by "
        "character.")
    add("")
    for arm in ("deterministic", "gold_loop_llm"):
        summary = _ok(phases, f"N4-summary-{arm}")
        if not summary:
            add(f"- **{ARM_NAMES.get(arm, arm)}** — _did not run_")
            continue
        for rep in summary["repeats"]:
            n, same = rep["n"], rep["identical"]
            verdict = ("every answer identical" if n and same == n
                       else f"{n - same} of {n} answers differed")
            add(f"- **{ARM_NAMES.get(arm, arm)}**, repeat `{rep['root']}`: {verdict}")
            if rep["differing"]:
                add(f"  - differed on: {', '.join(rep['differing'][:10])}")
    add("")
    det = _ok(phases, "N4-summary-deterministic")
    if det and all(r["n"] and r["identical"] == r["n"] for r in det["repeats"]):
        add("**The templated system is exactly reproducible.** Any difference it shows "
            "against another version is a real difference, not run-to-run wobble.")
        add("")

    # -- 4. an independent grader --------------------------------------------
    add("## 4. Is the ranking the system's, or the grader's?")
    add("")
    add("The grader used so far is a language model served from the same box the system "
        "uses. Last night a **different model** re-graded the *same saved answers* — not "
        "new runs, the identical files — so any difference is the grader and nothing "
        "else.")
    add("")
    any_cross = False
    add("| version | our grader | independent grader | difference | agreement |")
    add("|---|---:|---:|---:|---:|")
    for arm, label in ARM_NAMES.items():
        result = _ok(phases, f"N5-cross-{arm}")
        agree = (result or {}).get("agreement") or {}
        if not agree.get("n"):
            add(f"| {label} | — | _did not run_ | — | — |")
            continue
        any_cross = True
        r = agree.get("pearson_r")
        add(f"| {label} | {agree['home_mean']:.4f} | {agree['cross_mean']:.4f} | "
            f"{agree['offset']:+.4f} | {'—' if r is None else f'{r:.2f}'} |")
    add("")
    if any_cross:
        add("*Difference* is how much more generous our grader is. A consistent offset "
            "across all four rows is harmless — it cancels out of every comparison. An "
            "offset that varies by version is not, because then the grader is picking a "
            "winner. *Agreement* is how closely the two graders rank the same questions; "
            "near 1.0 means they disagree on the absolute score but not on which answers "
            "are better.")
        add("")
        worst = []
        for arm, label in ARM_NAMES.items():
            result = _ok(phases, f"N5-cross-{arm}")
            for row in ((result or {}).get("agreement") or {}).get("biggest_disagreements", [])[:3]:
                worst.append((abs(row["gap"]), label, row))
        for _, label, row in sorted(worst, reverse=True)[:6]:
            add(f"- `{row['case']}` ({label}): ours {row['home']:.2f}, independent "
                f"{row['cross']:.2f}")
        if worst:
            add("")
            add("Those are worth reading by hand — a question where two graders disagree "
                "by half a point is usually a question where the expected answer is "
                "ambiguous, which is a defect in the question set, not in either grader.")
            add("")
    else:
        add("_The independent grade did not run, so the grader remains unchecked._")
        add("")

    # -- 5. merged store -----------------------------------------------------
    add("## 5. The merged-database counterfactual")
    add("")
    add("The project's pitch is that keeping the two databases separate, each in its own "
        "language, is worth the complexity. The obvious alternative — pour both into one "
        "database — has never been built, so the pitch has never been contrasted with "
        "anything. Last night did the mechanical half: load both sources into a separate, "
        "isolated database and prove they can still be told apart inside it.")
    add("")
    merged = _ok(phases, "N6")
    if merged:
        sep = merged["separation"]
        add(f"Loaded into `{merged['uri']}`.")
        add("")
        add("| check | count |")
        add("|---|---:|")
        add(f"| entities from ATT&CK | {sep['attack_objects']} |")
        add(f"| entities from CAPEC | {sep['capec_objects']} |")
        add(f"| entities belonging to neither | {sep['unmarked']} |")
        add(f"| things called \"Mitigation\" in total | {sep['mitigations_total']} |")
        add(f"| …of which ATT&CK's | {sep['mitigations_attack']} |")
        add(f"| …of which CAPEC's | {sep['mitigations_capec']} |")
        add("")
        if sep["unmarked"]:
            add(f"⚠ **{sep['unmarked']} entities carry no source marker**, so a query "
                "cannot tell which catalogue they came from. That has to be fixed before "
                "this database can be compared against anything.")
        elif sep["mitigations_total"] == sep["mitigations_attack"] + sep["mitigations_capec"]:
            add("**Both catalogues are present and separable.** \"Mitigation\" is the one "
                "word both catalogues use for different things, and it splits cleanly, "
                "which was the specific risk of putting them in one place.")
        add("")
        add("**What is still missing:** something that answers questions against this "
            "database. The existing queries are written per-source, so this needs a "
            "deliberate code change — which is why it was not done unattended.")
        add("")
    else:
        add("_The merged load did not run._")
        add("")

    # -- 6. what ran ---------------------------------------------------------
    add("## 6. What ran")
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

    # -- 7. next -------------------------------------------------------------
    add("## 7. What is worth doing next")
    add("")
    add("- **Write the night into the research record** as an experiment — until it is in "
        "`docs/research/`, none of it counts.")
    add("- **Build the arm that queries the merged database**, now that the database "
        "itself exists and is verified. That is the last claim with no comparison behind "
        "it.")
    add("- **Read the questions where the two graders disagreed most** (§4) — those are "
        "likely faults in the question set.")
    add(f"- **{_unpushed()} commits are still local.** Nothing has been pushed.")
    add("")

    path = out_dir / "REPORT.md"
    path.write_text("\n".join(lines) + "\n")
    (out_dir / "metrics.json").write_text(json.dumps({
        "bank2": _ok(phases, "N1"),
        "bank2_arms": {a: _roll(phases, f"N2-judge-{a}") for a in ARM_NAMES},
        "bank2_llm_query_split": _ok(phases, "N2-split"),
        "llm_query_funded": _roll(phases, "N3-judge"),
        "llm_query_funded_split": _ok(phases, "N3-split"),
        "self_variance": {a: _ok(phases, f"N4-summary-{a}")
                          for a in ("deterministic", "gold_loop_llm")},
        "cross_grader": {a: ((_ok(phases, f"N5-cross-{a}") or {}).get("agreement"))
                         for a in ARM_NAMES},
        "merged_store": _ok(phases, "N6"),
    }, indent=2) + "\n")
    return path


if __name__ == "__main__":
    import sys
    print(write_report(Path(sys.argv[1])))
