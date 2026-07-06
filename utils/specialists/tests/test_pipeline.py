#!/usr/bin/env python3
"""The single pipeline orchestrator: degradation semantics, provenance
threading, per-stage timings, the total-pipeline deadline, and determinism.

Hermetic: fixture cards, a fixed probe, fake specialists, LLM off.
"""

from __future__ import annotations

from utils.planner.agent import PlanningAgent
from utils.planner.config import PlannerConfig
from utils.planner.discovery import LiveSourceView
from utils.planner.drafter import DeterministicDrafter
from utils.planner.tests._fixtures import load_fixture_cards, make_live_view

from utils.specialists.contracts import EvidenceRecord, Provenance, SpecialistResult, SpecialistTask
from utils.specialists.pipeline import iter_pipeline, run_pipeline

from utils.synthesis.config import SynthesisConfig

CARDS = load_fixture_cards()
QUESTION = "Which CAPEC patterns related to credential theft map to ATT&CK techniques, and what mitigations appear for those techniques?"
SYNTH = SynthesisConfig(llm_enabled=False)


class FixedProbe:
    def __init__(self, view: LiveSourceView) -> None:
        self._view = view

    def get_live_sources(self, cards, force: bool = False) -> LiveSourceView:
        return self._view


def _agent(live=("attack", "capec")) -> PlanningAgent:
    return PlanningAgent(
        PlannerConfig(data_dir="data"),
        cards=CARDS,
        drafter=DeterministicDrafter(),
        probe=FixedProbe(make_live_view(live=live)),
    )


def _prov(dataset: str, backend: str) -> Provenance:
    return Provenance(
        source=dataset, dataset=dataset, backend=backend,
        query=f"query against {backend}", record_id="r1",
        timestamp="2026-07-06T00:00:00+00:00",
    )


class FakeSpecialist:
    def __init__(self, source: str, join_values: tuple[str, ...], *,
                 ok: bool = True, error: str | None = None) -> None:
        self._source = source
        self._join_values = join_values
        self._ok = ok
        self._error = error
        self.tasks: list[SpecialistTask] = []

    def run(self, task: SpecialistTask) -> SpecialistResult:
        self.tasks.append(task)
        backend = "neo4j" if self._source == "attack" else "gremlin"
        records = [
            EvidenceRecord(
                primary_id=v, id_scheme=f"{self._source}-id", label="X", name=v,
                join_values=(v,), provenance=_prov(self._source, backend),
            )
            for v in self._join_values
        ] if self._ok else []
        return SpecialistResult(
            task=task, query=f"query against {backend}" if self._ok else "",
            records=records, summary="s" if records else "",
            ok=self._ok, partial=not self._ok, error=self._error,
        )


def _specialists(**overrides) -> dict:
    base = {
        "capec": FakeSpecialist("capec", ("T1110.001", "T1555")),
        "attack": FakeSpecialist("attack", ("T1110.001", "T1555")),
    }
    base.update(overrides)
    return base


def _run(specialists=None, agent=None, **kwargs):
    return run_pipeline(
        QUESTION,
        agent=agent or _agent(),
        specialists=specialists if specialists is not None else _specialists(),
        synthesis_config=SYNTH,
        **kwargs,
    )


# -- happy path ---------------------------------------------------------------


def test_pipeline_answers_cleanly_with_both_sources_up() -> None:
    run = _run()
    assert (run.status, run.exit_code) == ("answered", 0)
    assert run.evidence is not None and not run.evidence.partial
    assert run.answer is not None and run.answer.rendered_claims()


def test_event_order_matches_streaming_contract() -> None:
    events = [e for e, _ in iter_pipeline(
        QUESTION, agent=_agent(), specialists=_specialists(), synthesis_config=SYNTH,
    )]
    assert events[0] == "status" and events[-1] == "done"
    core = [e for e in events if e != "status"]
    assert core[:2] == ["probe", "plan"]
    assert core[-3:] == ["evidence", "answer", "done"]
    assert all(e == "specialist" for e in core[2:-3])


# -- degradation modes --------------------------------------------------------


def test_attack_down_is_partial_exit_1() -> None:
    # Planner sees attack dead: the attack part becomes unsupported.
    run = _run(agent=_agent(live=("capec",)))
    assert (run.status, run.exit_code) == ("partial", 1)
    assert run.evidence.unsupported or run.evidence.skipped


def test_capec_down_is_partial_exit_1() -> None:
    run = _run(agent=_agent(live=("attack",)))
    assert (run.status, run.exit_code) == ("partial", 1)


def test_specialist_failure_is_partial_exit_1() -> None:
    run = _run(specialists=_specialists(
        capec=FakeSpecialist("capec", (), ok=False, error="backend refused"),
    ))
    assert (run.status, run.exit_code) == ("partial", 1)


def test_both_up_one_empty_is_answered_with_abstention() -> None:
    # An empty-but-clean producer is honest, not partial: the consumer becomes
    # a dependency abstention and the run still exits 0.
    run = _run(specialists=_specialists(capec=FakeSpecialist("capec", ())))
    assert (run.status, run.exit_code) == ("answered", 0)
    assert run.answer.abstentions, "empty sources must abstain, not vanish"


def test_no_cards_is_exit_2() -> None:
    agent = PlanningAgent(
        PlannerConfig(data_dir="data"), cards={},
        drafter=DeterministicDrafter(), probe=FixedProbe(LiveSourceView({})),
    )
    run = run_pipeline(QUESTION, agent=agent, synthesis_config=SYNTH)
    assert (run.status, run.exit_code) == ("no_sources", 2)


def test_unsupported_part_present_is_partial() -> None:
    run = run_pipeline(
        "Which CAPEC patterns map to techniques, and which assets do they target?",
        agent=_agent(), specialists=_specialists(), synthesis_config=SYNTH,
    )
    if run.plan.unsupported:  # drafter routed the asset part as unsupported
        assert (run.status, run.exit_code) == ("partial", 1)


# -- provenance threads end-to-end --------------------------------------------


def test_every_rendered_claim_resolves_to_executed_query_provenance() -> None:
    run = _run()
    by_key = {}
    for result in run.evidence.results:
        for rec in result.records:
            by_key[(result.task.source, rec.primary_id)] = rec
    for claim in run.answer.rendered_claims():
        assert claim.citations
        for cite in claim.citations:
            rec = by_key.get((cite.source, cite.primary_id))
            assert rec is not None, f"citation {cite} resolves to no retrieved record"
            assert rec.provenance is not None
            assert rec.provenance.query, "provenance must carry the executed query"
            assert rec.provenance.timestamp, "provenance must carry a timestamp"


# -- timings & deadline --------------------------------------------------------


def test_per_stage_timings_recorded() -> None:
    run = _run()
    assert "plan_ms" in run.timings and "synthesis_ms" in run.timings
    assert "total_ms" in run.timings
    stages = run.timings["specialists"]
    assert {t["sub_question"] for t in stages} == {sq.id for sq in run.plan.sub_questions}
    assert all(t["ms"] >= 0 for t in stages)


def test_total_pipeline_deadline_skips_late_specialists() -> None:
    run = _run(timeout_s=-1.0)  # already expired: nothing may run
    assert run.evidence is not None
    assert not run.timings["specialists"], "no specialist may start past the deadline"
    assert run.evidence.skipped and all(
        "timeout" in s["reason"] for s in run.evidence.skipped
    )
    assert (run.status, run.exit_code) == ("partial", 1)


# -- determinism ----------------------------------------------------------------


def test_llm_off_pipeline_is_reproducible() -> None:
    one = _run(specialists=_specialists())
    two = _run(specialists=_specialists())
    assert one.answer.to_dict() == two.answer.to_dict()
    e1, e2 = one.evidence.to_dict(), two.evidence.to_dict()
    for ev in (e1, e2):  # timestamps are the only legitimate difference
        for r in ev["results"]:
            for rec in r["records"]:
                rec.get("provenance", {}).pop("timestamp", None)
    assert e1 == e2
    assert (one.status, one.exit_code) == (two.status, two.exit_code)
