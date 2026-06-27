#!/usr/bin/env python3
"""CLI glue for running the planning agent against the live graphs.

Keeps ``main.py`` thin: this builds the agent, re-probes the live graphs,
emits the machine-readable plan, and prints a readable summary.
"""

from __future__ import annotations

import dataclasses
import json
import logging
from pathlib import Path

from .agent import PlanningAgent
from .config import PlannerConfig

logger = logging.getLogger("ariadne.planner.cli")


def run_plan_command(
    question: str,
    *,
    use_llm: bool = False,
    data_dir: str | None = None,
    agent: PlanningAgent | None = None,
) -> int:
    """Plan ``question`` and print the live-source view plus the emitted plan.

    Returns a process exit code: 0 on a fully-answerable plan, 1 when the plan
    is partial (some part unsupported), 2 when no source cards are available.
    """
    if agent is None:
        overrides: dict[str, object] = {"llm_enabled": use_llm}
        if data_dir is not None:
            overrides["data_dir"] = Path(data_dir)
        config = dataclasses.replace(PlannerConfig.from_env(), **overrides)
        agent = PlanningAgent(config)

    if not agent.cards:
        print("No source cards found. Build them first: uv run main.py --build all")
        return 2

    live_view = agent.live_sources()
    print("\n=== Live sources (probed now) ===")
    for ds in sorted(live_view.sources):
        src = live_view.sources[ds]
        flag = "LIVE" if src.live else "DOWN"
        detail = f"nodes={src.node_count}" if src.live else src.reason
        print(f"  [{flag}] {ds} ({src.backend}) — {detail}")

    plan = agent.plan(question)

    print("\n=== Plan ===")
    print(json.dumps(plan.to_dict(), indent=2))

    print("\n=== Summary ===")
    drafter = plan.trace[-1]["drafter"] if plan.trace else "?"
    print(f"  drafter: {drafter} | iterations: {len(plan.trace)} | partial: {plan.partial}")
    print(f"  routed to: {sorted(plan.target_sources()) or '(none)'}")
    if plan.joins:
        print(f"  joins: {[j.key for j in plan.joins]}")
    if plan.unsupported:
        print("  unsupported:")
        for part in plan.unsupported:
            print(f"    - {part.description}: {part.reason}")
    return 1 if plan.partial else 0
