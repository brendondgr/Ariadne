#!/usr/bin/env python3
"""Roll the two experiment arms' independent judgments into ``summary.md``.

Reads ``<root>/<arm>/answers/<id>.judgment.json`` (written by the Sonnet panel)
alongside ``<id>.json`` (the answer + its full retrieved evidence), and emits the
headline means, verdict counts, hallucination totals, the Arm B − Arm A delta,
the delta of both against the committed **truncated** baseline in
``docs/evaluation/independent-eval.md``, and per-category mean correctness.
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any

ARMS = ("deterministic", "llm")
METRICS = ("correctness", "completeness", "faithfulness", "groundedness")
VERDICTS = ("CORRECT", "PARTIAL", "INCORRECT")

# The committed baseline this experiment is measured against: the TRUNCATED run
# graded by the same independent Sonnet panel (docs/evaluation/independent-eval.md).
BASELINE = {
    "label": "baseline (truncated, committed)",
    "n": 120,
    "correctness": 0.8946,
    "completeness": 0.8952,
    "faithfulness": 0.9558,
    "groundedness": 0.9575,
    "verdicts": {"CORRECT": 91, "PARTIAL": 27, "INCORRECT": 2},
    "answers_with_hallucinations": 11,
}
BASELINE_CATEGORIES = {
    "C-ABS": 0.17, "C-CSQ": 0.35, "A-SW": 0.45, "F-CWE": 0.59, "A-GRP": 0.76,
    "A-SCN": 0.85, "A-CMP": 0.86, "C-LKP": 0.88, "A-MC": 0.88, "F-PART": 0.91,
    "F-CTM": 0.92, "A-MIT": 0.94, "C-PRE": 0.95, "A-DET": 0.97, "C-EXE": 0.98,
}


def _category_of(qid: str) -> str:
    parts = qid.split("-")
    return "-".join(parts[:2]) if len(parts) >= 3 else qid


def load_arm(root: Path, arm: str) -> list[dict[str, Any]]:
    """Every judged case for one arm, joined to its answer artifact."""
    answers = root / arm / "answers"
    rows: list[dict[str, Any]] = []
    for judgment_path in sorted(answers.glob("*.judgment.json")):
        cid = judgment_path.name[: -len(".judgment.json")]
        try:
            judgment = json.loads(judgment_path.read_text())
        except ValueError:
            continue
        artifact_path = answers / f"{cid}.json"
        artifact = json.loads(artifact_path.read_text()) if artifact_path.exists() else {}
        rows.append({
            "id": cid,
            "category": artifact.get("category") or _category_of(cid),
            "tier": artifact.get("tier", ""),
            "verdict": judgment.get("verdict"),
            **{m: float(judgment.get(m) or 0.0) for m in METRICS},
            "hallucinations": list(judgment.get("hallucinations") or []),
            "rationale": judgment.get("rationale", ""),
            "evidence_volume": artifact.get("evidence_volume", {}),
            "coverage": (artifact.get("deterministic_scores") or {}).get("coverage"),
            "wall_s": (artifact.get("run_meta") or {}).get("wall_s"),
        })
    return rows


def _mean(vals: list[float]) -> float:
    return round(statistics.fmean(vals), 4) if vals else 0.0


def summarize_arm(rows: list[dict[str, Any]]) -> dict[str, Any]:
    verdicts = {v: sum(1 for r in rows if r["verdict"] == v) for v in VERDICTS}
    halls = [h for r in rows for h in r["hallucinations"]]
    covered = [r["coverage"] for r in rows if r.get("coverage")]
    by_cat: dict[str, dict[str, Any]] = {}
    for row in rows:
        cat = by_cat.setdefault(row["category"], {"n": 0, "correctness": [], "verdicts": {}})
        cat["n"] += 1
        cat["correctness"].append(row["correctness"])
        cat["verdicts"][row["verdict"]] = cat["verdicts"].get(row["verdict"], 0) + 1
    for cat in by_cat.values():
        cat["mean_correctness"] = _mean(cat["correctness"])
        del cat["correctness"]
    return {
        "n": len(rows),
        **{m: _mean([r[m] for r in rows]) for m in METRICS},
        "verdicts": verdicts,
        "total_hallucinations": len(halls),
        "answers_with_hallucinations": sum(1 for r in rows if r["hallucinations"]),
        "evidence_records": sum(r["evidence_volume"].get("records", 0) for r in rows),
        "evidence_related": sum(r["evidence_volume"].get("related", 0) for r in rows),
        "mean_answer_coverage": _mean([c["coverage"] for c in covered]),
        "coverage_entries": len(covered),
        "by_category": dict(sorted(by_cat.items())),
    }


def _sign(x: float, places: int = 4) -> str:
    return f"{x:+.{places}f}"


def render(root: Path, arms: dict[str, dict[str, Any]], rows: dict[str, list[dict]],
           notes: list[str]) -> str:
    det, llm = arms.get("deterministic", {}), arms.get("llm", {})
    out: list[str] = []
    a = out.append

    a("# Un-truncated Retrieval Experiment — Two Arms, 120 Questions Each")
    a("")
    a("Same 120 golden questions, same order, same two graphs (ATT&CK/Neo4j 4,369 nodes; "
      "CAPEC/Gremlin 4,769 nodes). The **common** change to both arms lifts every retrieval, "
      "synthesis-evidence and judge-artifact cap so `describe`/`expand` return full "
      "neighbourhoods and synthesis receives the whole evidence set. The **independent "
      "variable** is the LLM: Arm A runs no LLM at all, Arm B runs LLM planning + LLM "
      "synthesis. Each arm was graded case-by-case by 120 independent Sonnet 5 agents "
      "(240 total) against the gold assertions *and* the full retrieved evidence.")
    a("")

    a("## Headline")
    a("")
    a("| Metric | Arm A — deterministic | Arm B — LLM-planned | Baseline (truncated) |")
    a("|---|---|---|---|")
    for m in METRICS:
        a(f"| {m} | **{det.get(m, 0):.4f}** | **{llm.get(m, 0):.4f}** | {BASELINE[m]:.4f} |")
    a(f"| n graded | {det.get('n', 0)} | {llm.get('n', 0)} | {BASELINE['n']} |")
    a("")
    a("**Verdicts**")
    a("")
    a("| Arm | CORRECT | PARTIAL | INCORRECT | answers w/ hallucinations | total hallucinations |")
    a("|---|---|---|---|---|---|")
    for label, s in (("A — deterministic", det), ("B — LLM-planned", llm)):
        v = s.get("verdicts", {})
        a(f"| {label} | {v.get('CORRECT', 0)} | {v.get('PARTIAL', 0)} | {v.get('INCORRECT', 0)} "
          f"| {s.get('answers_with_hallucinations', 0)} | {s.get('total_hallucinations', 0)} |")
    bv = BASELINE["verdicts"]
    a(f"| Baseline (truncated) | {bv['CORRECT']} | {bv['PARTIAL']} | {bv['INCORRECT']} "
      f"| {BASELINE['answers_with_hallucinations']} | — |")
    a("")

    a("## Deltas")
    a("")
    a("| Metric | B − A | A − baseline | B − baseline |")
    a("|---|---|---|---|")
    for m in METRICS:
        a(f"| {m} | {_sign(llm.get(m, 0) - det.get(m, 0))} "
          f"| {_sign(det.get(m, 0) - BASELINE[m])} | {_sign(llm.get(m, 0) - BASELINE[m])} |")
    a("")
    a("| Verdict | B − A | A − baseline | B − baseline |")
    a("|---|---|---|---|")
    for v in VERDICTS:
        dv, lv = det.get("verdicts", {}).get(v, 0), llm.get("verdicts", {}).get(v, 0)
        a(f"| {v} | {lv - dv:+d} | {dv - bv[v]:+d} | {lv - bv[v]:+d} |")
    a("")

    a("## Retrieval volume actually pulled")
    a("")
    a("| Arm | evidence records | related neighbours | mean answer coverage (gold ids surfaced) |")
    a("|---|---|---|---|")
    for label, s in (("A — deterministic", det), ("B — LLM-planned", llm)):
        a(f"| {label} | {s.get('evidence_records', 0)} | {s.get('evidence_related', 0)} "
          f"| {s.get('mean_answer_coverage', 0):.4f} ({s.get('coverage_entries', 0)} scorable) |")
    a("")

    a("## Weakest categories by mean correctness")
    a("")
    for label, key in (("Arm A — deterministic", "deterministic"), ("Arm B — LLM-planned", "llm")):
        s = arms.get(key, {})
        cats = sorted(
            ((c, d) for c, d in s.get("by_category", {}).items() if d["mean_correctness"] < 1.0),
            key=lambda kv: kv[1]["mean_correctness"],
        )
        a(f"### {label}")
        a("")
        if not cats:
            a("Every category scored a mean correctness of 1.0.")
            a("")
            continue
        a("| Category | n | mean correctness | baseline | Δ vs baseline | verdicts |")
        a("|---|---|---|---|---|---|")
        for cat, d in cats:
            base = BASELINE_CATEGORIES.get(cat)
            base_s = f"{base:.2f}" if base is not None else "1.00*"
            delta = d["mean_correctness"] - (base if base is not None else 1.0)
            a(f"| {cat} | {d['n']} | {d['mean_correctness']:.2f} | {base_s} | {delta:+.2f} "
              f"| {json.dumps(d['verdicts'], sort_keys=True)} |")
        a("")
        a("<sub>*Categories absent from the baseline's weakest table scored 1.00 there.</sub>")
        a("")

    a("## Every non-CORRECT case")
    a("")
    for label, key in (("Arm A — deterministic", "deterministic"), ("Arm B — LLM-planned", "llm")):
        bad = [r for r in rows.get(key, []) if r["verdict"] != "CORRECT"]
        a(f"### {label} — {len(bad)} of {len(rows.get(key, []))}")
        a("")
        if not bad:
            a("None.")
            a("")
            continue
        a("| Case | verdict | corr | compl | faith | ground | hallucinations |")
        a("|---|---|---|---|---|---|---|")
        for r in sorted(bad, key=lambda r: (r["correctness"], r["id"])):
            h = len(r["hallucinations"])
            a(f"| {r['id']} | {r['verdict']} | {r['correctness']:.2f} | {r['completeness']:.2f} "
              f"| {r['faithfulness']:.2f} | {r['groundedness']:.2f} | {h} |")
        a("")

    a("## Hallucinations flagged")
    a("")
    for label, key in (("Arm A — deterministic", "deterministic"), ("Arm B — LLM-planned", "llm")):
        flagged = [(r["id"], h) for r in rows.get(key, []) for h in r["hallucinations"]]
        a(f"### {label} — {len(flagged)}")
        a("")
        if not flagged:
            a("None flagged.")
            a("")
            continue
        for cid, h in flagged:
            a(f"- **{cid}**: {h}")
        a("")

    if notes:
        a("## Notes and caveats")
        a("")
        for n in notes:
            a(f"- {n}")
        a("")

    a("Per-case verdicts: `<arm>/answers/<id>.judgment.json`; answers + full retrieved "
      "evidence: `<arm>/answers/<id>.json`; run configuration: `<arm>/manifest.json`.")
    a("")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="docs/evaluation/experiments/untruncated")
    parser.add_argument("--note", action="append", default=[])
    args = parser.parse_args(argv)

    root = Path(args.root)
    rows = {arm: load_arm(root, arm) for arm in ARMS}
    arms = {arm: summarize_arm(r) for arm, r in rows.items() if r}
    (root / "summary.json").write_text(
        json.dumps({"arms": arms, "baseline": BASELINE}, indent=2), encoding="utf-8"
    )
    (root / "summary.md").write_text(render(root, arms, rows, args.note), encoding="utf-8")
    for arm, s in arms.items():
        print(f"{arm}: n={s['n']} " + " ".join(f"{m}={s[m]:.4f}" for m in METRICS))
    print(f"wrote {root/'summary.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
