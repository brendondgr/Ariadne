#!/usr/bin/env python3
"""Reporter agent (stage 3): ``judgments.jsonl`` -> ``golden-eval.{md,json}``.

Aggregates the judge's per-answer correctness verdicts (joined with the runner's
answers for set/tier/source context) into overall, per-set, per-tier, and
per-source roll-ups, plus a worst-performers list for follow-up. Produces both a
machine-readable JSON and a human-readable Markdown report purely from the
persisted judgments, so reporting is cheap and repeatable and never re-runs the
pipeline or the judge. No wall-clock timestamp is embedded, so an LLM-off report
is byte-reproducible (matching the ``utils.evaluation`` discipline).
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

from utils.evaluation.harness.contracts import (
    AnswerRecord,
    CorrectnessVerdict,
    read_jsonl,
)
from utils.evaluation.harness.golden import ALL_SETS
from utils.evaluation.stats import wilson_interval

logger = logging.getLogger("ariadne.evaluation.harness.reporter")

TIERS = ("easy", "medium", "hard")
_WORST_LIMIT = 15


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _agg(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Roll one group of joined rows into summary metrics."""
    n = len(rows)
    labels = {"correct": 0, "partial": 0, "incorrect": 0}
    for r in rows:
        labels[r["label"]] = labels.get(r["label"], 0) + 1
    p, lo, hi = wilson_interval(labels["correct"], n)
    return {
        "n": n,
        "correct": labels["correct"],
        "partial": labels["partial"],
        "incorrect": labels["incorrect"],
        "pass_rate": round(p, 4),
        "pass_rate_ci95": [round(lo, 4), round(hi, 4)],
        "mean_correctness": round(_mean([r["correctness"] for r in rows]), 4),
        "mean_id_recall": round(_mean([r["id_recall"] for r in rows]), 4),
        "mean_id_precision": round(_mean([r["id_precision"] for r in rows]), 4),
        "llm_graded": sum(1 for r in rows if r["verdict_source"] == "llm"),
    }


def build_report(
    verdicts: list[CorrectnessVerdict],
    answers_by_id: dict[str, AnswerRecord],
) -> dict[str, Any]:
    """Join verdicts with answers and aggregate into the report structure."""
    rows: list[dict[str, Any]] = []
    for v in verdicts:
        a = answers_by_id.get(v.question_id)
        rows.append(
            {
                "question_id": v.question_id,
                "set": a.set_name if a else "?",
                "tier": a.tier if a else "?",
                "source": a.source if a else "?",
                "question": a.question if a else "",
                "correctness": v.correctness,
                "label": v.label,
                "id_recall": v.id_recall,
                "id_precision": v.id_precision,
                "verdict_source": v.source,
                "missing_ids": v.missing_ids,
                "rationale": v.rationale,
                "error": a.error if a else None,
            }
        )

    by_set = {s: _agg([r for r in rows if r["set"] == s]) for s in ALL_SETS}
    by_set = {s: agg for s, agg in by_set.items() if agg["n"]}
    by_tier = {t: _agg([r for r in rows if r["tier"] == t]) for t in TIERS}
    by_tier = {t: agg for t, agg in by_tier.items() if agg["n"]}
    by_source = {s: _agg([r for r in rows if r["source"] == s]) for s in ALL_SETS}
    by_source = {s: agg for s, agg in by_source.items() if agg["n"]}

    worst = [
        {
            "question_id": r["question_id"],
            "set": r["set"],
            "tier": r["tier"],
            "correctness": round(r["correctness"], 4),
            "label": r["label"],
            "missing_ids": r["missing_ids"],
            "rationale": r["rationale"],
            "error": r["error"],
        }
        for r in sorted(rows, key=lambda r: r["correctness"])
        if r["label"] != "correct"
    ][:_WORST_LIMIT]

    llm_graded = sum(1 for r in rows if r["verdict_source"] == "llm")
    return {
        "overall": _agg(rows),
        "by_set": by_set,
        "by_tier": by_tier,
        "by_source": by_source,
        "worst": worst,
        "meta": {
            "answers_covered": len(answers_by_id),
            "judged": len(rows),
            "llm_graded": llm_graded,
            "grading": (
                "local-LLM (correctness) with deterministic id backstop"
                if llm_graded
                else "deterministic id backstop only (LLM off / all fell back)"
            ),
        },
    }


def _md_row(name: str, agg: dict[str, Any]) -> str:
    return (
        f"| {name} | {agg['n']} | {agg['correct']} | {agg['partial']} | "
        f"{agg['incorrect']} | {agg['pass_rate']:.2f} | {agg['mean_correctness']:.2f} | "
        f"{agg['mean_id_recall']:.2f} | {agg['mean_id_precision']:.2f} |"
    )


def render_markdown(report: dict[str, Any]) -> str:
    o = report["overall"]
    meta = report["meta"]
    lines = [
        "# Golden Evaluation — Correctness Report",
        "",
        "Run → judge → report over the golden question set. Correctness is graded "
        "against each entry's golden expected answer (the bank assertions): the "
        "local LLM rates correctness with a deterministic id recall/precision "
        "backstop.",
        "",
        f"- **Grading:** {meta['grading']}",
        f"- **Judged:** {meta['judged']} answers "
        f"({meta['llm_graded']} by the local LLM, the rest by the deterministic backstop)",
        "",
        "## Overall",
        "",
        f"- **Pass rate (label = correct):** {o['pass_rate']:.2%} "
        f"(95% CI {o['pass_rate_ci95'][0]:.2%}–{o['pass_rate_ci95'][1]:.2%})",
        f"- **Mean correctness:** {o['mean_correctness']:.3f}",
        f"- **Labels:** correct={o['correct']} · partial={o['partial']} · incorrect={o['incorrect']} (n={o['n']})",
        f"- **Mean id recall / precision:** {o['mean_id_recall']:.3f} / {o['mean_id_precision']:.3f}",
        "",
    ]
    header = (
        "| Group | n | correct | partial | incorrect | pass | mean corr | "
        "id recall | id prec |\n"
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"
    )
    for title, block in (
        ("By set", report["by_set"]),
        ("By tier", report["by_tier"]),
        ("By source", report["by_source"]),
    ):
        lines += [f"## {title}", "", header]
        for name, agg in block.items():
            lines.append(_md_row(name, agg))
        lines.append("")

    lines += ["## Lowest-scoring answers", ""]
    if not report["worst"]:
        lines.append("_All judged answers were graded correct._")
    else:
        for w in report["worst"]:
            miss = (
                f" missing {', '.join(w['missing_ids'][:8])}" if w["missing_ids"] else ""
            )
            err = f" [error: {w['error']}]" if w["error"] else ""
            lines.append(
                f"- **{w['question_id']}** ({w['set']}/{w['tier']}) — "
                f"{w['label']}, correctness {w['correctness']:.2f}.{miss}{err} "
                f"{w['rationale']}".rstrip()
            )
    lines.append("")
    return "\n".join(lines)


class ReporterAgent:
    """Aggregates judgments into the final Markdown + JSON report."""

    def run_files(
        self,
        answers_path: str,
        judgments_path: str,
        report_md: str,
        report_json: str,
    ) -> int:
        if not os.path.exists(judgments_path):
            print(
                f"[report] no judgments at {judgments_path} — run the 'judge' stage first",
                file=sys.stderr,
            )
            return 1
        verdicts = [CorrectnessVerdict.from_dict(d) for d in read_jsonl(judgments_path)]
        answers_by_id: dict[str, AnswerRecord] = {}
        if os.path.exists(answers_path):
            for d in read_jsonl(answers_path):
                rec = AnswerRecord.from_dict(d)
                answers_by_id[rec.question_id] = rec

        report = build_report(verdicts, answers_by_id)
        self._write(report, report_md, report_json)
        o = report["overall"]
        print(
            f"[report] wrote {report_md} and {report_json} — "
            f"pass rate {o['pass_rate']:.2%}, mean correctness {o['mean_correctness']:.3f} "
            f"over {o['n']} answers",
            file=sys.stderr,
        )
        return 0

    @staticmethod
    def _write(report: dict[str, Any], report_md: str, report_json: str) -> None:
        import json

        for path in (report_md, report_json):
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
        with open(report_json, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        with open(report_md, "w", encoding="utf-8") as handle:
            handle.write(render_markdown(report))
