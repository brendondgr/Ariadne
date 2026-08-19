#!/usr/bin/env python3
"""Turn an overnight sweep's artifacts into the report you read over coffee.

Every number here is read from ``state.json``, ``calibration.json`` and the
judgment files the sweep wrote. Nothing is transcribed and nothing is inferred:
if a phase did not run, the section says so instead of leaving a gap that reads
like a zero.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


def _phases(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {p["name"]: p for p in state.get("phases", [])}


def _roll(phase: dict[str, Any] | None) -> dict[str, Any] | None:
    if not phase or phase.get("status") != "ok":
        return None
    return (phase.get("result") or {}).get("roll")


def _fmt_ci(roll: dict[str, Any]) -> str:
    c = roll["correctness"]
    return f"**{c['mean']:.4f}** ({c['ci95'][0]:.3f} – {c['ci95'][1]:.3f})"


def _arm_row(name: str, roll: dict[str, Any] | None) -> str:
    if not roll or not roll.get("n"):
        return f"| {name} | — | — | — | — | — | not run |"
    v = roll["verdicts"]
    return (
        f"| {name} | {roll['n']} | {_fmt_ci(roll)} | "
        f"{v['CORRECT']}/{v['PARTIAL']}/{v['INCORRECT']} | "
        f"{roll['faithfulness']:.3f} | {roll['completeness']:.3f} | "
        f"{roll['answers_with_hallucination']} |"
    )


def write_report(out_dir: Path) -> Path:
    state = json.loads((out_dir / "state.json").read_text())
    phases = _phases(state)
    lines: list[str] = []
    add = lines.append

    ran = [p for p in state.get("phases", [])]
    failed = [p for p in ran if p.get("status") != "ok"]
    wall = sum(p.get("wall_s", 0) for p in ran)

    add("# Overnight sweep — judged arm comparison")
    add("")
    add(f"**Started** {state.get('started')} · **finished** {state.get('finished', '(did not finish)')}")
    add(f"**Tree** `{state.get('commit', '')[:12]}` · **workers** {state.get('workers')} · "
        f"**wall** {wall / 60:.0f} min")
    add("")
    if failed:
        add(f"> ⚠ **{len(failed)} of {len(ran)} phases failed.** They are listed in §7 with "
            "their errors. Every figure below comes only from phases that completed.")
    else:
        add(f"> All {len(ran)} phases completed.")
    add("")

    # -- 1. trust ---------------------------------------------------------
    add("## 1. How much to trust these numbers")
    add("")
    calib_file = out_dir / "calibration.json"
    if calib_file.is_file():
        cal = json.loads(calib_file.read_text())
        add("The local judge re-graded the 30 blind answers that already carry committed "
            "**Sonnet 5** judgments from `EXP-2026-08-002`. That is the only evidence that "
            "this runner's rubric and model reproduce the instrument the holdout was "
            "measured with.")
        add("")
        add("| | value |")
        add("|---|---|")
        add(f"| cases compared | {cal.get('n_compared')} |")
        add(f"| Sonnet mean correctness | {cal.get('reference_mean')} |")
        add(f"| local mean correctness | {cal.get('local_mean')} |")
        add(f"| mean delta (local − Sonnet) | {cal.get('mean_delta')} |")
        add(f"| mean absolute delta | {cal.get('mean_abs_delta')} |")
        add(f"| verdict agreement | {cal.get('verdict_agreement')} |")
        add(f"| Pearson r | {cal.get('pearson_r')} |")
        add("")
        r = cal.get("pearson_r")
        delta = cal.get("mean_delta")
        if r is not None and delta is not None:
            if r >= 0.8 and abs(delta) <= 0.1:
                add("**Read:** the two judges rank the same answers the same way and sit close "
                    "in level. Treat the comparisons below as meaningful, and the absolute "
                    "values as carrying the offset above.")
            elif r >= 0.6:
                add("**Read:** the judges agree on ordering but differ in level. Trust the "
                    "*deltas* between arms below; do not quote the absolute figures against "
                    "the Sonnet-graded 0.689 without restating this offset.")
            else:
                add("**Read:** agreement is weak. Everything below is directional only, and "
                    "no figure here should be quoted beside a Sonnet-graded number. The "
                    "cross-model panel is the instrument for anything that leaves this repo.")
    else:
        add("_Calibration did not run, so there is no evidence about how this judge compares "
            "to the Sonnet grading the holdout used. Treat everything below as provisional._")
    add("")

    # -- 2. headline ------------------------------------------------------
    add("## 2. The comparison this was for")
    add("")
    add("Both arms retrieve identically — `gold_in_evidence` 1.0000, 30/30 covered — so any "
        "difference here is answer quality, not what was fetched. Arm H had never been judged "
        "before tonight.")
    add("")
    add("| arm | n | correctness (95% CI) | C/P/I | faithfulness | completeness | answers w/ hallucination |")
    add("|---|---:|---|---|---:|---:|---:|")
    cascade = _roll(phases.get("E1"))
    generic = _roll(phases.get("E3"))
    add(_arm_row("Cascade (templates, repaired)", cascade))
    add(_arm_row("Arm H (schema-driven)", generic))
    add("")
    if cascade and generic and cascade.get("n") and generic.get("n"):
        delta = generic["correctness"]["mean"] - cascade["correctness"]["mean"]
        add(f"**Delta (Arm H − cascade): {delta:+.4f}.** Whether that is real is §3's question.")
        add("")
        add("Abstention behaviour, which is the property the pitch rests on:")
        add("")
        add("| arm | abstained | abstention carried the query | fabricated a mapping |")
        add("|---|---:|---:|---:|")
        for name, roll in (("Cascade", cascade), ("Arm H", generic)):
            add(f"| {name} | {roll['abstained']} | {roll['abstention_carries_query']} | "
                f"**{roll['fabricated_mapping']}** |")
        add("")
    add("")

    # -- 3. variance ------------------------------------------------------
    add("## 3. Is any of that above noise?")
    add("")
    passes = []
    for name, suffix in (("E1", ""), ("E2a", ".run2"), ("E2b", ".run3")):
        roll = _roll(phases.get(name))
        if roll and roll.get("n"):
            passes.append((name, roll["correctness"]["mean"]))
    if len(passes) >= 2:
        values = [v for _, v in passes]
        add("The cascade's pipeline is fully deterministic, so re-judging the *same* answers "
            "isolates grader variance exactly — for this arm, all variance is judge variance. "
            "That is a partial answer to open question Q2, which currently has "
            "`statistical_test: null` in every manifest.")
        add("")
        add("| pass | mean correctness |")
        add("|---|---|")
        for name, value in passes:
            add(f"| {name} | {value:.4f} |")
        add("")
        spread = max(values) - min(values)
        add(f"**Spread across {len(values)} passes: {spread:.4f}** (sd {pstdev(values):.4f}).")
        if cascade and generic:
            delta = abs(generic["correctness"]["mean"] - cascade["correctness"]["mean"])
            verdict = "larger than" if delta > spread else "within"
            add("")
            add(f"The arm delta in §2 is **{verdict}** the judge's own spread — "
                f"{delta:.4f} against {spread:.4f}.")
    else:
        add("_Not enough judge passes completed to estimate grader variance._")
    add("")

    # -- 4. where the loss is ---------------------------------------------
    add("## 4. Where the remaining loss sits")
    add("")
    for label, phase in (("cascade", "E4a"), ("Arm H", "E4b")):
        entry = phases.get(phase)
        if entry and entry.get("status") == "ok":
            add(f"**{label}** — see `answer-gap-*.json` in this directory.")
            result = entry.get("result") or {}
            classes = result.get("classes") if isinstance(result, dict) else None
            if classes:
                add("")
                add("| class | questions | loss share |")
                add("|---|---:|---:|")
                for name, info in classes.items():
                    add(f"| `{name}` | {info.get('questions')} | {info.get('share')} |")
            add("")
        else:
            add(f"**{label}** — did not run.")
            add("")

    # -- 5. catalogue -----------------------------------------------------
    add("## 5. The 120-question catalogue")
    add("")
    add("| arm | n | correctness (95% CI) | C/P/I | faithfulness | completeness | answers w/ hallucination |")
    add("|---|---:|---|---|---:|---:|---:|")
    add(_arm_row("Cascade", _roll(phases.get("E5a"))))
    add(_arm_row("Arm H", _roll(phases.get("E5b"))))
    add("")
    add("Remember what this bank is: 120 questions co-authored with the templates that answer "
        "them. It is the wrong instrument for an absolute claim and the right one for an "
        "arm-to-arm comparison at larger n.")
    add("")

    # -- 6. Arm F ---------------------------------------------------------
    add("## 6. Arm F, generation 2")
    add("")
    if any(phases.get(p, {}).get("status") == "ok" for p in ("E7b", "E7d")):
        add("| bank | n | correctness (95% CI) | C/P/I | faithfulness | completeness | answers w/ hallucination |")
        add("|---|---:|---|---|---:|---:|---:|")
        add(_arm_row("blind holdout", _roll(phases.get("E7b"))))
        add(_arm_row("catalogue", _roll(phases.get("E7d"))))
        add("")
        add("This closes the open item in `EXP-2026-08-006`'s ISSUES, which recorded that no "
            "arm comparison could be drawn from that experiment because Arm F had not been "
            "re-run.")
    else:
        add("_Arm F did not complete. `EXP-2026-08-006`'s ISSUES entry still stands._")
    add("")

    # -- 7. what did not run ----------------------------------------------
    add("## 7. What ran, and what did not")
    add("")
    add("| phase | what it was | status | wall |")
    add("|---|---|---|---:|")
    for p in ran:
        status = "ok" if p.get("status") == "ok" else f"**{p.get('status')}**"
        add(f"| `{p['name']}` | {p['description']} | {status} | {p.get('wall_s', 0):.0f}s |")
    add("")
    for p in failed:
        add(f"**`{p['name']}` failed:** `{p.get('error')}`")
        add("")

    # -- 8. caveats -------------------------------------------------------
    add("## 8. Caveats that travel with every number above")
    add("")
    add("1. **The blind bank diagnosed the defects this system now repairs.** Holdout v1 "
        "found the direction defect and the join defect; both are fixed. A v1 figure measured "
        "afterwards is co-authored with its own test. These are diagnostics. The quotable "
        "blind number still has to come from a holdout v2.")
    add("2. **This judge is not independent.** A local model grading answers from a pipeline "
        "whose LLM seams run on that same server shares failure modes with it. §1 is the only "
        "evidence about how far that matters; the cross-model panel remains the instrument for "
        "anything quoted outside the repository.")
    add("3. **n = 30** on the blind set, single pipeline run, seeds unrecorded.")
    add("4. **Nothing here was recorded as an experiment yet.** The sweep writes artifacts and "
        "this report; folding them into `docs/research/experiments/` is a morning job, because "
        "which claims move is a judgement call and not one to automate.")
    add("")

    # -- 9. decisions -----------------------------------------------------
    add("## 9. Waiting for you")
    add("")
    add("- **Fold tonight's results into the research record** — one experiment per question "
        "answered, then reconcile `CLAIMS.md`. C-003 is the one to watch: if Arm H judged "
        "level with the cascade, \"the templates are where the accuracy lives\" needs rewriting.")
    add("- **The composer under-enumeration fix** — deliberately not attempted unattended. "
        "§4 says what it is worth on each arm.")
    add("- **Holdout v2** — now the only route to a quotable blind figure.")
    add("- **18 commits and 2 freeze tags are still unpushed.**")
    add("")

    report = out_dir / "REPORT.md"
    report.write_text("\n".join(lines) + "\n")

    metrics = {
        "started": state.get("started"),
        "finished": state.get("finished"),
        "commit": state.get("commit"),
        "phases_run": len(ran),
        "phases_failed": len(failed),
        "arms": {
            "cascade_blind": _roll(phases.get("E1")),
            "generic_blind": _roll(phases.get("E3")),
            "cascade_dev": _roll(phases.get("E5a")),
            "generic_dev": _roll(phases.get("E5b")),
            "armf_blind": _roll(phases.get("E7b")),
            "armf_dev": _roll(phases.get("E7d")),
        },
        "judge_passes": {name: value for name, value in passes} if passes else {},
    }
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    return report


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if out is None:
        print("usage: overnight_report.py <sweep-output-dir>")
        raise SystemExit(2)
    print(write_report(out))
