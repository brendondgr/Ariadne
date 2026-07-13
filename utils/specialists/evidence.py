#!/usr/bin/env python3
"""Shared evidence emitter + the deterministic contract check.

This is one of the briefing's two non-negotiable gates (§4.2): the
normalize/contract check keeps malformed evidence out of synthesis. It is pure
deterministic Python — no LLM — so it is fast and reliable. Both specialists
build records through ``emit_record`` and are graded by ``check_contract`` before
their result ships.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .contracts import EvidenceRecord, Provenance, SpecialistResult

# Provenance fields that must be present and non-empty on every record.
_REQUIRED_PROVENANCE = ("source", "dataset", "backend", "query", "record_id", "timestamp")


def now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string (provenance timestamp)."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def make_provenance(
    *,
    card: Any,
    query: str,
    record_id: str,
    timestamp: str | None = None,
) -> Provenance:
    """Build a ``Provenance`` from a source card view + the executed query."""
    provenance = card.provenance or {}
    return Provenance(
        source=str(provenance.get("source_name") or card.dataset),
        dataset=str(card.dataset),
        backend=str(card.runtime_backend),
        query=query,
        record_id=str(record_id),
        timestamp=timestamp or now_iso(),
    )


def emit_record(
    *,
    card: Any,
    query: str,
    record_id: str,
    primary_id: str,
    id_scheme: str,
    label: str,
    name: str,
    properties: dict[str, Any] | None = None,
    related: list[dict[str, Any]] | None = None,
    join_values: tuple[str, ...] = (),
    facets: list[dict[str, Any]] | None = None,
    timestamp: str | None = None,
) -> EvidenceRecord:
    """Construct an ``EvidenceRecord`` with provenance attached."""
    return EvidenceRecord(
        primary_id=primary_id,
        id_scheme=id_scheme,
        label=label,
        name=name,
        properties=dict(properties or {}),
        related=list(related or []),
        join_values=tuple(join_values),
        facets=list(facets or []),
        provenance=make_provenance(
            card=card, query=query, record_id=record_id, timestamp=timestamp
        ),
    )


def check_record(record: EvidenceRecord) -> list[str]:
    """Return the contract violations for one record (empty list = conforms)."""
    problems: list[str] = []
    if not record.primary_id and not record.name:
        problems.append("record has neither a primary_id nor a name")
    if not record.id_scheme:
        problems.append(f"record {record.primary_id or record.name!r} missing id_scheme")
    if not record.label:
        problems.append(f"record {record.primary_id or record.name!r} missing label")
    prov = record.provenance
    if prov is None:
        problems.append(f"record {record.primary_id or record.name!r} missing provenance")
        return problems
    prov_dict = prov.to_dict()
    for key in _REQUIRED_PROVENANCE:
        if not prov_dict.get(key):
            problems.append(
                f"record {record.primary_id or record.name!r} provenance missing {key!r}"
            )
    return problems


def check_contract(records: list[EvidenceRecord]) -> list[str]:
    """Return every contract violation across the records (empty = all conform)."""
    problems: list[str] = []
    for record in records:
        problems.extend(check_record(record))
    return problems


def result_conforms(result: SpecialistResult) -> bool:
    """True when every record in a result satisfies the evidence contract."""
    return not check_contract(result.records)
