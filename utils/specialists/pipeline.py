#!/usr/bin/env python3
"""Compatibility seam for the pipeline orchestrator.

The orchestration itself moved to ``utils.orchestration.main`` in the
LangGraph migration: the composition

    probe → plan → [sequenced specialists] → bundle → synthesize → done

now runs as a compiled LangGraph ``StateGraph`` there, streaming the same
``(event, payload)`` tuples this module's generator always yielded. This
module re-exports the public names so existing imports
(``from utils.specialists.pipeline import iter_pipeline, run_pipeline,
PipelineRun``) keep working; new code should import from
``utils.orchestration.main`` directly.
"""

from __future__ import annotations

from utils.orchestration.main import (  # noqa: F401
    DEFAULT_PIPELINE_TIMEOUT_S,
    PipelineRun,
    iter_pipeline,
    pipeline_timeout_s,
    run_pipeline,
)

__all__ = [
    "DEFAULT_PIPELINE_TIMEOUT_S",
    "PipelineRun",
    "iter_pipeline",
    "pipeline_timeout_s",
    "run_pipeline",
]
