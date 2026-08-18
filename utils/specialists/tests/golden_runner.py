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

from typing import Any

from utils.specialists.contracts import EvidenceRecord
from utils.specialists.contracts import SpecialistResult
from utils.specialists.evidence import check_contract

# Shared with the synthesis verifier so both layers ground ids identically.
from utils.synthesis.grounding import id_pool, normalize_id

__all__ = ["normalize_id", "id_pool", "check_assertions", "check_traces"]


def _prop_value(record: EvidenceRecord, key: str) -> Any:
    v = record.properties.get(key)
    if isinstance(v, list):  # Gremlin multi-cardinality wrapping
        return v[0] if v else None
    return v


def check_assertions(result: SpecialistResult, assertions: dict[str, Any]) -> list[str]:
    """Return every assertion violation (empty list = the answer is correct)."""
    problems: list[str] = []
    records = result.records

    if assertions.get("expect_boundary"):
        # Schema-boundary refusal: honest empty with NO query executed —
        # the source doesn't model the asked-about entity at all.
        if records:
            got = sorted(id_pool(records))[:10]
            problems.append(f"expected boundary refusal, got {len(records)} records ({got})")
        if not result.ok:
            problems.append(f"expected ok=True on boundary refusal, got error={result.error!r}")
        if result.query:
            problems.append(f"expected no executed query, got {result.query!r}")
        if "doesn't model" not in result.summary:
            problems.append(f"summary does not name the boundary: {result.summary!r}")
        return problems

    if assertions.get("expect_no_join"):
        # The outer-join contract (D-0NN, 2026-08-18): a cross-source question
        # whose anchor maps to nothing returns the *anchor*, with an empty join.
        # Records are expected; join values are not. The record is what lets the
        # answer say "this pattern maps to nothing" and cite what it read.
        if not result.ok:
            problems.append(f"expected ok=True on empty-join, got error={result.error!r}")
        if not records:
            problems.append("expected the anchor record, got no records at all")
        joined = sorted({
            value for record in records for value in (record.join_values or ())
        })
        if joined:
            problems.append(f"expected no join values, got {joined[:10]}")
        return problems

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
    steps = [t.step for t in result.traces]
    if assertions.get("expect_boundary"):
        # A boundary refusal must stop before the gate: no query drafted,
        # gated, or executed — the refusal is the answer.
        problems = []
        if "boundary" not in steps:
            problems.append(f"no boundary trace recorded (steps: {steps})")
        for banned in ("gate", "execute"):
            if banned in steps:
                problems.append(f"boundary refusal must not reach {banned!r} (steps: {steps})")
        return problems

    required = {"gate", "execute"} if assertions.get("expect_empty") else {
        "gate", "execute", "assess", "normalize",
    }
    if assertions.get("expect_no_join"):
        # Records exist, so normalization ran and must be clean.
        required = {"gate", "execute", "assess", "normalize"}
    problems = []
    for trace in result.traces:
        if trace.step in required and not trace.ok:
            problems.append(f"trace {trace.step} not ok: {trace.reasons}")
    return problems
