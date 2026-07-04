#!/usr/bin/env python3
"""The shared specialist scaffold — the ReAct-style internal loop (briefing §3).

Both specialists inherit this loop unchanged and inject four language-specific
swap points (builder, validator, connector, normalizer) plus the source card.
The loop runs the briefing's reference flow:

    intake → resolve → draft → pre-run gate → execute → assess → normalize → handoff

with two distinct checkpoints — the **pre-run gate** (cheap static check before
spending a DB call) and the post-execution **assess + contract** check — and a
**capped** redraft loop so a failing draft can't loop forever. The model (or the
deterministic builder) drafts; deterministic code grades.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from .contracts import EvidenceRecord, EvaluatorTrace, SpecialistResult, SpecialistTask
from .errors import SpecialistError
from .evidence import check_contract
from .resolve import ResolvedTask, resolve
from .validation import BaseValidator, QueryDraft

logger = logging.getLogger("ariadne.specialists")

_TECHNIQUE_ID_RE = re.compile(r"^T\d{4}(?:\.\d{3})?$")


# -- swap-point protocols ---------------------------------------------------


class QueryBuilder(Protocol):
    """Drafts a bounded query from a resolved task (the 'query prompt' swap)."""

    def build(
        self, resolved: ResolvedTask, feedback: list[str] | None = None
    ) -> QueryDraft: ...


class Connector(Protocol):
    """Bounded, read-only execution against one backend (the 'connector' swap)."""

    def connect(self) -> None: ...
    def close(self) -> None: ...
    def run(
        self, query: str, params: dict[str, Any], limits: dict[str, int]
    ) -> list[dict[str, Any]]: ...


class Normalizer(Protocol):
    """Shapes raw results into evidence records (the 'normalizer' swap)."""

    def normalize(
        self, rows: list[dict[str, Any]], resolved: ResolvedTask, query: str, card: Any
    ) -> list[EvidenceRecord]: ...

    def summarize(
        self, records: list[EvidenceRecord], resolved: ResolvedTask
    ) -> str: ...


# -- shared assessment (deterministic) --------------------------------------


@dataclass(frozen=True)
class Assessment:
    """Verdict of the post-execution self-evaluation (briefing §3 step 6)."""

    ok: bool
    partial: bool
    reasons: list[str] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)


def assess_rows(rows: list[dict[str, Any]], resolved: ResolvedTask) -> Assessment:
    """Deterministically judge raw results: shape, emptiness, plausibility.

    Empty is a *valid* answer ("none found"), so it never fails the run — only
    a wrong shape does. Join-key integrity is checked after normalisation, on the
    records' ``join_values`` (the synthesis spine, §4.1).
    """
    reasons: list[str] = []
    if not isinstance(rows, list):
        return Assessment(False, True, ["result is not a list of rows"], {"row_count": 0})
    non_mappings = [r for r in rows if not isinstance(r, dict)]
    if non_mappings:
        reasons.append(f"{len(non_mappings)} result row(s) are not key/value mappings")
    detail = {"row_count": len(rows)}
    if not rows and resolved.seed_ids:
        detail["empty_with_seeds"] = list(resolved.seed_ids)
    return Assessment(ok=not reasons, partial=bool(reasons), reasons=reasons, detail=detail)


def join_integrity_problems(
    records: list[EvidenceRecord], resolved: ResolvedTask
) -> list[str]:
    """For an ATT&CK-technique-id join, every join value must be a real T-number."""
    if resolved.join_key != "attack-technique-id":
        return []
    problems: list[str] = []
    for rec in records:
        for value in rec.join_values:
            if not _TECHNIQUE_ID_RE.match(value):
                problems.append(
                    f"record {rec.primary_id or rec.name!r} has malformed join value {value!r}"
                )
    return problems


# -- the specialist scaffold ------------------------------------------------


class QuerySpecialist:
    """Runs the shared draft→gate→execute→assess→normalize loop for one source."""

    def __init__(
        self,
        *,
        card: Any,
        builder: QueryBuilder,
        validator: BaseValidator,
        connector: Connector,
        normalizer: Normalizer,
        max_retries: int = 2,
    ) -> None:
        self.card = card
        self.builder = builder
        self.validator = validator
        self.connector = connector
        self.normalizer = normalizer
        self.max_retries = max(0, int(max_retries))

    # -- public entry point -------------------------------------------------

    def run(self, task: SpecialistTask) -> SpecialistResult:
        """Resolve, draft, gate, execute, assess, and normalise one task.

        Always returns a ``SpecialistResult`` — failures are reported in the
        result (with traces), never raised, so a federation caller can keep going.
        """
        traces: list[EvaluatorTrace] = []

        intake_problem = self._intake(task)
        traces.append(
            EvaluatorTrace(
                "intake",
                ok=intake_problem is None,
                reasons=[] if intake_problem is None else [intake_problem],
                detail={"source": task.source, "card": self.card.dataset},
            )
        )
        if intake_problem is not None:
            return SpecialistResult(
                task=task, traces=traces, ok=False, partial=True, error=intake_problem
            )

        resolved = resolve(task, self.card)
        resolve_reasons = (
            [f"entities not in card: {list(resolved.unknown_entities)}"]
            if resolved.unknown_entities
            else []
        )
        traces.append(
            EvaluatorTrace(
                "resolve",
                ok=True,
                reasons=resolve_reasons,
                detail={
                    "labels": list(resolved.labels),
                    "relationships": list(resolved.relationships),
                    "seed_ids": list(resolved.seed_ids),
                    "join_key": resolved.join_key,
                },
            )
        )

        # Schema-boundary refusal: an entity the card doesn't model means no
        # query can express the question as asked. Answering with whatever the
        # known entities *can* express would be answering a different question
        # — the wrong-but-plausible failure. Return an honest empty instead:
        # ok, zero records, no query executed, the boundary named in the trace.
        if resolved.unknown_entities:
            unknown = ", ".join(resolved.unknown_entities)
            traces.append(
                EvaluatorTrace(
                    "boundary",
                    ok=True,
                    reasons=[
                        f"entities not modeled by the {self.card.dataset} source: {unknown}"
                    ],
                    detail={"unknown_entities": list(resolved.unknown_entities)},
                )
            )
            return SpecialistResult(
                task=task,
                query="",
                records=[],
                summary=(
                    f"The {self.card.dataset} source doesn't model {unknown} — "
                    f"no query can express this question against its schema."
                ),
                traces=traces,
                ok=True,
                partial=False,
                error=None,
            )

        limits = self._effective_limits(task)
        return self._loop(task, resolved, limits, traces)

    # -- internals ----------------------------------------------------------

    def _intake(self, task: SpecialistTask) -> str | None:
        if not task.sub_question_id:
            return "task is missing a sub_question_id"
        if task.source != self.card.dataset:
            return (
                f"task targets source {task.source!r} but this specialist serves "
                f"{self.card.dataset!r}"
            )
        return None

    def _effective_limits(self, task: SpecialistTask) -> dict[str, int]:
        return {
            "max_traversal_depth": task.max_depth(),
            "max_result_rows": task.max_rows(),
            "query_timeout_ms": task.timeout_ms(),
        }

    def _loop(
        self,
        task: SpecialistTask,
        resolved: ResolvedTask,
        limits: dict[str, int],
        traces: list[EvaluatorTrace],
    ) -> SpecialistResult:
        feedback: list[str] | None = None
        last_reasons: list[str] = []
        connected = False
        try:
            for attempt in range(1, self.max_retries + 2):
                draft = self.builder.build(resolved, feedback)
                result = self.validator.validate(draft, self.card, limits)
                traces.append(
                    EvaluatorTrace(
                        "gate",
                        ok=result.ok,
                        reasons=list(result.reasons),
                        detail={
                            "attempt": attempt,
                            "template": draft.template,
                            "query": result.query,
                            "injected": list(result.injected),
                        },
                    )
                )
                if not result.ok:
                    feedback = result.reasons
                    last_reasons = result.reasons
                    continue

                if not connected:
                    self.connector.connect()
                    connected = True

                started = time.perf_counter()
                try:
                    rows = self.connector.run(result.query, result.params, limits)
                except SpecialistError as exc:
                    traces.append(
                        EvaluatorTrace("execute", ok=False, reasons=[str(exc)], detail={})
                    )
                    return SpecialistResult(
                        task=task, query=result.query, traces=traces,
                        ok=False, partial=True, error=str(exc),
                    )
                elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
                traces.append(
                    EvaluatorTrace(
                        "execute", ok=True, reasons=[],
                        detail={"row_count": len(rows), "timing_ms": elapsed_ms},
                    )
                )

                assessment = assess_rows(rows, resolved)
                traces.append(
                    EvaluatorTrace(
                        "assess", ok=assessment.ok, reasons=list(assessment.reasons),
                        detail=assessment.detail,
                    )
                )

                records = self.normalizer.normalize(rows, resolved, result.query, self.card)
                contract = check_contract(records)
                join_problems = join_integrity_problems(records, resolved)
                traces.append(
                    EvaluatorTrace(
                        "normalize",
                        ok=not contract and not join_problems,
                        reasons=[*contract, *join_problems],
                        detail={"record_count": len(records)},
                    )
                )
                summary = self.normalizer.summarize(records, resolved)
                ok = not contract
                partial = bool(join_problems) or assessment.partial
                return SpecialistResult(
                    task=task,
                    query=result.query,
                    records=records,
                    summary=summary,
                    traces=traces,
                    ok=ok,
                    partial=partial,
                    error="; ".join(contract) if contract else None,
                )

            # Every draft was rejected by the gate within the retry budget.
            error = "pre-run gate rejected all drafts: " + "; ".join(last_reasons)
            return SpecialistResult(
                task=task, traces=traces, ok=False, partial=True, error=error
            )
        finally:
            if connected:
                try:
                    self.connector.close()
                except Exception:  # noqa: BLE001 - close failures must not mask the result
                    logger.debug("connector close failed", exc_info=True)
