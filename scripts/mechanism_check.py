#!/usr/bin/env python3
"""Per-mechanism verification: did each repair actually fix its own defect?

    uv run python scripts/mechanism_check.py                 # model-free slices
    uv run python scripts/mechanism_check.py --narrator      # + the live LLM slice

`EXP-2026-09-018`. The judged runs cost nine hours and the last two both found
defects a cheap check could have caught, so this asserts each mechanism's
*defining property* on its own slice instead of inferring it from a mean.

The slices come from `EXP-2026-09-017`'s committed `mechanisms.csv` and are
fixed at the pre-repair commit: a denominator that moves with the intervention
measures the intervention twice.

Each mechanism has one property that says whether its repair works, and it is
not the score:

``ns``        a Category or View anchor must RETRIEVE. Zero records means the
              seed bound to nothing, which is the defect itself.
``capec``     a draft touching one of the five edges must reach the database.
              A gate rejection naming ``allowed_edge_patterns`` is the defect.
``chain``     a two-hop request must emit an ordered route, and where it walks
              two legs the neighbour must name the hop it came through.
``filter``    a bound filter must reach the query, and the claim must say what
              the set was restricted to — and only when the query did it.
``empty``     an empty requested set must be stated, not left to inference.
``narrator``  the narrator must actually run. Fallbacks over ANSWERS, never
              over files (`EXP-2026-09-016` A-8).
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path
from statistics import mean

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

MECHANISMS = REPO / (
    "docs/research/experiments/EXP-2026-09-017-correctness-improvement-diagnostic"
    "/data/mechanisms.csv"
)
CONTROL = REPO / (
    "docs/research/experiments/EXP-2026-09-018-correctness-repair"
    "/data/reference/reference-datafix.json"
)
BANK = REPO / "docs/evaluation/composition/bank/bank-dev.json"
#: `EXP-2026-09-016` A-8: healthy is at or below this, over answers.
HEALTHY_FALLBACK = 0.14


def _answers(directory: Path) -> dict[str, dict]:
    out = {}
    for path in sorted(directory.glob("*.json")):
        if ".judgment" in path.name:
            continue
        answer = json.loads(path.read_text())
        out[answer["id"]] = answer
    return out


def _records(answer: dict) -> int:
    return sum(
        len(r.get("records") or [])
        for r in ((answer.get("logic_flow") or {}).get("results") or [])
    )


def _coverage(answer: dict) -> float:
    return ((answer.get("deterministic_scores") or {}).get("coverage") or {}).get(
        "coverage"
    ) or 0.0


def _claims(answer: dict) -> list[dict]:
    return (answer.get("answer") or {}).get("claims") or []


def _queries(answer: dict) -> str:
    return " ".join(
        str(r.get("query") or "")
        for r in ((answer.get("logic_flow") or {}).get("results") or [])
    )


def _errors(answer: dict) -> str:
    return " ".join(
        str(r.get("error") or "")
        for r in ((answer.get("logic_flow") or {}).get("results") or [])
    )


def check(now: dict[str, dict], slices: dict[str, list[str]], control: dict) -> dict:
    report: dict[str, dict] = {}
    for name, ids in slices.items():
        ids = [i for i in ids if i in now]
        if not ids:
            continue
        before = mean(control[i]["coverage"] or 0.0 for i in ids)
        after = mean(_coverage(now[i]) for i in ids)
        row: dict = {
            "n": len(ids),
            "coverage_control": round(before, 4),
            "coverage_now": round(after, 4),
            "zero_record_control": sum(1 for i in ids if control[i]["records"] == 0),
            "zero_record_now": sum(1 for i in ids if _records(now[i]) == 0),
        }
        if name == "capec":
            row["gate_rejections_naming_allowlist"] = sum(
                1 for i in ids if "allowed_edge_patterns" in _errors(now[i])
            )
        if name == "chain":
            row["answers_with_an_ordered_route"] = sum(
                1 for i in ids if "(via " in " ".join(c.get("text", "") for c in _claims(now[i]))
            )
        if name == "filter":
            row["claims_stating_the_restriction"] = sum(
                1 for i in ids
                if "restricted to" in " ".join(c.get("text", "") for c in _claims(now[i]))
            )
        if name == "empty":
            row["answers_stating_an_empty_set"] = sum(
                1 for i in ids if any(c.get("kind") == "absence" for c in _claims(now[i]))
            )
        report[name] = row
    return report


def narrator_slice(ids: list[str], workers: int) -> dict:
    """Run the LLM arm on the narrator slice only, and count fallbacks."""
    root = REPO / "docs/evaluation/experiments/mechanism-narrator-check"
    cmd = [
        sys.executable, "-m", "utils.evaluation.experiment_untruncated",
        "--arm", "generic", "--bank", str(BANK), "--root", str(root),
        "--workers", str(workers), "--llm-model", "default-model",
        "--only", ",".join(ids),
    ]
    env = {
        **__import__("os").environ,
        "SYNTHESIS_LLM_TIMEOUT_S": "600.0",
        "SPECIALIST_LLM_TIMEOUT_S": "4096",
        "ORCH_MAX_HOPS": "5",
    }
    subprocess.check_call(cmd, cwd=REPO, env=env)
    answers = _answers(root / "generic" / "answers")
    fallbacks = {
        i: (a.get("answer") or {}).get("fallback_reason")
        for i, a in answers.items()
        if (a.get("answer") or {}).get("fallback_reason")
    }
    rate = len(fallbacks) / max(len(answers), 1)
    return {
        "answers": len(answers),
        "fallbacks": len(fallbacks),
        "rate": round(rate, 4),
        "healthy_reference": HEALTHY_FALLBACK,
        "healthy": rate <= HEALTHY_FALLBACK,
        "reasons": sorted({str(v).split("(")[0].strip() for v in fallbacks.values()}),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--answers",
        default="docs/evaluation/experiments/repair-after-fixes2-dev/generic_composed/answers",
    )
    parser.add_argument("--narrator", action="store_true",
                        help="also run the LLM arm over the narrator slice")
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    rows = list(csv.DictReader(MECHANISMS.open()))
    slices: dict[str, list[str]] = {}
    for row in rows:
        slices.setdefault(row["mechanism"], []).append(row["id"])
    control = json.loads(CONTROL.read_text())["captures"]["dev/generic_composed"]["cases"]
    now = _answers(REPO / args.answers)

    report = check(now, slices, control)
    order = ["capec", "ns", "chain", "filter", "empty", "narrator", "none"]
    print(f"{'mechanism':10s} {'n':>4s} {'coverage':>18s} {'zero-record':>14s}  property")
    for name in order:
        row = report.get(name)
        if not row:
            continue
        extra = {k: v for k, v in row.items() if k not in
                 ("n", "coverage_control", "coverage_now",
                  "zero_record_control", "zero_record_now")}
        detail = "; ".join(f"{k}={v}" for k, v in extra.items()) or "—"
        print(
            f"{name:10s} {row['n']:4d}  "
            f"{row['coverage_control']:.4f} -> {row['coverage_now']:.4f}   "
            f"{row['zero_record_control']:3d} -> {row['zero_record_now']:3d}    {detail}"
        )

    if args.narrator:
        print("\n-- narrator slice, live LLM arm --")
        report["narrator_live"] = narrator_slice(slices["narrator"], args.workers)
        for key, value in report["narrator_live"].items():
            print(f"  {key}: {value}")

    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2) + "\n")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
