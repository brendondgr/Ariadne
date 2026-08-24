#!/usr/bin/env python3
"""EXP-2026-08-014 — what each verifier gate actually cuts.

    uv run python scripts/ablation_sweep.py --out docs/evaluation/ablation-2026-08-23

**Why this runs the pipeline rather than reading the committed artifacts.** The
first version of this script re-verified the recorded answers offline, which
would have been free and perfectly isolated. It reported zero unsupported claims
across 1,756 claims — and that was an artifact, not a result:
``utils/evaluation/generate_e2e.py::_answer_dict`` serialises
``ans.rendered_claims()``, the **supported** set. Every claim the verifier cut
was already gone from the file, and no recorded run carries a ``verification``
block at all. The committed corpus therefore holds no auditable trace of the
verifier, which is a finding in its own right and is written up in RESULTS.

So the pipeline runs. But it runs **once per question, not once per condition.**
The verifier is a pure function of (claims, evidence) and one pass yields both as
live objects, so the five conditions re-verify *identical inputs*. Any difference
between conditions is the gate and nothing else — a guarantee five separate runs
could not give, since each would re-plan and re-retrieve.

Every run is deterministic and LLM-free, so the reading is byte-reproducible.

**The measurement is the diff.** For each gate, the claims that are `unsupported`
with it on and `supported` with it off are exactly what that gate cuts. Each is
classified *mechanically*, without a judge:

``gold_absent``   none of the claim's entity ids appear in the question's gold,
                  so the gate cut something the answer had no business
                  asserting — the gate earning its place.
``gold_backed``   every entity id is in gold, so the gate cut something true —
                  a false positive for the gate.
``ambiguous``     partial overlap, or the question carries no usable gold. The
                  residual: counted and exported, never guessed at.

Judging the residual is deliberately out of scope (see
``docs/plans/2026-08-23-record-hardening-decisions.md`` Q2). It is written to
``residual.json`` judge-ready, so buying Sonnet later is one command.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
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
from utils.synthesis.verifier import (  # noqa: E402
    _records_by_source,
    _verify_claim,
)

GATES = ("cited", "resolvable", "grounded", "correlated")
HOLDOUT_BANK_PATH = REPO / "utils/specialists/tests/golden/holdout_questions.json"

#: Deterministic, LLM-free everywhere. Mirrors the arm harnesses so the
#: condition this ablates is the one every recorded figure was measured under.
BASE_ENV: dict[str, str] = {
    "PLANNER_LLM_ENABLED": "false",
    "SPECIALIST_LLM_ENABLED": "false",
    "SYNTHESIS_LLM_ENABLED": "false",
    "CONVERSATION_LLM_ENABLED": "false",
    "ORCH_MAX_HOPS": "5",
}


def _banks() -> list[tuple[str, Path]]:
    return [
        ("attack", ATTACK_BANK_PATH),
        ("capec", CAPEC_BANK_PATH),
        ("federated", FEDERATED_BANK_PATH),
        ("holdout", HOLDOUT_BANK_PATH),
    ]


def _gold_ids(entry: dict[str, Any]) -> set[str]:
    """Every identifier this question's gold asserts, however the bank shapes it."""
    out: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, str):
            out.add(normalize_id(node))
        elif isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            for key, value in node.items():
                if key in {
                    "must_include",
                    "must_include_related",
                    "expected",
                    "ids",
                    "gold",
                    "ex_gold",
                }:
                    walk(value)

    for key in ("gold", "assertions", "ex_gold"):
        walk(entry.get(key))
    return {v for v in out if v}


def _classify(entity_ids: tuple[str, ...], gold: set[str]) -> str:
    ids = {normalize_id(e) for e in entity_ids if e}
    if not gold or not ids:
        return "ambiguous"
    hits = ids & gold
    if hits == ids:
        return "gold_backed"
    if not hits:
        return "gold_absent"
    return "ambiguous"


def _cfg(disabled: str | None) -> SynthesisConfig:
    return SynthesisConfig(**{f"gate_{g}": (g != disabled) for g in GATES})


def run_question(question: str, synthesis_config: SynthesisConfig) -> tuple[Any, Any]:
    """One pipeline pass; returns the (answer, evidence) live objects.

    ``synthesis_config`` is injected rather than left to the environment, and
    that is load-bearing. ``iter_pipeline`` does
    ``replace(SynthesisConfig.from_env(), llm_enabled=use_llm)``, so passing
    ``use_llm=False`` would force the deterministic composer **regardless of
    SYNTHESIS_LLM_ENABLED** — the first LLM-arm run of this sweep was silently
    the deterministic composer for exactly that reason, and only
    ``answer.composer`` revealed it. An explicitly injected config wins over the
    override, which lets the composer be switched **on its own** while planning
    and query construction stay deterministic. One variable, as an ablation
    requires.
    """
    from utils.orchestration.main import PipelineRun, iter_pipeline

    run = PipelineRun(question=question, mode="query")
    answer = evidence = None
    for event, payload in iter_pipeline(
        question,
        mode="query",
        use_llm=False,
        run=run,
        synthesis_config=synthesis_config,
    ):
        if event == "evidence":
            evidence = payload.get("evidence")
        elif event == "answer":
            if payload.get("evidence") is not None:
                evidence = payload["evidence"]
            answer = payload.get("synthesized")
    return answer, evidence


def sweep(synthesis_config: SynthesisConfig, limit: int | None = None) -> dict[str, Any]:
    conditions = {"baseline": None, **{f"no_{g}": g for g in GATES}}
    per_bank: dict[str, Any] = {}
    residual: list[dict[str, Any]] = []
    totals = {g: {"gold_absent": 0, "gold_backed": 0, "ambiguous": 0} for g in GATES}
    condition_totals = {
        name: {"claims": 0, "supported": 0, "unsupported": 0} for name in conditions
    }

    for bank_name, path in _banks():
        if not Path(path).is_file():
            per_bank[bank_name] = {"error": f"missing bank: {path}"}
            continue
        entries = load_bank(Path(path))
        questions = entries["questions"] if isinstance(entries, dict) else entries
        if limit:
            questions = questions[:limit]

        stats = {name: {"claims": 0, "supported": 0, "unsupported": 0} for name in conditions}
        cuts = {g: {"gold_absent": 0, "gold_backed": 0, "ambiguous": 0} for g in GATES}
        answered = errors = 0
        # Provenance, not decoration: an arm that silently fell back to the
        # deterministic composer would otherwise report a clean zero and look
        # like a result. Counted per answer and asserted in RESULTS.
        composers: dict[str, int] = defaultdict(int)
        fallbacks: dict[str, int] = defaultdict(int)

        for i, entry in enumerate(questions, 1):
            text = entry.get("question") or entry.get("text") or ""
            if not text:
                continue
            try:
                answer, evidence = run_question(text, synthesis_config)
            except Exception as exc:  # noqa: BLE001 - one bad question must not end the sweep
                errors += 1
                print(f"  [{bank_name}] {entry.get('id','?')}: ERROR {type(exc).__name__}: {exc}")
                continue
            if answer is None or evidence is None or not getattr(answer, "claims", None):
                continue
            answered += 1
            composers[getattr(answer, "composer", "?")] += 1
            if getattr(answer, "fallback_reason", None):
                fallbacks[str(answer.fallback_reason)[:80]] += 1

            by_source = _records_by_source(evidence)
            cross = {normalize_id(v) for v in evidence.cross_source_join_values()}
            gold = _gold_ids(entry)

            verdicts: dict[str, list[Any]] = {}
            for name, disabled in conditions.items():
                cfg = _cfg(disabled)
                vs = [_verify_claim(c, by_source, cross, cfg) for c in answer.claims]
                verdicts[name] = vs
                stats[name]["claims"] += len(vs)
                stats[name]["supported"] += sum(1 for v in vs if v.supported)
                stats[name]["unsupported"] += sum(1 for v in vs if not v.supported)

            for gate in GATES:
                for claim, base, off in zip(
                    answer.claims, verdicts["baseline"], verdicts[f"no_{gate}"]
                ):
                    if base.supported or not off.supported:
                        continue
                    verdict = _classify(claim.entity_ids, gold)
                    cuts[gate][verdict] += 1
                    if verdict == "ambiguous":
                        residual.append(
                            {
                                "bank": bank_name,
                                "case_id": entry.get("id", ""),
                                "gate": gate,
                                "question": text,
                                "claim": claim.text,
                                "entity_ids": list(claim.entity_ids),
                                "citations": [c.to_dict() for c in claim.citations],
                                "gate_objection": list(base.reasons),
                                "gold_ids": sorted(gold),
                            }
                        )

            if i % 20 == 0:
                print(f"  [{bank_name}] {i}/{len(questions)}")

        per_bank[bank_name] = {
            "questions": len(questions),
            "answered": answered,
            "errors": errors,
            "composer_used": dict(composers),
            "fallback_reasons": dict(fallbacks),
            "conditions": stats,
            "cuts_by_gate": cuts,
        }
        for gate in GATES:
            for key, value in cuts[gate].items():
                totals[gate][key] += value
        for name in conditions:
            for key, value in stats[name].items():
                condition_totals[name][key] += value

    for counts in totals.values():
        counts["total"] = sum(v for k, v in counts.items() if k != "total")

    return {
        "banks": per_bank,
        "condition_totals": condition_totals,
        "totals": totals,
        "residual": residual,
    }


#: The two composer conditions. The gates can only bite where a *language model
#: proposes claims* — `llm_composer.py` builds `Claim.from_dict` off model JSON,
#: while the deterministic composer assembles claims from retrieved records and
#: so cannot construct one that fails a gate. Running only the default arm would
#: measure the verifier where it has nothing to catch, which is precisely the
#: mistake C-017 has been making by resting on provenance reading 1.0.
COMPOSERS: dict[str, dict[str, str]] = {
    "deterministic": {"SYNTHESIS_LLM_ENABLED": "false"},
    "llm": {
        "SYNTHESIS_LLM_ENABLED": "true",
        # skynet is a reasoning model and truncates to empty on a small budget;
        # the thinking cap derives as half of max_tokens unless set.
        "SYNTHESIS_LLM_MAX_TOKENS": "8192",
        "SYNTHESIS_LLM_THINKING_BUDGET": "3072",
    },
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    parser.add_argument("--limit", type=int, default=None, help="first N per bank (smoke test)")
    parser.add_argument(
        "--composer",
        default="deterministic",
        choices=sorted(COMPOSERS),
        help="which composer proposes the claims the gates rule on",
    )
    args = parser.parse_args()

    for key, value in {**BASE_ENV, **COMPOSERS[args.composer]}.items():
        os.environ[key] = value
    synthesis_config = SynthesisConfig.from_env()
    print(f"== composer arm: {args.composer} (llm_enabled={synthesis_config.llm_enabled}, "
          f"gates_all_on={synthesis_config.gates_all_on()})")

    result = sweep(synthesis_config, limit=args.limit)
    result["composer"] = args.composer
    result["synthesis_llm_enabled"] = synthesis_config.llm_enabled
    out_dir = REPO / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    residual = result.pop("residual")
    suffix = args.composer
    (out_dir / f"metrics-{suffix}.json").write_text(json.dumps(result, indent=2) + "\n")
    (out_dir / f"residual-{suffix}.json").write_text(json.dumps(residual, indent=2) + "\n")

    print("\n== per bank")
    for name, bank in result["banks"].items():
        if "error" in bank:
            print(f"  {name:12s} SKIPPED — {bank['error']}")
            continue
        base = bank["conditions"]["baseline"]
        used = ",".join(f"{k}:{v}" for k, v in sorted(bank["composer_used"].items()))
        print(f"  {name:12s} {bank['answered']:3d}/{bank['questions']:3d} answered, "
              f"{base['claims']:5d} claims, {base['unsupported']:4d} unsupported, "
              f"{bank['errors']:2d} errors, composer[{used}]")

    print("\n== claims admitted when each gate is disabled")
    print(f"  {'gate':12s} {'total':>6s} {'gold_absent':>12s} {'gold_backed':>12s} {'ambiguous':>10s}")
    for gate, c in result["totals"].items():
        print(f"  {gate:12s} {c['total']:6d} {c['gold_absent']:12d} "
              f"{c['gold_backed']:12d} {c['ambiguous']:10d}")

    ct = result["condition_totals"]
    print("\n== supported-claim count per condition")
    for name, c in ct.items():
        print(f"  {name:14s} {c['supported']:5d} supported / {c['claims']:5d} claims")
    print(f"\n  residual: {len(residual)} ambiguous claims -> {args.out}/residual-{suffix}.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
