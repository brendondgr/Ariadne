#!/usr/bin/env python3
"""Dependent sub-question sequencing (Wk 10–11, Option B).

The federation runs a declared join's producer first, harvests its T-prefixed
join values, and injects them as the consumer's ``seed_ids`` — bounded, honest
about truncation, and skipping the consumer (abstention, not a broad unseeded
query) when the producer yields nothing. Independent plans are unchanged.
"""

from __future__ import annotations

from utils.planner.schema import JoinDeclaration, Limits, Plan, SubQuestion

from utils.specialists.concepts import concept_terms
from utils.specialists.contracts import EvidenceRecord, Provenance, SpecialistResult, SpecialistTask
from utils.specialists.federation import (
    SpecialistRouter,
    dependency_map,
    dependency_skip_result,
    execution_order,
    harvest_seed_ids,
)
from utils.specialists.gremlin.builder import GremlinQueryBuilder
from utils.specialists.resolve import resolve
from utils.specialists.tests._fixtures import fixture_card

from utils.synthesis.config import SynthesisConfig
from utils.synthesis.factory import synthesize


class FakeSpecialist:
    def __init__(self, result: SpecialistResult) -> None:
        self._result = result
        self.tasks: list[SpecialistTask] = []

    def run(self, task: SpecialistTask) -> SpecialistResult:
        self.tasks.append(task)
        self._result.task = task
        return self._result


def _prov(dataset: str, backend: str) -> Provenance:
    return Provenance(
        source=dataset, dataset=dataset, backend=backend,
        query="q", record_id="r1", timestamp="2026-07-06T00:00:00+00:00",
    )


def _result(source: str, join_values: tuple[str, ...], ok: bool = True) -> SpecialistResult:
    backend = "neo4j" if source == "attack" else "gremlin"
    records = [
        EvidenceRecord(
            primary_id=f"{source}-{i}", id_scheme=f"{source}-id", label="X",
            name=f"{source}-{i}", join_values=(v,), provenance=_prov(source, backend),
        )
        for i, v in enumerate(join_values)
    ]
    return SpecialistResult(
        task=SpecialistTask(sub_question_id="", source=source, text=""),
        query="q" if ok else "", records=records, summary="s", ok=ok, partial=not ok,
    )


def _sub(qid: str, source: str, join_key: str | None = "attack-technique-id") -> SubQuestion:
    return SubQuestion(
        id=qid, source=source, text=f"about {source}",
        entities=["AttackPattern"] if source == "capec" else ["Technique", "Mitigation"],
        limits=Limits(3, 1000, 5000), join_key=join_key,
    )


def _joined_plan() -> Plan:
    # Consumer (attack) deliberately listed FIRST: ordering must be derived
    # from the join, not the plan's list order.
    return Plan(
        request="credential theft",
        sub_questions=[_sub("q-attack", "attack"), _sub("q-capec", "capec")],
        joins=[JoinDeclaration("attack-technique-id", ["capec", "attack"])],
    )


def test_dependency_derived_from_canonical_key_endpoints() -> None:
    plan = _joined_plan()
    # CAPEC reaches the key via MAPS_TO (producer); ATT&CK carries it natively.
    assert dependency_map(plan) == {"q-attack": ("q-capec",)}
    assert [sq.id for sq in execution_order(plan)] == ["q-capec", "q-attack"]


def test_independent_plan_order_unchanged() -> None:
    plan = Plan(
        request="two independent asks",
        sub_questions=[_sub("q1", "attack", None), _sub("q2", "capec", None)],
    )
    assert dependency_map(plan) == {}
    assert [sq.id for sq in execution_order(plan)] == ["q1", "q2"]


def test_producer_join_values_seed_the_consumer() -> None:
    cards = {"attack": fixture_card("attack"), "capec": fixture_card("capec")}
    capec = FakeSpecialist(_result("capec", ("T1110.001", "T1555", "T1110.001")))
    attack = FakeSpecialist(_result("attack", ("T1110.001",)))
    router = SpecialistRouter(cards=cards, specialists={"attack": attack, "capec": capec})

    evidence = router.run_plan(_joined_plan())

    assert len(capec.tasks) == 1 and capec.tasks[0].seed_ids == ()
    assert len(attack.tasks) == 1
    assert attack.tasks[0].seed_ids == ("T1110.001", "T1555")  # deduped, sorted
    assert evidence.sequencing == [
        {"consumer": "q-attack", "producer": "q-capec",
         "seed_count": 2, "truncated": False, "skipped": None}
    ]


def test_zero_producer_join_values_skips_consumer_honestly() -> None:
    cards = {"attack": fixture_card("attack"), "capec": fixture_card("capec")}
    capec = FakeSpecialist(_result("capec", ()))  # clean but empty
    attack = FakeSpecialist(_result("attack", ("T1110.001",)))
    router = SpecialistRouter(cards=cards, specialists={"attack": attack, "capec": capec})

    evidence = router.run_plan(_joined_plan())

    assert attack.tasks == [], "consumer must NOT run a broad unseeded query"
    consumer = next(r for r in evidence.results if r.task.source == "attack")
    assert consumer.ok and not consumer.records and consumer.query == ""
    assert any(t.step == "dependency" for t in consumer.traces)

    # The synthesis empty-source path renders it as an honest abstention
    # naming the dependency, with no invented query proof.
    answer = synthesize(evidence, SynthesisConfig(llm_enabled=False))
    abst = [a for a in answer.abstentions if a.source == "attack"]
    assert len(abst) == 1
    assert abst[0].query == ""
    assert "depends on" in abst[0].statement or "q-capec" in abst[0].statement


def test_failed_producer_skips_consumer() -> None:
    cards = {"attack": fixture_card("attack"), "capec": fixture_card("capec")}
    capec = FakeSpecialist(_result("capec", (), ok=False))
    attack = FakeSpecialist(_result("attack", ("T1110.001",)))
    router = SpecialistRouter(cards=cards, specialists={"attack": attack, "capec": capec})

    evidence = router.run_plan(_joined_plan())
    assert attack.tasks == []
    assert evidence.partial is True  # failed producer makes the bundle partial
    assert evidence.sequencing[0]["skipped"].startswith("it failed")


def test_seed_harvest_is_bounded_with_honest_truncation() -> None:
    producer = _result("capec", tuple(f"T{1000 + i}" for i in range(30)))
    seeds, truncated = harvest_seed_ids(producer, cap=10)
    assert len(seeds) == 10 and truncated is True
    seeds_all, truncated_all = harvest_seed_ids(producer, cap=1000)
    assert len(seeds_all) == 30 and truncated_all is False


def test_dependency_skip_result_shape() -> None:
    task = SpecialistTask(sub_question_id="q2", source="attack", text="t")
    result = dependency_skip_result(task, producer_id="q1", reason="it returned no join values")
    assert result.ok and not result.partial and result.query == "" and not result.records
    assert "q1" in result.summary


# -- concept scoping (the producer side of the credential-theft flow) --------


def test_concept_terms_detected_from_committed_vocabulary() -> None:
    assert concept_terms("Which CAPEC patterns related to credential theft map?") == (
        "credential", "password", "authentication",
    )
    assert concept_terms("techniques used by G0016") == ()


def test_gremlin_maps_to_scoped_by_concept() -> None:
    card = fixture_card("capec")
    task = SpecialistTask(
        sub_question_id="q1", source="capec",
        text="find credential theft patterns and mapped ATT&CK ids",
        entities=("AttackPattern", "MAPS_TO", "TaxonomyEntry"),
        join_key="attack-technique-id",
    )
    draft = GremlinQueryBuilder().build(resolve(task, card))
    assert draft.template == "capec_maps_to"
    assert 'TextP.regex("(?i).*(credential|password|authentication).*")' in draft.query

    # Without a recognized concept the broad scan is unchanged.
    broad = SpecialistTask(
        sub_question_id="q1", source="capec",
        text="which patterns map to ATT&CK techniques",
        entities=("AttackPattern", "MAPS_TO", "TaxonomyEntry"),
        join_key="attack-technique-id",
    )
    draft2 = GremlinQueryBuilder().build(resolve(broad, card))
    assert "TextP" not in draft2.query


# -- routing by what each store can express (EXP-2026-09-018, I-11) ----------


def _bridge_sub(qid: str, source: str, text: str, entities: list[str]) -> SubQuestion:
    return SubQuestion(
        id=qid, source=source, text=text, entities=entities,
        limits=Limits(3, 1000, 5000), join_key="attack-technique-id",
    )


def _reversed_plan() -> Plan:
    """"Which CAPEC patterns correspond to T1555, and which CWE do those exploit"."""
    return Plan(
        request=(
            "Which CAPEC attack patterns correspond to Credentials from Password "
            "Stores (T1555), and which CWE weaknesses do those exploit?"
        ),
        sub_questions=[
            _bridge_sub("q1", "attack",
                        "For T1555: the CAPEC attack patterns that correspond to it.",
                        ["Technique", "MAPS_TO", "AttackPattern"]),
            _bridge_sub("q2", "capec",
                        "For each of those: the CWE weaknesses each of those exploits.",
                        ["AttackPattern", "EXPLOITS_WEAKNESS", "Weakness"]),
        ],
        joins=[JoinDeclaration("attack-technique-id", ["capec", "attack"])],
    )


def test_a_hop_goes_to_the_store_that_models_most_of_what_it_names() -> None:
    from utils.specialists.federation import reroute_source, rerouted

    cards = {"attack": fixture_card("attack"), "capec": fixture_card("capec")}
    first, second = _reversed_plan().sub_questions
    # NO card models all three entities — the hop spans both catalogues — so the
    # test has to be comparative rather than all-or-nothing.
    assert cards["capec"].unknown_entities(list(first.entities)) == ["Technique"]
    assert reroute_source(first, cards) == "capec"
    moved = rerouted(first, cards)
    assert moved is not None and moved.source == "capec"
    # `Technique` is the far end of the declared join, not a boundary: carrying
    # it would trip the specialist's schema refusal on the way to a question
    # CAPEC can answer.
    assert "Technique" not in moved.entities
    # A hop its own store fully models is never moved.
    assert reroute_source(second, cards) is None


def test_the_declared_join_direction_flips_for_a_self_anchored_hop() -> None:
    plan = _reversed_plan()
    # The key says CAPEC produces and ATT&CK consumes. Here the ATT&CK-side hop
    # names the only identifier in the question and the CAPEC-side hop says
    # "each of those", so the declared direction is backwards.
    assert dependency_map(plan) == {"q2": ("q1",)}
    assert [sq.id for sq in execution_order(plan)] == ["q1", "q2"]


def test_two_hops_in_one_store_still_chain() -> None:
    """`dependency_map` is keyed by source, so a same-store join declared nothing."""
    plan = Plan(
        request="Which patterns sit inside CAPEC-513, and what do those map to?",
        sub_questions=[
            _bridge_sub("q1", "capec", "For CAPEC-513: the patterns it contains.",
                        ["Category", "MEMBER_OF", "AttackPattern"]),
            _bridge_sub("q2", "capec", "For each of those: the techniques each corresponds to.",
                        ["AttackPattern", "MAPS_TO", "Technique"]),
        ],
        joins=[JoinDeclaration("attack-technique-id", ["capec", "attack"])],
    )
    assert dependency_map(plan) == {"q2": ("q1",)}


def test_a_same_store_consumer_takes_the_ids_of_the_label_it_anchors_on() -> None:
    """The category's 52 members, not the category the walk anchored on."""
    anchor = EvidenceRecord(
        primary_id="CAPEC-513", id_scheme="capec-id", label="Category", name="Software",
        related=[
            {"id": "CAPEC-272", "name": "Protocol Manipulation", "label": "AttackPattern"},
            {"id": "CAPEC-100", "name": "Overflow Buffers", "label": "AttackPattern"},
        ],
        provenance=_prov("capec", "gremlin"),
    )
    producer = SpecialistResult(
        task=SpecialistTask(sub_question_id="q1", source="capec", text=""),
        query="q", records=[anchor], summary="s", ok=True,
    )
    seeds, _ = harvest_seed_ids(
        producer, cap=100, prefer_primary_ids=True, wanted_labels=["AttackPattern"]
    )
    assert seeds == ("CAPEC-100", "CAPEC-272")
    # With no label to steer by it falls back to the anchors themselves.
    plain, _ = harvest_seed_ids(producer, cap=100, prefer_primary_ids=True)
    assert plain == ("CAPEC-513",)


def test_two_independent_asks_are_not_chained_by_adjacency() -> None:
    from utils.specialists.federation import refers_back

    plan = Plan(
        request="two independent asks",
        sub_questions=[_sub("q1", "attack", None), _sub("q2", "capec", None)],
    )
    assert dependency_map(plan) == {}
    assert refers_back(plan.sub_questions[1]) is False
