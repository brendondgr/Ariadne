#!/usr/bin/env python3
"""Execution Accuracy (EX) — result-set correctness, phrasing-invariant.

EX is the community-standard text-to-query correctness metric: does the query's
executed result set match the gold result set, regardless of how the query was
written. It is strictly better than string/exact-query match, which false-negs
two different valid queries that return the same rows.

For Ariadne, EX compares the specialist's normalized ``EvidenceRecord`` id pool
against the full snapshot-derived ``ex_gold`` set (see questions.py). Two
variants are reported so a near-miss (4 of 5 mitigations) is visible, not just
pass/fail:

* **exact-set-match** — the returned id set equals the gold set exactly.
* **precision / recall / F1** — partial credit against the gold set.

Every miss is bucketed into an error taxonomy (missing_hop, over_broad,
mismatch, empty_when_nonempty, fabricated_nonempty, boundary_failure,
cardinality) so a score becomes an actionable finding. This scorer is **live**:
it executes against Neo4j/Gremlin, so agreement with the independently-derived
gold also measures ingestion faithfulness.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import asdict, dataclass
from typing import Any

from utils.evaluation.stats import wilson_interval
from utils.specialists.contracts import SpecialistResult, SpecialistTask
from utils.specialists.evalset.compile_banks import (
    ATTACK_BANK_PATH,
    CAPEC_BANK_PATH,
    load_bank,
)
from utils.specialists.evalset.score_validity import build_specialists
from utils.synthesis.grounding import id_pool, normalize_id

BANK_PATHS = {"attack": ATTACK_BANK_PATH, "capec": CAPEC_BANK_PATH}

TAXONOMY = (
    "missing_hop",          # recall < 1, precision == 1 (under-fetch / dropped hop)
    "over_broad",           # precision < 1, recall == 1 (over-fetch / broad scan)
    "mismatch",             # both < 1 (wrong set)
    "empty_when_nonempty",  # gold nonempty but nothing returned
    "fabricated_nonempty",  # gold empty but something returned
    "boundary_failure",     # a boundary refusal was expected but a query ran
    "cardinality",          # a bounded scan fell outside its row window
)


@dataclass
class ExCase:
    id: str
    tier: str
    template: str
    kind: str          # "set" | "boundary" | "scan"
    exact: bool
    precision: float
    recall: float
    f1: float
    bucket: str | None
    n_expected: int
    n_got: int
    query: str


def _got_pool(records: list[Any], pool: str, seeds: tuple[str, ...]) -> set[str]:
    """The id surface of the result the EX gold is compared against.

    * node      — the record ids themselves (a lookup returns the node).
    * neighbors — everything the result exposes minus the seed inputs (the seed
      is the question, not the answer).
    * join      — the T-prefixed ATTACK join values only (capec_maps_to), so a
      pattern's other-taxonomy mappings don't dilute precision.
    """
    seed_set = {normalize_id(s) for s in seeds}
    if pool == "node":
        return {normalize_id(r.primary_id) for r in records if r.primary_id}
    if pool == "join":
        return {normalize_id(jv) for r in records for jv in r.join_values}
    return id_pool(records) - seed_set  # neighbors


def _score_set(expected: set[str], got: set[str]) -> tuple[bool, float, float, float, str | None]:
    if not expected:
        exact = not got
        return exact, (1.0 if exact else 0.0), 1.0, (1.0 if exact else 0.0), (
            None if exact else "fabricated_nonempty"
        )
    tp = len(expected & got)
    recall = tp / len(expected)
    precision = tp / len(got) if got else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    exact = expected == got
    if exact:
        bucket: str | None = None
    elif not got:
        bucket = "empty_when_nonempty"
    elif recall < 1.0 and precision == 1.0:
        bucket = "missing_hop"
    elif precision < 1.0 and recall == 1.0:
        bucket = "over_broad"
    else:
        bucket = "mismatch"
    return exact, precision, recall, f1, bucket


def score_question(specialist: Any, q: dict[str, Any]) -> ExCase:
    result: SpecialistResult = specialist.run(SpecialistTask.from_dict(q["task"]))
    tier = str(q.get("tier", "?"))
    tmpl = str(q["expected_template"])
    assertions = q["assertions"]

    if assertions.get("expect_boundary"):
        ok = bool(result.ok) and result.query == "" and not result.records
        return ExCase(q["id"], tier, tmpl, "boundary", ok, float(ok), float(ok),
                      float(ok), None if ok else "boundary_failure", 0,
                      len(result.records), result.query)

    if "ex_gold" not in q:  # bounded scans: EX == cardinality within the window
        lo = int(assertions.get("min_records", 0))
        hi = int(assertions.get("max_records", 10 ** 9))
        ok = bool(result.ok) and lo <= len(result.records) <= hi
        return ExCase(q["id"], tier, tmpl, "scan", ok, float(ok), float(ok),
                      float(ok), None if ok else "cardinality", 0,
                      len(result.records), result.query)

    ex = q["ex_gold"]
    expected = {normalize_id(x) for x in ex["expected"]}
    seeds = tuple(q["task"].get("seed_ids", []))
    got = _got_pool(result.records, ex["pool"], seeds)
    exact, precision, recall, f1, bucket = _score_set(expected, got)
    return ExCase(q["id"], tier, tmpl, "set", exact, precision, recall, f1,
                  bucket, len(expected), len(got), result.query)


def _rate(successes: int, n: int) -> dict[str, Any]:
    point, low, high = wilson_interval(successes, n)
    return {"k": successes, "n": n, "rate": round(point, 4),
            "ci_low": round(low, 4), "ci_high": round(high, 4)}


def _aggregate(cases: list[ExCase]) -> dict[str, Any]:
    n = len(cases)
    exact_k = sum(1 for c in cases if c.exact)
    set_cases = [c for c in cases if c.kind == "set"]
    return {
        "exact_match": _rate(exact_k, n),
        "mean_precision": round(statistics.fmean(c.precision for c in set_cases), 4) if set_cases else None,
        "mean_recall": round(statistics.fmean(c.recall for c in set_cases), 4) if set_cases else None,
        "mean_f1": round(statistics.fmean(c.f1 for c in set_cases), 4) if set_cases else None,
        "n_set": len(set_cases),
    }


def score_source(specialist: Any, questions: list[dict]) -> dict[str, Any]:
    cases = [score_question(specialist, q) for q in questions]
    tiers = sorted({c.tier for c in cases})
    taxonomy: dict[str, int] = {}
    for c in cases:
        if c.bucket:
            taxonomy[c.bucket] = taxonomy.get(c.bucket, 0) + 1
    return {
        "overall": _aggregate(cases),
        "by_tier": {t: _aggregate([c for c in cases if c.tier == t]) for t in tiers},
        "taxonomy": taxonomy,
        "cases": [asdict(c) for c in cases],
    }


def score_execution() -> dict[str, Any]:
    """Full EX report across both specialists (live)."""
    specialists = build_specialists()
    out: dict[str, Any] = {}
    for source, specialist in specialists.items():
        questions = load_bank(BANK_PATHS[source])["questions"]
        out[source] = score_source(specialist, questions)
    return out


def main() -> int:  # pragma: no cover - thin CLI wrapper
    print(json.dumps(score_execution(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
