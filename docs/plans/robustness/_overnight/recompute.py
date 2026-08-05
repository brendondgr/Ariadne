"""Task 4 — recompute every arm figure from the committed judgment files.

Reads nothing but the artifacts on disk: no number is carried in from prose.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path("docs/evaluation/experiments")
# The two pre-fix runs. Kept separate; never aggregated with the post-fix ones.
SUPERSEDED = {"untruncated", "untruncated-loop"}


def mean(xs: list[float]) -> float | None:
    return round(sum(xs) / len(xs), 6) if xs else None


def arm_stats(arm_dir: Path) -> dict:
    answers = arm_dir / "answers"
    judgments = sorted(answers.glob("*.judgment.json"))
    answer_files = sorted(p for p in answers.glob("*.json") if not p.name.endswith(".judgment.json"))

    correctness, completeness, faithfulness, groundedness = [], [], [], []
    verdicts: Counter[str] = Counter()
    halluc_total = 0
    halluc_cases = 0
    for p in judgments:
        j = json.loads(p.read_text())
        for key, bucket in (
            ("correctness", correctness),
            ("completeness", completeness),
            ("faithfulness", faithfulness),
            ("groundedness", groundedness),
        ):
            v = j.get(key)
            if isinstance(v, (int, float)):
                bucket.append(float(v))
        verdicts[str(j.get("verdict", "MISSING"))] += 1
        hs = j.get("hallucinations") or []
        halluc_total += len(hs)
        halluc_cases += 1 if hs else 0

    records = related = 0
    coverage_vals: list[float] = []
    for p in answer_files:
        a = json.loads(p.read_text())
        ev = a.get("evidence_volume") or {}
        records += int(ev.get("records") or 0)
        related += int(ev.get("related") or 0)
        cov = ((a.get("deterministic_scores") or {}).get("coverage") or {}).get("coverage")
        if isinstance(cov, (int, float)):
            coverage_vals.append(float(cov))

    manifest_path = arm_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}

    return {
        "n": len(judgments),
        "mean_correctness": mean(correctness),
        "mean_completeness": mean(completeness),
        "mean_faithfulness": mean(faithfulness),
        "mean_groundedness": mean(groundedness),
        "verdicts": {
            "CORRECT": verdicts.get("CORRECT", 0),
            "PARTIAL": verdicts.get("PARTIAL", 0),
            "INCORRECT": verdicts.get("INCORRECT", 0),
            "other": {k: v for k, v in verdicts.items() if k not in {"CORRECT", "PARTIAL", "INCORRECT"}},
        },
        "hallucinations_total": halluc_total,
        "hallucination_cases": halluc_cases,
        "evidence_records": records,
        "related": related,
        "mean_coverage": mean(coverage_vals),
        "wall_s": manifest.get("wall_s"),
        "manifest_count": manifest.get("count"),
        "manifest_ok": manifest.get("ok"),
        "llm": manifest.get("llm"),
        "source_files": {
            "judgments": len(judgments),
            "answers": len(answer_files),
            "manifest": 1 if manifest_path.exists() else 0,
        },
    }


LETTERS = {
    "untruncated-fixed/deterministic": "A",
    "untruncated-fixed/llm": "B",
    "untruncated-fixed/gold_llm": "C",
    "untruncated-claimnarr/gold_llm": "D",
    "untruncated-loop2/llm_loop": "E",
    "untruncated-goldloop/gold_loop_llm": "F",
    "untruncated-generic/generic": "G",
}


def main() -> None:
    current: dict[str, dict] = {}
    superseded: dict[str, dict] = {}
    for run_dir in sorted(ROOT.iterdir()):
        if not run_dir.is_dir():
            continue
        for arm_dir in sorted(run_dir.iterdir()):
            if not arm_dir.is_dir() or not (arm_dir / "answers").is_dir():
                continue
            key = f"{run_dir.name}/{arm_dir.name}"
            target = superseded if run_dir.name in SUPERSEDED else current
            stats = arm_stats(arm_dir)
            target[key] = {"letter": LETTERS.get(key), **stats}

    a = current["untruncated-fixed/deterministic"]
    b = current["untruncated-fixed/llm"]
    c = current["untruncated-fixed/gold_llm"]
    f = current["untruncated-goldloop/gold_loop_llm"]
    g = current["untruncated-generic/generic"]
    derived = {
        "b_minus_c_correctness": round(b["mean_correctness"] - c["mean_correctness"], 6),
        "g_minus_f_correctness": round(g["mean_correctness"] - f["mean_correctness"], 6),
        "wall_ratio_B_over_A": round(b["wall_s"] / a["wall_s"], 2),
        "wall_ratio_F_over_A": round(f["wall_s"] / a["wall_s"], 2),
        "wall_ratio_E_over_A": round(current["untruncated-loop2/llm_loop"]["wall_s"] / a["wall_s"], 2),
        "sign_convention": (
            "Both deltas are treated-minus-reference, so both are negative and "
            "directly comparable: B - C isolates LLM planning against the same "
            "extraction and synthesis; G - F isolates disabling the templates "
            "against the best deterministic-planned arm. Plan 01 calls the "
            "second one the 'F - G delta (-0.357)'; F - G is +0.356834, so the "
            "figure it quotes is this G - F value and the letters in its label "
            "are the wrong way round."
        ),
        "wall_ratio_note": (
            "Wall ratios divide the arm's manifest wall_s by Arm A's 1.6 s. The "
            "pre-fix record quoted 392x for B over A, which is 1019.7 / 2.6 - "
            "the same numerator against the superseded Arm A wall time."
        ),
    }

    doc = {
        "_derivation": {
            "generated_by": "docs/plans/robustness/_overnight/ Task 4",
            "generated_at": "2026-08-04",
            "method": (
                "Every metric is recomputed from the committed artifacts. Means "
                "are unweighted over the arm's *.judgment.json files; verdict "
                "counts are of the judgment `verdict` field; hallucinations "
                "count entries in the judgment `hallucinations` list, and "
                "`hallucination_cases` counts judgments with a non-empty list. "
                "`evidence_records` and `related` sum `evidence_volume.records` "
                "and `evidence_volume.related` over the answer files; "
                "`mean_coverage` averages "
                "`deterministic_scores.coverage.coverage`. `wall_s` is read "
                "from the arm's manifest.json. No figure is carried in from "
                "prose."
            ),
            "superseded_rule": (
                "untruncated/ and untruncated-loop/ are the pre-defect-fix runs. "
                "They are reported separately and must never be aggregated with "
                "the post-fix arms."
            ),
            "unjudged": (
                "Arms with n=0 have answers but no judgment files. Their means "
                "are null by construction; only their artifact-level counts are "
                "meaningful."
            ),
        },
        "arms": current,
        "derived": derived,
        "superseded": superseded,
    }
    print(json.dumps(doc, indent=2))


if __name__ == "__main__":
    main()
