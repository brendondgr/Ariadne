#!/usr/bin/env python3
"""EXP-2026-08-018 — Q20: reconnect the LLM claims composer and measure it.

    uv run python scripts/composer_arm_sweep.py --out docs/evaluation/composer-2026-08-24 --repeats 3

`OpenAICompatibleComposer` is the only thing in this codebase that lets a
language model **propose a claim**. `factory.synthesize` never called
`select_composer`, so it had no caller, and EXP-2026-08-014 could therefore only
report that all four verifier gates cut zero claims from 888 — a true result and
a vacuous one. **A gate cannot cut what cannot be constructed.**

Q20 asked for the composer to be reconnected and measured before any decision to
delete it, and for **a series of tests rather than one check**. This runs five,
over the same evidence:

``T1 engagement``   does the composer actually run, per question, or does the
                    hybrid fall back? Measured from ``answer.composer`` and
                    ``fallback_reason`` — never from the flag, which is how
                    EXP-2026-08-014's first LLM arm silently ran deterministic.
``T2 gates``        do the four verifier gates fire when an LLM proposes the
                    claims? This is the measurement Q10/C-017 could not make.
``T3 grounding``    of the claims that survive, do they carry the gold the
                    deterministic composer carries? Same retrieval, so any
                    difference is composition.
``T4 variance``     the composer is nondeterministic, so every figure above is
                    reported over ``--repeats`` runs with its spread. A
                    single-run number here would be exactly the n=1 problem Q2
                    exists to fix.
``T5 cost``         wall clock against the deterministic composer.

**Retrieval is held constant.** Planning and query construction stay
deterministic in every condition, so the evidence bundle a question produces is
identical and only composition varies.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from collections import defaultdict
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

BASE_ENV: dict[str, str] = {
    "PLANNER_LLM_ENABLED": "false",
    "SPECIALIST_LLM_ENABLED": "false",
    "CONVERSATION_LLM_ENABLED": "false",
    "ORCH_MAX_HOPS": "5",
}

#: The composer is a reasoning model and truncates to empty on a small budget,
#: which reads exactly like a dead server. Measured guidance in
#: `ariadne-skynet-reasoning-budget`: never below 2048, and cap the thinking
#: share so the answer has room.
LLM_ENV: dict[str, str] = {
    "SYNTHESIS_LLM_MAX_TOKENS": "8192",
    "SYNTHESIS_LLM_THINKING_BUDGET": "3072",
}

ARMS: dict[str, dict[str, bool]] = {
    "deterministic": {"llm_claims": False},
    "llm_claims": {"llm_claims": True},
}


def _banks() -> list[tuple[str, Path]]:
    return [
        ("attack", Path(ATTACK_BANK_PATH)),
        ("capec", Path(CAPEC_BANK_PATH)),
        ("federated", Path(FEDERATED_BANK_PATH)),
    ]


def _gold_ids(entry: dict[str, Any]) -> set[str]:
    out: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, str):
            out.add(normalize_id(node))
        elif isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            for key, value in node.items():
                if key in {"must_include", "must_include_related", "expected", "ids", "gold", "ex_gold"}:
                    walk(value)

    for key in ("gold", "assertions", "ex_gold"):
        walk(entry.get(key))
    return {v for v in out if v}


def run_one(question: str, config: SynthesisConfig) -> dict[str, Any]:
    """One pipeline pass under the given synthesis config."""
    from utils.orchestration.main import PipelineRun, iter_pipeline

    started = time.monotonic()
    run = PipelineRun(question=question, mode="query")
    answer = evidence = None
    for event, payload in iter_pipeline(
        question, mode="query", use_llm=False, run=run, synthesis_config=config
    ):
        if event == "evidence":
            evidence = payload.get("evidence")
        elif event == "answer":
            if payload.get("evidence") is not None:
                evidence = payload["evidence"]
            answer = payload.get("synthesized")
    elapsed = time.monotonic() - started

    if answer is None:
        return {"error": "no answer", "elapsed_s": round(elapsed, 3)}

    verdicts = answer.verification.verdicts if answer.verification else []
    claim_ids: set[str] = set()
    for claim in answer.claims:
        claim_ids.update(normalize_id(e) for e in claim.entity_ids if e)
    supported_ids: set[str] = set()
    for claim, verdict in zip(answer.claims, verdicts):
        if verdict.supported:
            supported_ids.update(normalize_id(e) for e in claim.entity_ids if e)

    return {
        "composer": getattr(answer, "composer", "?"),
        "fallback_reason": answer.fallback_reason,
        "claims": len(answer.claims),
        "unsupported": sum(1 for v in verdicts if not v.supported),
        "unsupported_reasons": [r for v in verdicts if not v.supported for r in v.reasons][:4],
        "abstentions": len(answer.abstentions or []),
        "claim_ids": sorted(claim_ids),
        "supported_ids": sorted(supported_ids),
        "elapsed_s": round(elapsed, 3),
    }


def sweep_arm(arm: str, repeat: int, workers: int, limit: int | None) -> dict[str, Any]:
    config = SynthesisConfig.from_env()
    config = type(config)(**{**config.__dict__, **ARMS[arm]})

    jobs: list[tuple[str, str, str, set[str]]] = []
    for bank_name, path in _banks():
        entries = load_bank(path)
        questions = entries["questions"] if isinstance(entries, dict) else entries
        if limit:
            questions = questions[:limit]
        for entry in questions:
            text = entry.get("question") or entry.get("text") or ""
            if text:
                jobs.append((bank_name, entry.get("id", ""), text, _gold_ids(entry)))

    rows: list[dict[str, Any]] = []

    def work(job):
        bank, cid, text, gold = job
        try:
            out = run_one(text, config)
        except Exception as exc:  # noqa: BLE001 - one question must not end the sweep
            out = {"error": f"{type(exc).__name__}: {exc}"}
        out.update({"bank": bank, "case_id": cid})
        if "error" not in out and gold:
            sup = set(out["supported_ids"])
            out["gold_in_claims"] = round(len(sup & gold) / len(gold), 4)
        return out

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i, row in enumerate(pool.map(work, jobs), 1):
            rows.append(row)
            if i % 25 == 0:
                print(f"  [{arm} r{repeat}] {i}/{len(jobs)}")

    scored = [r for r in rows if "error" not in r]
    composers: dict[str, int] = defaultdict(int)
    for r in scored:
        composers[r["composer"]] += 1
    covered = [r["gold_in_claims"] for r in scored if "gold_in_claims" in r]

    return {
        "arm": arm,
        "repeat": repeat,
        "questions": len(jobs),
        "answered": len(scored),
        "errors": len(rows) - len(scored),
        "composer_used": dict(composers),
        "fallbacks": sum(1 for r in scored if r.get("fallback_reason")),
        "claims_total": sum(r["claims"] for r in scored),
        "unsupported_total": sum(r["unsupported"] for r in scored),
        "answers_with_unsupported": sum(1 for r in scored if r["unsupported"]),
        "abstentions_total": sum(r["abstentions"] for r in scored),
        "gold_in_claims_mean": round(statistics.fmean(covered), 4) if covered else None,
        "gold_in_claims_n": len(covered),
        "wall_s_total": round(sum(r["elapsed_s"] for r in scored), 1),
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    for key, value in {**BASE_ENV, **LLM_ENV}.items():
        os.environ[key] = value
    # `llm_enabled` stays FALSE throughout: this experiment isolates the claims
    # composer, and leaving the prose narrator on would confound the two seams.
    os.environ["SYNTHESIS_LLM_ENABLED"] = "false"

    out_dir = REPO / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []

    for arm in ARMS:
        # The deterministic arm is byte-reproducible, so one run is the whole
        # distribution — repeating it would only burn wall clock.
        repeats = 1 if arm == "deterministic" else args.repeats
        for r in range(1, repeats + 1):
            print(f"== {arm}, repeat {r}/{repeats}")
            results.append(sweep_arm(arm, r, args.workers, args.limit))

    (out_dir / "metrics.json").write_text(json.dumps(results, indent=2) + "\n")

    print(f"\n{'arm':16s} {'rep':>3s} {'answered':>8s} {'composer':>22s} {'claims':>7s} "
          f"{'unsup':>6s} {'gold':>7s} {'wall_s':>8s}")
    for r in results:
        comp = ",".join(f"{k}:{v}" for k, v in sorted(r["composer_used"].items()))
        gold = f"{r['gold_in_claims_mean']:.4f}" if r["gold_in_claims_mean"] is not None else "—"
        print(f"{r['arm']:16s} {r['repeat']:>3d} {r['answered']:>8d} {comp:>22s} "
              f"{r['claims_total']:>7d} {r['unsupported_total']:>6d} {gold:>7s} "
              f"{r['wall_s_total']:>8.1f}")

    llm = [r for r in results if r["arm"] == "llm_claims"]
    if len(llm) > 1:
        for field in ("claims_total", "unsupported_total", "gold_in_claims_mean"):
            vals = [r[field] for r in llm if r[field] is not None]
            if len(vals) > 1:
                print(f"  variance {field}: mean {statistics.fmean(vals):.4f} "
                      f"sd {statistics.stdev(vals):.4f} range [{min(vals)}, {max(vals)}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
