#!/usr/bin/env python3
"""Assemble the end-to-end evaluation report (JSON + Markdown).

Distinct from ``component_report`` (planner + specialists in isolation): this
report grades the *assembled* pipeline on the four ``goals.md`` end-to-end
metrics plus the LLM-judge dimensions. ``build_json`` / ``build_markdown`` are
pure so the LLM-off report is byte-reproducible; the LLM-judge block is labeled
non-reproducible only when a real LLM verdict contributed.
"""

from __future__ import annotations

import json
from typing import Any

# Concrete, reviewable operationalizations of the two novel metrics (surfaced in
# the report header so the definitions travel with the numbers).
DEFINITIONS = {
    "cross_source_answer_accuracy": (
        "Live cross-source join values vs the snapshot-derived must_correlate set "
        "(exact-set-match + precision/recall/F1); negatives must surface none."
    ),
    "capec_attack_mapping_recall": (
        "Of the resolvable ATT&CK technique ids a CAPEC pattern maps to, the "
        "fraction the pipeline surfaced on the CAPEC side (micro-averaged)."
    ),
    "provenance_correctness": (
        "Fraction of rendered-claim citations resolving to a retrieved record "
        "whose provenance is complete and whose recorded query was executed; "
        "abstentions must carry a truthful proof."
    ),
    "analyst_inspectability": (
        "Mean of citation coverage, claim->record->query traceability, and "
        "abstention-proof completeness across every answer."
    ),
}


def collect_e2e(
    *,
    live: bool,
    judge_config=None,
    limit: int | None = None,
    include_single: bool = True,
) -> dict[str, Any]:
    """Run the e2e scorer and return its result block."""
    from utils.evaluation.score_e2e import score_e2e

    return score_e2e(
        live=live,
        judge_config=judge_config,
        limit=limit,
        include_single=include_single,
    )


def _diagnose(e2e: dict[str, Any]) -> list[str]:
    if not e2e.get("live"):
        return [
            "Hermetic run: no answers scored (graph stack unreachable or --no-live). "
            "Run with the Docker stack up for real end-to-end metrics."
        ]
    o = e2e.get("overall", {})
    findings: list[str] = []
    cs = o.get("cross_source_accuracy", {})
    if cs.get("exact_match", {}).get("rate", 1.0) < 1.0:
        findings.append(
            f"Cross-source exact-match below ceiling ({cs['exact_match']['rate']}): "
            f"inspect the missed federated entries in `cases`."
        )
    mr = o.get("mapping_recall", {})
    if mr.get("micro_recall", 1.0) < 1.0:
        findings.append(
            f"CAPEC->ATT&CK mapping recall {mr['micro_recall']}: "
            f"{mr['gold_mappings'] - mr['found_mappings']} gold mapping(s) unsurfaced."
        )
    pv = o.get("provenance_correctness", {})
    if pv.get("fully_provenanced", {}).get("rate", 1.0) < 1.0:
        findings.append(
            f"Provenance completeness {pv['fully_provenanced']['rate']}: "
            f"some citations lack a complete/executed-query provenance."
        )
    judge = o.get("llm_judge", {})
    if judge.get("source") != "deterministic":
        findings.append(
            f"LLM judge contributed {judge.get('llm_covered')} verdict(s) "
            f"(source={judge.get('source')}); those qualitative scores are "
            f"NON-reproducible — the deterministic proxy covers the rest."
        )
    if not findings:
        findings.append(
            "All end-to-end metrics at ceiling on the scored catalogue; the "
            "assembled pipeline matches the snapshot-derived gold."
        )
    return findings


def build_json(e2e: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    return {
        "meta": meta,
        "definitions": DEFINITIONS,
        "e2e": e2e,
        "diagnosis": _diagnose(e2e),
    }


# -- Markdown ---------------------------------------------------------------


def _rate_cell(r: dict[str, Any] | None) -> str:
    if not r:
        return "n/a"
    return f"{r['rate']:.3f} [{r['ci_low']:.2f}–{r['ci_high']:.2f}] (k={r['k']}/{r['n']})"


def _md_overall(o: dict[str, Any]) -> list[str]:
    cs = o["cross_source_accuracy"]
    mr = o["mapping_recall"]
    pv = o["provenance_correctness"]
    ins = o["analyst_inspectability"]
    judge = o["llm_judge"]
    lines = [
        "## End-to-End Metrics",
        "",
        "**Cross-source answer accuracy** — live join values vs snapshot `must_correlate`:",
        "",
        f"- exact-set-match (positives): {_rate_cell(cs['exact_match'])}",
        f"- precision / recall / F1: {cs['mean_precision']} / {cs['mean_recall']} / {cs['mean_f1']}",
        f"- no-fabrication (negatives): {_rate_cell(cs['no_fabrication_rate'])}",
        "",
        "**CAPEC→ATT&CK mapping recall** — gold technique mappings surfaced:",
        "",
        f"- micro-recall: {mr['micro_recall']} ({mr['found_mappings']}/{mr['gold_mappings']} mappings, {mr['entries']} entries)",
        f"- mean per-entry recall: {mr['mean_recall']}",
        "",
        "**Provenance correctness** — citations trace to complete, executed-query records:",
        "",
        f"- mean citation-provenance rate: {pv['mean_citation_provenance_rate']}",
        f"- fully-provenanced answers: {_rate_cell(pv['fully_provenanced'])}",
        "",
        "**Analyst inspectability** — claim→record→query chains + abstention proofs:",
        "",
        f"- mean inspectability: {ins['mean_inspectability']}",
        f"- citation coverage / traceability / abstention proofs: "
        f"{ins['mean_citation_coverage']} / {ins['mean_traceability']} / {ins['mean_abstention_proofs']}",
        "",
        "## LLM Evaluator (judge)",
        "",
        f"Source: **{judge['source']}** "
        + (
            "(deterministic proxy — reproducible)"
            if judge["source"] == "deterministic"
            else f"({judge['llm_covered']} LLM verdicts — NON-reproducible)"
        ),
        "",
        f"- mean faithfulness: {judge['mean_faithfulness']}",
        f"- mean groundedness: {judge['mean_groundedness']}",
        f"- mean evidence sufficiency: {judge['mean_evidence_sufficiency']}",
        f"- mean unsupported-claim rate: {judge['mean_unsupported_claim_rate']} (deterministic)",
        f"- cross-source conflicts: {judge.get('total_conflicts', 0)} across "
        f"{judge.get('answers_with_conflicts', 0)} answer(s) (deterministic)",
        "",
    ]
    return lines


def build_markdown(data: dict[str, Any]) -> str:
    meta = data["meta"]
    e2e = data["e2e"]
    lines = [
        "# End-to-End Evaluation",
        "",
        f"ATT&CK {meta.get('attack_version')} · CAPEC {meta.get('capec_version')} · "
        f"{meta.get('generated_note', '')}",
        "",
        "The assembled pipeline (probe → plan → specialists → synthesis) scored "
        "against snapshot-derived gold. The four end-to-end metrics and the "
        "unsupported-claim rate are deterministic and reproducible; the LLM "
        "judge's qualitative scores are opt-in and labeled where they contribute.",
        "",
        "**Metric definitions**",
        "",
    ]
    for key, text in data["definitions"].items():
        lines.append(f"- *{key}*: {text}")
    lines.append("")

    if not e2e.get("live"):
        lines += [
            "> _Hermetic run — no live backend. No answers were scored._",
            "",
            "## What this diagnoses",
            "",
        ]
        lines += [f"- {f}" for f in data["diagnosis"]]
        lines += [""]
        return "\n".join(lines)

    lines += _md_overall(e2e["overall"])
    if e2e.get("by_tier"):
        lines += ["## By tier", "", "| Tier | X-source exact | Mapping recall | Provenance | Inspectability |", "|---|---|---|---|---|"]
        for tier, agg in e2e["by_tier"].items():
            lines.append(
                f"| {tier} | {agg['cross_source_accuracy']['exact_match']['rate']} "
                f"| {agg['mapping_recall']['micro_recall']} "
                f"| {agg['provenance_correctness']['fully_provenanced']['rate']} "
                f"| {agg['analyst_inspectability']['mean_inspectability']} |"
            )
        lines.append("")
    lines += ["## What this diagnoses", ""]
    lines += [f"- {f}" for f in data["diagnosis"]]
    lines += [""]
    return "\n".join(lines)


def write_report(data: dict[str, Any], md_path: str, json_path: str) -> None:
    import os

    os.makedirs(os.path.dirname(md_path), exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(build_markdown(data))
