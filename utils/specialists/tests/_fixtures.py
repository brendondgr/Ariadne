#!/usr/bin/env python3
"""Shared test helpers for the specialist suite.

Loads the small committed fixture source cards (a subset of the real ATT&CK and
CAPEC cards) and provides simple fake swap points so the shared scaffold loop can
be exercised without a live database.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from utils.planner.cards import SourceCardView, load_source_cards

from utils.specialists.contracts import EvidenceRecord, SpecialistTask
from utils.specialists.evidence import emit_record
from utils.specialists.resolve import ResolvedTask
from utils.specialists.validation import BaseValidator, QueryDraft

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture_cards() -> dict[str, SourceCardView]:
    return load_source_cards(FIXTURES_DIR)


def fixture_card(dataset: str) -> SourceCardView:
    return load_fixture_cards()[dataset]


def live_stack_enabled() -> bool:
    """True when live integration tests against the Docker stack should run."""
    return os.environ.get("ARIADNE_LIVE_TESTS", "").strip().lower() in {"1", "true", "yes", "on"}


# -- fakes for exercising the scaffold loop ---------------------------------


class StubValidator(BaseValidator):
    """Accepts anything; echoes the draft query. Used to test the loop."""

    kind = "stub"

    def __init__(self, *, reject: list[str] | None = None) -> None:
        # Optional canned rejection reasons to force the gate to fail.
        self._reject = reject or []

    def structural_reasons(self, query: str) -> list[str]:
        return list(self._reject)

    def violates_read_only(self, query: str, card: Any) -> list[str]:
        return []

    def schema_reasons(self, query: str, card: Any) -> list[str]:
        return []

    def inject_caps(self, query: str, limits: dict[str, int], card: Any) -> tuple[str, list[str]]:
        return query, []


class StubBuilder:
    def __init__(self, query: str = "MATCH (n) RETURN n", template: str = "stub") -> None:
        self._query = query
        self._template = template
        self.feedback_seen: list[list[str] | None] = []

    def build(self, resolved: ResolvedTask, feedback: list[str] | None = None) -> QueryDraft:
        self.feedback_seen.append(feedback)
        return QueryDraft(query=self._query, params={}, template=self._template)


class StubConnector:
    def __init__(self, rows: list[dict[str, Any]] | None = None, raise_on_run: Exception | None = None) -> None:
        self._rows = rows if rows is not None else [{"id": "x", "attack_id": "T1047", "name": "WMI"}]
        self._raise = raise_on_run
        self.connected = False
        self.closed = False
        self.run_count = 0

    def connect(self) -> None:
        self.connected = True

    def close(self) -> None:
        self.closed = True

    def run(self, query: str, params: dict[str, Any], limits: dict[str, int]) -> list[dict[str, Any]]:
        self.run_count += 1
        if self._raise is not None:
            raise self._raise
        return list(self._rows)


class StubNormalizer:
    def __init__(self, card: Any) -> None:
        self._card = card

    def normalize(
        self, rows: list[dict[str, Any]], resolved: ResolvedTask, query: str, card: Any
    ) -> list[EvidenceRecord]:
        out: list[EvidenceRecord] = []
        for row in rows:
            aid = str(row.get("attack_id", "") or row.get("id", ""))
            out.append(
                emit_record(
                    card=card,
                    query=query,
                    record_id=str(row.get("id", aid)),
                    primary_id=aid,
                    id_scheme="attack-id",
                    label="Technique",
                    name=str(row.get("name", "")),
                    join_values=(aid,) if aid.startswith("T") else (),
                )
            )
        return out

    def summarize(self, records: list[EvidenceRecord], resolved: ResolvedTask) -> str:
        return f"{len(records)} record(s)"


def make_task(**overrides: Any) -> SpecialistTask:
    base = dict(
        sub_question_id="q1",
        source="attack",
        text="What mitigations apply to T1047?",
        entities=("Technique", "Mitigation"),
        limits={"max_traversal_depth": 3, "max_result_rows": 1000, "query_timeout_ms": 5000},
        join_key=None,
        seed_ids=(),
    )
    base.update(overrides)
    return SpecialistTask(**base)  # type: ignore[arg-type]
