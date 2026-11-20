"""Phase D tests: the Cypher and Gremlin compilers, and the shared ``finish``.

No store runs here. These check that every class compiles on both backends, that
no user value reaches the query text, that identifiers are checked, the query
shapes the semantics (``docs/era-2-expansion/operator-algebra.md``) require, and
the post-steps' meaning. The live agreement test is Phase E's.
"""

from __future__ import annotations

import re

import pytest

from utils.specialists.algebra import (Anchors, Common, Cond, Count, Describe, Expand, FromStep, GroupBy, Having, Hop,
                                       Intersect, Nodes, Reach, Scan, Shortest, TypeScan, Union_, Verify, Walk, Where)
from utils.specialists.algebra.compiled import (Backend, Compiled, UnsafeIdentifier, finish, median, rank_rows)
from utils.specialists.algebra.edges import Absence
from utils.specialists.algebra.tests import test_ir
from utils.specialists.algebra.tests.test_ir import G, USES, every_class_example
from utils.specialists.cypher.compile import compile_cypher
from utils.specialists.gremlin.compile import compile_gremlin

#: test_ir's module-scoped toy card (Group, Technique, Mitigation, Tactic), reused as this module's fixture.
card = test_ir.card
T = Anchors(("T1",), "Technique")
NASTY = ("O'Brien \"quoted\" back\\slash \\ space", "x' OR 1=1 //", "it\\'s")


def _backends(card):
    return [(compile_cypher, Backend.cypher(card)), (compile_gremlin, Backend.gremlin(card))]


# --- every class compiles on both backends ---------------------------------------

@pytest.mark.parametrize("node", every_class_example(), ids=lambda n: type(n).__name__)
def test_every_example_compiles_on_both(node, card):
    for compile_, backend in _backends(card):
        c = compile_(node, backend)
        assert isinstance(c, Compiled) and c.text and c.kind
        assert c.post in (None, "rank", "group", "median", "shortest")
        for name in c.params:
            assert re.fullmatch(r"p\d+", name)
            assert re.search(rf"[$(, ]{name}\b", c.text), (name, c.text)


@pytest.mark.parametrize("node", every_class_example(), ids=lambda n: type(n).__name__)
def test_examples_compile_without_a_card(node):
    compile_cypher(node)
    compile_gremlin(node)


def test_same_contract_on_both(card):
    for node in every_class_example():
        cy, gr = compile_cypher(node, Backend.cypher(card)), compile_gremlin(node, Backend.gremlin(card))
        assert (cy.kind, cy.post) == (gr.kind, gr.post), type(node).__name__


# --- no user value in the query text ------------------------------------------------

def _value_trees(v: str) -> list:
    return [
        Where(Scan("Technique"), (Cond("name", "=", v),)),
        Where(Scan("Technique"), (Cond("name", "<>", v),)),
        TypeScan("Technique", (Cond("name", "starts_with", v), Cond("name", "contains_text", v))),
        Where(Scan("Technique"), (Cond("platforms", "contains", v),)),
        Absence(Scan("Technique"), Hop("MITIGATES", "in", "Mitigation"), (Cond("name", "ends_with", v),)),
        Describe(Anchors((v,), "Group")),
        Expand(Walk(Anchors((v,), "Group"), (USES,), 1, (Cond("name", "=", v),))),
        Verify(Anchors((v,), "Group"), Anchors((v + "2",), "Technique"), "USES", "out"),
        Shortest(Anchors((v,), "Group"), Anchors((v + "2",), "Mitigation")),
        Common(Anchors((v, v + "2"))),
        Count(Reach(Anchors((v,), "Technique"), (("HAS_SUB", "out"),), 3)),
        GroupBy(Scan("Group"), (USES,), end_conds=(Cond("name", "=", v),)),
        Where(Scan("Group"), (Cond("created", "after", "2020-01-01" + v),)),
    ]


@pytest.mark.parametrize("value", NASTY)
def test_values_only_in_params(value, card):
    for node in _value_trees(value):
        for compile_, backend in _backends(card):
            c = compile_(node, backend)
            assert value not in c.text, (type(node).__name__, c.text)
            assert "O'Brien" not in c.text and "1=1" not in c.text
            flat = repr(c.params)
            if not (isinstance(node, Where) and node.conds[0].op == "after"):
                assert repr(value)[1:-1] in flat or value in str(c.params), (type(node).__name__, c.params)


def test_date_value_is_cut_to_its_day(card):
    """S6: only the YYYY-MM-DD prefix of a date value is compared, and it is a parameter."""
    node = Where(Scan("Group"), (Cond("created", "before", "2020-01-01T00:00' OR x"),))
    for compile_, backend in _backends(card):
        c = compile_(node, backend)
        assert "2020-01-01" in c.params.values() and "2020-01-01" not in c.text


def test_from_step_ids_are_a_runner_parameter(card):
    node = Count(Walk(FromStep("q'1", ("Group",)), (USES,)))
    for compile_, backend in _backends(card):
        c = compile_(node, backend)
        (name, step), = c.meta["inputs"].items()
        assert step == "q'1" and c.params[name] is None and "q'1" not in c.text


# --- identifiers are checked -----------------------------------------------------

@pytest.mark.parametrize("node", [
    Nodes(Scan("Group') DETACH DELETE n //")),
    Expand(Walk(G, (Hop("USES]->() DELETE x", "out", "Technique"),))),
    Expand(Walk(G, (Hop("USES", "out", "Tech nique"),))),
    Where(Scan("Technique"), (Cond("na`me", "=", "x"),)),
    Nodes(Scan("Group"), ("name; drop",)),
    Verify(G, T, "USES').drop().V('", "out"),
])
def test_unsafe_identifier_raises(node):
    """No card, so nothing but the identifier check stands between the name and the text."""
    for compile_ in (compile_cypher, compile_gremlin):
        with pytest.raises(UnsafeIdentifier):
            compile_(node)


def test_unsafe_backend_spelling_raises():
    bad = lambda r: r + "'); g.V().drop(); ('"  # noqa: E731
    for backend, compile_ in ((Backend.cypher(rel_name=bad), compile_cypher),
                              (Backend.gremlin(rel_name=bad), compile_gremlin)):
        with pytest.raises(UnsafeIdentifier):
            compile_(Expand(Walk(G, (USES,))), backend)


def test_gremlin_spells_relations_the_store_way():
    c = compile_gremlin(Expand(Walk(T, (Hop("ChildOf", "out", "AttackPattern"),))))
    assert "out('CHILD_OF')" in c.text and c.meta["rels"]["CHILD_OF"] == "ChildOf"
    assert ":ChildOf]->" in compile_cypher(Expand(Walk(T, (Hop("ChildOf", "out", "AttackPattern"),)))).text


# --- Gremlin: no re.escape artefacts ------------------------------------------------

def test_gremlin_text_has_no_escapes(card):
    trees = every_class_example() + [t for v in NASTY for t in _value_trees(v)] + [
        Where(Scan("Technique"), (Cond("modified", "year", 2020, ">="),)),
        Where(Scan("Group"), (Cond("created", "between", ("2020-01-01", "2020-12-31")),))]
    for node in trees:
        text = compile_gremlin(node, Backend.gremlin(card)).text
        assert "\\" not in text, text  # every regex and value is a binding
        assert re.escape("a b") not in text


def test_gremlin_binding_limit():
    """The limit is enforced; a query with more distinct values than the server binds is refused."""
    many = Where(Scan("Technique"), tuple(Cond("name", "<>", f"n{i}") for i in range(20)))
    with pytest.raises(ValueError, match="binds at most 16"):
        compile_gremlin(many)
    compile_cypher(many)


def test_reach_from_fifty_anchors_fits_the_binding_limit(card):
    """The start ids are one list binding, whatever their number."""
    ids = tuple(f"T{i}" for i in range(50))
    for node in (Count(Reach(Anchors(ids, "Technique"), (("HAS_SUB", "out"),), 6)),
                 Nodes(Reach(Anchors(ids, "Technique"), (("HAS_SUB", "out"),), 6))):
        c = compile_gremlin(node, Backend.gremlin(card))
        assert len(c.params) <= 16 and list(c.params.values()).count(list(ids)) == 1


def test_reach_from_a_walk_start(card):
    """Per start node, exclude only that node (S10): no start set is aggregated as 'seen'."""
    node = Nodes(Reach(Walk(G, (USES,)), (("HAS_SUB", "out"),), 3))
    gr = compile_gremlin(node, Backend.gremlin(card)).text
    assert re.search(r"\.out\('USES'\)\.hasLabel\('Technique'\)\.dedup\(\)\.as\('s\d+'\)\.repeat\(", gr)
    assert re.search(r"where\(neq\('s\d+'\)\)", gr) and re.search(r"dedup\('s\d+', 'v\d+'\)", gr)
    assert "without(" not in gr.split("total_beyond")[0]
    cy = compile_cypher(node, Backend.cypher(card)).text
    assert "ANY SHORTEST" in cy and re.search(r"WHERE v\d+ <> v\d+", cy)


def test_equal_values_share_one_parameter():
    c = compile_gremlin(Common(Anchors(("G1", "M1"))))
    assert list(c.params.values()).count(["G1", "M1"]) == 1


# --- golden shapes per operator ------------------------------------------------------

def test_anchor_match_on_stored_id(card):
    cy, gr = compile_cypher(Describe(G), Backend.cypher(card)), compile_gremlin(Describe(G), Backend.gremlin(card))
    assert "MATCH (v1:Group) WHERE v1.id IN $p0" in cy.text and "attack_id" not in cy.text
    assert gr.text.startswith("g.V().has('id', within(p0)).hasLabel('Group')")


def test_untargeted_hop_keeps_every_label(card):
    node = Expand(Walk(G, (Hop("USES", "out"),)))
    assert re.search(r"-\[r\d+:USES\]->\(t\d+\) ", compile_cypher(node, Backend.cypher(card)).text)
    assert ".dedup().out('USES').dedup()" in compile_gremlin(node, Backend.gremlin(card)).text


def test_dedup_everywhere(card):
    cy = compile_cypher(Count(Walk(G, (USES,))), Backend.cypher(card)).text
    assert "count(DISTINCT" in cy and "WITH DISTINCT" in cy
    gr = compile_gremlin(Count(Walk(G, (USES,))), Backend.gremlin(card)).text
    assert ".dedup().fold().project('value'" in gr


def test_missing_never_matches(card):
    """S4: every comparison tests presence; not_contains and <> included."""
    node = Where(Scan("Technique"), (Cond("name", "<>", "x"), Cond("platforms", "not_contains", "Linux"),
                                    Cond("platforms", "size", 2, "<")))
    cy = compile_cypher(node, Backend.cypher(card)).text
    assert cy.count("IS NOT NULL") == 3
    gr = compile_gremlin(node, Backend.gremlin(card)).text
    assert ".has('name', neq(" in gr and ".has('platforms').not(" in gr and ".has('platforms').where(" in gr


def test_dates_compare_on_iso_prefix(card):
    node = Where(Scan("Technique"), (Cond("modified", "<=", "2020-06-01"),))
    cy = compile_cypher(node, Backend.cypher(card))
    assert "substring(v2.`modified`, 0, 10) <= $p1" in cy.text and "=~ $p0" in cy.text
    gr = compile_gremlin(node, Backend.gremlin(card))
    assert "TextP.regex(p0)" in gr.text and "TextP.startingWith(p1)" in gr.text and "lt(p1)" in gr.text


def test_year_on_both(card):
    node = Where(Scan("Technique"), (Cond("modified", "year", 2020, "="),))
    assert "toInteger(substring(" in compile_cypher(node, Backend.cypher(card)).text
    gr = compile_gremlin(node, Backend.gremlin(card))
    assert "2020" in gr.params.values() and "TextP.startingWith" in gr.text
    never = compile_gremlin(Where(Scan("Technique"), (Cond("modified", "year", 12000, "="),)), Backend.gremlin(card))
    assert ".not(__.identity())" in never.text


def test_number_text_reads_as_a_number(card):
    card.labels["Technique"].properties["cvss"] = type(card.labels["Technique"].properties["score"])(
        "cvss", "number_text", "float_text")
    try:
        node = Where(Scan("Technique"), (Cond("cvss", ">", 7),))
        assert "toFloat(v2.`cvss`) > $p1" in compile_cypher(node, Backend.cypher(card)).text
        assert "asNumber(GType.DOUBLE).is(gt(p1))" in compile_gremlin(node, Backend.gremlin(card)).text
    finally:
        del card.labels["Technique"].properties["cvss"]


def test_expand_returns_every_prefix(card):
    """Amendment 3: each prefix's end nodes, whether or not the walk continues; conditions on the full walk."""
    node = Expand(Walk(G, (USES, Hop("HAS_SUB", "out", "Technique")), 1, (Cond("score", ">", 1),)))
    cy = compile_cypher(node, Backend.cypher(card)).text
    arms = re.search(r"CALL \{ (.*) \} WITH DISTINCT", cy).group(1).split(" UNION ")
    assert len(arms) == 2 and "HAS_SUB" not in arms[0] and "score" not in arms[0]
    assert "HAS_SUB" in arms[1] and "score" in arms[1] and "OPTIONAL" not in cy
    gr = compile_gremlin(node, Backend.gremlin(card)).text
    assert (".union(__.out('USES').hasLabel('Technique'), "
            "__.out('USES').hasLabel('Technique').out('HAS_SUB').hasLabel('Technique').has('score', gt(p1))).dedup()"
            in gr)


def test_expand_repeated_hop_keeps_every_step(card):
    # Amendment 3: each repetition count is a prefix; its end nodes are kept (and
    # filtered), not every node on a path to a filtered end (EXP-2026-11-021).
    node = Expand(Walk(T, (Hop("HAS_SUB", "out", "Technique"),), 3))
    cy = compile_cypher(node, Backend.cypher(card)).text
    assert "*1..3" in cy and "UNWIND nodes(" not in cy
    gr = compile_gremlin(node, Backend.gremlin(card)).text
    assert ".emit().times(3)" in gr and "select(Pop.all" not in gr


def test_repeated_walk_is_acyclic(card):
    node = Count(Walk(T, (Hop("HAS_SUB", "out", "Technique"),), 3))
    assert "<> v" in compile_cypher(node, Backend.cypher(card)).text
    assert "simplePath().from('s" in compile_gremlin(node, Backend.gremlin(card)).text


def test_reach_and_shortest_shapes(card):
    reach = Nodes(Reach(T, (("HAS_SUB", "out"),), 4))
    cy = compile_cypher(reach, Backend.cypher(card)).text
    assert "ANY SHORTEST" in cy and "{1,5}" in cy and "AS partial" in cy
    gr = compile_gremlin(reach, Backend.gremlin(card)).text
    assert ".times(4)" in gr and ".times(5)" in gr and ".barrier().dedup('s" in gr
    sp = Shortest(G, Anchors(("M1",), "Mitigation"), depth=4)
    cy = compile_cypher(sp, Backend.cypher(card)).text
    assert "ALL SHORTEST" in cy and "{1,4}" in cy and "{1,5}" in cy
    gr = compile_gremlin(sp, Backend.gremlin(card)).text
    assert ".barrier().aggregate(" in gr and "loops().is(4)" in gr and "path().from('s" in gr


def test_mixed_direction_reach(card):
    node = Count(Reach(T, (("HAS_SUB", "out"), ("MITIGATES", "in")), 2))
    cy = compile_cypher(node, Backend.cypher(card)).text
    assert "startNode(" in cy and "endNode(" in cy
    gr = compile_gremlin(node, Backend.gremlin(card)).text
    assert "union(__.out('HAS_SUB'), __.in('MITIGATES'))" in gr


def test_groupby_keeps_empty_groups(card):
    """S9: an OPTIONAL walk per member (Cypher) / a per-member child traversal (Gremlin)."""
    node = GroupBy(Scan("Group"), (USES,), "sum", "score")
    cy = compile_cypher(node, Backend.cypher(card)).text
    assert "OPTIONAL MATCH" in cy and "sum(" in cy
    gr = compile_gremlin(node, Backend.gremlin(card)).text
    assert "coalesce(__.unfold().sum(), __.constant(0))" in gr


def test_verify_and_common_shapes(card):
    v = Verify(G, T)
    cy = compile_cypher(v, Backend.cypher(card)).text
    assert "AS a_found" in cy and "AS b_found" in cy and "-[r" in cy and "USES" in cy
    gr = compile_gremlin(v, Backend.gremlin(card)).text
    assert ".bothE('USES')" in gr and "otherV()" in gr
    c = compile_cypher(Common(Anchors(("G1", "M1"))), Backend.cypher(card)).text
    assert "count(DISTINCT" in c and "--(" in c


def test_intersect_and_having_target(card):
    node = Nodes(Having(Scan("Group"), USES, True, (), Intersect((Walk(G, (USES,)), Scan("Technique")))))
    cy = compile_cypher(node, Backend.cypher(card)).text
    assert "IN c" in cy and "EXISTS {" in cy
    gr = compile_gremlin(node, Backend.gremlin(card)).text
    assert "aggregate('i" in gr and "where(within('i" in gr and "where(within('t" in gr


def test_union_dedups(card):
    node = Union_((Scan("Group"), Scan("Tactic")))
    assert " UNION " in compile_cypher(node, Backend.cypher(card)).text
    assert ").dedup()" in compile_gremlin(node, Backend.gremlin(card)).text


# --- finish: the shared post-steps ---------------------------------------------------

def _c(kind, post=None, **meta):
    return Compiled("", {}, kind, post, {"row_cap": 3, **meta})


def test_median():
    assert median([3, 1, 2]) == 2
    assert median([4, 1, 3, 2]) == 2.5
    assert median([]) is None


def test_rank_ties_and_missing_last():
    rows = [{"id": "a", "value": 3}, {"id": "b", "value": 5}, {"id": "c", "value": 3}, {"id": "d", "value": None},
            {"id": "e", "value": 1}]
    assert [r["id"] for r in rank_rows(rows, "desc", 2)] == ["b", "a", "c"]
    assert [r["id"] for r in rank_rows(rows, "asc", 1)] == ["e"]
    assert [r["id"] for r in rank_rows(rows, "asc", 5)] == ["e", "a", "c", "b", "d"]


def test_finish_rank_drops_and_counts_missing():
    raw = [{"rows": [{"id": "a", "name": "A", "value": 2}, {"id": "b", "name": "B", "value": None},
                     {"id": "c", "name": "C", "value": 2}]}]
    r = finish(raw, _c("rank", "rank", order="desc", k=1, drop_missing=True))
    assert [x["id"] for x in r.rows] == ["a", "c"] and r.info["unranked"] == 1


def test_finish_group_median_having_rank():
    raw = {"rows": [{"id": "g1", "name": "x", "value": [1, 3]}, {"id": "g2", "name": "y", "value": []},
                    {"id": "g3", "name": "z", "value": [5]}]}
    r = finish(raw, _c("groupby", "group", fn="median", having=None, order="desc", k=2))
    assert [(x["id"], x["value"]) for x in r.rows] == [("g3", 5), ("g1", 2)]
    r = finish(raw, _c("groupby", "group", fn="median", having=[">", 1], order=None, k=None))
    assert [x["id"] for x in r.rows] == ["g1", "g3"]


def test_finish_having_selects_zero():
    raw = {"rows": [{"id": "g1", "name": "x", "value": 0}, {"id": "g2", "name": "y", "value": 4}]}
    r = finish(raw, _c("groupby", "group", fn="count", having=["=", 0], order=None, k=None))
    assert [x["id"] for x in r.rows] == ["g1"]


def test_finish_nodes_total_and_found():
    raw = {"total": 5, "rows": [{"id": i, "name": i} for i in "abc"], "found_0": ["G1"]}
    r = finish(raw, _c("nodes", props=(), anchors=[["G1", "G9"]]))
    assert r.total == 5 and not r.complete and r.info["anchor_not_found"] == ["G9"]


def test_finish_reach_partial():
    r = finish({"total": 2, "rows": [{"id": "a", "name": None}, {"id": "b", "name": None}], "total_beyond": 3},
               _c("nodes", props=()))
    assert r.partial and not r.complete
    r = finish({"total": 0, "rows": [], "partial": False}, _c("nodes", props=()))
    assert r.complete and r.total == 0


def test_finish_verify_not_found_is_distinct():
    meta = {"anchors": [["G1"], ["T9"]], "rels": {"CHILD_OF": "ChildOf"}}
    r = finish({"a_found": 1, "b_found": 0, "witness": []}, _c("verify", **meta))
    assert r.info["anchor_not_found"] == ["T9"] and r.info["exists"] is False
    r = finish({"a_found": True, "b_found": True,
                "witness": [{"relation": "CHILD_OF", "direction": "out", "properties": {"id": "e1"}}] * 2},
               _c("verify", **meta))
    assert r.info["exists"] and r.rows == [{"relation": "ChildOf", "direction": "out", "properties": {"id": "e1"}}]


def test_finish_shortest_both_shapes_agree():
    meta = {"anchors": [["a"], ["c"]], "rels": {"CHILD_OF": "ChildOf"}}
    cy = finish({"a_found": True, "b_found": True, "beyond": False,
                 "paths": [{"nodes": ["a", "b", "c"], "rels": ["CHILD_OF", "CHILD_OF"]}] * 2},
                _c("shortest", "shortest", **meta))
    gr = finish({"a_found": 1, "b_found": 1, "total_within": 3, "total_beyond": 3,
                 "paths": [["a", "CHILD_OF", "b", "CHILD_OF", "c"]]}, _c("shortest", "shortest", **meta))
    assert cy.rows == gr.rows == [{"path": ["a", "ChildOf", "b", "ChildOf", "c"], "rels": ["ChildOf", "ChildOf"]}]
    none = finish({"a_found": 1, "b_found": 1, "total_within": 3, "total_beyond": 4, "paths": []},
                  _c("shortest", "shortest", **meta))
    assert none.partial and none.total == 0


def test_finish_aggregate_median_and_empty_count():
    assert finish({"value": [1, 2, 3, 10]}, _c("aggregate", "median")).value == 2.5
    assert finish({"value": None}, _c("count")).value == 0


def test_finish_describe_strips_gremlin_tokens():
    class Tok:  # stands in for gremlin_python's T.id / T.label keys
        pass

    raw = {"rows": [{"id": "G1", "name": "APT", "properties": {Tok(): 7, "id": "G1", "name": "APT"}}]}
    r = finish(raw, _c("describe", anchors=[["G1", "G2"]]))
    assert r.rows[0]["properties"] == {"id": "G1", "name": "APT"} and r.info["anchor_not_found"] == ["G2"]
