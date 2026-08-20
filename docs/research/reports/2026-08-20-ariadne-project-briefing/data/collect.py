#!/usr/bin/env python3
"""Collect every number this report quotes, from the files that produced them.

Nothing here is typed by hand. Each figure is read out of an experiment's
``data/metrics.json`` (the file the research record's own validator requires to
be non-empty) or out of the second night's sweep metrics, which is the one body
of results in this report that has not yet been scaffolded as an experiment.

Run from anywhere:

    python3 docs/research/reports/2026-08-20-ariadne-project-briefing/data/collect.py

It writes ``briefing.json`` beside itself and prints a one-line summary. A
missing key raises rather than defaulting, because a briefing that silently
drops a figure is worse than one that fails to build.
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
EXP = REPO / "docs" / "research" / "experiments"
NIGHT2 = REPO / "docs" / "evaluation" / "night2-2026-08-20" / "metrics.json"


def load(exp_dir: str) -> dict:
    return json.loads((EXP / exp_dir / "data" / "metrics.json").read_text())


def dig(obj: dict, path: str):
    """Fetch a dotted path, raising with the full path if any step is absent."""
    cur = obj
    for part in path.split("."):
        if part not in cur:
            raise KeyError(f"{path} — missing at {part!r}")
        cur = cur[part]
    return cur


# -- the seven-arm study on the development catalogue ------------------------
ARM_DIRS = {
    "A": ("EXP-2026-07-001-arm-a-deterministic", "Deterministic"),
    "B": ("EXP-2026-07-002-arm-b-llm-planned", "LLM planner"),
    "C": ("EXP-2026-07-003-arm-c-llm-writer-evidence", "Writer on evidence"),
    "D": ("EXP-2026-07-004-arm-d-llm-writer-claims", "Writer on claims"),
    "E": ("EXP-2026-07-005-arm-e-llm-planned-loop", "LLM planner + loop"),
    "F": ("EXP-2026-07-006-arm-f-determ-loop-llm-writer", "Authored plan + loop + writer"),
    "G": ("EXP-2026-07-007-arm-g-templates-disabled", "Templates disabled"),
}

seven_arm = {}
for letter, (folder, label) in ARM_DIRS.items():
    m = load(folder)
    seven_arm[letter] = {
        "experiment": m["experiment"],
        "label": label,
        "n": m["n_questions"],
        "correctness": dig(m, "metrics.correctness.mean"),
        "faithfulness": dig(m, "metrics.faithfulness.mean"),
        "hallucination_cases": m["hallucination_cases"],
        "wall_clock_seconds": m["wall_clock_seconds"],
    }

# -- the blind holdout, and the retrieval repair that followed ---------------
h003 = load("EXP-2026-08-003-arm-h-blind-holdout")
h006 = load("EXP-2026-08-006-template-outer-join")
h005 = load("EXP-2026-08-005-binding-direction-portability")

blind_v1 = {
    "arm_a_catalogue": seven_arm["A"]["correctness"],
    "arm_f_catalogue": seven_arm["F"]["correctness"],
    "arm_a_blind": dig(h003, "reference_arms.arm_a_deterministic.judged_correctness"),
    "arm_f_blind": dig(h003, "reference_arms.arm_f_loop_llm.judged_correctness"),
    "n": h003["n_questions"],
}

retrieval_repair = {
    "cascade_original": dig(h006, "progression_blind.template_cascade_original"),
    "after_binding_and_direction": dig(h006, "progression_blind.after_binding_and_direction"),
    "after_outer_join": dig(h006, "progression_blind.after_outer_join"),
    "catalogue_before": dig(h005, "development_catalogue.before.gold_in_evidence"),
    "catalogue_after": dig(h006, "development_catalogue.after.gold_in_evidence"),
    "catalogue_regressed": dig(h006, "development_catalogue.paired.regressed"),
    "n_blind": dig(h006, "blind_holdout.n"),
    "n_catalogue": dig(h006, "development_catalogue.n"),
}

# -- the judged comparison, generation 2 -------------------------------------
g2 = load("EXP-2026-08-007-judged-arm-comparison-gen2")
judged_gen2 = {
    "judge_model": dig(g2, "judge.model"),
    "calibration_pearson_r": dig(g2, "judge.calibration_vs_sonnet.pearson_r"),
    "calibration_mean_delta": dig(g2, "judge.calibration_vs_sonnet.mean_delta"),
    "grader_spread": dig(g2, "judge.pass_spread.spread"),
    "grader_passes": dig(g2, "judge.pass_spread.passes"),
    "repair_delta": dig(g2, "repair_paired_delta.delta"),
    "repair_before": dig(g2, "repair_paired_delta.before_mean"),
    "repair_after": dig(g2, "repair_paired_delta.after_mean"),
    "arms": {k: {"n": v["n"], "correctness": v["correctness"]["mean"],
                 "abstained": v["abstained"],
                 "abstention_carries_query": v["abstention_carries_query"],
                 "answers_with_hallucination": v["answers_with_hallucination"]}
             for k, v in g2["arms"].items()},
    "coauthorship_gap": dig(g2, "coauthorship_gap.gap"),
}

# -- the composer fix and the first generated bank ---------------------------
g3 = load("EXP-2026-08-008-composer-fix-and-fresh-bank")
fresh_bank = {
    "composer_fix": dig(g3, "composer_fix_paired_blind"),
    "arms": {k: {"n": v["n"], "correctness": v["correctness"]["mean"],
                 "ci95": v["correctness"]["ci95"],
                 "correct": dig(v, "correct_rate.correct"),
                 "answers_with_hallucination": v["answers_with_hallucination"],
                 "abstained": v["abstained"],
                 "abstention_carries_query": v["abstention_carries_query"]}
             for k, v in g3["arms_fresh_bank"].items()},
    "llm_query_split": dig(g3, "llm_query_failure_split"),
    "llm_query_excluding_reader_failures": dig(
        g3, "llm_query_excluding_reader_failures.mean"),
    "catalogue_after_fix": {
        "n": dig(g3, "catalogue_after_fix.n"),
        "correctness": dig(g3, "catalogue_after_fix.correctness.mean"),
        "abstained": dig(g3, "catalogue_after_fix.abstained"),
        "abstention_carries_query": dig(g3, "catalogue_after_fix.abstention_carries_query"),
        "answers_with_hallucination": dig(g3, "catalogue_after_fix.answers_with_hallucination"),
    },
    "coauthorship_gap_before_fix": dig(g3, "coauthorship_gap.before_fix"),
    "coauthorship_gap_after_fix_same_questions": dig(
        g3, "coauthorship_gap.after_fix_same_questions"),
    "coauthorship_gap_after_fix_fresh_bank": dig(
        g3, "coauthorship_gap.after_fix_fresh_bank"),
}

# -- the second night: a disjoint bank, repeats, and a second grader ---------
n2 = json.loads(NIGHT2.read_text())
second_night = {
    "bank2_questions": dig(n2, "bank2.questions"),
    "bank2_overlap_with_prior_banks": len(dig(n2, "bank2.overlap_with_prior_banks")),
    "arms": {k: {"n": v["n"], "correctness": v["correctness"]["mean"],
                 "ci95": v["correctness"]["ci95"],
                 "correct": dig(v, "correct_rate.correct"),
                 "answers_with_hallucination": v["answers_with_hallucination"],
                 "abstained": v["abstained"],
                 "abstention_carries_query": v["abstention_carries_query"]}
             for k, v in n2["bank2_arms"].items()},
    "llm_query_split": dig(n2, "bank2_llm_query_split.counts"),
    "llm_query_funded": dig(n2, "llm_query_funded.correctness.mean"),
    "llm_query_funded_split": dig(n2, "llm_query_funded_split.counts"),
    "self_variance": {
        arm: [{"root": r["root"], "n": r["n"], "identical": r["identical"]}
              for r in block["repeats"]]
        for arm, block in n2["self_variance"].items()
    },
    "cross_grader": {k: {"n": v["n"], "home_mean": v["home_mean"],
                         "cross_mean": v["cross_mean"], "offset": v["offset"],
                         "pearson_r": v["pearson_r"]}
                     for k, v in n2["cross_grader"].items()},
    "merged_store": n2["merged_store"],
}

# The narrator arm's spread against itself is the sharpest number of the night
# and it is not in the sweep's own metrics file — it lives in the graded repeat
# runs, beside it. Read it there rather than restating it.
spread_path = NIGHT2.parent / "repeat_spread.json"
repeats = json.loads(spread_path.read_text())
narrator_runs = sorted(
    [dig(fresh_bank, "arms.gold_loop_llm.correctness")]
    + [v["correctness"]["mean"] for v in repeats.values()]
)
second_night["narrator_self_variance"] = {
    "runs": narrator_runs,
    "spread": round(max(narrator_runs) - min(narrator_runs), 4),
    "source": "docs/evaluation/night2-2026-08-20/repeat_spread.json plus the "
              "graded bank-1 run in EXP-2026-08-008",
}

out = {
    "generated_by": "docs/research/reports/2026-08-20-ariadne-project-briefing/data/collect.py",
    "seven_arm_catalogue": seven_arm,
    "blind_holdout_v1": blind_v1,
    "retrieval_repair": retrieval_repair,
    "judged_gen2": judged_gen2,
    "generated_bank_1": fresh_bank,
    "generated_bank_2": second_night,
}
(HERE / "briefing.json").write_text(json.dumps(out, indent=2, sort_keys=False) + "\n")
print(f"wrote {HERE / 'briefing.json'} — "
      f"{len(seven_arm)} catalogue arms, "
      f"{len(fresh_bank['arms'])} arms on bank 1, "
      f"{len(second_night['arms'])} on bank 2")
