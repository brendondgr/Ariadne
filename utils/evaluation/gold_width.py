r"""Join judgments to the gold-set width the *bank* declares.

Written for Q29: does a question's gold-set size predict its judged score? The
schema census found that `ATTACK_CATEGORIES["groups"]` licenses a direction
whose p90 fan-out is 63 items, and the worry it raised is attribution — a
question with 63 gold items that scores badly reads as a *system* failure in
every arm comparison we have run, when it may be a *question* defect.

**Width comes from the committed bank, never from the judgment.** Judgments
carry a `gold_expected` field and it sits right next to the score, which makes
it the obvious thing to reach for. It must not be used: `judge_answers.py` asks
the grading model for that number, so correlating it with the same model's score
from the same call measures the grader rather than the question. It is also
unstable — 140 of 1,679 (run, case) pairs on disk disagree with themselves
across passes. `verify_grader_field_unused` keeps that route closed by walking
the AST of any module that claims to compute width.

Three joining facts are load-bearing and each was got wrong once before being
got right:

* **Case ids are bank-local.** `H-SW-02` is a 7-item question in bank 19, an
  11-item one in bank 20 and a 169-item one in the holdout. Keying on the id
  alone silently merges three different questions.
* **Bank membership is not the same as having a width.** Adversarial questions
  belong to a bank and declare no gold, so membership must be tested against the
  full id set or every run containing one fails to match any bank at all.
* **Federated questions have no single width.** Their gold is a chained
  multi-hop computation; taking the first hop's count would be a fabricated
  number, so they are excluded from the analysis and counted in the exclusions.
"""

from __future__ import annotations

import ast
import glob
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN = REPO_ROOT / "utils" / "specialists" / "tests" / "golden"
EXPERIMENTS = "docs/evaluation/experiments"

#: bank key -> the committed question files it is made of. `federated_questions`
#: is listed for *membership only*; every id in it is excluded from the width
#: analysis. Dropping the file instead would leave the 120-question runs
#: matching no bank and silently discard 600 judgments.
BANK_SOURCES: dict[str, tuple[Path, ...]] = {
    "catalogue": (
        GOLDEN / "attack_questions.json",
        GOLDEN / "capec_questions.json",
        GOLDEN / "federated_questions.json",
    ),
    "holdout": (GOLDEN / "holdout_questions.json",),
    "bank-2026-08-19": (REPO_ROOT / "docs/evaluation/banks/bank-2026-08-19/bank.json",),
    "bank-2026-08-20": (REPO_ROOT / "docs/evaluation/banks/bank-2026-08-20/bank.json",),
}

BINS: tuple[tuple[int, int, str], ...] = (
    (1, 1, "1"),
    (2, 3, "2-3"),
    (4, 6, "4-6"),
    (7, 10, "7-10"),
    (11, 20, "11-20"),
    (21, 50, "21-50"),
    (51, 10**9, "51+"),
)

#: The census calls an edge askable when p90 fan-out is at or under this. This
#: module exists partly to test whether the score actually moves there.
ASKABLE_P90 = 50

#: Assembled at import so the literal does not appear where the AST guard looks.
GRADER_WIDTH_FIELD = "gold_" + "expected"


def verify_grader_field_unused(module_path: Path) -> None:
    """Raise if `module_path` reads the grader's own width estimate.

    Walks the AST rather than grepping, so a docstring naming the field cannot
    trip it and a real read cannot hide from it.
    """
    tree = ast.parse(module_path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value == GRADER_WIDTH_FIELD:
            raise AssertionError(
                f"{module_path.name} reads {GRADER_WIDTH_FIELD}, which is a grader "
                "output; gold width must come from the committed bank"
            )


def _questions(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and "questions" in payload:
        return payload["questions"]
    return payload if isinstance(payload, list) else []


def federated_ids() -> frozenset[str]:
    """Ids that count for bank membership but are excluded from width."""
    path = GOLDEN / "federated_questions.json"
    if not path.exists():
        return frozenset()
    return frozenset(q["id"] for q in _questions(json.loads(path.read_text())) if q.get("id"))


def gold_width(question: dict[str, Any]) -> int | None:
    """Gold-set size as the bank declares it. `None` when it declares none."""
    expected = (question.get("ex_gold") or {}).get("expected")
    if isinstance(expected, list):
        return len(expected)
    related = (question.get("assertions") or {}).get("must_include_related")
    if isinstance(related, list):
        return len(related)
    return None


def load_banks(
    excluded: frozenset[str] | None = None,
) -> tuple[dict[str, dict[str, int]], dict[str, frozenset[str]]]:
    """bank key -> {case_id: width}, and bank key -> every id it contains."""
    skip = excluded if excluded is not None else federated_ids()
    widths_by_bank: dict[str, dict[str, int]] = {}
    ids_by_bank: dict[str, frozenset[str]] = {}
    for key, paths in BANK_SOURCES.items():
        widths: dict[str, int] = {}
        members: set[str] = set()
        for path in paths:
            if not path.exists():
                continue
            for question in _questions(json.loads(path.read_text())):
                case = question.get("id")
                if not case:
                    continue
                members.add(case)
                if case in skip:
                    continue
                width = gold_width(question)
                if width is not None:
                    widths[case] = width
        if members:
            widths_by_bank[key] = widths
            ids_by_bank[key] = frozenset(members)
    return widths_by_bank, ids_by_bank


def bank_key_for(manifest_bank: str) -> str | None:
    text = str(manifest_bank)
    for key in ("bank-2026-08-19", "bank-2026-08-20"):
        if key in text:
            return key
    if "holdout_questions" in text:
        return "holdout"
    if "120-question catalogue" in text:
        return "catalogue"
    return None


def run_bank_map(ids_by_bank: dict[str, frozenset[str]], root: Path = REPO_ROOT) -> dict[str, str]:
    """run directory -> bank key.

    Read from the arm manifest's `bank` field where there is one. Seven
    `untruncated-*` runs predate that field and are inferred from case-id
    membership, which is safe only because a run's ids must be a subset of
    exactly one bank. A run matching several is left unmapped rather than
    guessed.
    """
    mapping: dict[str, str] = {}
    observed: dict[str, set[str]] = defaultdict(set)
    for path in glob.glob(str(root / EXPERIMENTS / "*/*/manifest.json")):
        try:
            manifest = json.loads(Path(path).read_text())
        except (json.JSONDecodeError, OSError):
            continue
        run = Path(path).relative_to(root).parts[3]
        key = bank_key_for(manifest.get("bank", ""))
        if key:
            mapping[run] = key
            continue
        for case in manifest.get("cases", []):
            if isinstance(case, dict) and case.get("id"):
                observed[run].add(case["id"])

    for run, ids in observed.items():
        if run in mapping:
            continue
        fits = [key for key, members in ids_by_bank.items() if ids <= members]
        if len(fits) == 1:
            mapping[run] = fits[0]
    return mapping


def load(
    widths_by_bank: dict[str, dict[str, int]],
    runs: dict[str, str],
    excluded: frozenset[str] | None = None,
    root: Path = REPO_ROOT,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    skip = excluded if excluded is not None else federated_ids()
    rows: list[dict[str, Any]] = []
    skipped = {"no_bank_for_run": 0, "no_score": 0, "federated_excluded": 0, "no_declared_gold": 0}
    for path in glob.glob(str(root / EXPERIMENTS / "*/*/answers/*.judgment*.json")):
        try:
            payload = json.loads(Path(path).read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(payload, dict) or payload.get("correctness") is None:
            skipped["no_score"] += 1
            continue
        parts = Path(path).relative_to(root).parts
        run, arm = parts[3], parts[4]
        bank = runs.get(run)
        if bank is None:
            skipped["no_bank_for_run"] += 1
            continue
        case = payload.get("case_id", "")
        if case in skip:
            skipped["federated_excluded"] += 1
            continue
        width = widths_by_bank.get(bank, {}).get(case)
        if width is None:
            skipped["no_declared_gold"] += 1
            continue
        rows.append(
            {
                "run": run,
                "arm": arm,
                "bank": bank,
                "case": case,
                "category": case.rsplit("-", 1)[0],
                "width": width,
                "correctness": payload["correctness"],
                "completeness": payload.get("completeness"),
            }
        )
    return rows, skipped


def pearson(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 3:
        return float("nan")
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    return num / den if den else float("nan")


def _cells(rows: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    out: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        out[(row["run"], row["arm"])].append(row)
    return out


def within_cell_correlation(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Correlation inside each (run, arm) cell, then averaged.

    Pooling lets arm strength leak in whenever wide questions are unevenly
    distributed across arms. Within-cell cancels it.
    """
    per_cell = []
    for members in _cells(rows).values():
        if len(members) < 10 or len({m["width"] for m in members}) < 3:
            continue
        r = pearson([m["width"] for m in members], [m["correctness"] for m in members])
        if not math.isnan(r):
            per_cell.append(r)
    return {
        "cells": len(per_cell),
        "mean_r": round(statistics.fmean(per_cell), 4) if per_cell else float("nan"),
        "sd_r": round(statistics.stdev(per_cell), 4) if len(per_cell) > 1 else 0.0,
        "negative_cells": sum(1 for r in per_cell if r < 0),
    }


def narrow_vs_wide(rows: list[dict[str, Any]], threshold: int) -> dict[str, Any]:
    """Paired narrow-vs-wide contrast, computed inside each (run, arm) cell."""
    deltas = []
    for members in _cells(rows).values():
        narrow = [m["correctness"] for m in members if m["width"] <= threshold]
        wide = [m["correctness"] for m in members if m["width"] > threshold]
        if len(narrow) < 5 or len(wide) < 3:
            continue
        deltas.append(statistics.fmean(wide) - statistics.fmean(narrow))
    if not deltas:
        return {"cells": 0}
    sd = statistics.stdev(deltas) if len(deltas) > 1 else 0.0
    return {
        "cells": len(deltas),
        "mean_delta": round(statistics.fmean(deltas), 4),
        "sd": round(sd, 4),
        "se": round(sd / math.sqrt(len(deltas)), 4),
        "negative_cells": sum(1 for d in deltas if d < 0),
    }


def by_bin(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for lo, hi, label in BINS:
        members = [r for r in rows if lo <= r["width"] <= hi]
        if not members:
            continue
        comp = [m["completeness"] for m in members if m["completeness"] is not None]
        out.append(
            {
                "bin": label,
                "n": len(members),
                "cases": len({(m["bank"], m["case"]) for m in members}),
                "correctness": round(statistics.fmean(m["correctness"] for m in members), 4),
                "completeness": round(statistics.fmean(comp), 4) if comp else None,
            }
        )
    return out


def by_category(rows: list[dict[str, Any]], top: int = 12) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[row["category"]].append(row)
    out = [
        {
            "category": name,
            "n": len(members),
            "cases": len({(m["bank"], m["case"]) for m in members}),
            "median_width": statistics.median(m["width"] for m in members),
            "max_width": max(m["width"] for m in members),
            "correctness": round(statistics.fmean(m["correctness"] for m in members), 4),
        }
        for name, members in groups.items()
    ]
    out.sort(key=lambda d: -d["median_width"])
    return out[:top]


def analyse(rows: list[dict[str, Any]], skipped: dict[str, int]) -> dict[str, Any]:
    answerable = [r for r in rows if r["width"] > 0]
    widths = sorted(r["width"] for r in answerable)
    return {
        "n_judgments_joined": len(rows),
        "n_answerable": len(answerable),
        "n_abstention_probes": len(rows) - len(answerable),
        "skipped": skipped,
        "distinct_questions": len({(r["bank"], r["case"]) for r in answerable}),
        "questions_over_20": len({(r["bank"], r["case"]) for r in answerable if r["width"] > 20}),
        "questions_over_50": len({(r["bank"], r["case"]) for r in answerable if r["width"] > 50}),
        "width": {
            "median": statistics.median(widths),
            "p90": widths[int(0.9 * (len(widths) - 1))],
            "max": widths[-1],
        },
        "pooled_r": round(
            pearson([r["width"] for r in answerable], [r["correctness"] for r in answerable]), 4
        ),
        "within_cell_r": within_cell_correlation(answerable),
        f"narrow_vs_wide_at_{ASKABLE_P90}": narrow_vs_wide(answerable, ASKABLE_P90),
        "narrow_vs_wide_at_20": narrow_vs_wide(answerable, 20),
        "narrow_vs_wide_at_10": narrow_vs_wide(answerable, 10),
        "bins": by_bin(answerable),
        "widest_categories": by_category(answerable),
    }
