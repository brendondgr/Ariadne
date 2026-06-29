#!/usr/bin/env python3
"""Tests for the federation router (planner Plan -> specialists -> evidence)."""

from __future__ import annotations

from utils.planner.schema import JoinDeclaration, Limits, Plan, SubQuestion, UnsupportedPart

from utils.specialists.contracts import EvidenceRecord, Provenance, SpecialistResult
from utils.specialists.federation import FederatedEvidence, SpecialistRouter
from utils.specialists.tests._fixtures import fixture_card


class FakeSpecialist:
    """Returns a canned result; records the task it was handed."""

    def __init__(self, result: SpecialistResult) -> None:
        self._result = result
        self.tasks: list = []

    def run(self, task):
        self.tasks.append(task)
        # Echo the task onto the result so by_source() routes correctly.
        self._result.task = task
        return self._result


def _prov(dataset: str, backend: str) -> Provenance:
    return Provenance(
        source=dataset, dataset=dataset, backend=backend,
        query="q", record_id="r1", timestamp="2026-06-29T00:00:00+00:00",
    )


def _result(source: str, primary_id: str, join_values: tuple[str, ...], ok: bool = True) -> SpecialistResult:
    backend = "neo4j" if source == "attack" else "gremlin"
    rec = EvidenceRecord(
        primary_id=primary_id, id_scheme=f"{source}-id", label="X", name=primary_id,
        join_values=join_values, provenance=_prov(source, backend),
    )
    from utils.specialists.contracts import SpecialistTask
    return SpecialistResult(
        task=SpecialistTask(sub_question_id="", source=source, text=""),
        query="q", records=[rec], summary="s", ok=ok, partial=not ok,
    )


def _sub(qid: str, source: str, join_key: str | None = None) -> SubQuestion:
    return SubQuestion(
        id=qid, source=source, text=f"about {source}",
        entities=["AttackPattern"] if source == "capec" else ["Technique"],
        limits=Limits(3, 1000, 5000), join_key=join_key,
    )


def test_router_dispatches_each_sub_question_to_its_specialist() -> None:
    cards = {"attack": fixture_card("attack"), "capec": fixture_card("capec")}
    attack_spec = FakeSpecialist(_result("attack", "T1574.010", ("T1574.010",)))
    capec_spec = FakeSpecialist(_result("capec", "CAPEC-1", ("T1574.010",)))
    plan = Plan(
        request="credential theft cross source",
        sub_questions=[_sub("q1", "capec", "attack-technique-id"), _sub("q2", "attack", "attack-technique-id")],
        joins=[JoinDeclaration("attack-technique-id", ["capec", "attack"])],
    )
    router = SpecialistRouter(
        cards=cards, specialists={"attack": attack_spec, "capec": capec_spec}
    )
    evidence = router.run_plan(plan)

    assert len(evidence.results) == 2
    assert len(attack_spec.tasks) == 1 and len(capec_spec.tasks) == 1
    # The CAPEC sub-question's join_key is threaded into the specialist task.
    assert capec_spec.tasks[0].source == "capec"
    by_source = evidence.by_source()
    assert set(by_source) == {"attack", "capec"}


def test_router_builds_cross_source_join_index() -> None:
    cards = {"attack": fixture_card("attack"), "capec": fixture_card("capec")}
    router = SpecialistRouter(
        cards=cards,
        specialists={
            "attack": FakeSpecialist(_result("attack", "T1574.010", ("T1574.010",))),
            "capec": FakeSpecialist(_result("capec", "CAPEC-1", ("T1574.010",))),
        },
    )
    plan = Plan(
        request="x",
        sub_questions=[_sub("q1", "capec"), _sub("q2", "attack")],
    )
    evidence = router.run_plan(plan)
    index = evidence.join_index()
    assert "T1574.010" in index
    # T1574.010 is reported by BOTH sources -> a cross-source join candidate.
    assert evidence.cross_source_join_values() == ["T1574.010"]


def test_router_skips_unknown_source_and_marks_partial() -> None:
    cards = {"attack": fixture_card("attack")}  # no capec card
    router = SpecialistRouter(
        cards=cards, specialists={"attack": FakeSpecialist(_result("attack", "T1", ()))}
    )
    plan = Plan(request="x", sub_questions=[_sub("q1", "capec"), _sub("q2", "attack")])
    evidence = router.run_plan(plan)
    assert len(evidence.results) == 1
    assert len(evidence.skipped) == 1
    assert evidence.skipped[0]["source"] == "capec"
    assert evidence.partial  # a skipped sub-question makes the bundle partial


def test_partial_when_plan_has_unsupported_parts() -> None:
    cards = {"attack": fixture_card("attack")}
    router = SpecialistRouter(
        cards=cards, specialists={"attack": FakeSpecialist(_result("attack", "T1", ()))}
    )
    plan = Plan(
        request="x",
        sub_questions=[_sub("q2", "attack")],
        unsupported=[UnsupportedPart("k8s pods", "out of scope")],
        partial=True,
    )
    evidence = router.run_plan(plan)
    assert evidence.partial
    assert evidence.unsupported and evidence.unsupported[0]["description"] == "k8s pods"
    assert not evidence.ok()


def test_evidence_to_dict_round_trips_shape() -> None:
    ev = FederatedEvidence(request="x", results=[_result("attack", "T1", ("T1",))], partial=False)
    data = ev.to_dict()
    assert data["request"] == "x"
    assert data["results"][0]["records"][0]["primary_id"] == "T1"
    assert "join_index" in data and "cross_source_join_values" in data
