"""Phase C tests: the internal form, its validation against a card, and the TypedStep front end."""

from __future__ import annotations

import json

import pytest

from utils.agent.catalog import CardModel, LabelModel, PropertyModel, RelationModel
from utils.specialists.algebra import (Aggregate, Anchors, Common, Cond, Count, Describe, Expand, FromStep, GroupBy,
                                       Having, Hop, Intersect, InvalidOp, Nodes, OPS, Rank, Reach, Scan, Shortest,
                                       TypeScan, Union_, Values, Verify, Walk, Where, check, from_dict,
                                       operators_used, to_dict)
from utils.specialists.algebra.edges import Absence
from utils.specialists.algebra.from_typed_step import from_typed_step, normalise, to_typed_step
from utils.specialists.signals import TypedStep


def P(name: str, vtype: str) -> PropertyModel:
    return PropertyModel(name, vtype, vtype)


@pytest.fixture(scope="module")
def card() -> CardModel:
    """Group -USES-> Technique -HAS_SUB-> Technique; Mitigation -MITIGATES-> Technique; Tactic -HAS-> Technique."""
    props = {
        "Group": {"name": P("name", "string"), "created": P("created", "string"), "aliases": P("aliases", "list")},
        "Technique": {"name": P("name", "string"), "platforms": P("platforms", "list"),
                      "is_sub": P("is_sub", "boolean"), "score": P("score", "number"),
                      "modified": P("modified", "date"), "rank": P("rank", "integer")},
        "Mitigation": {"name": P("name", "string")},
        "Tactic": {"name": P("name", "string"), "order": P("order", "integer")},
    }
    labels = {k: LabelModel(k, "", "name", v) for k, v in props.items()}
    rels = {
        "USES": RelationModel("USES", patterns=(("Group", "Technique"),),
                              properties={"since": P("since", "date"), "weight": P("weight", "number")}),
        "HAS_SUB": RelationModel("HAS_SUB", patterns=(("Technique", "Technique"),)),
        "MITIGATES": RelationModel("MITIGATES", patterns=(("Mitigation", "Technique"),)),
        "HAS": RelationModel("HAS", patterns=(("Tactic", "Technique"),)),
    }
    return CardModel("toy", "test", "neo4j", labels, rels, 3, "test")


G = Anchors(("G1",), "Group")
USES = Hop("USES", "out", "Technique")


# --- every class round-trips through JSON -------------------------------------

def every_class_example() -> list:
    return [
        Describe(G), Common(Anchors(("G1", "M1"))), Expand(Walk(G, (USES,))), Count(Walk(G, (USES,))),
        Nodes(Scan("Group"), ("name",)), Values(Scan("Technique"), "score", True),
        Where(Scan("Technique"), (Cond("score", ">", 2.5), Cond("platforms", "contains", "Linux"))),
        Aggregate(Scan("Technique"), "median", "score"), Rank(Scan("Group"), "desc", 3, by_walk=(USES,)),
        Verify(G, Anchors(("T1",), "Technique"), "USES", "out"), TypeScan("Technique", (Cond("is_sub", "=", True),)),
        GroupBy(Scan("Group"), (USES,), "count", having=(">", 10), order="desc", k=5),
        Union_((Walk(G, (USES,)), Walk(Anchors(("M1",), "Mitigation"), (Hop("MITIGATES", "out", "Technique"),)))),
        Absence(Scan("Technique"), Hop("MITIGATES", "in", "Mitigation")),
        Having(Scan("Group"), USES, True, (Cond("modified", "between", ("2020-01-01", "2021-12-31")),)),
        Reach(Anchors(("T1",), "Technique"), (("HAS_SUB", "out"),), 4),
        Shortest(Anchors(("G1",), "Group"), Anchors(("M1",), "Mitigation")),
        Count(Intersect((Walk(G, (USES,)), Scan("Technique")))),
        Expand(Walk(FromStep("q1", ("Group",)), (Hop("USES", "out", "Technique", (Cond("since", "after", "2019-06-01"),)),))),
    ]


def test_every_class_has_an_example():
    used = {type(x).__name__ for e in every_class_example() for x in _walk(e)}
    assert set(OPS) <= used, set(OPS) - used


def _walk(x):
    import dataclasses
    yield x
    if dataclasses.is_dataclass(x):
        for f in dataclasses.fields(x):
            yield from _walk(getattr(x, f.name))
    elif isinstance(x, tuple):
        for y in x:
            yield from _walk(y)


@pytest.mark.parametrize("node", every_class_example(), ids=lambda n: type(n).__name__)
def test_json_round_trip_and_valid(node, card):
    assert from_dict(json.loads(json.dumps(to_dict(node)))) == node
    check(node, card)


def test_from_dict_refuses_unknown_class_and_field():
    with pytest.raises(InvalidOp):
        from_dict({"@": "Teleport"})
    with pytest.raises(InvalidOp):
        from_dict({"@": "Scan", "label": "Group", "colour": "red"})


def test_operators_used():
    assert operators_used(Expand(Walk(G, (USES,)))) == {0}
    assert operators_used(GroupBy(Scan("Group"), (USES,))) == {0, 6}
    assert 7 in operators_used(Where(Scan("Technique"), (Cond("modified", "year", 2020, "="),)))
    assert 7 in operators_used(Walk(G, (Hop("USES", "out", "Technique", (Cond("weight", ">", 1),)),)))


# --- validation refuses, with a message that says what is allowed ---------------

@pytest.mark.parametrize("node,fragment", [
    (Scan("Weapon"), "unknown label"),
    (Walk(G, (Hop("TELEPORTS", "out"),)), "unknown relationship"),
    (Walk(G, (Hop("USES", "sideways"),)), "direction"),
    (Walk(G, (Hop("MITIGATES", "out"),)), "joins none"),
    (Walk(G, (Hop("USES", "out", "Tactic"),)), "reaches ['Technique'], not Tactic"),
    (Walk(G, (USES,), depth=2), "does not repeat"),
    (Walk(G, (USES, Hop("HAS_SUB", "out", "Technique")), depth=2), "repeats a single hop"),
    (Walk(G, (USES,), depth=4), "depth must be 1..3"),
    (Walk(Anchors(("T1",), "Technique"), (Hop("HAS_SUB", "out", "Technique"),), 5), "depth must be 1..3"),
    (Walk(G, ()), "at least one hop"),
    (Describe(Anchors((), "Group")), "at least one id"),
    (Where(Scan("Technique"), (Cond("platforms", "=", "Linux"),)), "not '='"),
    (Where(Scan("Technique"), (Cond("score", ">", "high"),)), "numeric value"),
    (Where(Scan("Technique"), (Cond("is_sub", ">", True),)), "not '>'"),
    (Where(Scan("Technique"), (Cond("colour", "=", "red"),)), "unknown property"),
    (Where(Scan("Technique"), (Cond("modified", "before", "last year"),)), "ISO date"),
    (Where(Scan("Technique"), (Cond("modified", "between", ("2020-01-01",)),)), "two ISO dates"),
    (Where(Scan("Technique"), (Cond("platforms", "size", 3),)), "needs cmp"),
    (Where(Scan("Technique"), (Cond("name", "missing", "x"),)), "takes no value"),
    (Where(Scan("Technique"), ()), "at least one condition"),
    (Aggregate(Scan("Technique"), "mode", "score"), "fn must be"),
    (Aggregate(Scan("Technique"), "sum", "name"), "numeric property"),
    (Aggregate(Scan("Technique"), "count", "score"), "takes no prop"),
    (Rank(Scan("Group"), "up", 3, "name"), "asc or desc"),
    (Rank(Scan("Group"), "desc", 0, "name"), "positive integer"),
    (Rank(Scan("Group"), "desc", 3, "name", (USES,)), "exactly one"),
    (Rank(Scan("Group"), "desc", 3, "aliases"), "orderable"),
    (Verify(Anchors(("G1", "G2"), "Group"), Anchors(("T1",), "Technique")), "exactly one id"),
    (Verify(G, Anchors(("T1",), "Technique"), "MITIGATES"), "never joins"),
    (Verify(G, Anchors(("T1",), "Technique"), None, "out"), "direction needs a relation"),
    (GroupBy(Scan("Group"), (USES,), "count", "score"), "takes no prop"),
    (GroupBy(Scan("Group"), (USES,), having=("~", 1)), "having must be"),
    (GroupBy(Scan("Group"), (USES,), k=3), "k needs an order"),
    (Union_((Scan("Group"),)), "at least two parts"),
    (Intersect((Scan("Group"), Scan("Technique"))), "share no label"),
    (Having(Scan("Group"), Hop("MITIGATES", "in"), False), "joins none"),
    (Reach(G, (("USES", "out"),), 11), "depth must be 1..10"),
    (Reach(G, (("HAS", "out"),)), "reach nothing"),
    (Shortest(G, G), "must differ"),
    (Walk(G, (Hop("USES", "out", "Technique", (Cond("colour", "=", "x"),)),)), "unknown property"),
    (Common(Anchors(("G1",))), "at least two anchors"),
    ("not an op", "not an operator"),
])
def test_validation_refuses(node, fragment, card):
    with pytest.raises(InvalidOp) as exc:
        check(node, card)
    assert fragment in str(exc.value)


def test_label_sets(card):
    assert check(Walk(G, (USES,)), card) == {"Technique"}
    assert check(Walk(G, (Hop("USES", "out"),)), card) == {"Technique"}
    assert check(Union_((Scan("Group"), Scan("Tactic"))), card) == {"Group", "Tactic"}
    assert check(Reach(Anchors(("TA1",), "Tactic"), (("HAS", "out"), ("HAS_SUB", "out")), 3), card) == {"Technique"}
    assert check(FromStep("q1"), card) == set(card.labels)


def test_text_dates_take_time_ops(card):
    """S6: ISO dates stored as text (ATT&CK's created) take the time ops."""
    check(Where(Scan("Group"), (Cond("created", "after", "2020-01-01"),)), card)
    check(Where(Scan("Group"), (Cond("created", "year", 2020, ">="),)), card)


# --- the TypedStep front end -----------------------------------------------------

STEPS = [
    {"kind": "expand", "anchor_label": "Group", "anchor_ids": ["G1"],
     "hops": [{"relation": "USES", "direction": "out", "target_label": "Technique"}], "depth": 1},
    {"kind": "expand", "anchor_label": "Technique", "anchor_ids": ["T1"],
     "hops": [{"relation": "HAS_SUB", "direction": "out", "target_label": "Technique"}], "depth": 3},
    {"kind": "count", "anchor_label": "Group", "anchor_ids": ["G1"],
     "hops": [{"relation": "USES", "direction": "out", "target_label": "Technique"}], "depth": 1,
     "filter": {"property": "name", "value": "Phishing"}},
    {"kind": "describe", "anchor_label": "Group", "anchor_ids": ["G1"], "hops": [], "depth": 1},
    {"kind": "common", "anchor_label": "", "anchor_ids": ["G1", "M1"], "hops": [], "depth": 1},
    {"kind": "scan", "anchor_label": "Group", "anchor_ids": [], "hops": [], "depth": 1},
]


@pytest.mark.parametrize("step", STEPS, ids=lambda s: s["kind"])
def test_typed_step_round_trip(step, card):
    ts = TypedStep.from_dict(step)
    node = from_typed_step(ts, card)
    assert to_typed_step(node) == normalise(ts)
    check(node, card)


def test_typed_step_kinds_map():
    assert isinstance(from_typed_step(TypedStep.from_dict(STEPS[0])), Expand)
    assert isinstance(from_typed_step(TypedStep.from_dict(STEPS[2])), Count)
    assert isinstance(from_typed_step(TypedStep.from_dict(STEPS[3])), Describe)
    assert isinstance(from_typed_step(TypedStep.from_dict(STEPS[4])), Common)
    assert from_typed_step(TypedStep.from_dict(STEPS[5])) == Nodes(Scan("Group"))


def test_expand_without_hops_is_describe():
    """The builder treats a hop-less expand as describe; so does the front end."""
    ts = TypedStep.from_dict({"kind": "expand", "anchor_label": "Group", "anchor_ids": ["G1"], "hops": [],
                              "depth": 2, "filter": {"property": "name", "value": "x"}})
    assert from_typed_step(ts) == Describe(Anchors(("G1",), "Group"))
    assert normalise(ts)["kind"] == "describe"


def test_list_filter_becomes_contains_with_a_card(card):
    step = {"kind": "expand", "anchor_label": "Group", "anchor_ids": ["G1"],
            "hops": [{"relation": "USES", "direction": "out", "target_label": "Technique"}], "depth": 1,
            "filter": {"property": "platforms", "value": "Linux"}}
    ts = TypedStep.from_dict(step)
    with_card = from_typed_step(ts, card)
    assert with_card.walk.last_conds == (Cond("platforms", "contains", "Linux"),)
    assert from_typed_step(ts).walk.last_conds == (Cond("platforms", "=", "Linux"),)
    assert to_typed_step(with_card) == normalise(ts)
    check(with_card, card)


def test_runtime_anchors_are_refused_until_filled(card):
    ts = TypedStep.from_dict({**STEPS[0], "anchor_ids": []})
    with pytest.raises(InvalidOp, match="at least one id"):
        check(from_typed_step(ts, card), card)


def test_to_typed_step_refuses_what_it_cannot_hold():
    with pytest.raises(ValueError):
        to_typed_step(GroupBy(Scan("Group"), (USES,)))
    with pytest.raises(ValueError):
        to_typed_step(Expand(Walk(G, (USES,), 1, (Cond("score", ">", 1),))))


def test_strings_order_by_code_point(card):
    """Amendment 2: <, >, <=, >= are allowed on text."""
    check(Where(Scan("Technique"), (Cond("name", ">=", "M"),)), card)


def test_groupby_end_conds(card):
    """Amendment 2: per group, count only the end nodes meeting end_conds."""
    node = GroupBy(Scan("Group"), (USES,), end_conds=(Cond("platforms", "contains", "Linux"),))
    check(node, card)
    assert from_dict(json.loads(json.dumps(to_dict(node)))) == node
    with pytest.raises(InvalidOp, match="unknown property"):
        check(GroupBy(Scan("Group"), (USES,), end_conds=(Cond("colour", "=", "x"),)), card)
