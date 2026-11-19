"""The builders execute a typed step exactly as written (EXP-2026-11-015 item 6).

A typed step names its anchor ids, each hop's relation, direction and target
label, a depth and a filter. These tests compile steps with both builders and
check that every stated choice reaches the query, that the draft passes the
source's own validator, and that a task without a step never takes the typed
path. No store is reached.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from utils.specialists.contracts import SpecialistTask
from utils.specialists.resolve import resolve
from utils.specialists.signals import TypedHop, TypedStep, step_signals

REPO = Path(__file__).resolve().parents[3]
pytestmark = pytest.mark.skipif(
    not (REPO / "data" / "source_cards" / "attack.json").exists(),
    reason="needs the committed source cards under data/source_cards",
)

LIMITS = {"max_traversal_depth": 3, "max_result_rows": 1000, "query_timeout_ms": 5000}


@pytest.fixture(scope="module")
def cards():
    from utils.config import load_env
    from utils.planner.cards import load_source_cards

    load_env()
    return load_source_cards(REPO / "data")


@pytest.fixture(scope="module")
def catalogs(cards):
    from utils.planner.typed import catalogs_for

    return catalogs_for(cards)


def _task(source: str, step: TypedStep) -> SpecialistTask:
    return SpecialistTask(sub_question_id="q1", source=source, text="", entities=tuple(step.entities()),
                          limits=dict(LIMITS), seed_ids=step.anchor_ids, signals=step_signals(step))


def _option(cat, *, direction: str, repeating: bool | None = None):
    for lab in cat.labels():
        for o in cat.options(lab):
            if o.direction == direction and (repeating is None or o.repeating == repeating):
                return lab, o
    pytest.skip(f"no {direction} option in {cat.name}")


def _build(source: str, step: TypedStep, cards):
    from utils.specialists.cypher.builder import CypherQueryBuilder
    from utils.specialists.cypher.validator import CypherValidator
    from utils.specialists.gremlin.builder import GremlinQueryBuilder
    from utils.specialists.gremlin.validator import GremlinValidator

    card = cards[source]
    resolved = resolve(_task(source, step), card)
    if card.runtime_backend == "gremlin":
        builder, validator = GremlinQueryBuilder(), GremlinValidator()
    else:
        builder, validator = CypherQueryBuilder(), CypherValidator()
    draft = builder.build(resolved, None)
    return draft, validator.validate(draft, card, LIMITS)


class TestCypher:
    def test_an_inbound_hop_keeps_its_direction_and_target_label(self, cards, catalogs):
        lab, o = _option(catalogs["attack"], direction="in")
        step = TypedStep("expand", lab, ("X0001",), (TypedHop(o.relation, "in", o.target),))
        draft, gate = _build("attack", step, cards)
        assert draft.template == "typed_step"
        assert f"<-[:{o.relation}]-(t0:{o.target})" in draft.query
        assert draft.params["ids"] == ["X0001"]
        assert gate.ok, gate.reasons

    def test_a_two_hop_path_collects_the_intermediate_and_the_end(self, cards, catalogs):
        cat = catalogs["attack"]
        pairs = [(lab, a, b) for lab in cat.labels() for a in cat.options(lab) if not a.repeating
                 for b in cat.options(a.target) if b.target not in (lab, a.target)]
        if not pairs:
            pytest.skip("no two-hop path")
        lab, first, second = pairs[0]
        step = TypedStep("expand", lab, ("X0001",), (TypedHop(first.relation, first.direction, first.target),
                                                     TypedHop(second.relation, second.direction, second.target)))
        draft, gate = _build("attack", step, cards)
        assert "AS k0" in draft.query and "AS k1" in draft.query
        assert gate.ok, gate.reasons

    def test_a_filter_restricts_only_the_last_label(self, cards):
        step = TypedStep("expand", "Software", ("S0001",), (TypedHop("USES", "out", "Technique"),),
                         filter=("x_mitre_platforms", "Windows"))
        draft, gate = _build("attack", step, cards)
        assert "$filterValue IN coalesce(t0.`x_mitre_platforms`, [])" in draft.query
        assert draft.params["filterValue"] == "Windows"
        assert gate.ok, gate.reasons

    def test_describe_and_scan_reuse_the_existing_compilers(self, cards):
        d, _ = _build("attack", TypedStep("describe", "Technique", ("T1059",)), cards)
        s, _ = _build("attack", TypedStep("scan", "Tactic"), cards)
        assert d.template == "describe" and s.template == "label_scan"


    def test_common_is_the_existing_intersection_primitive(self, cards):
        d, gate = _build("attack", TypedStep("common", "Tactic", ("TA0006", "M1027")), cards)
        assert d.template == "generic_intersect" and gate.ok, gate.reasons


class TestGremlin:
    def test_a_repeating_hop_is_one_bounded_repeat_in_the_stated_direction(self, cards, catalogs):
        lab, o = _option(catalogs["capec"], direction="out", repeating=True)
        step = TypedStep("expand", lab, ("CAPEC-66",), (TypedHop(o.relation, "out", o.target),), depth=3)
        draft, gate = _build("capec", step, cards)
        from utils.graph_loader.stores.gremlin import gremlin_edge_label

        assert f'repeat(__.out("{gremlin_edge_label(o.relation)}")).times(3)' in draft.query
        assert f'hasLabel("{o.target}")' in draft.query
        assert gate.ok, gate.reasons

    def test_an_inbound_hop_is_in(self, cards, catalogs):
        lab, o = _option(catalogs["capec"], direction="in", repeating=False)
        step = TypedStep("expand", lab, ("CAPEC-66",), (TypedHop(o.relation, "in", o.target),))
        draft, gate = _build("capec", step, cards)
        from utils.graph_loader.stores.gremlin import gremlin_edge_label

        assert f'in("{gremlin_edge_label(o.relation)}").hasLabel("{o.target}")' in draft.query
        assert draft.template == "typed_step" and gate.ok, gate.reasons


def test_a_joined_step_over_the_join_edge_is_left_to_the_bridge(cards):
    """A producer walking the declared join edge must yield join values; the engine's bridge does."""
    from utils.specialists.gremlin.builder import GremlinQueryBuilder
    from utils.planner.join_keys import CANONICAL_JOIN_KEYS

    key = next((k for k in CANONICAL_JOIN_KEYS
                if any(e.dataset == "capec" and e.via_edge for e in k.endpoints)), None)
    if key is None:
        pytest.skip("no join key produced by this source")
    via = next(e.via_edge for e in key.endpoints if e.dataset == "capec")
    step = TypedStep("expand", "AttackPattern", ("CAPEC-98",), (TypedHop(via, "out", "TaxonomyEntry"),))
    task = SpecialistTask(sub_question_id="q1", source="capec", text="", entities=tuple(step.entities()),
                          limits=dict(LIMITS), join_key=key.name, seed_ids=step.anchor_ids,
                          signals=step_signals(step))
    resolved = resolve(task, cards["capec"])
    assert GremlinQueryBuilder()._typed_step(resolved) is None  # noqa: SLF001
    assert GremlinQueryBuilder().build(resolved, None, generic=True).template != "typed_step"


def test_a_task_without_a_step_never_takes_the_typed_path(cards):
    from utils.specialists.cypher.builder import CypherQueryBuilder

    task = SpecialistTask(sub_question_id="q1", source="attack", text="What mitigates T1059?",
                          entities=("Technique", "MITIGATES", "Mitigation"), limits=dict(LIMITS))
    assert task.signals.step is None
    for generic in (True, False):
        draft = CypherQueryBuilder().build(resolve(task, cards["attack"]), None, generic=generic)
        assert draft.template != "typed_step"
