#!/usr/bin/env python3
"""The ``assess`` super-graph node: judge sufficiency, update the frontier.

Runs after ``bundle`` (so ``state['evidence']`` is populated). It folds this
hop's evidence delta into ``frontier``/``visited`` and writes an
``Assessment``; the super-graph's ``route_sufficiency`` edge reads
``assessment.sufficient`` to decide synthesize-vs-replan. All loop policy
(join closure, novelty, hop cap, optional LLM critic) lives in ``policy`` — the
node only wires state to it.
"""

from __future__ import annotations

from typing import Any

from langgraph.config import get_stream_writer

from utils.orchestration.agents.assess.contracts import Assessment
from utils.orchestration.agents.assess.frontier import (
    extract_frontier,
    update_visited,
)
from utils.orchestration.agents.assess.policy import LLMCritic, assess
from utils.orchestration.config import OrchestrationConfig
from utils.orchestration.state import PipelineState


def build_assess_node(
    orch: OrchestrationConfig, *, critic: LLMCritic | None = None
):
    """Return the ``assess`` node bound to this run's loop configuration."""

    def assess_node(state: PipelineState) -> dict[str, Any]:
        plan = state["plan"]
        evidence = state["evidence"]
        hop = int(state.get("hop") or 1)
        prior_frontier = set(state.get("frontier") or set())
        prior_visited = set(state.get("visited") or set())
        results = list(evidence.results)

        new_frontier = extract_frontier(results, plan) - prior_frontier
        new_visited = update_visited(prior_visited, results)

        verdict: Assessment = assess(
            evidence=evidence,
            plan=plan,
            prior_frontier=prior_frontier,
            prior_visited=prior_visited,
            hop=hop,
            max_hops=orch.max_hops,
            assess_mode=orch.assess_mode,
            use_llm=bool(state.get("use_llm")),
            critic=critic,
            chase_facets=orch.chase_facets,
            max_facet_expansions=orch.max_facet_expansions,
            expand_unbound=getattr(orch, "expand_unbound", False),
            expand_unbound_max_members=getattr(orch, "expand_unbound_max_members", 50),
        )

        # Surface the verdict for inspectability, but only when the loop is
        # actually enabled — at max_hops=1 the pipeline is single-pass and the
        # event stream must stay byte-identical to the pre-loop contract.
        if orch.max_hops > 1:
            writer = get_stream_writer()
            writer(("assess", {
                "assessment": verdict.to_dict(),
                "hop": hop,
                "max_hops": orch.max_hops,
            }))

        return {
            "assessment": verdict,
            "frontier": new_frontier,
            "visited": new_visited,
        }

    return assess_node
