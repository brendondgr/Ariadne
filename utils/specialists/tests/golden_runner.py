#!/usr/bin/env python3
"""Shared runner for the golden live tests.

Loads a committed question bank, runs each entry through the real specialist
against the live graph stack, and checks the entry's assertions. The runner
asserts *correctness of the answer*, not merely that the query ran — this is
the layer that measures the confident-but-wrong failure mode (the "97%
problem"): a syntactically clean query that answers the wrong question fails
the ID-set assertions here even though it raised no error anywhere.
"""

from __future__ import annotations

import re
from typing import Any

from utils.specialists.contracts import EvidenceRecord, SpecialistResult
from utils.specialists.evidence import check_contract

_GREMLIN_CAPEC_RE = re.compile(r"^capec:attack-pattern:(\d+)$")
_GREMLIN_CWE_RE = re.compile(r"^cwe:(\d+)$")


def normalize_id(value: str) -> str:
    """Canonicalize backend id forms so assertions are backend-agnostic."""
    value = (value or "").strip()
    m = _GREMLIN_CAPEC_RE.match(value)
    if m:
        return f"CAPEC-{m.group(1)}"
    m = _GREMLIN_CWE_RE.match(value)
    if m:
        return f"CWE-{m.group(1)}"
    return value


def id_pool(records: list[EvidenceRecord]) -> set[str]:
    """Every id a result exposes: primary ids, join values, related ids."""
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


def _prop_value(record: EvidenceRecord, key: str) -> Any:
    v = record.properties.get(key)
    if isinstance(v, list):  # Gremlin multi-cardinality wrapping
        return v[0] if v else None
    return v


def check_assertions(result: SpecialistResult, assertions: dict[str, Any]) -> list[str]:
    """Return every assertion violation (empty list = the answer is correct)."""
    problems: list[str] = []
    records = result.records

    if assertions.get("expect_empty"):
        if records:
            got = sorted(id_pool(records))[:10]
            problems.append(f"expected empty result, got {len(records)} records ({got})")
        if not result.ok:
            problems.append(f"expected ok=True on honest-empty, got error={result.error!r}")
        return problems

    if not result.ok:
        problems.append(f"result not ok: {result.error!r}")
        return problems

    n = len(records)
    if "min_records" in assertions and n < assertions["min_records"]:
        problems.append(f"expected >= {assertions['min_records']} records, got {n}")
    if "max_records" in assertions and n > assertions["max_records"]:
        problems.append(f"expected <= {assertions['max_records']} records, got {n}")

    pool = id_pool(records)
    primary = {normalize_id(r.primary_id) for r in records if r.primary_id}

    for want in assertions.get("must_include_ids", []):
        if normalize_id(want) not in primary:
            problems.append(f"missing primary id {want} (primary ids: {sorted(primary)[:10]})")
    for want in assertions.get("must_include_related", []):
        if normalize_id(want) not in pool:
            problems.append(f"missing related id {want}")
    for banned in assertions.get("forbid_ids", []):
        if normalize_id(banned) in pool:
            problems.append(f"forbidden id {banned} present")

    by_id = {normalize_id(r.primary_id): r for r in records if r.primary_id}
    for want_id, want_name in assertions.get("expect_names", {}).items():
        rec = by_id.get(normalize_id(want_id))
        if rec is None:
            problems.append(f"expect_names: no record for {want_id}")
        elif rec.name != want_name:
            problems.append(f"expect_names: {want_id} named {rec.name!r}, expected {want_name!r}")
    for want_id, props in assertions.get("expect_properties", {}).items():
        rec = by_id.get(normalize_id(want_id))
        if rec is None:
            problems.append(f"expect_properties: no record for {want_id}")
            continue
        for key, want_value in props.items():
            got = _prop_value(rec, key)
            if got != want_value:
                problems.append(
                    f"expect_properties: {want_id}.{key} = {got!r}, expected {want_value!r}"
                )

    problems.extend(check_contract(records))
    return problems


def check_traces(result: SpecialistResult, assertions: dict[str, Any]) -> list[str]:
    """Gate and execute must always pass; assess/normalize only for non-empties."""
    required = {"gate", "execute"} if assertions.get("expect_empty") else {
        "gate", "execute", "assess", "normalize",
    }
    problems = []
    for trace in result.traces:
        if trace.step in required and not trace.ok:
            problems.append(f"trace {trace.step} not ok: {trace.reasons}")
    return problems
