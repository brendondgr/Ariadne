#!/usr/bin/env python3
"""EXP-2026-08-016 phase 2 — does a customer graph leak into catalogue answers?

    uv run python scripts/isolation_probes.py --out docs/evaluation/isolation-2026-08-23

With three live sources — two public catalogues and one tenant's identity graph —
"is this query safe" stops being the only safety question. The deployment
question a customer actually has is **tenant isolation**: when I ask about
ATT&CK, can records from my identity graph appear in the answer, and vice versa?

The safety *gate* cannot answer that. It rules on one query against one card and
is structurally incapable of seeing a cross-source contamination, because each
individual query is perfectly legal for the source it was sent to. Isolation is a
property of **routing**, one layer up, and it has never been measured.

**This is a controlled before/after, not an assertion.** The comparative
source-selection rule (2026-08-22) was introduced to fix over-routing, and its
effect on leakage was described rather than quantified. `ARIADNE_SOURCE_SELECTION`
now switches between the pre-fix absolute rule and the shipped comparative one,
so the same probes run under both and the difference is the fix's value.

**Metric.** For each probe, whose records reached the evidence:

``leaked_sources``   sources present in the evidence that the probe is not about
``leaked_records``   how many records those sources contributed
``routed``           what the planner selected

A probe about ATT&CK that returns identity records has leaked, whether or not
the answer quotes them: the records crossed a tenancy boundary into a bundle the
composer reads.
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

TRI_ENV: dict[str, str] = {
    "ARIADNE_DATA_DIR": "data-tri",
    "ARIADNE_ENDPOINT_ATTACK": "bolt://localhost:5456",
    "ARIADNE_ENDPOINT_CAPEC": "ws://localhost:6455/gremlin",
    "ARIADNE_ENDPOINT_IDENTITY": "bolt://localhost:5459",
    "NEO4J_URI": "bolt://localhost:5456",
    "PLANNER_LLM_ENABLED": "false",
    "SPECIALIST_LLM_ENABLED": "false",
    "SYNTHESIS_LLM_ENABLED": "false",
    "CONVERSATION_LLM_ENABLED": "false",
    "ORCH_MAX_HOPS": "5",
}

#: Each probe names the single source it is legitimately about. Everything else
#: reaching the evidence is a leak. Deliberately phrased in ordinary analyst
#: English, including the generic words ("group", "user", "domain") that caused
#: the over-routing in the first place — a probe set that avoided them would be
#: testing nothing.
PROBES: list[tuple[str, str, str]] = [
    # --- about ATT&CK only -------------------------------------------------
    ("attack", "attack_mitigations", "What mitigations does ATT&CK list for T1047?"),
    ("attack", "attack_group", "Which group uses T1059.001?"),
    ("attack", "attack_technique", "What is T1003.006?"),
    ("attack", "attack_software", "Which software implements T1005?"),
    ("attack", "attack_tactic", "Which techniques belong to the credential access tactic?"),
    # --- about CAPEC only --------------------------------------------------
    ("capec", "capec_pattern", "What is CAPEC-66?"),
    ("capec", "capec_weakness", "Which weaknesses does CAPEC-66 exploit?"),
    ("capec", "capec_mitigation", "What mitigations does CAPEC-98 list?"),
    ("capec", "capec_children", "What are the child patterns of CAPEC-116?"),
    # --- about the tenant identity graph only ------------------------------
    ("identity", "identity_group", "Which users are members of the Domain Admins group?"),
    ("identity", "identity_device", "What devices does the finance department own?"),
    ("identity", "identity_privilege", "Which groups hold GENERIC_ALL over a domain?"),
    ("identity", "identity_user", "What is the department of the user account jmartin?"),
    ("identity", "identity_trust", "Which domains have a forest trust with each other?"),
]


def _apply(env: dict[str, str]) -> None:
    for key, value in env.items():
        os.environ[key] = value


def _clear(env: dict[str, str]) -> None:
    for key in env:
        os.environ.pop(key, None)


def _evidence_by_source(evidence: Any) -> dict[str, int]:
    """Record counts per source, straight off the live evidence bundle."""
    counts: dict[str, int] = defaultdict(int)
    for result in getattr(evidence, "results", []) or []:
        source = getattr(getattr(result, "task", None), "source", None) or "?"
        counts[source] += len(getattr(result, "records", []) or [])
    return dict(counts)


def run_probe(question: str) -> tuple[list[str], dict[str, int]]:
    from utils.orchestration.main import PipelineRun, iter_pipeline

    run = PipelineRun(question=question, mode="query")
    routed: list[str] = []
    evidence = None
    for event, payload in iter_pipeline(question, mode="query", use_llm=False, run=run):
        if event == "plan":
            plan = payload.get("plan")
            if plan is not None:
                routed = sorted(plan.target_sources())
        elif event == "evidence":
            evidence = payload.get("evidence")
        elif event == "answer":
            if payload.get("evidence") is not None:
                evidence = payload["evidence"]
    return routed, _evidence_by_source(evidence) if evidence is not None else {}


def sweep_rule(rule: str) -> dict[str, Any]:
    env = dict(TRI_ENV)
    if rule == "absolute":
        env["ARIADNE_SOURCE_SELECTION"] = "absolute"
    _apply(env)
    try:
        rows: list[dict[str, Any]] = []
        for about, name, question in PROBES:
            try:
                routed, counts = run_probe(question)
            except Exception as exc:  # noqa: BLE001 — one probe must not end the sweep
                rows.append({"probe": name, "about": about, "error":
                             f"{type(exc).__name__}: {exc}"})
                continue
            leaked = {s: n for s, n in counts.items() if s != about and n}
            rows.append({
                "probe": name,
                "about": about,
                "question": question,
                "routed": routed,
                "records_by_source": counts,
                "leaked_sources": sorted(leaked),
                "leaked_records": sum(leaked.values()),
            })
            flag = "LEAK" if leaked else "ok  "
            print(f"  [{rule:10s}] {flag} {name:20s} routed={','.join(routed) or '-':24s} "
                  f"leaked={sum(leaked.values()):4d} {sorted(leaked)}")
        scored = [r for r in rows if "error" not in r]
        return {
            "rule": rule,
            "probes": len(PROBES),
            "scored": len(scored),
            "errors": len(rows) - len(scored),
            "probes_leaking": sum(1 for r in scored if r["leaked_records"]),
            "leaked_records_total": sum(r["leaked_records"] for r in scored),
            "worst_probe": max(
                (r for r in scored), key=lambda r: r["leaked_records"], default=None
            ),
            "rows": rows,
        }
    finally:
        _clear(env)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    result: dict[str, Any] = {}
    for rule in ("absolute", "comparative"):
        print(f"== source-selection rule: {rule}")
        result[rule] = sweep_rule(rule)

    out_dir = REPO / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "metrics.json").write_text(json.dumps(result, indent=2) + "\n")

    print("\n== tenant isolation, three live sources")
    print(f"  {'rule':14s} {'probes leaking':>15s} {'leaked records':>15s}")
    for rule, r in result.items():
        print(f"  {rule:14s} {r['probes_leaking']:>10d}/{r['scored']:<4d} "
              f"{r['leaked_records_total']:>15d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
