#!/usr/bin/env python3
"""The single pipeline orchestrator (Wk 10–11 integration).

Both entry points — the CLI (``utils/specialists/cli.py``) and the API
(``api/services/query.py``) — previously re-implemented
plan → specialists → bundle → synthesize and could drift. This module is now
the only place that composition lives:

    probe → plan → [sequenced specialists] → bundle → synthesize → done

``iter_pipeline`` is a synchronous generator yielding ``(event, payload)``
tuples at every boundary, with *raw objects* in the payloads — presentation
(printing, SSE JSON) stays with the caller. ``run_pipeline`` drains it and
returns a ``PipelineRun`` for callers that only want the outcome.

Per-stage wall-clock timings (plan, each specialist, synthesis, total) are
recorded on the run and in the ``done`` payload so the Wk 11–13 evaluation can
read latency without re-instrumenting. A total-pipeline deadline
(``PIPELINE_TIMEOUT_S``, default 120 s) bounds multi-hop runs: specialists that
would start after the deadline are skipped honestly, never half-run.
"""

from __future__ import annotations

import dataclasses
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from utils.planner.agent import PlanningAgent
from utils.planner.config import PlannerConfig
from utils.planner.schema import Plan
from utils.synthesis.config import SynthesisConfig
from utils.synthesis.contracts import SynthesizedAnswer
from utils.synthesis.factory import synthesize

from . import build_specialist
from .config import SpecialistConfig
from .contracts import SpecialistResult, SpecialistTask
from .federation import (
    FederatedEvidence,
    bundle_evidence,
    dependency_map,
    dependency_skip_result,
    execution_order,
    harvest_seed_ids,
    status_and_exit,
)

DEFAULT_PIPELINE_TIMEOUT_S = 120.0


def pipeline_timeout_s() -> float:
    """Total-pipeline deadline from the environment (seconds)."""
    raw = os.environ.get("PIPELINE_TIMEOUT_S", "")
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_PIPELINE_TIMEOUT_S
    return value if value > 0 else DEFAULT_PIPELINE_TIMEOUT_S


@dataclass
class PipelineRun:
    """Everything one pipeline execution produced, plus per-stage timings."""

    question: str
    mode: str = "query"
    plan: Plan | None = None
    evidence: FederatedEvidence | None = None
    answer: SynthesizedAnswer | None = None
    status: str = "no_sources"
    exit_code: int = 2
    timings: dict[str, Any] = field(default_factory=dict)
    live_view: Any = None


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


def iter_pipeline(
    question: str,
    *,
    mode: str = "query",
    use_llm: bool = False,
    data_dir: str | None = None,
    agent: PlanningAgent | None = None,
    specialists: dict[str, Any] | None = None,
    specialist_config: SpecialistConfig | None = None,
    synthesis_config: SynthesisConfig | None = None,
    timeout_s: float | None = None,
    run: PipelineRun | None = None,
) -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield ``(event, payload)`` at each pipeline boundary; payloads carry raw objects.

    Event order matches the streaming contract the web UI consumes:
    status(probing) → probe → status(planning) → plan → status(querying)
    → (specialist-start → specialist)*/skipped* → evidence
    → status(answering) → answer → done. ``specialist-start`` fires the moment
    a specialist is about to run (with its seeding info), so a UI can animate
    "now querying <source>" truthfully.
    Pass ``run`` to have the outcome recorded on a caller-owned ``PipelineRun``.
    """
    run = run if run is not None else PipelineRun(question=question, mode=mode)
    run.question, run.mode = question, mode
    deadline = time.monotonic() + (timeout_s if timeout_s is not None else pipeline_timeout_s())
    t_start = time.monotonic()

    if agent is None:
        overrides: dict[str, object] = {"llm_enabled": use_llm}
        if data_dir is not None:
            overrides["data_dir"] = Path(data_dir)
        agent = PlanningAgent(dataclasses.replace(PlannerConfig.from_env(), **overrides))

    if not agent.cards:
        run.status, run.exit_code = status_and_exit(cards_present=False)
        yield ("status", {"phase": "probing", "message": "Checking source cards"})
        yield (
            "done",
            {
                "status": run.status,
                "exit_code": run.exit_code,
                "timings": run.timings,
                "message": "No source cards found. Build them with: uv run main.py --build all",
            },
        )
        return

    # 1. Probe live sources (content probe: node counts + labels).
    yield ("status", {"phase": "probing", "message": "Probing live graph backends"})
    run.live_view = agent.live_sources()
    yield ("probe", {"live_view": run.live_view})

    # 2. Plan (re-probe hits the short-TTL cache from step 1).
    yield ("status", {"phase": "planning", "message": "Planning and routing the question"})
    t0 = time.monotonic()
    plan = agent.plan(question)
    run.timings["plan_ms"] = round((time.monotonic() - t0) * 1000, 3)
    run.plan = plan
    yield ("plan", {"plan": plan})

    if mode == "plan":
        run.status, run.exit_code = status_and_exit(cards_present=True, mode="plan", plan=plan)
        run.timings["total_ms"] = round((time.monotonic() - t_start) * 1000, 3)
        yield ("status", {"phase": "answering", "message": "Composing plan summary"})
        yield ("answer", {"plan": plan, "evidence": None, "synthesized": None,
                          "status": run.status, "exit_code": run.exit_code})
        yield ("done", {"status": run.status, "exit_code": run.exit_code,
                        "timings": run.timings})
        return

    # 3. Run each routed specialist in dependency order, seeding declared-join
    # consumers from their producer's harvested join values.
    if specialist_config is None:
        specialist_config = dataclasses.replace(
            SpecialistConfig.from_env(data_dir=data_dir), llm_enabled=use_llm
        )
    yield ("status", {"phase": "querying", "message": "Querying source specialists",
                      "count": len(plan.sub_questions)})

    results: list[SpecialistResult] = []
    skipped: list[dict[str, Any]] = []
    sequencing: list[dict[str, Any]] = []
    specialist_timings: list[dict[str, Any]] = []
    deps = dependency_map(plan)
    by_id: dict[str, SpecialistResult] = {}
    total = len(plan.sub_questions)

    for index, sq in enumerate(execution_order(plan)):
        specialist = _specialist_for(sq.source, agent.cards, specialist_config, specialists)
        if specialist is None:
            skip = {"sub_question": sq.id, "source": sq.source,
                    "reason": f"no specialist available for source {sq.source!r}"}
            skipped.append(skip)
            yield ("skipped", skip)
            continue

        if time.monotonic() > deadline:
            skip = {"sub_question": sq.id, "source": sq.source,
                    "reason": "total pipeline timeout exceeded before this sub-question ran"}
            skipped.append(skip)
            yield ("skipped", skip)
            continue

        seed_ids: tuple[str, ...] = ()
        producer_id = deps.get(sq.id)
        if producer_id:
            producer = by_id.get(producer_id)
            reason: str | None = None
            if producer is None or not producer.ok:
                reason = (
                    "it was not run" if producer is None
                    else f"it failed ({producer.error or 'no valid evidence'})"
                )
            else:
                seed_ids, truncated = harvest_seed_ids(producer, cap=sq.limits.max_result_rows)
                if not seed_ids:
                    reason = "it returned no join values"
            if reason is not None:
                result = dependency_skip_result(
                    SpecialistTask.from_sub_question(sq),
                    producer_id=producer_id, reason=reason,
                )
                results.append(result)
                by_id[sq.id] = result
                sequencing.append({"consumer": sq.id, "producer": producer_id,
                                   "seed_count": 0, "truncated": False, "skipped": reason})
                yield ("specialist-start", {"sub_question": sq.id, "source": sq.source,
                                            "index": index, "total": total,
                                            "seed_count": 0, "producer": producer_id,
                                            "skipped": reason})
                yield ("specialist", {"result": result, "index": index, "total": total})
                continue
            sequencing.append({"consumer": sq.id, "producer": producer_id,
                               "seed_count": len(seed_ids), "truncated": truncated,
                               "skipped": None})

        # Announce the run the moment it is true — the UI animates "now
        # querying <source>" off this, so it must precede the blocking call.
        yield ("specialist-start", {"sub_question": sq.id, "source": sq.source,
                                    "index": index, "total": total,
                                    "seed_count": len(seed_ids),
                                    "producer": producer_id, "skipped": None})
        t0 = time.monotonic()
        result = specialist.run(SpecialistTask.from_sub_question(sq, seed_ids=seed_ids))
        specialist_timings.append({
            "sub_question": sq.id,
            "source": sq.source,
            "ms": round((time.monotonic() - t0) * 1000, 3),
        })
        results.append(result)
        by_id[sq.id] = result
        yield ("specialist", {"result": result, "index": index, "total": total})

    run.timings["specialists"] = specialist_timings

    # 4. Bundle through the one shared rule.
    evidence = bundle_evidence(plan, results, skipped, sequencing)
    run.evidence = evidence
    yield ("evidence", {"evidence": evidence})

    # 5. Synthesize: claims-with-citations, always verified deterministically.
    run.status, run.exit_code = status_and_exit(cards_present=True, evidence=evidence)
    yield ("status", {"phase": "answering",
                      "message": "Composing and verifying the grounded answer"})
    t0 = time.monotonic()
    answer = synthesize(evidence, synthesis_config or SynthesisConfig.from_env())
    run.timings["synthesis_ms"] = round((time.monotonic() - t0) * 1000, 3)
    run.answer = answer
    run.timings["total_ms"] = round((time.monotonic() - t_start) * 1000, 3)

    yield ("answer", {"plan": plan, "evidence": evidence, "synthesized": answer,
                      "status": run.status, "exit_code": run.exit_code})
    yield ("done", {"status": run.status, "exit_code": run.exit_code,
                    "timings": run.timings})


def run_pipeline(
    question: str,
    **kwargs: Any,
) -> PipelineRun:
    """Run the full pipeline and return the outcome (see ``iter_pipeline``)."""
    run = PipelineRun(question=question, mode=str(kwargs.get("mode", "query")))
    for _event, _payload in iter_pipeline(question, run=run, **kwargs):
        pass
    return run
