#!/usr/bin/env python3
"""Specialist-execution nodes: one dependency-ordered sub-question per cycle.

The loop preserves the pipeline's honesty guarantees exactly:

* strictly sequential execution in ``execution_order`` (deterministic —
  the committed evaluation artifacts depend on it),
* declared-join consumers seeded from their producer's harvested join values,
* dependency skips (producer missing/failed/empty) surfaced as honest empty
  results with the dependency named — never a broad unseeded query,
* sub-questions that would start past the pipeline deadline skipped honestly,
* ``specialist-start`` emitted the moment the run is true, *before* the
  blocking call, so a UI can animate "now querying <source>" truthfully.

Events are emitted through LangGraph's custom stream writer with the same
``(event, payload)`` vocabulary the pipeline has always yielded; when the
graph is invoked without custom streaming the writes are simply dropped.
"""

from __future__ import annotations

import dataclasses
import time
from typing import Any, Callable

from langgraph.config import get_stream_writer

from utils.orchestration.state import PipelineState
from utils.specialists import build_specialist
from utils.specialists.config import SpecialistConfig
from utils.specialists.contracts import SpecialistTask
from utils.specialists.federation import (
    dependency_map,
    carries_its_own_seeds,
    dependency_skip_result,
    execution_order,
    harvest_seed_ids,
    request_seeds,
    reroute_source,
    rerouted,
)

NodeFn = Callable[[PipelineState], dict[str, Any]]


def specialist_for(
    source: str,
    cards: dict[str, Any],
    config: SpecialistConfig,
    injected: dict[str, Any] | None,
) -> Any | None:
    """Resolve the specialist for a source: injected (tests) or built from its card."""
    if injected and source in injected:
        return injected[source]
    card = cards.get(source)
    if card is None:
        return None
    try:
        return build_specialist(source, card, config)
    except ValueError:
        return None


def build_nodes(
    cards: dict[str, Any],
    specialist_config: SpecialistConfig,
    injected: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the specialist loop's node + router, closed over collaborators."""

    def run_specialist(state: PipelineState) -> dict[str, Any]:
        plan = state["plan"]
        order = execution_order(plan)
        deps = dependency_map(plan)
        index = int(state.get("cursor") or 0)
        total = len(plan.sub_questions)
        planned = order[index]
        writer = get_stream_writer()
        delta: dict[str, Any] = {"cursor": index + 1}

        # Route by what each store can actually express. `reroute_source` is a
        # pure function of the sub-question and the cards, so the producers'
        # stores are re-derived rather than carried in state — the loop runs one
        # sub-question per cycle and must not depend on a mutable side channel.
        moved = rerouted(planned, cards)
        sq = moved or planned
        ran_in = {
            other.id: (reroute_source(other, cards) or other.source) for other in order
        }
        if moved is not None:
            delta["rerouted"] = [{
                "sub_question": sq.id,
                "from": planned.source,
                "to": sq.source,
                "reason": f"{planned.source} does not model "
                          + ", ".join(cards[planned.source].unknown_entities(
                              list(planned.entities))),
            }]

        specialist = specialist_for(sq.source, cards, specialist_config, injected)
        if specialist is None:
            skip = {"sub_question": sq.id, "source": sq.source,
                    "reason": f"no specialist available for source {sq.source!r}"}
            writer(("skipped", skip))
            delta["skipped"] = [skip]
            return delta

        if time.monotonic() > state["deadline"]:
            skip = {"sub_question": sq.id, "source": sq.source,
                    "reason": "total pipeline timeout exceeded before this sub-question ran"}
            writer(("skipped", skip))
            delta["skipped"] = [skip]
            return delta

        seed_ids: tuple[str, ...] = ()
        producer_ids = deps.get(sq.id) or ()
        producer_id = ", ".join(producer_ids)
        if producer_ids:
            by_id_state = state.get("by_id") or {}
            found = [by_id_state.get(pid) for pid in producer_ids]
            # Every producer that actually ran and succeeded. A consumer at the
            # end of two joins is seeded from the union; one producer failing is
            # not a reason to discard what the other found.
            usable = [p for p in found if p is not None and p.ok]
            reason: str | None = None
            truncated = False
            if not usable:
                failed = [p for p in found if p is not None and not p.ok]
                if failed:
                    # Keep the producer's own words. "no valid evidence" is
                    # a summary of the summary and loses what actually went
                    # wrong, which is the only useful part of an abstention.
                    reason = "it failed (" + "; ".join(
                        p.error or "no valid evidence" for p in failed
                    ) + ")"
                else:
                    reason = "it was not run"
            else:
                # Producer and consumer in the SAME store are not linked by
                # the cross-source key: the consumer anchors on the producer's
                # own records. See `harvest_seed_ids`.
                same_store = all(ran_in.get(pid) == sq.source for pid in producer_ids)
                seed_ids, truncated = harvest_seed_ids(
                    usable, cap=sq.limits.max_result_rows,
                    prefer_primary_ids=same_store,
                    wanted_labels=list(sq.entities),
                )
                if not seed_ids:
                    # Before abstaining, take identifiers the REQUEST literally
                    # names — the analyst's own words, never an invention, and
                    # empty for a request that names none.
                    seed_ids = request_seeds(
                        getattr(plan, "request", "") or "", sq.source
                    )
                if not seed_ids:
                    reason = "it returned no join values"
            # A sub-question that names its own identifiers is not a consumer.
            # `dependency_map` reads the join key's fixed direction, which is
            # backwards for a question seeded on the consuming side — and that
            # skipped 21 of 27 federated development questions unseeded.
            if reason is not None and carries_its_own_seeds(sq):
                reason = None
                seed_ids, truncated = (), False
            if reason is not None:
                result = dependency_skip_result(
                    SpecialistTask.from_sub_question(sq),
                    producer_id=producer_id, reason=reason,
                )
                writer(("specialist-start", {"sub_question": sq.id, "source": sq.source,
                                             "index": index, "total": total,
                                             "seed_count": 0, "producer": producer_id,
                                             "skipped": reason}))
                writer(("specialist", {"result": result, "index": index, "total": total}))
                delta.update(
                    results=[result],
                    by_id={sq.id: result},
                    sequencing=[{"consumer": sq.id, "producer": producer_id,
                                 "seed_count": 0, "truncated": False, "skipped": reason}],
                )
                return delta
            delta["sequencing"] = [{"consumer": sq.id, "producer": producer_id,
                                    "seed_count": len(seed_ids), "truncated": truncated,
                                    "skipped": None}]

        # Announce the run the moment it is true — before the blocking call.
        writer(("specialist-start", {"sub_question": sq.id, "source": sq.source,
                                     "index": index, "total": total,
                                     "seed_count": len(seed_ids),
                                     "producer": producer_id, "skipped": None}))
        t0 = time.monotonic()
        result = specialist.run(SpecialistTask.from_sub_question(sq, seed_ids=seed_ids))
        delta["specialist_timings"] = [{
            "sub_question": sq.id,
            "source": sq.source,
            "ms": round((time.monotonic() - t0) * 1000, 3),
        }]
        writer(("specialist", {"result": result, "index": index, "total": total}))
        delta["results"] = [result]
        delta["by_id"] = {sq.id: result}
        return delta

    def has_next(state: PipelineState) -> bool:
        return int(state.get("cursor") or 0) < len(state["plan"].sub_questions)

    return {"run_specialist": run_specialist, "has_next": has_next}
