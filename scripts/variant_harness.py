#!/usr/bin/env python3
"""Variant robustness — does a paraphrase extract what the gold question extracts?

    uv run python scripts/variant_harness.py capture --out docs/evaluation/variants-2026-08-29
    uv run python scripts/variant_harness.py compare --out docs/evaluation/variants-2026-08-29

The deterministic router matches a question's words against the node labels and
relationship types named in each source's schema card, case-folded and exact,
with a trailing ``s`` as its entire morphology. So ``"mitigations"`` routes and
``"defend against"``, ``"countermeasures"``, ``"remediate"`` and the typo
``"mitgations"`` do not. This measures what that costs.

**Two modes, and the order matters.**

``capture``   Run the 120 golden questions and record what each one extracts.
              This is the *reference*: every variant is scored against the
              behaviour of its own gold question, not against a hand-written
              expectation. Run it twice and diff — a reference that is not
              reproducible makes every downstream number meaningless.
``compare``   Run each variant and score it against its gold question's entry.

**Three levels of "the same", captured in one pass**, because they answer
different questions and the gaps between them are the interesting part:

``records``   the set of entity identifiers pulled out of the graph. **Primary.**
              This is "extract the same things" in the operator's phrasing, and
              a variant that reaches them through a *different* query is a
              success here — outcome, not interpretation.
``queries``   the emitted query strings, compared verbatim. Strictest: identical
              queries mean the router reached an identical interpretation.
``claims``    the composed claim texts. What a reader would actually be told.

**Nothing time-varying is captured at all.** No wall clock, no timestamps, no
provenance block. The recorded-answer regressions of 2026-08-23 spent a day
chasing a diff that was entirely ``wall_s`` and ``timing_ms``; the fix is to
never record the field, not to remember to exclude it.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from utils.config import load_env  # noqa: E402

load_env()

from utils.specialists.evalset.compile_banks import (  # noqa: E402
    ATTACK_BANK_PATH,
    CAPEC_BANK_PATH,
    FEDERATED_BANK_PATH,
    load_bank,
)
from utils.synthesis.config import SynthesisConfig  # noqa: E402
from utils.synthesis.grounding import normalize_id  # noqa: E402

#: Every LLM seam off. The whole point is to measure the deterministic router,
#: and an LLM anywhere in the chain would make the reference non-reproducible.
BASE_ENV: dict[str, str] = {
    "PLANNER_LLM_ENABLED": "false",
    "SPECIALIST_LLM_ENABLED": "false",
    "SYNTHESIS_LLM_ENABLED": "false",
    "CONVERSATION_LLM_ENABLED": "false",
    "ORCH_MAX_HOPS": "5",
}

BANKS: tuple[tuple[str, str], ...] = (
    ("attack", ATTACK_BANK_PATH),
    ("capec", CAPEC_BANK_PATH),
    ("federated", FEDERATED_BANK_PATH),
)


# -- capture ----------------------------------------------------------------


def _entity_ids(result: Any) -> set[str]:
    """Every identifier a result surfaced: anchors and their related items.

    ``related`` counts. A question about T1176's mitigations returns *one*
    record whose five mitigations live in ``related``; scoring anchors alone
    would call that identical to a bare ``describe`` of T1176, which is exactly
    the failure this harness exists to detect.
    """
    out: set[str] = set()
    for rec in getattr(result, "records", []) or []:
        pid = normalize_id(getattr(rec, "primary_id", "") or "")
        if pid:
            out.add(pid)
        for rel in getattr(rec, "related", []) or []:
            rid = rel.get("id") if isinstance(rel, dict) else rel
            rid = normalize_id(str(rid or ""))
            if rid:
                out.add(rid)
    return out


def _norm_query(query: str) -> str:
    """Collapse whitespace so formatting never registers as a routing change."""
    return " ".join((query or "").split())


def capture_one(question: str, config: SynthesisConfig) -> dict[str, Any]:
    """Everything one question extracts, with nothing time-varying in it."""
    from utils.orchestration.main import PipelineRun, iter_pipeline

    run = PipelineRun(question=question, mode="query")
    evidence = answer = None
    try:
        for event, payload in iter_pipeline(
            question, mode="query", use_llm=False, run=run, synthesis_config=config
        ):
            if event == "evidence":
                evidence = payload.get("evidence")
            elif event == "answer":
                evidence = payload.get("evidence") or evidence
                answer = payload.get("synthesized")
    except Exception as exc:  # noqa: BLE001 — one question must not end the run
        return {"error": f"{type(exc).__name__}: {exc}"}

    ids: set[str] = set()
    queries: list[str] = []
    sources: set[str] = set()
    per_source: dict[str, set[str]] = defaultdict(set)
    records = 0
    for result in getattr(evidence, "results", []) or []:
        source = getattr(getattr(result, "task", None), "source", "") or "?"
        got = _entity_ids(result)
        ids |= got
        per_source[source] |= got
        records += len(getattr(result, "records", []) or [])
        if getattr(result, "query", ""):
            queries.append(_norm_query(result.query))
        if got:
            sources.add(source)

    claims = sorted(
        str(getattr(c, "text", c)) for c in (getattr(answer, "claims", None) or [])
    )
    abstentions = sorted(
        str(getattr(a, "reason", "") or getattr(a, "text", "") or a)
        for a in (getattr(answer, "abstentions", None) or [])
    )
    return {
        "entity_ids": sorted(ids),
        "entity_ids_by_source": {k: sorted(v) for k, v in sorted(per_source.items())},
        "queries": sorted(queries),
        "sources": sorted(sources),
        "record_count": records,
        "claims": claims,
        "abstentions": abstentions,
        "unsupported": len(getattr(evidence, "unsupported", []) or []),
    }


def gold_questions() -> list[dict[str, Any]]:
    """The 120 golden questions, flattened, with their bank and gold answers."""
    out: list[dict[str, Any]] = []
    for bank, path in BANKS:
        entries = load_bank(Path(path))
        questions = entries["questions"] if isinstance(entries, dict) else entries
        for entry in questions:
            text = entry.get("question") or entry.get("text") or ""
            if not text:
                continue
            out.append(
                {
                    "case_id": entry.get("id", ""),
                    "bank": bank,
                    "question": text,
                    "expected_template": entry.get("expected_template", ""),
                    "seed_ids": list(
                        (entry.get("task") or {}).get("seed_ids") or []
                    ),
                }
            )
    return out


def cmd_capture(args: argparse.Namespace) -> int:
    config = SynthesisConfig.from_env()
    questions = gold_questions()
    if args.limit:
        questions = questions[: args.limit]
    print(f"== capturing {len(questions)} golden questions, {args.workers} workers")

    started = time.monotonic()

    def work(item: dict[str, Any]) -> dict[str, Any]:
        return {**item, **capture_one(item["question"], config)}

    rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for i, row in enumerate(pool.map(work, questions), 1):
            rows.append(row)
            if i % 20 == 0:
                print(f"   {i}/{len(questions)}")

    out_dir = REPO / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / args.name
    path.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n")

    errors = [r for r in rows if "error" in r]
    empty = [r for r in rows if not r.get("error") and not r.get("entity_ids")]
    print(f"\n   wrote {path.relative_to(REPO)} in {time.monotonic() - started:.1f}s")
    print(f"   {len(rows)} questions | {len(errors)} errors | {len(empty)} extracted nothing")
    for r in empty[:8]:
        print(f"     empty: {r['case_id']:12s} {r['question'][:60]}")
    return 0


# -- compare ----------------------------------------------------------------


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def score(variant: dict[str, Any], gold: dict[str, Any]) -> dict[str, Any]:
    """Score one variant against its gold question's captured behaviour.

    ``wrong_entity`` is the metric that matters most and is easiest to miss: the
    variant returned records and **none of them** is one the gold question
    found. Nothing downstream catches that — every claim is genuinely grounded
    in a genuinely retrieved record — so an accuracy-only read scores it the
    same as returning nothing, and it is far worse.
    """
    g_ids = set(gold.get("entity_ids") or [])
    v_ids = set(variant.get("entity_ids") or [])
    g_q = set(gold.get("queries") or [])
    v_q = set(variant.get("queries") or [])
    g_c = set(gold.get("claims") or [])
    v_c = set(variant.get("claims") or [])

    abstained = bool(variant.get("abstentions")) or not v_ids
    return {
        "records_exact": g_ids == v_ids,
        "records_jaccard": round(_jaccard(g_ids, v_ids), 4),
        "records_recall": round(len(g_ids & v_ids) / len(g_ids), 4) if g_ids else None,
        "queries_exact": g_q == v_q,
        "claims_exact": g_c == v_c,
        "abstained": abstained,
        "wrong_entity": bool(v_ids) and not (v_ids & g_ids),
        "gold_n": len(g_ids),
        "variant_n": len(v_ids),
    }


def cmd_compare(args: argparse.Namespace) -> int:
    out_dir = REPO / args.out
    gold_rows = json.loads((out_dir / args.reference).read_text())
    gold_by_id = {r["case_id"]: r for r in gold_rows}
    variants = json.loads((out_dir / args.variants).read_text())
    if args.limit:
        variants = variants[: args.limit]

    config = SynthesisConfig.from_env()
    print(f"== scoring {len(variants)} variants, {args.workers} workers")

    def work(v: dict[str, Any]) -> dict[str, Any]:
        gold = gold_by_id.get(v["case_id"])
        if gold is None:
            return {**v, "error": "no reference for case_id"}
        got = capture_one(v["question"], config)
        if "error" in got:
            return {**v, **got}
        return {**v, **got, **score(got, gold)}

    rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for i, row in enumerate(pool.map(work, variants), 1):
            rows.append(row)
            if i % 50 == 0:
                print(f"   {i}/{len(variants)}")

    (out_dir / args.name).write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n")
    print(f"\n   wrote {(out_dir / args.name).relative_to(REPO)}")
    report(rows)
    return 0


def report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-tier table. A pooled figure would average two different problems."""
    scored = [r for r in rows if "records_exact" in r]
    by_tier: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in scored:
        by_tier[str(r.get("tier", "?"))].append(r)

    print(f"\n{'tier':6s} {'n':>4s} {'rec=':>6s} {'recall':>7s} {'query=':>7s} "
          f"{'claim=':>7s} {'abstain':>8s} {'WRONG':>6s}")
    print("-" * 62)
    summary: dict[str, Any] = {}
    for tier in sorted(by_tier):
        g = by_tier[tier]
        n = len(g)
        recalls = [r["records_recall"] for r in g if r.get("records_recall") is not None]
        cells = {
            "n": n,
            "records_exact": round(sum(r["records_exact"] for r in g) / n, 4),
            "records_recall": round(sum(recalls) / len(recalls), 4) if recalls else None,
            "queries_exact": round(sum(r["queries_exact"] for r in g) / n, 4),
            "claims_exact": round(sum(r["claims_exact"] for r in g) / n, 4),
            "abstained": round(sum(r["abstained"] for r in g) / n, 4),
            "wrong_entity": round(sum(r["wrong_entity"] for r in g) / n, 4),
        }
        summary[tier] = cells
        rc = f"{cells['records_recall']:.4f}" if cells["records_recall"] is not None else "—"
        print(f"{tier:6s} {n:>4d} {cells['records_exact']:>6.4f} {rc:>7s} "
              f"{cells['queries_exact']:>7.4f} {cells['claims_exact']:>7.4f} "
              f"{cells['abstained']:>8.4f} {cells['wrong_entity']:>6.4f}")
    errs = [r for r in rows if "error" in r]
    if errs:
        print(f"\n   {len(errs)} errored: {Counter(r['error'][:40] for r in errs).most_common(3)}")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    cap = sub.add_parser("capture", help="record what the golden questions extract")
    cap.add_argument("--out", required=True)
    cap.add_argument("--name", default="reference.json")
    cap.add_argument("--workers", type=int, default=8)
    cap.add_argument("--limit", type=int, default=None)
    cap.set_defaults(func=cmd_capture)

    cmp_ = sub.add_parser("compare", help="score variants against the reference")
    cmp_.add_argument("--out", required=True)
    cmp_.add_argument("--reference", default="reference.json")
    cmp_.add_argument("--variants", default="variants.json")
    cmp_.add_argument("--name", default="scored.json")
    cmp_.add_argument("--workers", type=int, default=8)
    cmp_.add_argument("--limit", type=int, default=None)
    cmp_.set_defaults(func=cmd_compare)

    args = parser.parse_args()
    for key, value in BASE_ENV.items():
        os.environ[key] = value
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
