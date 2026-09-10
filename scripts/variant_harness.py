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

#: What each ``--rewrite`` mode means, as environment. ``off`` is stated rather
#: than left unset on purpose: an arm that inherits a flag from the operator's
#: ``.env`` is not the arm its name claims, and this file has been bitten by
#: exactly that before (the import-time ``load_env`` leak, D-029).
REWRITE_ENV: dict[str, dict[str, str]] = {
    "off": {"ARIADNE_REWRITE": "0", "ARIADNE_REWRITE_MODEL": "0",
            "ARIADNE_REWRITE_DERIVE_RELATION": "1"},
    "det": {"ARIADNE_REWRITE": "1", "ARIADNE_REWRITE_MODEL": "0",
            "ARIADNE_REWRITE_DERIVE_RELATION": "1"},
    "model": {"ARIADNE_REWRITE": "1", "ARIADNE_REWRITE_MODEL": "1",
              "ARIADNE_REWRITE_DERIVE_RELATION": "1"},
    # EXP-2026-09-015's control: the model rung exactly as EXP-2026-09-014 ran
    # it, with the relation asked for rather than derived from the label pair.
    # Every value is written explicitly so an ambient variable cannot decide
    # which arm ran.
    "model_ask": {"ARIADNE_REWRITE": "1", "ARIADNE_REWRITE_MODEL": "1",
                  "ARIADNE_REWRITE_DERIVE_RELATION": "0"},
}

#: Where the understanding-gold lives, relative to ``--out``.
SLOT_GOLD_NAME = "slot_gold.json"

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
    evidence = answer = plan = None
    try:
        for event, payload in iter_pipeline(
            question, mode="query", use_llm=False, run=run, synthesis_config=config
        ):
            if event == "plan":
                plan = payload.get("plan")
            elif event == "evidence":
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
    out: dict[str, Any] = {
        "entity_ids": sorted(ids),
        "entity_ids_by_source": {k: sorted(v) for k, v in sorted(per_source.items())},
        "queries": sorted(queries),
        "sources": sorted(sources),
        "record_count": records,
        "claims": claims,
        "abstentions": abstentions,
        "unsupported": len(getattr(evidence, "unsupported", []) or []),
    }
    # Present only when the rewrite stage actually ran. With the flags off
    # ``Plan.rewrite`` is ``None`` and this key never appears, so a capture is
    # byte-identical to every one taken before the stage existed.
    rewrite = getattr(plan, "rewrite", None)
    if rewrite:
        out["rewrite"] = rewrite
    return out


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
    print(f"\n   wrote {_rel(path)} in {time.monotonic() - started:.1f}s")
    print(f"   {len(rows)} questions | {len(errors)} errors | {len(empty)} extracted nothing")
    for r in empty[:8]:
        print(f"     empty: {r['case_id']:12s} {r['question'][:60]}")
    return 0


# -- compare ----------------------------------------------------------------


#: A result is a dump when it is both large in absolute terms and large relative
#: to what the gold question returned. Both bounds are needed: 60 records is a
#: legitimate answer to "list the techniques of a prolific group", and 12
#: records is a dump when the gold answer was one.
_DUMP_FLOOR = 50
_DUMP_RATIO = 10


def _rel(path: Path) -> str:
    """``path`` relative to the repo when it is inside it, else as given.

    ``Path.relative_to`` raises for anything outside the tree, and it did — a
    run that wrote its output to a scratch directory crashed *after* writing the
    file, on the line that prints where it went.
    """
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


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

    # A bulk scan of a whole label, returned as though it answered the question.
    # This is the failure mode that inflates recall while retrieving nothing:
    # the anchor did not resolve, the router still matched a schema word, and
    # the builder fell through to `label_scan`, which returns the label. The
    # gold answer is then "found" because it is inside a dump of everything.
    # Same species as the I-11 defect in C-023, on a different axis.
    g_recs = int(gold.get("record_count") or 0)
    v_recs = int(variant.get("record_count") or 0)
    dumped = v_recs >= _DUMP_FLOOR and (g_recs == 0 or v_recs >= _DUMP_RATIO * g_recs)

    return {
        "catalogue_dump": dumped,
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


def _slot_gold_index(out_dir: Path, name: str = SLOT_GOLD_NAME) -> dict[str, dict[str, Any]]:
    path = out_dir / name
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    records = data["records"] if isinstance(data, dict) else data
    return {str(r.get("case_id") or ""): r for r in records}


def score_slots(row: dict[str, Any], gold: dict[str, Any] | None) -> dict[str, Any]:
    """Per-slot accuracy of the *understanding*, against ``slot_gold.json``.

    This is the metric that separates understanding from retrieval, and neither
    of the two failures it isolates is visible in ``records_exact``:

    * a form that is **right** but renders to a sentence the engine mishandles is
      a renderer defect, and looks like a retrieval failure;
    * a form that is **wrong** and still retrieves the gold — by dumping the
      label the gold happens to be in — looks like a success. That is the I-11
      failure class, and `catalogue_dump` is what pairs with this to catch it.

    Every field is ``None`` when the stage did not run or the gold records no
    slots, because a slot nobody claimed and a slot nobody asked about are
    different things and averaging them together invents a number.
    """
    form = ((row.get("rewrite") or {}).get("form")) or {}
    if not form or not gold:
        return {
            "slot_anchor": None, "slot_anchor_label": None, "slot_target_label": None,
            "slot_relation": None, "form_exact": None, "slots_scored": 0,
        }

    def _match(got: Any, want: Any) -> bool | None:
        want_set = {str(v).upper() for v in (want or ())}
        if not want_set:
            return None
        return bool({str(v).upper() for v in (got or ())} & want_set)

    cells = {
        "slot_anchor": _match(form.get("anchors"), gold.get("anchors")),
        "slot_anchor_label": _match(form.get("anchor_labels"), gold.get("anchor_labels")),
        "slot_target_label": _match(form.get("target_labels"), gold.get("target_labels")),
        "slot_relation": _match(
            [form.get("relation")] if form.get("relation") else [],
            [gold.get("relation")] if gold.get("relation") else [],
        ),
    }
    scored = [v for v in cells.values() if v is not None]
    cells["slots_scored"] = len(scored)
    cells["form_exact"] = bool(scored) and all(scored)
    return cells


def _rewrite_fields(row: dict[str, Any]) -> dict[str, Any]:
    """The provenance columns Step 7 reports mean and spread over."""
    rewrite = row.get("rewrite") or {}
    return {
        "rung": rewrite.get("rung", "off"),
        "model_consulted": rewrite.get("rung") in {"model", "abstain"}
        and bool(rewrite.get("served_model")),
        "cache_hit": bool(rewrite.get("cache_hit")),
        "served_model": rewrite.get("served_model", ""),
        "canonical_question": rewrite.get("canonical_question", ""),
    }


def cmd_compare(args: argparse.Namespace) -> int:
    out_dir = REPO / args.out
    gold_rows = json.loads((out_dir / args.reference).read_text())
    gold_by_id = {r["case_id"]: r for r in gold_rows}
    variants = json.loads((out_dir / args.variants).read_text())
    if getattr(args, "split", None):
        # The frozen half must be unreachable while tuning, not merely unused.
        # Filtering here means a sweep physically cannot score against it.
        assignment = json.loads((out_dir / "split.json").read_text())["assignment"]
        variants = [v for v in variants if assignment.get(v["case_id"]) == args.split]
        print(f"== split '{args.split}': {len(variants)} variants")
    if args.limit:
        variants = variants[: args.limit]

    slot_gold = _slot_gold_index(out_dir)
    config = SynthesisConfig.from_env()
    repeats = max(1, int(getattr(args, "repeat", 1) or 1))
    print(f"== scoring {len(variants)} variants, {args.workers} workers, "
          f"rewrite={getattr(args, 'rewrite', 'off')}, {repeats} run(s)")

    def work(v: dict[str, Any]) -> dict[str, Any]:
        gold = gold_by_id.get(v["case_id"])
        if gold is None:
            return {**v, "error": "no reference for case_id"}
        started = time.monotonic()
        got = capture_one(v["question"], config)
        elapsed = round(time.monotonic() - started, 3)
        if "error" in got:
            return {**v, **got}
        row = {**v, **got, **score(got, gold)}
        row.update(_rewrite_fields(row))
        row.update(score_slots(row, slot_gold.get(v["case_id"])))
        # Kept in its own key and never compared: this module's opening note is
        # that nothing time-varying is captured, and a whole day was once spent
        # diffing `wall_s`. Step 7 reports it, no identity check reads it.
        row["timing"] = {"latency_s": elapsed}
        return row

    all_rows: list[dict[str, Any]] = []
    for run_index in range(repeats):
        if repeats > 1:
            print(f"== run {run_index + 1}/{repeats}")
        rows: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            for i, row in enumerate(pool.map(work, variants), 1):
                rows.append({**row, "run_index": run_index})
                if i % 50 == 0:
                    print(f"   {i}/{len(variants)}")
        name = args.name if repeats == 1 else _numbered(args.name, run_index)
        (out_dir / name).write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n")
        print(f"\n   wrote {_rel(out_dir / name)}")
        report(rows)
        all_rows.extend(rows)

    if getattr(args, "metrics", None):
        path = Path(args.metrics)
        if not path.is_absolute():
            path = out_dir / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(aggregate(all_rows, repeats), indent=2, sort_keys=True) + "\n")
        print(f"   wrote {path}")
    return 0


def _numbered(name: str, index: int) -> str:
    stem, _, ext = name.rpartition(".")
    return f"{stem or name}.run{index + 1}.{ext or 'json'}"


def aggregate(rows: list[dict[str, Any]], repeats: int) -> dict[str, Any]:
    """Mean and spread per tier across repeats — the file every figure reads.

    Spread is reported as the **population standard deviation across runs of the
    same arm**, not as a confidence interval, because three runs is three runs.
    Q2 has been open since August precisely because no LLM-in-the-loop arm had
    ever been run twice; a single draw reported without its spread is what kept
    it open.
    """
    scored = [r for r in rows if "records_exact" in r]
    per_run: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for r in scored:
        per_run[int(r.get("run_index") or 0)].append(r)

    metrics = (
        "records_exact", "records_recall", "queries_exact",
        "claims_exact", "abstained", "wrong_entity", "catalogue_dump",
    )
    slots = ("slot_anchor", "slot_anchor_label", "slot_target_label", "slot_relation",
             "form_exact")

    out: dict[str, Any] = {"runs": repeats, "n_scored": len(scored), "tiers": {}}
    tiers = sorted({str(r.get("tier", "?")) for r in scored})
    for tier in tiers:
        cells: dict[str, Any] = {}
        for metric in metrics:
            draws = []
            for run_rows in per_run.values():
                group = [r for r in run_rows if str(r.get("tier", "?")) == tier]
                values = [r[metric] for r in group if r.get(metric) is not None]
                if values:
                    draws.append(sum(bool(v) if isinstance(v, bool) else v for v in values) / len(values))
            cells[metric] = _spread(draws)
        for slot in slots:
            draws = []
            for run_rows in per_run.values():
                group = [r for r in run_rows if str(r.get("tier", "?")) == tier]
                values = [r[slot] for r in group if r.get(slot) is not None]
                if values:
                    draws.append(sum(bool(v) for v in values) / len(values))
            cells[slot] = _spread(draws)
        # Recall with the dumps removed — the honest recall number, and a
        # derivation rather than a row field, so it is computed here rather than
        # looked up and silently found missing.
        clean_draws = []
        for run_rows in per_run.values():
            group = [
                r for r in run_rows
                if str(r.get("tier", "?")) == tier
                and r.get("records_recall") is not None
                and not r.get("catalogue_dump")
            ]
            if group:
                clean_draws.append(sum(r["records_recall"] for r in group) / len(group))
        cells["records_recall_no_dump"] = _spread(clean_draws)

        group_all = [r for r in scored if str(r.get("tier", "?")) == tier]
        cells["n"] = len(group_all) // max(1, repeats)
        cells["model_consulted"] = _spread([
            sum(bool(r.get("model_consulted")) for r in run_rows
                if str(r.get("tier", "?")) == tier)
            / max(1, len([r for r in run_rows if str(r.get("tier", "?")) == tier]))
            for run_rows in per_run.values()
            if any(str(r.get("tier", "?")) == tier for r in run_rows)
        ])
        cells["cache_hit"] = _spread([
            sum(bool(r.get("cache_hit")) for r in run_rows
                if str(r.get("tier", "?")) == tier)
            / max(1, len([r for r in run_rows if str(r.get("tier", "?")) == tier]))
            for run_rows in per_run.values()
            if any(str(r.get("tier", "?")) == tier for r in run_rows)
        ])
        latencies = [
            (r.get("timing") or {}).get("latency_s")
            for r in group_all
            if (r.get("timing") or {}).get("latency_s") is not None
        ]
        cells["latency_s_mean"] = round(sum(latencies) / len(latencies), 3) if latencies else None
        out["tiers"][tier] = cells

    out["served_models"] = sorted({r.get("served_model", "") for r in scored} - {""})
    out["rungs"] = dict(Counter(r.get("rung", "off") for r in scored))
    return out


def _spread(draws: list[float]) -> dict[str, Any] | None:
    """``{mean, sd, n}`` over the per-run figures, or ``None`` when there are none."""
    if not draws:
        return None
    mean = sum(draws) / len(draws)
    if len(draws) == 1:
        return {"mean": round(mean, 4), "sd": None, "n": 1}
    variance = sum((d - mean) ** 2 for d in draws) / len(draws)
    return {"mean": round(mean, 4), "sd": round(variance ** 0.5, 4), "n": len(draws)}


def report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-tier table. A pooled figure would average two different problems."""
    scored = [r for r in rows if "records_exact" in r]
    by_tier: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in scored:
        by_tier[str(r.get("tier", "?"))].append(r)

    print(f"\n{'tier':6s} {'n':>4s} {'rec=':>6s} {'recall':>7s} {'r|nodump':>9s} "
          f"{'query=':>7s} {'abstain':>8s} {'WRONG':>6s} {'DUMP':>6s}")
    print("-" * 72)
    summary: dict[str, Any] = {}
    for tier in sorted(by_tier):
        g = by_tier[tier]
        n = len(g)
        recalls = [r["records_recall"] for r in g if r.get("records_recall") is not None]
        # Recall with the dumps removed. **This is the honest recall number.**
        # Reporting only the pooled figure credits the system for answers it
        # found by returning everything, which is not retrieval.
        clean = [r["records_recall"] for r in g
                 if r.get("records_recall") is not None and not r.get("catalogue_dump")]
        cells = {
            "n": n,
            "records_exact": round(sum(r["records_exact"] for r in g) / n, 4),
            "records_recall": round(sum(recalls) / len(recalls), 4) if recalls else None,
            "records_recall_no_dump": round(sum(clean) / len(clean), 4) if clean else None,
            "queries_exact": round(sum(r["queries_exact"] for r in g) / n, 4),
            "claims_exact": round(sum(r["claims_exact"] for r in g) / n, 4),
            "abstained": round(sum(r["abstained"] for r in g) / n, 4),
            "wrong_entity": round(sum(r["wrong_entity"] for r in g) / n, 4),
            "catalogue_dump": round(sum(bool(r.get("catalogue_dump")) for r in g) / n, 4),
        }
        summary[tier] = cells
        rc = f"{cells['records_recall']:.4f}" if cells["records_recall"] is not None else "—"
        rn = (f"{cells['records_recall_no_dump']:.4f}"
              if cells["records_recall_no_dump"] is not None else "—")
        print(f"{tier:6s} {n:>4d} {cells['records_exact']:>6.4f} {rc:>7s} {rn:>9s} "
              f"{cells['queries_exact']:>7.4f} "
              f"{cells['abstained']:>8.4f} {cells['wrong_entity']:>6.4f} "
              f"{cells['catalogue_dump']:>6.4f}")
    errs = [r for r in rows if "error" in r]
    if errs:
        print(f"\n   {len(errs)} errored: {Counter(r['error'][:40] for r in errs).most_common(3)}")
    return summary


def preflight() -> None:
    """Refuse to run against a hollow graph.

    The Gremlin store is an in-memory TinkerGraph: a container restart empties
    it, and `--graph health` keeps reporting "reachable" because the socket
    still answers. This has now silently invalidated a capture **twice** in one
    session — the first time 22 of 120 golden questions returned nothing and it
    read like a code regression.

    An unattended run cannot afford that: every number after the store empties
    is garbage that looks like a result. So the harness verifies counts against
    the pinned manifest before it measures anything, and **dies** rather than
    producing a plausible wrong answer.
    """
    import subprocess

    for dataset in ("attack", "capec"):
        proc = subprocess.run(
            ["uv", "run", "main.py", "--dataset", dataset, "--graph", "verify"],
            cwd=REPO, capture_output=True, text=True, timeout=600,
        )
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout).strip().splitlines()[-1:]
            raise SystemExit(
                f"PREFLIGHT FAILED for {dataset}: {' '.join(tail)}\n"
                f"  Reload it before measuring:  "
                f"uv run main.py --dataset {dataset} --graph "
                f"{'neo4j' if dataset == 'attack' else 'gremlin'}"
            )
    print("== preflight: attack and capec verify against their pinned manifests")


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
    cmp_.add_argument("--split", choices=("tune", "report"), default=None,
                      help="score only one half of the frozen split")
    cmp_.add_argument("--rewrite", choices=tuple(REWRITE_ENV), default="off",
                      help="hybrid rewrite stage: off | det (deterministic fill "
                           "only) | model (gated model fill for unbound slots)")
    cmp_.add_argument("--llm-model", default=None,
                      help="served alias for the model fill (records the WEIGHTS "
                           "that answered, not this name)")
    cmp_.add_argument("--llm-base-url", default=None)
    cmp_.add_argument("--llm-timeout-s", type=float, default=None,
                      help="read timeout for one model call. At 32-way "
                           "concurrency per instance the served model exceeds "
                           "the 240s default on about a third of calls, and a "
                           "timed-out call abstains -- indistinguishable "
                           "downstream from a model with nothing to say.")
    cmp_.add_argument("--pipeline-timeout-s", type=float, default=None,
                      help="total budget for one question. The rewrite's model "
                           "call is charged against the SAME budget retrieval "
                           "needs, so at the shipped 120s a slow rewrite starves "
                           "the query and the question returns nothing -- which "
                           "reads as a method failure and is a clock failure.")
    cmp_.add_argument("--cache-dir", default=None,
                      help="rewrite cache root; clear it between runs to measure "
                           "model variance rather than cache variance")
    cmp_.add_argument("--repeat", type=int, default=1,
                      help="run the whole arm N times; each run is written "
                           "separately and metrics.json reports mean and sd")
    cmp_.add_argument("--metrics", default=None,
                      help="write the aggregated per-tier metrics here")
    cmp_.set_defaults(func=cmd_compare)

    args = parser.parse_args()
    for key, value in BASE_ENV.items():
        os.environ[key] = value
    # Arm environment, applied before anything reads a config. Stated in full
    # rather than left unset: an arm that inherits a flag from the operator's
    # `.env` is not the arm its name claims.
    os.environ.update(REWRITE_ENV[getattr(args, "rewrite", "off")])
    if getattr(args, "llm_model", None):
        os.environ["ARIADNE_LLM_MODEL"] = args.llm_model
        os.environ["PLANNER_LLM_MODEL"] = args.llm_model
    if getattr(args, "llm_base_url", None):
        os.environ["ARIADNE_LLM_BASE_URL"] = args.llm_base_url
        os.environ["PLANNER_LLM_BASE_URL"] = args.llm_base_url
    if getattr(args, "pipeline_timeout_s", None):
        os.environ["PIPELINE_TIMEOUT_S"] = str(args.pipeline_timeout_s)
    if getattr(args, "llm_timeout_s", None):
        os.environ["ARIADNE_LLM_TIMEOUT_S"] = str(args.llm_timeout_s)
        os.environ["PLANNER_LLM_TIMEOUT_S"] = str(args.llm_timeout_s)
    if getattr(args, "cache_dir", None):
        os.environ["ARIADNE_REWRITE_CACHE_DIR"] = args.cache_dir
    preflight()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
