"""Golden event-contract parity: the LangGraph pipeline must stream exactly
the pre-migration ``(event, payload)`` sequence for every scenario.

``utils/specialists/tests/test_pipeline.py`` pins outcomes; this pins the
*stream itself* — event names in order, payload key sets, and the mid-stream
``PipelineRun`` mutations the SSE layer reads while events are in flight.
"""

from __future__ import annotations

from utils.planner.agent import PlanningAgent
from utils.planner.config import PlannerConfig
from utils.planner.discovery import LiveSourceView
from utils.planner.drafter import DeterministicDrafter
from utils.planner.tests._fixtures import load_fixture_cards, make_live_view
from utils.specialists.contracts import EvidenceRecord, Provenance, SpecialistResult, SpecialistTask
from utils.specialists.pipeline import PipelineRun, iter_pipeline
from utils.synthesis.config import SynthesisConfig

CARDS = load_fixture_cards()
QUESTION = (
    "Which CAPEC patterns related to credential theft map to ATT&CK techniques, "
    "and what mitigations appear for those techniques?"
)
SYNTH = SynthesisConfig(llm_enabled=False)


class FixedProbe:
    def __init__(self, view) -> None:
        self._view = view

    def get_live_sources(self, cards, force: bool = False):
        return self._view


def _agent(live=("attack", "capec"), cards=CARDS) -> PlanningAgent:
    view = make_live_view(live=live) if cards else LiveSourceView({})
    return PlanningAgent(PlannerConfig(data_dir="data"), cards=cards,
                         drafter=DeterministicDrafter(), probe=FixedProbe(view))


def _prov(dataset: str) -> Provenance:
    backend = "neo4j" if dataset == "attack" else "gremlin"
    return Provenance(source=dataset, dataset=dataset, backend=backend,
                      query="q", record_id="r1", timestamp="2026-07-06T00:00:00+00:00")


class FakeSpecialist:
    def __init__(self, source: str, join_values: tuple[str, ...], *, ok: bool = True) -> None:
        self._source, self._join_values, self._ok = source, join_values, ok

    def run(self, task: SpecialistTask) -> SpecialistResult:
        records = [EvidenceRecord(primary_id=v, id_scheme=f"{self._source}-id", label="X",
                                  name=v, join_values=(v,), provenance=_prov(self._source))
                   for v in self._join_values] if self._ok else []
        return SpecialistResult(task=task, query="q" if self._ok else "", records=records,
                                summary="s" if records else "", ok=self._ok,
                                partial=not self._ok, error=None if self._ok else "boom")


def _events(**kwargs):
    defaults = dict(agent=_agent(), synthesis_config=SYNTH,
                    specialists={"capec": FakeSpecialist("capec", ("T1110.001",)),
                                 "attack": FakeSpecialist("attack", ("T1110.001",))})
    defaults.update(kwargs)
    return list(iter_pipeline(QUESTION, **defaults))


# The exact pre-migration sequences, from the generator contract.
QUERY_MODE_GOLDEN = [
    "status",            # probing
    "probe",
    "status",            # classifying (planner step one)
    "status",            # planning
    "plan",
    "status",            # querying
    "specialist-start", "specialist",   # capec (producer)
    "specialist-start", "specialist",   # attack (consumer, seeded)
    "evidence",
    "status",            # answering
    "assess",            # sufficiency verdict (loop enabled by default; single pass here)
    "answer",
    "done",
]

PAYLOAD_KEYS = {
    "probe": {"live_view"},
    "plan": {"plan"},
    "specialist-start": {"sub_question", "source", "backend", "index", "total",
                         "seed_count", "producer", "skipped"},
    "specialist": {"result", "index", "total"},
    "evidence": {"evidence"},
    "assess": {"assessment", "hop", "max_hops"},
    "answer": {"plan", "evidence", "synthesized", "status", "exit_code"},
    "done": {"status", "exit_code", "timings"},
}


def test_query_mode_event_sequence_is_golden():
    events = _events()
    assert [e for e, _ in events] == QUERY_MODE_GOLDEN
    for event, payload in events:
        if event in PAYLOAD_KEYS:
            assert set(payload) == PAYLOAD_KEYS[event], f"{event} payload keys drifted"
    # status phases in order, with the querying count present.
    statuses = [p for e, p in events if e == "status"]
    assert [s["phase"] for s in statuses] == [
        "probing", "classifying", "planning", "querying", "answering"]
    assert statuses[3]["count"] == 2


def test_plan_event_carries_classified_intent():
    # Planner step one is visible on the wire: a `classifying` status phase, and
    # the classified intent (label + why) rides the `plan` event for the UI.
    events = _events()
    phases = [p["phase"] for e, p in events if e == "status"]
    assert "classifying" in phases
    plan = dict(events)["plan"]["plan"]
    assert plan.intent is not None and plan.intent.label == "correlation"


def test_plan_mode_event_sequence_is_golden():
    events = _events(mode="plan")
    assert [e for e, _ in events] == [
        "status", "probe", "status", "status", "plan", "status", "answer", "done"]
    answer = dict(events)["answer"]
    assert answer["evidence"] is None and answer["synthesized"] is None
    done = dict(events)["done"]
    assert "plan_ms" in done["timings"] and "total_ms" in done["timings"]


def test_no_cards_event_sequence_is_golden():
    events = list(iter_pipeline(QUESTION, agent=_agent(cards={}), synthesis_config=SYNTH))
    assert [e for e, _ in events] == ["status", "done"]
    done = events[-1][1]
    assert done["status"] == "no_sources" and done["exit_code"] == 2
    assert "Build them with" in done["message"]


def test_dependency_skip_still_emits_start_then_result():
    events = _events(specialists={
        "capec": FakeSpecialist("capec", (), ok=False),
        "attack": FakeSpecialist("attack", ("T1110.001",)),
    })
    assert [e for e, _ in events] == QUERY_MODE_GOLDEN
    starts = [p for e, p in events if e == "specialist-start"]
    assert starts[1]["skipped"] and "it failed" in starts[1]["skipped"]
    assert starts[1]["seed_count"] == 0


def test_timeout_skips_emit_skipped_events():
    events = _events(timeout_s=-1.0)
    names = [e for e, _ in events]
    # The second trailing `status` is the over-budget synthesis notice: past the
    # deadline the composer drops to deterministic and says so rather than
    # spending another whole LLM timeout on prose nobody is waiting for.
    assert names == ["status", "probe", "status", "status", "plan", "status",
                     "skipped", "skipped", "evidence", "status", "assess",
                     "status", "answer", "done"]
    for _, payload in [ev for ev in events if ev[0] == "skipped"]:
        assert set(payload) == {"sub_question", "source", "reason"}
        assert "timeout" in payload["reason"]


def test_run_timings_are_populated_before_the_answer_event():
    """The SSE layer reads run.timings while shaping the answer frame."""
    run = PipelineRun(question=QUESTION)
    for event, _payload in iter_pipeline(
        QUESTION, agent=_agent(), synthesis_config=SYNTH, run=run,
        specialists={"capec": FakeSpecialist("capec", ("T1110.001",)),
                     "attack": FakeSpecialist("attack", ("T1110.001",))},
    ):
        if event == "answer":
            assert "plan_ms" in run.timings
            assert "synthesis_ms" in run.timings
            assert "total_ms" in run.timings
            assert {t["source"] for t in run.timings["specialists"]} == {"capec", "attack"}
    assert run.answer is not None and run.evidence is not None
