#!/usr/bin/env python3
"""LangGraph Studio entry point (``langgraph dev``).

Exports a compiled super-graph built from the environment — the same
composition every real query runs — so the workflow can be inspected and
stepped visually. Referenced by the root ``langgraph.json``; not imported by
the runtime path (``iter_pipeline`` builds a per-request graph with the
request's own collaborators).
"""

from __future__ import annotations

import dataclasses

from dotenv import load_dotenv

from utils.orchestration.main import build_pipeline_graph
from utils.planner.agent import PlanningAgent
from utils.planner.config import PlannerConfig
from utils.specialists.config import SpecialistConfig
from utils.synthesis.config import SynthesisConfig

load_dotenv()  # Studio runs from the repo root; live creds live in .env

_agent = PlanningAgent(PlannerConfig.from_env())
graph = build_pipeline_graph(
    _agent,
    None,
    dataclasses.replace(SpecialistConfig.from_env()),
    SynthesisConfig.from_env(),
)
