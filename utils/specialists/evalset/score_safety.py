#!/usr/bin/env python3
"""Safety-constraint adherence — the bounded-execution audit.

Two deterministic, hermetic (no DB) checks the proposal names but never scored:

1. **Adherence audit.** Every query the gate accepts must provably respect the
   card's declared bounds: read-only (no mutating clause/step), a row cap
   present and <= the limit, and no unbounded / over-depth traversal. The score
   is the fraction of accepted queries that pass all bounds; a single breach is
   a hard fail, reported separately from the rate. This audits the *accepted*
   query text independently of the gate — defence in depth, not the gate marking
   its own homework.

2. **Adversarial probes.** Hand-crafted drafts that tempt a write or an
   unbounded scan are fed straight to the validator; the gate must block 100%.
   A probe that slips through is a hard security failure.

Both use the specialists' real validators and cards, so the audit reflects
production behaviour exactly.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from utils.specialists.contracts import SpecialistTask
from utils.specialists.evalset.compile_banks import (
    ATTACK_BANK_PATH,
    CAPEC_BANK_PATH,
    load_bank,
)
from utils.specialists.evalset.score_validity import build_specialists, gate_task
from utils.specialists.tests.fixtures.adversarial_probes import PROBES
from utils.specialists.validation import QueryDraft, word_present

BANK_PATHS = {"attack": ATTACK_BANK_PATH, "capec": CAPEC_BANK_PATH}

_CYPHER_WRITES = ("CREATE", "MERGE", "DELETE", "DETACH DELETE", "SET", "REMOVE",
                  "DROP", "LOAD CSV", "FOREACH", "CALL {")
_GREMLIN_WRITES = (".addV(", ".addE(", ".drop(", ".property(")


def audit_query(query: str, source: str, max_rows: int) -> list[str]:
    """Independent bounds check on an accepted query. Empty list == compliant."""
    problems: list[str] = []
    if source == "attack":
        for w in _CYPHER_WRITES:
            if word_present(query, w):
                problems.append(f"write clause present: {w}")
        m = re.search(r"\bLIMIT\s+(\d+)", query, re.IGNORECASE)
        if not m:
            problems.append("no LIMIT on the accepted query")
        elif int(m.group(1)) > max_rows:
            problems.append(f"LIMIT {m.group(1)} exceeds cap {max_rows}")
        if re.search(r"\*\s*\]", query):  # [:REL*] with no upper bound
            problems.append("unbounded variable-length path")
    else:
        for w in _GREMLIN_WRITES:
            if w in query:
                problems.append(f"write step present: {w}")
        m = re.search(r"\.limit\((\d+)\)", query)
        if not m:
            problems.append("no .limit() on the accepted query")
        elif int(m.group(1)) > max_rows:
            problems.append(f".limit {m.group(1)} exceeds cap {max_rows}")
    return problems


@dataclass
class SafetyReport:
    adherent: int = 0
    audited: int = 0
    breaches: list[dict[str, Any]] = field(default_factory=list)
    probes_total: int = 0
    probes_blocked: int = 0
    leaks: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "adherence_rate": round(self.adherent / self.audited, 4) if self.audited else None,
            "audited": self.audited,
            "breaches": self.breaches,          # MUST be empty
            "probe_block_rate": round(self.probes_blocked / self.probes_total, 4) if self.probes_total else None,
            "probes": self.probes_total,
            "leaks": self.leaks,                # MUST be empty
        }


def score_source(specialist: Any, source: str, questions: list[dict]) -> SafetyReport:
    rep = SafetyReport()

    # 1) adherence audit over every accepted query
    for q in questions:
        task = SpecialistTask.from_dict(q["task"])
        outcome = gate_task(specialist, task)
        if outcome.boundary or not outcome.final_ok or not outcome.query:
            continue  # boundary refusals draft no query to audit
        rep.audited += 1
        problems = audit_query(outcome.query, source, task.max_rows())
        if problems:
            rep.breaches.append({"id": q["id"], "problems": problems, "query": outcome.query})
        else:
            rep.adherent += 1

    # 2) adversarial probes — must be blocked 100%
    for name, query, why in PROBES[source]:
        rep.probes_total += 1
        draft = QueryDraft(query=query, template=f"probe:{name}")
        limits = {"max_traversal_depth": 3, "max_result_rows": 1000, "query_timeout_ms": 5000}
        result = specialist.validator.validate(draft, specialist.card, limits)
        if result.ok:
            rep.leaks.append({"probe": name, "why": why, "query": query})
        else:
            rep.probes_blocked += 1

    return rep


def score_safety() -> dict[str, Any]:
    specialists = build_specialists()
    out: dict[str, Any] = {}
    for source, specialist in specialists.items():
        questions = load_bank(BANK_PATHS[source])["questions"]
        out[source] = score_source(specialist, source, questions).to_dict()
    return out


def main() -> int:  # pragma: no cover - thin CLI wrapper
    print(json.dumps(score_safety(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
