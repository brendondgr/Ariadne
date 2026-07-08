#!/usr/bin/env python3
"""Public entry point for running one conversational turn.

``iter_conversation`` streams the conversation super-graph's custom events in
order — the exact vocabulary the web app consumes:

    status(orchestrating) -> context -> route
      quick: -> final -> conversation -> done
      graph: -> (pipeline: status/probe/plan/specialist-start/specialist/
                 skipped/evidence/status/answer)*
             -> validation (-> pipeline again on retry -> validation)*
             -> final -> conversation -> done
"""

from __future__ import annotations

from typing import Any, Iterator

from utils.conversation.config import ConversationConfig
from utils.conversation.graph import build_conversation_graph
from utils.orchestration.config import OrchestrationConfig
from utils.orchestration.main import PipelineRun


def iter_conversation(
    question: str,
    *,
    conversation_id: str,
    history: list[dict[str, Any]] | None = None,
    mode: str = "query",
    use_llm: bool = False,
    config: ConversationConfig | None = None,
    graph: Any | None = None,
    run: PipelineRun | None = None,
    **build_kwargs: Any,
) -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield ``(event, payload)`` for one conversational turn.

    Pass ``run`` (a caller-owned ``PipelineRun``) to read ``run.timings`` while
    rendering the forwarded pipeline ``answer``/``done`` events. ``build_kwargs``
    are forwarded to :func:`build_conversation_graph` (e.g. injected clients or an
    alternate extraction ``runner``).
    """
    config = config or ConversationConfig.from_env()
    compiled = graph or build_conversation_graph(config, **build_kwargs)

    run = run if run is not None else PipelineRun(question=question, mode=mode)
    init: dict[str, Any] = {
        "question": question,
        "history": history or [],
        "conversation_id": conversation_id,
        "mode": mode,
        "use_llm": use_llm,
        "run": run,
        "validation_iterations": 0,
        "extraction_params": {},
        "trace": [],
    }
    orch = OrchestrationConfig.from_env()
    stream_config: dict[str, Any] = {"recursion_limit": orch.recursion_limit}

    for _namespace, chunk in compiled.stream(
        init,
        stream_mode="custom",
        subgraphs=True,
        config=stream_config,
    ):
        yield chunk
