#!/usr/bin/env python3
"""CLI glue for the end-to-end planner → specialists flow.

Keeps ``main.py`` thin: plan an analyst question with the federated planning
agent, then run the source-specific specialists over that plan and print each
validated query, the normalised evidence, grounded summaries, and the join
index synthesis would consume.
"""

from __future__ import annotations

import dataclasses
import json
import logging
from pathlib import Path

from utils.planner.agent import PlanningAgent
from utils.planner.config import PlannerConfig

from utils.synthesis.config import SynthesisConfig
from utils.synthesis.factory import synthesize

from .config import SpecialistConfig
from .federation import SpecialistRouter, status_and_exit

logger = logging.getLogger("ariadne.specialists.cli")


def run_query_command(
    question: str,
    *,
    use_llm: bool = False,
    data_dir: str | None = None,
) -> int:
    """Plan ``question`` and run the specialists over the plan.

    Returns a process exit code: 0 when every routed specialist returned valid
    evidence with nothing unsupported, 1 when the result is partial (a source
    down, a part unsupported, or a specialist failure), 2 when no source cards
    are available.
    """
    planner_overrides: dict[str, object] = {"llm_enabled": use_llm}
    if data_dir is not None:
        planner_overrides["data_dir"] = Path(data_dir)
    planner_config = dataclasses.replace(PlannerConfig.from_env(), **planner_overrides)
    agent = PlanningAgent(planner_config)

    if not agent.cards:
        print("No source cards found. Build them first: uv run main.py --build all")
        return 2

    # 1. Plan (probe live graphs + route).
    live_view = agent.live_sources()
    print("\n=== Live sources (probed now) ===")
    for ds in sorted(live_view.sources):
        src = live_view.sources[ds]
        flag = "LIVE" if src.live else "DOWN"
        detail = f"nodes={src.node_count}" if src.live else src.reason
        print(f"  [{flag}] {ds} ({src.backend}) — {detail}")

    plan = agent.plan(question)
    print("\n=== Plan ===")
    print(f"  routed to: {sorted(plan.target_sources()) or '(none)'}")
    for sq in plan.sub_questions:
        print(f"    - [{sq.source}] {sq.id}: entities={sq.entities} "
              f"limits={sq.limits.to_dict()} join_key={sq.join_key}")
    for part in plan.unsupported:
        print(f"    ! unsupported: {part.description} ({part.reason})")

    # 2. Run the specialists over the plan.
    specialist_config = SpecialistConfig.from_env(data_dir=data_dir)
    router = SpecialistRouter(specialist_config, cards=agent.cards)
    evidence = router.run_plan(plan)

    print("\n=== Specialist evidence ===")
    for result in evidence.results:
        status = "ok" if result.ok else ("partial" if result.partial else "FAIL")
        print(f"\n  [{result.task.source}] {result.task.sub_question_id} — {status}")
        print(f"    query: {result.query or '(none)'}")
        print(f"    records: {len(result.records)} | join_values: {result.join_values()}")
        print(f"    summary: {result.summary}")
        if result.error:
            print(f"    error: {result.error}")
    for skip in evidence.skipped:
        print(f"\n  [skipped] {skip['sub_question']} ({skip['source']}): {skip['reason']}")

    cross = evidence.cross_source_join_values()
    if cross:
        print(f"\n=== Cross-source join candidates (for synthesis) ===\n  {cross}")

    # 3. Synthesize: claims-with-citations, verified against the evidence.
    answer = synthesize(evidence, SynthesisConfig.from_env())
    print("\n=== Synthesized answer (verified) ===")
    print(f"  {answer.headline}")
    for claim in answer.rendered_claims():
        cites = ", ".join(f"{c.source}:{c.primary_id}" for c in claim.citations)
        print(f"  + [{claim.kind}] {claim.text}  [cites: {cites}]")
    for abst in answer.abstentions:
        print(f"  ~ [{abst.source}] {abst.statement}")
        print(f"      proof (executed query): {abst.query or '(none)'}")
    for claim, verdict in answer.flagged_claims():
        print(f"  x CUT: {claim.text}  ({'; '.join(verdict.reasons)})")
    for note in answer.notes:
        print(f"  ! {note}")
    if answer.fallback_reason:
        print(f"  (composer fallback: {answer.fallback_reason})")
    report = answer.verification
    print(
        f"  verification: {report.supported_count}/{len(report.verdicts)} claim(s) "
        f"supported, unsupported rate {report.unsupported_claim_rate:.0%}, "
        f"{report.repaired_abstentions} abstention repair(s)"
    )

    print("\n=== Federated evidence bundle (JSON) ===")
    print(json.dumps(evidence.to_dict(), indent=2))

    return status_and_exit(cards_present=True, evidence=evidence)[1]
