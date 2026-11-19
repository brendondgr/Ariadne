"""The typed planner (EXP-2026-11-015 build item 6) with a scripted model.

Every flow the protocol names: validity at first emission, a coercion fix, the
one repair turn fixing a refusal, a step still refused after it (dropped,
counted, an unsupported part, never floored), the four-call catalog budget, the
two prompt modes, and the fallback on an unusable reply. Plus the contract that
keeps every English plan byte-identical: no ``step`` and no ``typed`` key unless
the typed planner wrote one.

The catalogs come from the committed source cards and the entity index from
``data/graphs``; nothing here reaches a store or a model.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils.agent.tests.scripted import ScriptedModel
from utils.planner.schema import Limits, Plan, SubQuestion
from utils.specialists.contracts import SpecialistTask
from utils.specialists.signals import TypedStep, derive_signals, step_signals

REPO = Path(__file__).resolve().parents[3]
pytestmark = pytest.mark.skipif(
    not (REPO / "data" / "source_cards" / "attack.json").exists()
    or not (REPO / "data" / "graphs" / "attack" / "canonical" / "nodes.jsonl").exists(),
    reason="needs the ATT&CK and CAPEC source cards and canonical graphs under data/",
)


@pytest.fixture(scope="module")
def cards():
    from utils.config import load_env
    from utils.planner.cards import load_source_cards

    load_env()
    return load_source_cards(REPO / "data")


class _Live:
    def __init__(self, live):
        self._live = set(live)

    def is_live(self, ds):
        return ds in self._live


def _anchor_label(cards, graph):
    """A label with at least one outbound relation option, and that option (from the catalog)."""
    from utils.planner.typed import catalogs_for

    cat = catalogs_for(cards)[graph]
    for lab in cat.labels():
        opts = [o for o in cat.options(lab) if o.direction == "out" and not o.repeating]
        if opts:
            return lab, opts[0]
    raise AssertionError("no label with an outbound option")


def _entity(cards, graph, label):
    """One indexed entity id of ``label`` (from the name index; no store)."""
    from utils.specialists.schema.namesearch import index_for

    for eid, lab, _name, _toks in index_for(graph)._docs:  # noqa: SLF001
        if lab == label:
            return eid
    pytest.skip(f"no indexed {label} in {graph}")


def _step(cards, graph="attack", **over):
    lab, opt = _anchor_label(cards, graph)
    eid = _entity(cards, graph, lab)
    step = {"id": "q1", "graph": graph, "kind": "expand", "anchor": {"id": eid}, "anchor_label": lab,
            "path": [{"relation": opt.relation, "direction": "out", "target_label": opt.target}]}
    step.update(over)
    return step, lab, opt, eid


def _plan_json(*steps, **extra):
    return json.dumps({"steps": list(steps), "unsupported": [], "assumptions": [], **extra})


def _run(cards, script, mode="lazy"):
    from utils.planner.typed import TypedPlanner

    model = ScriptedModel(script)
    plan, log = TypedPlanner(model, mode).plan("a question", cards, {"attack", "capec"})
    return plan, log, model


class TestFirstEmission:
    def test_a_valid_plan_is_executed_as_a_typed_step_with_the_text_blank(self, cards):
        step, lab, opt, eid = _step(cards)
        plan, log, _ = _run(cards, [_plan_json(step)])
        assert log.valid_first and log.valid_first_raw and not log.repair_used
        assert log.still_refused == 0 and log.model_calls == 1
        [sq] = plan.sub_questions
        assert sq.text == "" and sq.source == "attack"
        assert sq.step["anchor_ids"] == [eid]
        assert sq.step["hops"] == [{"relation": opt.relation, "direction": "out", "target_label": opt.target}]
        assert sq.entities == [x for x in dict.fromkeys([lab, opt.relation, opt.target])]

    def test_a_near_miss_is_coerced_and_recorded(self, cards):
        step, _lab, opt, _ = _step(cards)
        step["path"][0]["relation"] = opt.relation.lower()
        plan, log, _ = _run(cards, [_plan_json(step)])
        assert log.valid_first and not log.valid_first_raw
        assert plan.sub_questions[0].step["hops"][0]["relation"] == opt.relation
        fixes = {(f["field"], f["filled_by"]) for f in log.as_dict()["coercions"]}
        assert ("path[0].relation", "case_separator") in fixes

    def test_catalog_calls_are_counted_and_capped_at_four(self, cards):
        step, *_ = _step(cards)
        five = [("find_schema", {"text": f"words {i}"}) for i in range(5)]
        plan, log, model = _run(cards, [five, _plan_json(step)])
        # Four ran; the fifth was refused with the budget envelope, and the next
        # turn was offered no tools, so it is the emission.
        assert len(log.catalog_calls) == 4 and log.model_calls == 2
        assert plan.sub_questions and log.valid_first

    def test_one_call_per_turn_still_stops_at_four(self, cards):
        step, *_ = _step(cards)
        turns = [[("describe", {"target": f"x{i}"})] for i in range(4)]
        plan, log, _ = _run(cards, [*turns, _plan_json(step)])
        assert len(log.catalog_calls) == 4 and log.model_calls == 5 and plan.sub_questions

    def test_prompt_modes_differ_only_in_how_much_card_they_show(self, cards):
        from utils.planner.typed import build_messages, catalogs_for

        cats = catalogs_for(cards)
        lazy = build_messages("q", cats, "lazy")[1]["content"]
        full = build_messages("q", cats, "full")[1]["content"]
        assert "Call find_schema or describe" in lazy and "properties:" not in lazy
        assert "properties:" in full and len(full) > 5 * len(lazy)


    def test_an_omitted_target_keeps_every_label_the_hop_reaches(self, cards):
        from utils.planner.typed import catalogs_for

        cat = catalogs_for(cards)["attack"]
        multi = [(lab, rel, d) for lab in cat.labels()
                 for (rel, d) in {(o.relation, o.direction) for o in cat.options(lab)}
                 if len({o.target for o in cat.options(lab, rel, d)}) > 1]
        if not multi:
            pytest.skip("no relation reaching several labels")
        lab, rel, d = multi[0]
        eid = _entity(cards, "attack", lab)
        step = {"id": "q1", "graph": "attack", "kind": "expand", "anchor": {"id": eid}, "anchor_label": lab,
                "path": [{"relation": rel, "direction": d}]}
        plan, log, _ = _run(cards, [_plan_json(step)])
        hop = plan.sub_questions[0].step["hops"][0]
        assert hop == {"relation": rel, "direction": d, "target_label": ""}
        assert any(f["filled_by"] == "all_targets" for f in log.coercions)


class TestRepair:
    def test_one_repair_turn_fixes_a_refused_step(self, cards):
        step, _lab, opt, _ = _step(cards)
        bad = dict(step, path=[{"relation": "NOT_A_RELATION_OF_ANY_CARD", "direction": "out"}])
        plan, log, model = _run(cards, [_plan_json(bad), _plan_json(step)])
        assert not log.valid_first and log.repair_used and log.fixed_by_repair
        assert log.still_refused == 0 and log.model_calls == 2
        assert plan.sub_questions[0].step["hops"][0]["relation"] == opt.relation
        # The repair turn carried the envelope, with its fix naming valid options.
        refusal = [r for r in log.refusals if not r["final"]][0]
        assert refusal["code"] in ("not_in_card", "invalid_request") and refusal["fix"]

    def test_a_step_still_refused_is_dropped_and_becomes_unsupported(self, cards):
        step, *_ = _step(cards)
        bad = dict(step, path=[{"relation": "NOT_A_RELATION_OF_ANY_CARD", "direction": "out"}])
        plan, log, _ = _run(cards, [_plan_json(bad), _plan_json(bad)])
        assert log.repair_used and not log.fixed_by_repair and log.still_refused == 1
        assert plan.sub_questions == [] and plan.partial
        assert any("could not be expressed" in u.description for u in plan.unsupported)

    def test_a_refused_plan_is_not_floored_by_the_deterministic_drafter(self, cards):
        from utils.planner.typed import TypedDrafter

        step, *_ = _step(cards)
        bad = dict(step, path=[{"relation": "NOT_A_RELATION_OF_ANY_CARD", "direction": "out"}])
        drafter = TypedDrafter(ScriptedModel([_plan_json(bad), _plan_json(bad)]), "lazy")
        plan = drafter.draft("which ones?", cards, _Live({"attack", "capec"}))
        assert plan.sub_questions == [] and drafter.logs[-1].get("fallback") is None
        assert plan.typed["still_refused"] == 1

    def test_an_unusable_reply_falls_back_like_the_english_drafter(self, cards):
        from utils.planner.typed import TypedDrafter

        drafter = TypedDrafter(ScriptedModel(["no json here", "still none"]), "lazy")
        plan = drafter.draft("What is T1059?", cards, _Live({"attack", "capec"}))
        assert drafter.logs[-1]["fallback"] == "unavailable"
        assert drafter.last_used == "DeterministicDrafter"
        assert all(sq.step is None for sq in plan.sub_questions)


class TestValidation:
    def test_an_unknown_id_is_refused_with_a_fix(self, cards):
        step, *_ = _step(cards, anchor={"id": "NOT-AN-ID-999"})
        plan, log, _ = _run(cards, [_plan_json(step), _plan_json(step)])
        assert log.still_refused == 1
        final = [r for r in log.refusals if r["final"]][0]
        assert final["code"] == "not_in_card" and "resolve_entity" in final["fix"]

    def test_depth_is_refused_on_a_relation_that_does_not_repeat(self, cards):
        step, *_ = _step(cards, depth=3)
        plan, log, _ = _run(cards, [_plan_json(step), _plan_json(step)])
        assert log.still_refused == 1
        assert [r for r in log.refusals if r["final"]][0]["detail"].endswith("so depth is 1")


    def test_common_needs_two_anchors_and_keeps_them(self, cards):
        from utils.planner.typed import catalogs_for

        labs = [lab for lab in catalogs_for(cards)["attack"].labels()][:2]
        ids = [_entity(cards, "attack", lab) for lab in labs]
        one = {"id": "q1", "graph": "attack", "kind": "common", "anchor": {"id": ids[:1]}}
        both = {"id": "q1", "graph": "attack", "kind": "common", "anchor": {"id": ids}}
        plan, log, _ = _run(cards, [_plan_json(one), _plan_json(both)])
        assert log.repair_used and log.fixed_by_repair
        assert plan.sub_questions[0].step["kind"] == "common"
        assert plan.sub_questions[0].step["anchor_ids"] == ids

    def test_a_same_graph_from_step_is_refused_with_the_path_fix(self, cards):
        step, lab, opt, _ = _step(cards)
        second = {"id": "q2", "graph": "attack", "kind": "expand", "anchor": {"from_step": "q1", "label": opt.target},
                  "path": [{"relation": opt.relation, "direction": "in", "target_label": lab}]}
        plan, log, _ = _run(cards, [_plan_json(step, second), _plan_json(step)])
        first = [r for r in log.refusals if not r["final"]][0]
        assert "same graph" in first["detail"] and "path of step q1" in first["fix"]
        assert log.fixed_by_repair

    def test_resolve_entity_answers_an_id_from_the_entity_index(self, cards):
        from utils.planner.typed import PlanContext, _run_tool, catalogs_for
        import tempfile

        lab, _ = _anchor_label(cards, "attack")
        eid = _entity(cards, "attack", lab)
        with tempfile.TemporaryDirectory() as d:
            ctx = PlanContext(cards, catalogs_for(cards), Path(d))
            try:
                got = _run_tool(ctx, "resolve_entity", {"text": eid.lower()})
            finally:
                ctx.close()
        assert got["ok"] and got["ids"] == [eid] and got["kind"] == lab and got["match"] == "id"


class TestByteIdentityWhenTypedIsOff:
    def test_an_english_sub_question_serialises_exactly_as_before(self):
        sq = SubQuestion("q1", "attack", "What mitigates T1059?", ["Technique"], Limits(3, 1000, 5000))
        d = sq.to_dict()
        assert list(d) == ["id", "source", "text", "entities", "limits", "join_key", "rationale"]
        assert SubQuestion.from_dict(d) == sq and sq.seed_ids == ()
        plan = Plan(request="r", sub_questions=[sq])
        assert "typed" not in plan.to_dict() and "step" not in json.dumps(plan.to_dict())
        assert Plan.from_dict(plan.to_dict()).to_dict() == plan.to_dict()

    def test_an_english_task_derives_its_signals_from_the_text(self):
        sq = SubQuestion("q1", "attack", "What mitigates T1059?", ["Technique"], Limits(3, 1000, 5000))
        task = SpecialistTask.from_sub_question(sq)
        assert task.signals == derive_signals(sq.text)
        assert "step" not in task.signals.to_dict()

    def test_a_typed_task_reads_no_words(self):
        step = TypedStep(kind="expand", anchor_label="Technique", anchor_ids=("T1059",))
        sq = SubQuestion("q1", "attack", "", ["Technique"], Limits(3, 1000, 5000), step=step.to_dict())
        task = SpecialistTask.from_sub_question(sq)
        assert task.text == "" and task.seed_ids == ("T1059",)
        assert task.signals == step_signals(step)
        s = task.signals
        assert not (s.name_candidates or s.name_tokens or s.question_words or s.mentioned_values)
        assert s.step == step and s.attack_ids == ("T1059",)
        # And it survives a round trip through the task's JSON.
        assert SpecialistTask.from_dict(task.to_dict()).signals == s
