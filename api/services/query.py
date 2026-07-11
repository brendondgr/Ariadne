"""Stream the federated query pipeline as Server-Sent Events.

The pipeline composition lives in ``utils.specialists.pipeline`` — the single
orchestrator the CLI shares — and yields an event at each boundary:

    status(probing) → probe → status(planning) → plan
      → status(querying) → (specialist-start → specialist)*/skipped* → evidence
      → status(answering) → answer → done

This module only *presents* those events: each raw-object payload is shaped
into the JSON contract the web UI consumes. The pipeline emits *evidence, not
prose*; the ``answer`` event keeps the deterministic per-source sections and
join index the UI renders today, and additionally carries the synthesis
agent's verified answer under ``answer.synthesis`` plus the per-stage
``timings`` the pipeline recorded (plan, each specialist, synthesis, total).

The generator is synchronous on purpose: Starlette iterates a sync generator
via its threadpool, so the blocking graph queries never stall the event loop
(health polling and other requests stay responsive).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Iterator

from utils.orchestration.main import PipelineRun, iter_pipeline
from utils.planner.agent import PlanningAgent
from utils.specialists.config import SpecialistConfig
from utils.specialists.contracts import SpecialistResult
from utils.specialists.federation import FederatedEvidence

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


def render_pipeline_event(
    event: str, payload: dict[str, Any], run: PipelineRun
) -> tuple[str, dict[str, Any]] | None:
    """Shape one raw pipeline ``(event, payload)`` into the ``(name, json)`` UI contract.

    Shared by ``stream_query_events`` and the conversation service so both present
    the pipeline identically. Returns ``None`` for events with no UI rendering.
    """
    if event == "status":
        return "status", payload
    if event == "probe":
        return "probe", {"live_sources": _live_sources_payload(payload["live_view"])}
    if event == "plan":
        plan = payload["plan"]
        return "plan", {
            "plan": plan.to_dict(),
            "target_sources": sorted(plan.target_sources()),
        }
    if event == "skipped":
        return "skipped", payload
    if event == "specialist-start":
        return "specialist-start", payload
    if event == "specialist":
        return "specialist", {
            "result": payload["result"].to_dict(),
            "index": payload["index"],
            "total": payload["total"],
        }
    if event == "assess":
        # Sufficiency verdict for the iterative-retrieval loop (already a plain
        # JSON dict from the assess node). Lets the UI show the hop + whether
        # another retrieval pass is coming.
        return "assess", payload
    if event == "evidence":
        return "evidence", {"evidence": payload["evidence"].to_dict()}
    if event == "answer":
        plan, evidence = payload["plan"], payload["evidence"]
        status, exit_code = payload["status"], payload["exit_code"]
        if evidence is None:  # plan mode
            answer = _plan_answer(plan)
        else:
            join_index = evidence.join_index()
            cross = [
                {"value": value, "entries": join_index.get(value, [])}
                for value in evidence.cross_source_join_values()
            ]
            answer = {
                "headline": _headline(status, evidence, cross),
                "sections": _answer_sections(evidence.results),
                "cross_source": cross,
                "unsupported": list(evidence.unsupported),
                "synthesis": payload["synthesized"].to_dict(),
            }
        return "answer", {
            **answer,
            "status": status,
            "exit_code": exit_code,
            "timings": run.timings,
        }
    if event == "done":
        done: dict[str, Any] = {
            "status": payload["status"],
            "exit_code": payload["exit_code"],
            "timings": payload.get("timings", {}),
        }
        if payload.get("message"):
            done["message"] = payload["message"]
        return "done", done
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

        run = PipelineRun(question=question, mode=mode)
        for event, payload in iter_pipeline(
            question,
            mode=mode,
            use_llm=use_llm,
            data_dir=data_dir,
            agent=agent,
            specialists=specialists,
            specialist_config=specialist_config,
            run=run,
        ):
            rendered = render_pipeline_event(event, payload, run)
            if rendered is not None:
                yield _sse(*rendered)

    except Exception as exc:  # noqa: BLE001 - any pipeline failure becomes a clean error event
        logger.exception("query pipeline failed")
        yield _sse("error", {"message": f"{type(exc).__name__}: {exc}"})
