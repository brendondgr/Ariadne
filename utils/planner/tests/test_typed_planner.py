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

    def test_a_same_graph_from_step_continues_the_path_it_starts_from(self, cards):
        """EXP-2026-11-018: the refusal's own fix ("add this step's hops to the path of step q1"), applied."""
        step, lab, opt, _ = _step(cards)
        second = {"id": "q2", "graph": "attack", "kind": "expand", "anchor": {"from_step": "q1", "label": opt.target},
                  "path": [{"relation": opt.relation, "direction": "in", "target_label": lab}]}
        plan, log, _ = _run(cards, [_plan_json(step, second)])
        assert log.valid_first and not log.repair_used
        merged = plan.sub_questions[1].step
        assert merged["anchor_ids"] == plan.sub_questions[0].step["anchor_ids"]
        assert [h["relation"] for h in merged["hops"]] == [opt.relation, opt.relation]
        assert any(f["filled_by"] == "same_graph_merge" for f in log.coercions)

    def test_a_same_graph_from_step_after_a_filter_is_still_refused_with_the_path_fix(self, cards):
        """A filter sits on the first step's last label; a longer path would move it, so no merge."""
        step, lab, opt, _ = _step(cards)
        props = sorted(cards["attack"].label_property_keys(opt.target) or ())
        if not props or not opt.target:
            pytest.skip("no filterable property on the hop's target")
        filtered = dict(step, filter={"property": props[0], "value": "x"})
        second = {"id": "q2", "graph": "attack", "kind": "expand", "anchor": {"from_step": "q1", "label": opt.target},
                  "path": [{"relation": opt.relation, "direction": "in", "target_label": lab}]}
        plan, log, _ = _run(cards, [_plan_json(filtered, second), _plan_json(filtered)])
        first = [r for r in log.refusals if not r["final"]][0]
        assert "same graph" in first["detail"] and "path of step q1" in first["fix"]

    def test_an_expand_with_no_path_is_a_describe(self, cards):
        step, *_ = _step(cards)
        bare = {k: v for k, v in step.items() if k != "path"}
        plan, log, _ = _run(cards, [_plan_json(bare)])
        assert log.valid_first and plan.sub_questions[0].step["kind"] == "describe"
        assert any(f["filled_by"] == "no_path" for f in log.coercions)

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


class TestNoAnchorlessScan:
    """EXP-2026-11-016: a named entity that does not resolve is never replaced by a whole-label scan."""

    @staticmethod
    def _ctx(cards, request):
        import tempfile

        from utils.planner.typed import PlanContext, catalogs_for

        d = tempfile.mkdtemp(prefix="typed-test-")
        return PlanContext(cards, catalogs_for(cards), Path(d), request=request)

    def test_a_scan_is_refused_when_the_question_names_an_id(self, cards):
        from utils.planner.typed import check_step

        ctx = self._ctx(cards, "Look up nonexistent technique T9999 — must return empty, not invent.")
        try:
            c = check_step({"graph": "attack", "kind": "scan", "anchor_label": "Technique"}, 0, ctx, {})
        finally:
            ctx.close()
        assert not c.ok and "T9999" in c.refusals[0]["detail"]
        assert '{"id": "T9999"}' in c.refusals[0]["fix"]

    def test_a_scan_with_no_named_entity_is_still_accepted(self, cards):
        from utils.planner.typed import check_step

        ctx = self._ctx(cards, "List ATT&CK software entries.")
        try:
            c = check_step({"graph": "attack", "kind": "scan", "anchor_label": "Software"}, 0, ctx, {})
        finally:
            ctx.close()
        assert c.ok and c.step.kind == "scan"

    def test_a_missing_id_is_reported_as_not_found_with_the_anchor_as_its_fix(self, cards):
        from utils.planner.typed import _run_tool, check_step

        ctx = self._ctx(cards, "which ones?")
        try:
            got = _run_tool(ctx, "resolve_entity", {"text": "T9999"})
            scan = check_step({"graph": "attack", "kind": "scan", "anchor_label": "Technique"}, 0, ctx, {})
            anchored = check_step({"graph": "attack", "kind": "describe", "anchor": {"id": "T9999"}}, 0, ctx, {})
        finally:
            ctx.close()
        assert got["ok"] and got["status"] == "not_found" and got["ids"] == []
        assert "anyway" in got["fix"] and "Do not replace it with a scan" in got["fix"]
        assert not scan.ok, "a failed id lookup also blocks the scan"
        assert anchored.ok and anchored.step.anchor_ids == ("T9999",)

    def test_an_id_of_the_other_graph_is_found_there_with_a_bridge_note(self, cards):
        from utils.planner.typed import _run_tool

        tech = _entity(cards, "attack", "Technique")
        ctx = self._ctx(cards, "x")
        try:
            got = _run_tool(ctx, "resolve_entity", {"text": tech, "graph": "capec"})
        finally:
            ctx.close()
        assert got["status"] == "found" and got["graph"] == "attack" and "join key" in got["note"]

    def test_the_no_anchor_refusal_no_longer_suggests_a_scan(self, cards):
        from utils.planner.typed import check_step

        ctx = self._ctx(cards, "x")
        try:
            c = check_step({"graph": "attack", "kind": "expand", "path": []}, 0, ctx, {})
        finally:
            ctx.close()
        assert not c.ok and "scan" not in c.refusals[0]["fix"]

    def test_the_planner_repairs_a_scan_into_the_named_anchor(self, cards):
        from utils.planner.typed import TypedPlanner

        scan = {"id": "q1", "graph": "attack", "kind": "scan", "anchor_label": "Technique"}
        fixed = {"id": "q1", "graph": "attack", "kind": "describe", "anchor": {"id": "T9999"}}
        model = ScriptedModel([_plan_json(scan), _plan_json(fixed)])
        plan, log = TypedPlanner(model, "lazy").plan("Look up technique T9999.", cards, {"attack", "capec"})
        assert log.repair_used and log.fixed_by_repair
        assert plan.sub_questions[0].step["kind"] == "describe"
        assert plan.sub_questions[0].step["anchor_ids"] == ["T9999"]


class TestNoUnlinkedScan:
    """EXP-2026-11-016 follow-up: the bridge route (F-REV-06 T5) — an entity found on one graph, then
    every member of a label listed on the other — is refused with the bridged anchor as its fix."""

    @staticmethod
    def _ctx(cards, request="How do CAPEC items relate to the method where intruders pull mail from a "
                            "hosted mail server, and what is this method?"):
        return TestNoAnchorlessScan._ctx(cards, request)

    def test_a_scan_beside_an_anchored_step_on_the_joined_graph_is_refused(self, cards):
        from utils.planner.typed import check_plan

        tech = _entity(cards, "attack", "Technique")
        ctx = self._ctx(cards)
        try:
            checks, _ = check_plan({"steps": [
                {"id": "q1", "graph": "attack", "kind": "describe", "anchor": {"id": tech}},
                {"id": "q2", "graph": "capec", "kind": "scan", "anchor_label": "TaxonomyEntry"}]}, ctx)
        finally:
            ctx.close()
        assert checks[0].ok and not checks[1].ok
        env = checks[1].refusals[0]
        assert "a scan lists every TaxonomyEntry" in env["detail"]
        assert f'"anchor": {{"id": "{tech}"}}' in env["fix"] and '"anchor_label": "TaxonomyEntry"' in env["fix"]

    def test_the_order_of_the_steps_does_not_matter(self, cards):
        from utils.planner.typed import check_plan

        tech = _entity(cards, "attack", "Technique")
        ctx = self._ctx(cards)
        try:
            checks, _ = check_plan({"steps": [
                {"id": "q1", "graph": "capec", "kind": "scan", "anchor_label": "TaxonomyEntry"},
                {"id": "q2", "graph": "attack", "kind": "describe", "anchor": {"id": tech}}]}, ctx)
        finally:
            ctx.close()
        assert not checks[0].ok and checks[1].ok

    def test_the_bridged_fix_is_itself_accepted(self, cards):
        from utils.planner.typed import check_plan

        tech = _entity(cards, "attack", "Technique")
        ctx = self._ctx(cards)
        try:
            checks, _ = check_plan({"steps": [
                {"id": "q1", "graph": "attack", "kind": "describe", "anchor": {"id": tech}},
                {"id": "q2", "graph": "capec", "kind": "describe", "anchor": {"id": tech},
                 "anchor_label": "TaxonomyEntry"}]}, ctx)
        finally:
            ctx.close()
        assert all(c.ok for c in checks), [c.refusals for c in checks]
        assert checks[1].join_key

    def test_the_plan_records_which_step_each_step_starts_from(self, cards):
        """EXP-2026-11-018: the engine links consumers by ``from_step``, so the plan must carry it."""
        from utils.planner.typed import check_plan, to_plan
        from utils.specialists.federation import dependency_map

        hop = {"relation": "HAS_TECHNIQUE", "direction": "in", "target_label": "Tactic"}
        ctx = self._ctx(cards)
        try:
            checks, _ = check_plan({"steps": [
                {"id": "q1", "graph": "capec", "kind": "expand", "anchor": {"id": "CAPEC-98"},
                 "path": [{"relation": "MAPS_TO", "direction": "out", "target_label": "TaxonomyEntry"}]},
                {"id": "q2", "graph": "attack", "kind": "expand",
                 "anchor": {"from_step": "q1", "label": "Technique"}, "path": [hop]},
                {"id": "q3", "graph": "attack", "kind": "expand",
                 "anchor": {"from_step": "q1", "label": "SubTechnique"}, "path": [hop]}]}, ctx)
        finally:
            ctx.close()
        if not all(c.ok for c in checks):
            pytest.skip(f"the cards refuse this bridge: {[c.refusals for c in checks]}")
        plan = to_plan("r", checks, {}, cards, [], "lazy")
        assert [sq.step.get("from_step") for sq in plan.sub_questions] == [None, "q1", "q1"]
        assert dependency_map(plan) == {"q2": ("q1",), "q3": ("q1",)}

    def test_a_scan_alone_or_beside_a_same_graph_anchor_is_still_accepted(self, cards):
        from utils.planner.typed import check_plan

        tech = _entity(cards, "attack", "Technique")
        ctx = self._ctx(cards, "List every ATT&CK tactic.")
        try:
            alone, _ = check_plan({"steps": [{"id": "q1", "graph": "attack", "kind": "scan",
                                              "anchor_label": "Tactic"}]}, ctx)
            same, _ = check_plan({"steps": [
                {"id": "q1", "graph": "attack", "kind": "describe", "anchor": {"id": tech}},
                {"id": "q2", "graph": "attack", "kind": "scan", "anchor_label": "Tactic"}]}, ctx)
        finally:
            ctx.close()
        assert alone[0].ok and all(c.ok for c in same)

    def test_a_step_started_from_a_refused_scan_is_refused_with_it(self, cards):
        from utils.planner.typed import check_plan

        tech = _entity(cards, "attack", "Technique")
        ctx = self._ctx(cards)
        try:
            checks, _ = check_plan({"steps": [
                {"id": "q1", "graph": "attack", "kind": "describe", "anchor": {"id": tech}},
                {"id": "q2", "graph": "capec", "kind": "scan", "anchor_label": "TaxonomyEntry"},
                {"id": "q3", "graph": "attack", "kind": "describe", "anchor": {"from_step": "q2", "label": "Technique"}}]},
                ctx)
        finally:
            ctx.close()
        assert checks[0].ok and not checks[1].ok
        assert not checks[2].ok or checks[2].from_step is None  # refused with q2, or never a from_step at all

    def test_the_same_graph_from_step_refusal_now_says_how_to_bridge(self, cards):
        from utils.planner.typed import check_plan

        tech = _entity(cards, "attack", "Technique")
        ctx = self._ctx(cards)
        try:
            checks, _ = check_plan({"steps": [
                {"id": "q1", "graph": "attack", "kind": "describe", "anchor": {"id": tech}},
                {"id": "q2", "graph": "capec", "kind": "describe", "anchor": {"id": tech},
                 "anchor_label": "TaxonomyEntry"},
                {"id": "q3", "graph": "capec", "kind": "describe",
                 "anchor": {"from_step": "q2", "label": "AttackPattern"}}]}, ctx)
        finally:
            ctx.close()
        env = checks[2].refusals[0]
        assert "is on the same graph" in env["detail"]
        assert f'"anchor": {{"id": "{tech}"}}' in env["fix"] and "join key" in env["fix"]

    def test_a_scan_that_drops_a_found_entity_is_refused(self, cards):
        """F-REV-06 T3 (T-full, spot-check): resolve_entity found the technique, the plan only scans CAPEC."""
        from utils.planner.typed import _run_tool, check_plan

        ctx = self._ctx(cards, "Which CAPEC items correspond to Remote Email Collection, and what does that cover?")
        try:
            got = _run_tool(ctx, "resolve_entity", {"text": "Remote Email Collection", "graph": "attack"})
            if got.get("status") != "found":
                pytest.skip("the name index does not resolve 'Remote Email Collection'")
            eid = got["ids"][0]
            scan, _ = check_plan({"steps": [{"id": "q1", "graph": "capec", "kind": "scan",
                                             "anchor_label": "TaxonomyEntry"}]}, ctx)
            used, _ = check_plan({"steps": [
                {"id": "q1", "graph": "attack", "kind": "describe", "anchor": {"id": eid}},
                {"id": "q2", "graph": "capec", "kind": "describe", "anchor": {"id": eid},
                 "anchor_label": "TaxonomyEntry"}]}, ctx)
        finally:
            ctx.close()
        assert not scan[0].ok
        env = scan[0].refusals[0]
        assert "a scan lists every TaxonomyEntry" in env["detail"]
        assert f'"anchor": {{"id": "{eid}"}}' in env["fix"] and "Remote Email Collection" in env["fix"]
        assert all(c.ok for c in used), [c.refusals for c in used]

    def test_a_scan_left_beside_a_refused_anchor_is_refused(self, cards):
        """F-REV-06 T5 (T-full, confirmation): the name anchor was ambiguous, the CAPEC scan was all that was left."""
        from utils.planner.typed import check_plan

        ctx = self._ctx(cards)
        try:
            checks, _ = check_plan({"steps": [
                {"id": "q1", "graph": "attack", "kind": "describe",
                 "anchor": {"name": "zzzz no such technique qqqq", "label": "Technique"}},
                {"id": "q2", "graph": "capec", "kind": "scan", "anchor_label": "TaxonomyEntry"}]}, ctx)
        finally:
            ctx.close()
        assert not checks[0].ok and not checks[1].ok
        assert "step q1" in checks[1].refusals[0]["fix"] and "was refused" in checks[1].refusals[0]["fix"]

    def test_the_no_join_key_refusal_names_the_bridged_anchor(self, cards):
        """F-REV-05 T1 in the spot-check: a from_step from ATT&CK into CAPEC, repaired by dropping the step."""
        from utils.planner.typed import check_plan

        tech = _entity(cards, "attack", "Technique")
        ctx = self._ctx(cards)
        try:
            checks, _ = check_plan({"steps": [
                {"id": "q1", "graph": "attack", "kind": "describe", "anchor": {"id": tech}},
                {"id": "q2", "graph": "capec", "kind": "describe",
                 "anchor": {"from_step": "q1", "label": "TaxonomyEntry"}}]}, ctx)
        finally:
            ctx.close()
        env = checks[1].refusals[0]
        if "no declared join key" not in env["detail"]:
            pytest.skip("the cards declare an ATT&CK -> CAPEC producer; the refusal does not arise")
        assert f'"anchor": {{"id": "{tech}"}}' in env["fix"] and '"anchor_label": "TaxonomyEntry"' in env["fix"]


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
