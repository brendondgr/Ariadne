"""Stream the federated query pipeline as Server-Sent Events.

The pipeline (``PlanningAgent.plan`` → specialists → ``FederatedEvidence``) is
synchronous and blocking, so this module reuses the exact composition
``utils.specialists.cli.run_query_command`` performs and yields a real event at
each boundary the pipeline exposes:

    status(probing) → probe → status(planning) → plan
      → status(querying) → specialist*/skipped* → evidence
      → status(answering) → answer → done

The per-specialist loop mirrors ``federation.SpecialistRouter.run_plan`` (using
the public ``build_specialist``) so each source's evidence can be emitted as it
completes, rather than only after the whole bundle is built. The pipeline emits
*evidence, not prose*; the ``answer`` event keeps the deterministic per-source
sections and join index the UI renders today, and additionally carries the
synthesis agent's verified answer under ``answer.synthesis`` — structured
claims-with-citations that passed the deterministic verification pass, enforced
abstentions ("the sources don't establish this") with the executed query as
proof, and the per-claim verdicts for anything that was cut.

The generator is synchronous on purpose: Starlette iterates a sync generator via
its threadpool, so the blocking graph queries never stall the event loop (health
polling and other requests stay responsive).
"""

from __future__ import annotations

import dataclasses
import json
import logging
from pathlib import Path
from typing import Any, Iterator

from utils.planner.agent import PlanningAgent
from utils.planner.config import PlannerConfig
from utils.specialists import build_specialist
from utils.specialists.config import SpecialistConfig
from utils.specialists.contracts import SpecialistResult, SpecialistTask
from utils.specialists.federation import (
    FederatedEvidence,
    bundle_evidence,
    dependency_map,
    dependency_skip_result,
    execution_order,
    harvest_seed_ids,
    status_and_exit,
)
from utils.synthesis.config import SynthesisConfig
from utils.synthesis.factory import synthesize

logger = logging.getLogger("ariadne.api.query")

# Fallback source→backend map when a result carries no records to read it from.
_SOURCE_BACKENDS = {"attack": "neo4j", "capec": "gremlin"}

# How many record ids to attach to an answer section as inline citations.
_MAX_CITATIONS = 8


def _sse(event: str, data: dict[str, Any]) -> str:
    """Format one Server-Sent Event frame."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _live_sources_payload(live_view: Any) -> list[dict[str, Any]]:
    payload = []
    for ds in sorted(live_view.sources):
        src = live_view.sources[ds]
        payload.append(
            {
                "dataset": src.dataset,
                "backend": src.backend,
                "endpoint": src.endpoint,
                "live": bool(src.live),
                "node_count": int(src.node_count),
                "observed_labels": list(src.observed_labels),
                "reason": src.reason,
            }
        )
    return payload


def _section_backend(result: SpecialistResult) -> str:
    for record in result.records:
        if record.provenance is not None:
            return record.provenance.backend
    return _SOURCE_BACKENDS.get(result.task.source, result.task.source)


def _answer_sections(results: list[SpecialistResult]) -> list[dict[str, Any]]:
    sections = []
    for result in results:
        record_ids = [r.primary_id for r in result.records if r.primary_id][:_MAX_CITATIONS]
        if result.summary:
            summary = result.summary
        elif result.error:
            summary = f"Specialist failed: {result.error}"
        elif result.ok:
            summary = "No matching records were found in this source."
        else:
            summary = "This source returned no usable evidence."
        sections.append(
            {
                "source": result.task.source,
                "backend": _section_backend(result),
                "ok": result.ok,
                "partial": result.partial,
                "summary": summary,
                "record_ids": record_ids,
                "record_count": len(result.records),
            }
        )
    return sections


def _headline(status: str, evidence: FederatedEvidence | None, cross: list[dict[str, Any]]) -> str:
    if status == "no_sources":
        return "No source cards are available — build them before querying."
    if evidence is None:  # plan-only mode
        return "Planning complete."
    record_total = sum(len(r.records) for r in evidence.results)
    source_total = len({r.task.source for r in evidence.results})
    parts = [
        f"Gathered {record_total} record(s) from {source_total} source(s)"
        if record_total
        else "No records were returned by the routed specialists",
    ]
    if cross:
        parts.append(f"{len(cross)} cross-source correlation(s) on shared identifiers")
    if evidence.unsupported:
        parts.append(f"{len(evidence.unsupported)} part(s) unsupported")
    return "; ".join(parts) + "."


def _plan_answer(plan: Any) -> dict[str, Any]:
    """A plan-mode answer: describe the routing rather than evidence."""
    sections = [
        {
            "source": sq.source,
            "backend": _SOURCE_BACKENDS.get(sq.source, sq.source),
            "ok": True,
            "partial": False,
            "summary": f"Routed to {sq.source}: {sq.text}",
            "record_ids": [],
            "record_count": 0,
        }
        for sq in plan.sub_questions
    ]
    return {
        "headline": (
            f"Routed to {sorted(plan.target_sources()) or '(none)'}; "
            f"{len(plan.sub_questions)} sub-question(s), {len(plan.unsupported)} unsupported."
        ),
        "sections": sections,
        "cross_source": [],
        "unsupported": [u.to_dict() for u in plan.unsupported],
    }


def _specialist_for(
    source: str,
    cards: dict[str, Any],
    config: SpecialistConfig,
    injected: dict[str, Any] | None,
) -> Any | None:
    if injected and source in injected:
        return injected[source]
    card = cards.get(source)
    if card is None:
        return None
    try:
        return build_specialist(source, card, config)
    except ValueError:
        return None


def stream_query_events(
    question: str,
    *,
    mode: str = "query",
    use_llm: bool = False,
    data_dir: str | None = None,
    agent: PlanningAgent | None = None,
    specialists: dict[str, Any] | None = None,
    specialist_config: SpecialistConfig | None = None,
) -> Iterator[str]:
    """Yield SSE frames for one analyst question.

    ``agent``/``specialists``/``specialist_config`` are injectable for testing;
    in production they are built fresh per request so live config edits apply.
    """
    try:
        question = (question or "").strip()
        if not question:
            yield _sse("error", {"message": "Question must not be empty."})
            return

        if agent is None:
            overrides: dict[str, object] = {"llm_enabled": use_llm}
            if data_dir is not None:
                overrides["data_dir"] = Path(data_dir)
            planner_config = dataclasses.replace(PlannerConfig.from_env(), **overrides)
            agent = PlanningAgent(planner_config)

        # No source cards → nothing can be answered (CLI exit 2).
        if not agent.cards:
            yield _sse("status", {"phase": "probing", "message": "Checking source cards"})
            yield _sse(
                "done",
                {
                    "status": "no_sources",
                    "exit_code": 2,
                    "message": "No source cards found. Build them with: uv run main.py --build all",
                },
            )
            return

        # 1. Probe live sources (real content probe: node counts + labels).
        yield _sse("status", {"phase": "probing", "message": "Probing live graph backends"})
        live_view = agent.live_sources()
        yield _sse("probe", {"live_sources": _live_sources_payload(live_view)})

        # 2. Plan (re-probe hits the short-TTL cache from step 1).
        yield _sse("status", {"phase": "planning", "message": "Planning and routing the question"})
        plan = agent.plan(question)
        yield _sse(
            "plan",
            {"plan": plan.to_dict(), "target_sources": sorted(plan.target_sources())},
        )

        if mode == "plan":
            status, exit_code = status_and_exit(cards_present=True, mode="plan", plan=plan)
            answer = _plan_answer(plan)
            yield _sse("status", {"phase": "answering", "message": "Composing plan summary"})
            yield _sse("answer", {**answer, "status": status, "exit_code": exit_code})
            yield _sse("done", {"status": status, "exit_code": exit_code})
            return

        # 3. Run each routed specialist, emitting evidence as it completes.
        if specialist_config is None:
            specialist_config = dataclasses.replace(
                SpecialistConfig.from_env(data_dir=data_dir), llm_enabled=use_llm
            )
        yield _sse(
            "status",
            {
                "phase": "querying",
                "message": "Querying source specialists",
                "count": len(plan.sub_questions),
            },
        )

        # Mirrors federation.SpecialistRouter.run_plan: declared-join consumers
        # run after their producer, seeded with its harvested join values.
        results: list[SpecialistResult] = []
        skipped: list[dict[str, Any]] = []
        sequencing: list[dict[str, Any]] = []
        deps = dependency_map(plan)
        by_id: dict[str, SpecialistResult] = {}
        total = len(plan.sub_questions)
        for index, sq in enumerate(execution_order(plan)):
            specialist = _specialist_for(sq.source, agent.cards, specialist_config, specialists)
            if specialist is None:
                skip = {
                    "sub_question": sq.id,
                    "source": sq.source,
                    "reason": f"no specialist available for source {sq.source!r}",
                }
                skipped.append(skip)
                yield _sse("skipped", skip)
                continue

            seed_ids: tuple[str, ...] = ()
            producer_id = deps.get(sq.id)
            if producer_id:
                producer = by_id.get(producer_id)
                if producer is None or not producer.ok:
                    reason = (
                        "it was not run" if producer is None
                        else f"it failed ({producer.error or 'no valid evidence'})"
                    )
                    result = dependency_skip_result(
                        SpecialistTask.from_sub_question(sq),
                        producer_id=producer_id, reason=reason,
                    )
                    results.append(result)
                    by_id[sq.id] = result
                    sequencing.append(
                        {"consumer": sq.id, "producer": producer_id,
                         "seed_count": 0, "truncated": False, "skipped": reason}
                    )
                    yield _sse(
                        "specialist",
                        {"result": result.to_dict(), "index": index, "total": total},
                    )
                    continue
                seed_ids, truncated = harvest_seed_ids(
                    producer, cap=sq.limits.max_result_rows
                )
                if not seed_ids:
                    reason = "it returned no join values"
                    result = dependency_skip_result(
                        SpecialistTask.from_sub_question(sq),
                        producer_id=producer_id, reason=reason,
                    )
                    results.append(result)
                    by_id[sq.id] = result
                    sequencing.append(
                        {"consumer": sq.id, "producer": producer_id,
                         "seed_count": 0, "truncated": False, "skipped": reason}
                    )
                    yield _sse(
                        "specialist",
                        {"result": result.to_dict(), "index": index, "total": total},
                    )
                    continue
                sequencing.append(
                    {"consumer": sq.id, "producer": producer_id,
                     "seed_count": len(seed_ids), "truncated": truncated, "skipped": None}
                )

            result = specialist.run(SpecialistTask.from_sub_question(sq, seed_ids=seed_ids))
            results.append(result)
            by_id[sq.id] = result
            yield _sse(
                "specialist",
                {"result": result.to_dict(), "index": index, "total": total},
            )

        # 4. Bundle through the one shared rule (same code the router and CLI use).
        evidence = bundle_evidence(plan, results, skipped, sequencing)
        yield _sse("evidence", {"evidence": evidence.to_dict()})

        # 5. Compose the grounded answer, then run the synthesis agent's
        # claim-by-claim verification pass over the same evidence.
        status, exit_code = status_and_exit(cards_present=True, evidence=evidence)
        join_index = evidence.join_index()
        cross = [
            {"value": value, "entries": join_index.get(value, [])}
            for value in evidence.cross_source_join_values()
        ]
        yield _sse(
            "status",
            {"phase": "answering", "message": "Composing and verifying the grounded answer"},
        )
        synthesized = synthesize(evidence, SynthesisConfig.from_env())
        answer = {
            "headline": _headline(status, evidence, cross),
            "sections": _answer_sections(results),
            "cross_source": cross,
            "unsupported": list(evidence.unsupported),
            "synthesis": synthesized.to_dict(),
            "status": status,
            "exit_code": exit_code,
        }
        yield _sse("answer", answer)
        yield _sse("done", {"status": status, "exit_code": exit_code})

    except Exception as exc:  # noqa: BLE001 - any pipeline failure becomes a clean error event
        logger.exception("query pipeline failed")
        yield _sse("error", {"message": f"{type(exc).__name__}: {exc}"})
