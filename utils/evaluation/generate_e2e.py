#!/usr/bin/env python3
"""Generate-only phase of the end-to-end evaluation.

Runs the assembled pipeline (probe → plan → specialists → synthesis) over the
whole golden catalogue and **persists every answer plus the logic/evidence
needed to judge it** — but does NOT judge. Judging is a separate, decoupled
step (an independent panel of agents) so the answer set is never scored by the
same model that produced it.

Parallelism: exactly ``--workers`` threads (default 4). Each worker thread owns
its own ``SpecialistRouter`` set via thread-local storage, because the Gremlin
connector opens/closes a client per task and is not safe to share across
threads. Synthesis runs with the configured LLM narrator on
(``SynthesisConfig.from_env``) so the persisted answer is the real pipeline
answer, not the deterministic-only draft.

Output: one ``<case_id>.json`` per question under ``--out-dir`` (default
``docs/evaluation/answers``), plus a ``manifest.json`` listing every case.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from utils.specialists.contracts import (
    EvidenceRecord,
    SpecialistResult,
    SpecialistTask,
)
from utils.specialists.federation import FederatedEvidence
from utils.synthesis.contracts import SynthesizedAnswer

MANIFEST_NAME = "manifest.json"
# Kept in step with the narrator's own evidence bounds (utils/synthesis/
# llm_composer.py): a judge that sees *less* than the narrator saw will flag
# faithful, grounded claims as hallucinations. The record cap matches the
# narrator's 50 so every record the answer could have drawn on is visible.
_MAX_RECORDS_PER_RESULT = 50
# Higher than the narrator's prose bound (30): the judge must see the *whole*
# related set that backs a structured enumeration claim (e.g. TrickBot's 55
# techniques), or it flags the enumerated ids beyond the cap as ungrounded.
_MAX_RELATED_PER_RECORD = 100
_MAX_FACETS_PER_RECORD = 20
_MAX_DESC_CHARS = 600
# Bulky citation arrays carry no evidentiary value for a judge and drown the
# real properties — dropped with an explicit marker rather than silently.
_SKIP_PROPERTIES = frozenset({"external_references"})


# -- serialization ----------------------------------------------------------


def _cap(name: str, default: int) -> int:
    """This artifact bound's live value: ``EVAL_ARTIFACT_<NAME>`` else the default.

    Read at call time so an un-truncated run can persist the *whole* retrieved
    neighbourhood for the judge — a judge that sees less than the pipeline saw
    flags faithful claims as hallucinations.
    """
    from utils.config import env_int

    return env_int(f"EVAL_ARTIFACT_{name}", default)


def _bound(text: Any, cap: int | None = None) -> str:
    cap = _cap("MAX_DESC_CHARS", _MAX_DESC_CHARS) if cap is None else cap
    s = "" if text is None else str(text)
    return s if len(s) <= cap else s[:cap] + f"… (+{len(s) - cap} chars)"


def _bounded_properties(properties: Any) -> dict[str, Any]:
    """A judge-safe view of a record's own properties (Abstraction, Status, …).

    Mirrors ``llm_composer._bounded_properties`` so the judge sees exactly the
    attribute set the narrator did: the description survives whole (bounded),
    long strings are marked-truncated, bulky arrays are trimmed, and known-noise
    keys are dropped with a marker. Dropping every property but ``description``
    is what previously made faithful reads of Abstraction/Status look invented.
    """
    out: dict[str, Any] = {}
    dropped: list[str] = []
    for key, value in (properties or {}).items() if isinstance(properties, dict) else []:
        if key in _SKIP_PROPERTIES:
            dropped.append(key)
            continue
        if isinstance(value, str):
            out[key] = _bound(value)
        elif isinstance(value, bool) or isinstance(value, (int, float)) or value is None:
            out[key] = value
        elif isinstance(value, list):
            items = _cap("MAX_PROP_LIST_ITEMS", 10)
            out[key] = [str(v) for v in value[:items]]
            if len(value) > items:
                out[key].append(f"…(+{len(value) - items} more)")
    if dropped:
        out["_omitted_properties"] = sorted(dropped)
    return out


def _record_dict(r: EvidenceRecord) -> dict[str, Any]:
    """A judging-oriented view of one record: identity + its neighbours' text.

    Keeps each related neighbour's *description* — the actual step / mitigation /
    consequence prose — plus the record's own bounded ``properties`` (so an
    attribute question's answer is checkable) and the ``facets`` adjacency counts
    (so a "how many sub-techniques" claim is grounded). These last two were
    dropped before, which under-served the judge, not the pipeline.
    """
    props = _bounded_properties(r.properties)
    related = []
    for rel in r.related[:_cap("MAX_RELATED", _MAX_RELATED_PER_RECORD)]:
        if not isinstance(rel, dict):
            related.append({"value": _bound(rel, 200)})
            continue
        entry = {
            k: rel.get(k)
            for k in ("id", "entry_id", "name", "label", "step", "role", "abstraction", "type", "direction")
            if k in rel
        }
        if rel.get("description"):
            entry["description"] = _bound(rel["description"])
        related.append(entry)
    return {
        "primary_id": r.primary_id,
        "name": r.name,
        "label": r.label,
        "description": props.get("description", ""),
        "properties": props,
        "facets": [
            {
                "rel": f.get("rel"),
                "direction": f.get("direction"),
                "neighbour_label": f.get("label"),
                "count": f.get("count"),
            }
            for f in (r.facets or [])[:_cap("MAX_FACETS", _MAX_FACETS_PER_RECORD)]
        ],
        "join_values": list(r.join_values),
        "related": related,
    }


def _result_dict(res: SpecialistResult) -> dict[str, Any]:
    return {
        "source": res.task.source,
        "sub_question_id": res.task.sub_question_id,
        "sub_question": res.task.text,
        "query": res.query,
        "ok": res.ok,
        "partial": res.partial,
        "error": res.error,
        "summary": res.summary,
        "traces": [
            {"step": t.step, "ok": t.ok, "reasons": list(t.reasons), "detail": t.detail}
            for t in res.traces
        ],
        "records": [
            _record_dict(r)
            for r in res.records[:_cap("MAX_RECORDS", _MAX_RECORDS_PER_RESULT)]
        ],
    }


def _answer_dict(ans: SynthesizedAnswer) -> dict[str, Any]:
    return {
        "headline": ans.headline,
        "narrative": ans.narrative,
        "composer": ans.composer,
        "fallback_reason": ans.fallback_reason,
        "claims": [
            {
                "text": c.text,
                "kind": c.kind,
                "entity_ids": list(c.entity_ids),
                "citations": [
                    {"source": cit.source, "primary_id": cit.primary_id}
                    for cit in c.citations
                ],
            }
            for c in ans.rendered_claims()
        ],
        "abstentions": [
            {"source": a.source, "statement": a.statement, "query": a.query}
            for a in ans.abstentions
        ],
        "notes": list(ans.notes),
    }


def _gold_dict(entry: dict) -> dict[str, Any]:
    return {
        k: entry[k]
        for k in ("assertions", "ex_gold", "gold_provenance", "sources", "hops")
        if entry.get(k) is not None
    }


def _artifact(entry: dict, kind: str, evidence: FederatedEvidence,
              answer: SynthesizedAnswer) -> dict[str, Any]:
    from utils.evaluation.score_e2e import _category_of, evaluate_case

    case = evaluate_case(entry, evidence, answer, kind=kind)
    logic: dict[str, Any] = {}
    if kind == "federated":
        logic["plan"] = [
            {"sub_question_id": s.get("sub_question_id"), "source": s.get("source"),
             "text": s.get("text"), "seed_from": s.get("seed_from")}
            for s in entry.get("sub_questions", [])
        ]
        logic["sequenced"] = entry.get("sequenced")
        logic["partial_mode"] = entry.get("partial_mode")
    else:
        logic["task"] = entry.get("task")
    logic["results"] = [_result_dict(r) for r in evidence.results]
    return {
        "id": entry["id"],
        "kind": kind,
        "tier": entry.get("tier"),
        "category": _category_of(entry["id"]),
        "question": entry["question"],
        "gold": _gold_dict(entry),
        "answer": _answer_dict(answer),
        "logic_flow": logic,
        "deterministic_scores": {
            k: v for k, v in case.to_dict().items()
            if k not in ("id", "kind", "tier", "category")
        },
    }


# -- parallel generation ----------------------------------------------------


class _RouterPool:
    """Thread-local router sets — each worker thread gets its own connectors."""

    def __init__(self) -> None:
        self._local = threading.local()

    def _build(self) -> dict[str, Any]:
        from utils.specialists.config import SpecialistConfig
        from utils.specialists.federation import SpecialistRouter

        config = SpecialistConfig.from_env()
        full = SpecialistRouter(config)
        routers = {
            None: full,
            "boundary": full,
            "attack_down": SpecialistRouter(config, cards=full.cards, specialists={"attack": None}),
            "capec_down": SpecialistRouter(config, cards=full.cards, specialists={"capec": None}),
        }
        return {"routers": routers, "full": full}

    def get(self) -> dict[str, Any]:
        state = getattr(self._local, "state", None)
        if state is None:
            state = self._build()
            self._local.state = state
        return state


def _generate_one(entry: dict, kind: str, pool: _RouterPool, synth_config) -> dict[str, Any]:
    from utils.evaluation.score_e2e import run_federated, run_single

    state = pool.get()
    if kind == "federated":
        router = state["routers"][entry["partial_mode"]]
        evidence, answer = run_federated(entry, router, synth_config)
    else:
        specialist = state["full"]._specialist_for(kind)
        evidence, answer = run_single(entry, specialist, synth_config)
    return _artifact(entry, kind, evidence, answer)


def generate_answers(
    out_dir: str = "docs/evaluation/answers",
    *,
    workers: int = 4,
    limit: int | None = None,
    include_single: bool = True,
) -> dict[str, Any]:
    """Run the pipeline over the catalogue in parallel and persist every answer.

    Returns a manifest dict. Never judges — that is a separate step.
    """
    from utils.config import load_env
    from utils.evaluation.score_e2e import _load_banks
    from utils.synthesis.config import SynthesisConfig

    load_env()  # honour .env (LLM seams, graph URIs) when run as a module
    synth_config = SynthesisConfig.from_env()  # LLM narrator on — the real answer
    federated, attack_q, capec_q = _load_banks()

    work: list[tuple[dict, str]] = []
    fed = federated[:limit] if limit is not None else federated
    work += [(e, "federated") for e in fed]
    if include_single:
        for source, entries in (("attack", attack_q), ("capec", capec_q)):
            single = entries[:limit] if limit is not None else entries
            work += [(e, source) for e in single]

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    pool = _RouterPool()
    manifest: list[dict[str, Any]] = []
    done = 0
    total = len(work)
    print(
        f"Generating {total} answers with {workers} workers "
        f"(LLM synthesis: {'on' if synth_config.llm_enabled else 'off'})…",
        file=sys.stderr,
    )
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_generate_one, e, k, pool, synth_config): e["id"] for e, k in work}
        for fut in as_completed(futures):
            cid = futures[fut]
            try:
                artifact = fut.result()
            except Exception as exc:  # noqa: BLE001 - one bad case must not sink the batch
                print(f"  ! {cid} failed: {exc}", file=sys.stderr)
                manifest.append({"id": cid, "ok": False, "error": str(exc)})
                continue
            (out / f"{cid}.json").write_text(
                json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            manifest.append({
                "id": cid, "ok": True, "kind": artifact["kind"],
                "tier": artifact["tier"], "category": artifact["category"],
            })
            done += 1
            if done % 10 == 0 or done == total:
                print(f"  … {done}/{total}", file=sys.stderr)

    manifest.sort(key=lambda m: m["id"])
    manifest_doc = {
        "count": len(manifest),
        "generated_ok": sum(1 for m in manifest if m.get("ok")),
        "workers": workers,
        "llm_synthesis": synth_config.llm_enabled,
        "cases": manifest,
    }
    (out / MANIFEST_NAME).write_text(
        json.dumps(manifest_doc, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"wrote {len(manifest)} artifacts + manifest to {out}/", file=sys.stderr)
    return manifest_doc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate (and save) e2e answers; no judging.")
    parser.add_argument("--out-dir", default="docs/evaluation/answers")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int, default=None, help="cap entries per bank (smoke)")
    parser.add_argument("--no-single", action="store_true", help="federated bank only")
    args = parser.parse_args(argv)
    generate_answers(
        args.out_dir,
        workers=args.workers,
        limit=args.limit,
        include_single=not args.no_single,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
