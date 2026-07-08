#!/usr/bin/env python3
"""The Graph Extraction agent — wraps the existing pipeline as a subgraph.

This node reuses ``utils.orchestration.iter_pipeline`` verbatim: it runs the
probe → plan → specialists → synthesis super-graph on the resolved question,
forwards every pipeline event to the conversation stream (so the UI still sees
probe/plan/specialist/evidence/answer), and returns the grounded evidence +
synthesis answer to conversation state.

On a validation retry, ``extraction_params`` (focus hints + the prior-attempt
reason) are folded into the question so the re-run searches with new parameters —
the analyst's explicitly requested "not enough info -> search again" behavior.
"""

from __future__ import annotations

from typing import Any, Callable

from utils.conversation.config import ConversationConfig
from utils.orchestration.main import PipelineRun, iter_pipeline

# A runner takes the question + run and forwards (event, payload) pairs, returning
# the completed PipelineRun. Injectable so tests need no live backends.
Runner = Callable[..., PipelineRun]


def default_runner(
    question: str,
    *,
    mode: str,
    use_llm: bool,
    run: PipelineRun,
    forward: Callable[[str, dict[str, Any]], None] | None = None,
    **pipeline_kwargs: Any,
) -> PipelineRun:
    """Drive ``iter_pipeline``, forwarding each event, and return the run."""
    for event, payload in iter_pipeline(
        question, mode=mode, use_llm=use_llm, run=run, **pipeline_kwargs
    ):
        if forward is not None:
            forward(event, payload)
    return run


def augment_question(base: str, params: dict[str, Any] | None) -> str:
    """Fold validation retry hints into the question for a re-run."""
    if not params:
        return base
    focus = params.get("focus") or []
    reason = str(params.get("reason", "")).strip()
    parts = [base]
    if focus:
        parts.append("Additionally focus on: " + "; ".join(str(f) for f in focus) + ".")
    if reason:
        parts.append(f"A previous attempt was insufficient because: {reason}")
    return " ".join(parts)


def _stream_forward() -> Callable[[str, dict[str, Any]], None] | None:
    """Return a forwarder onto the LangGraph custom stream, or None if unavailable."""
    try:
        from langgraph.config import get_stream_writer

        writer = get_stream_writer()
    except (ImportError, RuntimeError):
        return None

    def forward(event: str, payload: dict[str, Any]) -> None:
        writer((event, payload))

    return forward


def make_extraction_node(
    config: ConversationConfig,
    *,
    runner: Runner = default_runner,
    pipeline_kwargs: dict[str, Any] | None = None,
):
    """Build the LangGraph node that runs (or re-runs) graph extraction."""

    def extraction_node(state: dict[str, Any]) -> dict[str, Any]:
        base_q = state.get("resolved_question") or state.get("question", "")
        question = augment_question(base_q, state.get("extraction_params"))
        mode = state.get("mode", "query")
        run = state.get("run") or PipelineRun(question=question, mode=mode)
        attempt = int(state.get("validation_iterations", 0)) + 1

        result = runner(
            question,
            mode=mode,
            use_llm=bool(state.get("use_llm", False)),
            run=run,
            forward=_stream_forward(),
            **(pipeline_kwargs or {}),
        )
        return {
            "evidence": result.evidence,
            "answer": result.answer,
            "plan": result.plan,
            "live_view": result.live_view,
            "status": result.status,
            "exit_code": result.exit_code,
            "run": run,
            "trace": [
                {
                    "node": "graph_extraction",
                    "attempt": attempt,
                    "status": result.status,
                }
            ],
        }

    return extraction_node
