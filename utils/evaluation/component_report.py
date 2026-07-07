#!/usr/bin/env python3
"""Assemble the component-evaluation report (Markdown + JSON).

Pure builders (``build_json`` / ``build_markdown``) turn the scorer outputs into
the citable artifact, so the report shape is hermetically testable with
synthetic scores. ``collect_*`` gather the real scores; live scorers (EX,
latency) are skipped with an honest note when the stack is down.

The report covers exactly the proposal's named metrics — planner (source
selection, sub-question quality, unnecessary calls, schema adherence) and each
specialist (query validity, execution accuracy, safety adherence, latency) —
and a "what this diagnoses" section feeding the Wk 14-15 iteration pass.
"""

from __future__ import annotations

import json
from typing import Any


# -- collectors -------------------------------------------------------------

def collect_planner() -> dict[str, Any]:
    from utils.planner.cards import load_source_cards
    from utils.planner.evaluation.corpus import run_corpus
    from utils.planner.evaluation.scorer import aggregate

    cards = load_source_cards("data")
    results = run_corpus(cards)  # deterministic drafter
    scores = [s for _c, _p, s in results]

    def agg(subset: list) -> dict[str, Any]:
        return aggregate(subset) if subset else {"cases": 0}

    return {
        "drafter": "deterministic",
        "overall": aggregate(scores),
        "dev": agg([s for s in scores if s.split == "dev"]),
        "holdout": agg([s for s in scores if s.split == "holdout"]),
        "by_origin": {
            "curated": agg([s for s in scores if s.origin == "curated"]),
            "generated": agg([s for s in scores if s.origin == "generated"]),
        },
        "cases": [s.to_dict() for s in scores],
    }


def collect_specialists(*, live: bool) -> dict[str, Any]:
    from utils.specialists.evalset.score_safety import score_safety
    from utils.specialists.evalset.score_validity import score_validity

    va = score_validity()          # hermetic (gate only)
    safety = score_safety()        # hermetic (gate only)
    ex: dict[str, Any] | None = None
    latency: dict[str, Any] | None = None
    if live:
        from utils.specialists.evalset.latency import run_latency
        from utils.specialists.evalset.score_execution import score_execution
        ex = score_execution()
        latency = run_latency()

    out: dict[str, Any] = {}
    for source in ("attack", "capec"):
        out[source] = {
            "va": va.get(source),
            "ex": ex.get(source) if ex else None,
            "safety": safety.get(source),
            "latency": latency.get(source) if latency else None,
        }
    return out


# -- diagnosis (findings -> Wk 14-15) ---------------------------------------

def _diagnose(planner: dict[str, Any], specialists: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    agg = planner["overall"]
    if agg.get("mean_source_precision", 1.0) < 1.0:
        findings.append(
            f"Planner over-routes: source precision {agg['mean_source_precision']} "
            f"({agg.get('total_unnecessary_source_calls')} unnecessary source calls) — "
            "mitigation/mapping questions are sent to both sources. Tighten routing."
        )
    findings.append(
        "Planner cannot route bare id lookups (e.g. 'what is T1059.001?') — they were "
        "excluded from the generated corpus as unroutable. Add a lookup intent."
    )
    for source, s in specialists.items():
        ex = s.get("ex")
        if ex and ex.get("taxonomy"):
            findings.append(f"{source} EX misses: {ex['taxonomy']} — inspect the bucketed cases.")
        lat = s.get("latency")
        if lat:
            gap = lat["total_ms"].get("p50_p99_gap")
            findings.append(
                f"{source} latency p50={lat['total_ms']['p50']}ms p99={lat['total_ms']['p99']}ms "
                f"(gap {gap}ms), execute-dominated."
            )
    findings.append(
        "Safety: an adversarial probe surfaced (and this milestone fixed) a single-quoted "
        "unknown-label bypass in the Gremlin gate; keep probing as the gate evolves."
    )
    return findings


# -- JSON + Markdown builders (pure) ----------------------------------------

def build_json(planner: dict[str, Any], specialists: dict[str, Any],
               meta: dict[str, Any]) -> dict[str, Any]:
    return {
        "meta": meta,
        "planner": planner,
        "specialists": specialists,
        "diagnosis": _diagnose(planner, specialists),
    }


def _rate_cell(r: dict[str, Any] | None) -> str:
    if not r:
        return "n/a"
    return f"{r['rate']:.3f} [{r['ci_low']:.2f}–{r['ci_high']:.2f}] (k={r['k']}/{r['n']})"


def _md_planner(p: dict[str, Any]) -> list[str]:
    o = p["overall"]
    lines = ["## Planner", "", f"Drafter scored: **{p['drafter']}** (deterministic, reproducible).", ""]
    lines += [
        "| Metric | Overall | Dev | Holdout |",
        "|---|---|---|---|",
        f"| Source precision | {o.get('mean_source_precision')} | {p['dev'].get('mean_source_precision')} | {p['holdout'].get('mean_source_precision')} |",
        f"| Source recall | {o.get('mean_source_recall')} | {p['dev'].get('mean_source_recall')} | {p['holdout'].get('mean_source_recall')} |",
        f"| Unnecessary source calls | {o.get('total_unnecessary_source_calls')} | {p['dev'].get('total_unnecessary_source_calls')} | {p['holdout'].get('total_unnecessary_source_calls')} |",
        f"| Sub-question quality | {o.get('mean_sub_question_quality')} | {p['dev'].get('mean_sub_question_quality')} | {p['holdout'].get('mean_sub_question_quality')} |",
        f"| — routing accuracy | {o.get('routing_accuracy_rate')} | {p['dev'].get('routing_accuracy_rate')} | {p['holdout'].get('routing_accuracy_rate')} |",
        f"| — dependency accuracy | {o.get('dependency_accuracy_rate')} | {p['dev'].get('dependency_accuracy_rate')} | {p['holdout'].get('dependency_accuracy_rate')} |",
        f"| Schema adherence | {o.get('schema_adherence_rate')} | {p['dev'].get('schema_adherence_rate')} | {p['holdout'].get('schema_adherence_rate')} |",
        f"| Honesty (unsupported/partial) | {o.get('honesty_rate')} | {p['dev'].get('honesty_rate')} | {p['holdout'].get('honesty_rate')} |",
        "",
        f"Corpus: {o.get('cases')} cases "
        f"(curated {p['by_origin']['curated'].get('cases')}, generated {p['by_origin']['generated'].get('cases')}). "
        f"Curated-anchor pass rate {p['by_origin']['curated'].get('pass_rate')}.",
        "",
    ]
    return lines


def _md_specialist(source: str, s: dict[str, Any]) -> list[str]:
    lines = [f"### {source}", ""]
    va = s.get("va")
    if va:
        o = va["overall"]
        lines += [
            "**Query validity (VA)** — share of drafted queries clearing the gate:",
            "",
            f"- first-pass: {_rate_cell(o['first_pass_va'])}",
            f"- post-retry: {_rate_cell(o['post_retry_va'])}",
            f"- boundary (no query drafted): {o.get('boundary')}",
            "",
        ]
    ex = s.get("ex")
    if ex:
        o = ex["overall"]
        lines += [
            "**Execution accuracy (EX)** — result set vs snapshot gold:",
            "",
            f"- exact-set-match: {_rate_cell(o['exact_match'])}",
            f"- precision / recall / F1: {o.get('mean_precision')} / {o.get('mean_recall')} / {o.get('mean_f1')}",
            f"- error taxonomy: {ex.get('taxonomy') or 'none'}",
            "",
        ]
    else:
        lines += ["**Execution accuracy (EX)** — _skipped: graph stack not reachable._", ""]
    safety = s.get("safety")
    if safety:
        lines += [
            "**Safety adherence** — bounded-execution audit + adversarial probes:",
            "",
            f"- accepted-query adherence: {safety.get('adherence_rate')} ({safety.get('audited')} audited, breaches {len(safety.get('breaches', []))})",
            f"- adversarial probe block rate: {safety.get('probe_block_rate')} ({safety.get('probes')} probes, leaks {len(safety.get('leaks', []))})",
            "",
        ]
    lat = s.get("latency")
    if lat:
        t = lat["total_ms"]
        lines += [
            "**Latency** — p50/p95/p99 (ms), warm steady-state:",
            "",
            f"- total: p50 {t['p50']} · p95 {t['p95']} · p99 {t['p99']} · gap {t['p50_p99_gap']}",
            "- by stage (p50): "
            + ", ".join(f"{k.replace('_ms','')} {v['p50']}" for k, v in lat["by_stage"].items()),
            f"- cold p50 {lat['cold_vs_warm']['cold_p50']} vs warm p50 {lat['cold_vs_warm']['warm_p50']}",
            "",
        ]
    else:
        lines += ["**Latency** — _skipped: graph stack not reachable._", ""]
    return lines


def build_markdown(data: dict[str, Any]) -> str:
    meta = data["meta"]
    lines = [
        "# Component-Level Evaluation",
        "",
        f"ATT&CK {meta.get('attack_version')} · CAPEC {meta.get('capec_version')} · "
        f"{meta.get('generated_note', '')}",
        "",
        "Deterministic scoring against snapshot-derived gold — no LLM judge. "
        "The model drafts, deterministic code grades; every number here is reproducible.",
        "",
        "> **Read the ceiling honestly.** Ariadne's specialists do not free-generate "
        "queries — a deterministic builder fills read-only templates — so query validity "
        "sits at the ceiling by construction and EX misses point at routing/seed/ingest "
        "issues, not malformed queries. That is a design strength, stated plainly.",
        "",
    ]
    lines += _md_planner(data["planner"])
    lines += ["## Specialists", ""]
    for source, s in data["specialists"].items():
        lines += _md_specialist(source, s)
    lines += ["## What this diagnoses (-> Wk 14-15)", ""]
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
