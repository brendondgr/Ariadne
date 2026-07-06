#!/usr/bin/env python3
"""CLI glue for the end-to-end planner → specialists → synthesis flow.

Keeps ``main.py`` thin: the composition itself lives in ``pipeline.py``
(the single orchestrator the API shares); this module only *prints* each
boundary event — live sources, the plan, per-specialist evidence, the verified
synthesized answer, per-stage timings, and the machine-readable bundle.
"""

from __future__ import annotations

import json
import logging

from .pipeline import PipelineRun, iter_pipeline

logger = logging.getLogger("ariadne.specialists.cli")


def run_query_command(
    question: str,
    *,
    use_llm: bool = False,
    data_dir: str | None = None,
) -> int:
    """Plan ``question``, run the specialists, synthesize, and print it all.

    Returns a process exit code: 0 when every routed specialist returned valid
    evidence with nothing unsupported, 1 when the result is partial (a source
    down, a part unsupported, or a specialist failure), 2 when no source cards
    are available.
    """
    run = PipelineRun(question=question)
    for event, payload in iter_pipeline(
        question, use_llm=use_llm, data_dir=data_dir, run=run
    ):
        if event == "probe":
            live_view = payload["live_view"]
            print("\n=== Live sources (probed now) ===")
            for ds in sorted(live_view.sources):
                src = live_view.sources[ds]
                flag = "LIVE" if src.live else "DOWN"
                detail = f"nodes={src.node_count}" if src.live else src.reason
                print(f"  [{flag}] {ds} ({src.backend}) — {detail}")
        elif event == "plan":
            plan = payload["plan"]
            print("\n=== Plan ===")
            print(f"  routed to: {sorted(plan.target_sources()) or '(none)'}")
            for sq in plan.sub_questions:
                print(f"    - [{sq.source}] {sq.id}: entities={sq.entities} "
                      f"limits={sq.limits.to_dict()} join_key={sq.join_key}")
            for part in plan.unsupported:
                print(f"    ! unsupported: {part.description} ({part.reason})")
        elif event == "done" and payload["status"] == "no_sources":
            print(payload.get("message", "No source cards found."))
            return payload["exit_code"]

    evidence = run.evidence
    if evidence is None:  # defensive: query mode always bundles evidence
        return run.exit_code

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
    for seq in evidence.sequencing:
        note = f"skipped ({seq['skipped']})" if seq["skipped"] else (
            f"seeded with {seq['seed_count']} join value(s)"
            + (" [truncated]" if seq["truncated"] else "")
        )
        print(f"\n  [sequenced] {seq['consumer']} after {seq['producer']}: {note}")

    cross = evidence.cross_source_join_values()
    if cross:
        print(f"\n=== Cross-source join candidates (for synthesis) ===\n  {cross}")

    answer = run.answer
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

    timings = run.timings
    per_specialist = ", ".join(
        f"{t['sub_question']}={t['ms']:.0f}ms" for t in timings.get("specialists", [])
    )
    print(
        f"\n=== Timings ===\n  plan: {timings.get('plan_ms', 0):.0f}ms"
        + (f" | specialists: {per_specialist}" if per_specialist else "")
        + f" | synthesis: {timings.get('synthesis_ms', 0):.0f}ms"
        + f" | total: {timings.get('total_ms', 0):.0f}ms"
    )

    print("\n=== Federated evidence bundle (JSON) ===")
    print(json.dumps(evidence.to_dict(), indent=2))

    return run.exit_code
