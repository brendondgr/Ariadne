#!/usr/bin/env python3
"""In-memory evidence fixtures for hermetic synthesis tests.

Builds real ``EvidenceRecord`` / ``SpecialistResult`` / ``FederatedEvidence``
objects (no stub classes, no database) so the composer and verifier are tested
against the exact contracts the live pipeline produces.
"""

from __future__ import annotations

from typing import Any

from utils.specialists.contracts import (
    EvidenceRecord,
    Provenance,
    SpecialistResult,
    SpecialistTask,
)
from utils.specialists.federation import FederatedEvidence


def make_record(
    primary_id: str,
    *,
    name: str = "",
    source: str = "attack",
    backend: str = "neo4j",
    label: str = "Technique",
    join_values: tuple[str, ...] | None = None,
    related: list[dict[str, Any]] | None = None,
    properties: dict[str, Any] | None = None,
    facets: list[dict[str, Any]] | None = None,
    query: str = "MATCH (t:Technique) RETURN t",
    record_id: str = "",
) -> EvidenceRecord:
    return EvidenceRecord(
        primary_id=primary_id,
        id_scheme="attack-id" if source == "attack" else "capec-id",
        label=label,
        name=name or primary_id,
        properties=dict(properties or {}),
        related=list(related or []),
        facets=list(facets or []),
        join_values=join_values if join_values is not None else (primary_id,),
        provenance=Provenance(
            source=source,
            dataset=source,
            backend=backend,
            query=query,
            record_id=record_id or f"{source}:{primary_id}",
            timestamp="2026-07-04T00:00:00Z",
        ),
    )


def make_result(
    *,
    source: str = "attack",
    sub_question_id: str = "q1",
    text: str = "what mitigations apply?",
    entities: tuple[str, ...] = (),
    records: list[EvidenceRecord] | None = None,
    query: str = "MATCH (t:Technique) RETURN t",
    summary: str = "",
    ok: bool = True,
    partial: bool = False,
    error: str | None = None,
) -> SpecialistResult:
    task = SpecialistTask(
        sub_question_id=sub_question_id,
        source=source,
        text=text,
        entities=entities,
        limits={"max_traversal_depth": 3, "max_result_rows": 300, "query_timeout_ms": 5000},
    )
    return SpecialistResult(
        task=task,
        query=query,
        records=list(records or []),
        summary=summary,
        ok=ok,
        partial=partial,
        error=error,
    )


def make_evidence(
    results: list[SpecialistResult],
    *,
    request: str = "test question",
    unsupported: list[dict[str, Any]] | None = None,
    skipped: list[dict[str, Any]] | None = None,
    partial: bool = False,
) -> FederatedEvidence:
    return FederatedEvidence(
        request=request,
        results=results,
        unsupported=list(unsupported or []),
        skipped=list(skipped or []),
        partial=partial,
    )
