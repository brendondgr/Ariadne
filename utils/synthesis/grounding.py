#!/usr/bin/env python3
"""Backend-agnostic identifier grounding shared by verification layers.

Extracted from the golden-suite runner so the synthesis verifier and the
golden tests check grounding with the *same* normalization: Gremlin exposes
CAPEC/CWE ids in URI-ish forms (``capec:attack-pattern:555``, ``cwe:89``)
while Neo4j and the question banks use the canonical ``CAPEC-555`` /
``CWE-89`` forms.
"""

from __future__ import annotations

import re

from utils.specialists.contracts import EvidenceRecord

_GREMLIN_CAPEC_RE = re.compile(r"^capec:attack-pattern:(\d+)$")
_GREMLIN_CWE_RE = re.compile(r"^cwe:(\d+)$")


def normalize_id(value: str) -> str:
    """Canonicalize backend id forms so comparisons are backend-agnostic."""
    value = (value or "").strip()
    m = _GREMLIN_CAPEC_RE.match(value)
    if m:
        return f"CAPEC-{m.group(1)}"
    m = _GREMLIN_CWE_RE.match(value)
    if m:
        return f"CWE-{m.group(1)}"
    return value


def id_pool(records: list[EvidenceRecord]) -> set[str]:
    """Every id a set of records exposes: primary ids, join values, related ids."""
    pool: set[str] = set()
    for r in records:
        if r.primary_id:
            pool.add(normalize_id(r.primary_id))
        for jv in r.join_values:
            pool.add(normalize_id(jv))
        for rel in r.related:
            for key in ("id", "entry_id"):
                v = rel.get(key)
                if v:
                    pool.add(normalize_id(str(v)))
    return pool
