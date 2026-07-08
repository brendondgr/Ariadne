#!/usr/bin/env python3
"""The Q/A super-graph — LangGraph is the pipeline orchestrator.

Wires the full analyst-question workflow as one ``StateGraph``:

    check_cards → probe → plan → ┬─ (plan mode) plan_only ──────────────┐
                                 └─ announce_querying → specialists     │
                                      (subgraph) → bundle → synthesize ─┴→ END

and streams the *exact* event vocabulary the CLI/SSE layers have always
consumed — ``status``, ``probe``, ``plan``, ``skipped``, ``specialist-start``,
``specialist``, ``evidence``, ``answer``, ``done`` — through LangGraph's
custom stream writer. ``iter_pipeline`` (re-exported by
``utils.specialists.pipeline``) is the thin adapter draining
``graph.stream(stream_mode="custom", subgraphs=True)`` into the same
``(event, payload)`` tuples with the same raw-object payloads as before.

Node responsibilities stay with the domain seams: the planner node calls the
``PlanningAgent`` facade (itself the draft → gate → revise/degrade subgraph),
the specialists node *is* the Step-4 subgraph (same state schema, custom
events bubble up), and synthesis goes through ``synthesize()`` (the
compose → verify → narrate subgraph). The caller-owned ``PipelineRun`` rides
in the graph state and is mutated at the same boundaries as before, so
callers that read ``run.timings`` mid-stream (the SSE layer does) see the
same values at the same events.
"""

from __future__ import annotations

import dataclasses
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from utils.orchestration.agents.specialists.graph import build_specialists_graph
from utils.orchestration.config import OrchestrationConfig
from utils.orchestration.state import PipelineState
from utils.planner.agent import PlanningAgent
from utils.planner.config import PlannerConfig
from utils.planner.schema import Plan
from utils.specialists.config import SpecialistConfig
from utils.specialists.federation import (
    FederatedEvidence,
    bundle_evidence,
    status_and_exit,
)
from utils.synthesis.config import SynthesisConfig
from utils.synthesis.contracts import SynthesizedAnswer
from utils.synthesis.factory import synthesize

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


def build_pipeline_graph(
    agent: PlanningAgent,
    specialists: dict[str, Any] | None,
    specialist_config: SpecialistConfig,
    synthesis_config: SynthesisConfig,
) -> CompiledStateGraph:
    """Compile the super-graph for one request's collaborators."""

    def check_cards(state: PipelineState) -> dict[str, Any]:
        if agent.cards:
            return {}
        run = state["run"]
        writer = get_stream_writer()
        run.status, run.exit_code = status_and_exit(cards_present=False)
        writer(("status", {"phase": "probing", "message": "Checking source cards"}))
        writer(("done", {
            "status": run.status,
            "exit_code": run.exit_code,
            "timings": run.timings,
            "message": "No source cards found. Build them with: uv run main.py --build all",
        }))
        return {"status": run.status, "exit_code": run.exit_code}

    def probe(state: PipelineState) -> dict[str, Any]:
        writer = get_stream_writer()
        writer(("status", {"phase": "probing", "message": "Probing live graph backends"}))
        run = state["run"]
        run.live_view = agent.live_sources()
        writer(("probe", {"live_view": run.live_view}))
        return {"live_view": run.live_view}

    def plan_node(state: PipelineState) -> dict[str, Any]:
        writer = get_stream_writer()
        writer(("status", {"phase": "planning", "message": "Planning and routing the question"}))
        run = state["run"]
        t0 = time.monotonic()
        plan = agent.plan(state["question"])
        plan_ms = round((time.monotonic() - t0) * 1000, 3)
        run.timings["plan_ms"] = plan_ms
        run.plan = plan
        writer(("plan", {"plan": plan}))
        return {"plan": plan, "timings": {"plan_ms": plan_ms}}

    def plan_only(state: PipelineState) -> dict[str, Any]:
        run, plan = state["run"], state["plan"]
        writer = get_stream_writer()
        run.status, run.exit_code = status_and_exit(cards_present=True, mode="plan", plan=plan)
        total_ms = round((time.monotonic() - state["started_at"]) * 1000, 3)
        run.timings["total_ms"] = total_ms
        writer(("status", {"phase": "answering", "message": "Composing plan summary"}))
        writer(("answer", {"plan": plan, "evidence": None, "synthesized": None,
                           "status": run.status, "exit_code": run.exit_code}))
        writer(("done", {"status": run.status, "exit_code": run.exit_code,
                         "timings": run.timings}))
        return {"status": run.status, "exit_code": run.exit_code,
                "timings": {"total_ms": total_ms}}

    def announce_querying(state: PipelineState) -> dict[str, Any]:
        get_stream_writer()(("status", {
            "phase": "querying",
            "message": "Querying source specialists",
            "count": len(state["plan"].sub_questions),
        }))
        return {}

    def bundle(state: PipelineState) -> dict[str, Any]:
        run = state["run"]
        writer = get_stream_writer()
        run.timings["specialists"] = list(state.get("specialist_timings") or [])
        evidence = bundle_evidence(
            state["plan"],
            list(state.get("results") or []),
            list(state.get("skipped") or []),
            list(state.get("sequencing") or []),
        )
        run.evidence = evidence
        writer(("evidence", {"evidence": evidence}))
        run.status, run.exit_code = status_and_exit(cards_present=True, evidence=evidence)
        writer(("status", {"phase": "answering",
                           "message": "Composing and verifying the grounded answer"}))
        return {"evidence": evidence, "status": run.status, "exit_code": run.exit_code,
                "timings": {"specialists": run.timings["specialists"]}}

    def synthesize_node(state: PipelineState) -> dict[str, Any]:
        run, plan, evidence = state["run"], state["plan"], state["evidence"]
        writer = get_stream_writer()
        t0 = time.monotonic()
        answer = synthesize(evidence, synthesis_config)
        synthesis_ms = round((time.monotonic() - t0) * 1000, 3)
        run.timings["synthesis_ms"] = synthesis_ms
        run.answer = answer
        total_ms = round((time.monotonic() - state["started_at"]) * 1000, 3)
        run.timings["total_ms"] = total_ms
        writer(("answer", {"plan": plan, "evidence": evidence, "synthesized": answer,
                           "status": run.status, "exit_code": run.exit_code}))
        writer(("done", {"status": run.status, "exit_code": run.exit_code,
                         "timings": run.timings}))
        return {"answer": answer,
                "timings": {"synthesis_ms": synthesis_ms, "total_ms": total_ms}}

    def route_cards(state: PipelineState) -> str:
        return "probe" if agent.cards else END

    def route_mode(state: PipelineState) -> str:
        return "plan_only" if state["mode"] == "plan" else "announce_querying"

    graph = StateGraph(PipelineState)
    graph.add_node("check_cards", check_cards)
    graph.add_node("probe", probe)
    graph.add_node("plan", plan_node)
    graph.add_node("plan_only", plan_only)
    graph.add_node("announce_querying", announce_querying)
    graph.add_node(
        "specialists",
        build_specialists_graph(agent.cards, specialist_config, specialists),
    )
    graph.add_node("bundle", bundle)
    graph.add_node("synthesize", synthesize_node)

    graph.add_edge(START, "check_cards")
    graph.add_conditional_edges("check_cards", route_cards, {"probe": "probe", END: END})
    graph.add_edge("probe", "plan")
    graph.add_conditional_edges(
        "plan", route_mode,
        {"plan_only": "plan_only", "announce_querying": "announce_querying"},
    )
    graph.add_edge("plan_only", END)
    graph.add_edge("announce_querying", "specialists")
    graph.add_edge("specialists", "bundle")
    graph.add_edge("bundle", "synthesize")
    graph.add_edge("synthesize", END)
    return graph.compile()


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
    started_at = time.monotonic()
    deadline = started_at + (timeout_s if timeout_s is not None else pipeline_timeout_s())

    if agent is None:
        overrides: dict[str, object] = {"llm_enabled": use_llm}
        if data_dir is not None:
            overrides["data_dir"] = Path(data_dir)
        agent = PlanningAgent(dataclasses.replace(PlannerConfig.from_env(), **overrides))
    if specialist_config is None:
        specialist_config = dataclasses.replace(
            SpecialistConfig.from_env(data_dir=data_dir), llm_enabled=use_llm
        )
    # When the LLM drafter is selected, the LLM is used throughout — including
    # synthesis. An explicitly injected ``synthesis_config`` (tests) always wins.
    if synthesis_config is None:
        synthesis_config = dataclasses.replace(
            SynthesisConfig.from_env(), llm_enabled=use_llm
        )

    graph = build_pipeline_graph(agent, specialists, specialist_config, synthesis_config)
    orch = OrchestrationConfig.from_env()
    init: dict[str, Any] = {
        "question": question, "mode": mode, "use_llm": use_llm,
        "deadline": deadline, "started_at": started_at, "cursor": 0, "run": run,
    }
    for _namespace, chunk in graph.stream(
        init,
        stream_mode="custom",
        subgraphs=True,
        config={"recursion_limit": orch.recursion_limit},
    ):
        yield chunk


def run_pipeline(
    question: str,
    **kwargs: Any,
) -> PipelineRun:
    """Run the full pipeline and return the outcome (see ``iter_pipeline``)."""
    run = PipelineRun(question=question, mode=str(kwargs.get("mode", "query")))
    for _event, _payload in iter_pipeline(question, run=run, **kwargs):
        pass
    return run
