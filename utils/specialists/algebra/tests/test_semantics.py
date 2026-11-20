"""Phase E (EXP-2026-11-021): every rule of the semantics document, on both backends.

The expected answers are worked out by hand from ``docs/era-2-expansion/operator-algebra.md``
on the fixture graph in ``fx_graph.py`` (its docstring draws the graph), never from
the compilers. Each test runs on Cypher (Neo4j bolt 5480) and Gremlin (ws 6480),
the verification pair, and skips cleanly when those are not reachable.

§ 8 names one or more tests per rule (S1-S12); ``test_every_named_test_exists``
parses that table and fails when a named test is missing. The amendments (§ 9)
have their own tests at the end.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from utils.specialists.algebra import (Aggregate, Anchors, Common, Cond, Count, Describe, Expand, GroupBy, Having,
                                       Hop, InvalidOp, Nodes, Rank, Reach, Scan, Shortest, TypeScan, Union_, Values,
                                       Verify, Walk, Where, check)
from utils.specialists.algebra.compiled import Backend, Result
from utils.specialists.algebra.differential import Engines, compile_on, stores_up
from utils.specialists.algebra.edges import Absence
from utils.specialists.algebra.tests import fx_graph

DOC = Path(__file__).resolve().parents[4] / "docs" / "era-2-expansion" / "operator-algebra.md"
BACKENDS = ("cypher", "gremlin")
CARD = fx_graph.card()

pytestmark = pytest.mark.skipif(not stores_up(), reason="verification stores (bolt 5480, ws 6480) unreachable")


@pytest.fixture(scope="session")
def engines():
    e = Engines()
    report = fx_graph.load(e)
    assert report["neo4j"] == report["want"] == report["gremlin"], report
    yield e
    e.close()


@pytest.fixture(params=BACKENDS)
def run(request, engines):
    """``run(node, row_cap=1000)`` -> the finished Result on this test's backend."""
    name = request.param

    def _run(node: Any, row_cap: int = 1000) -> Result:
        backend = Backend.cypher(CARD, row_cap=row_cap) if name == "cypher" else Backend.gremlin(CARD, row_cap=row_cap)
        return engines.run(compile_on(node, backend), name)

    _run.backend = name
    return _run


def ids(r: Result) -> list[str]:
    return [row["id"] for row in r.rows]


def idset(r: Result) -> set[str]:
    return set(ids(r))


def by_id(r: Result) -> dict[str, Any]:
    return {row["id"]: row["value"] for row in r.rows}


def fx(*names: str) -> set[str]:
    return {f"fx:{n}" for n in names}


G = lambda *n: Anchors(tuple(f"fx:{x}" for x in n), "FxGroup")  # noqa: E731
T = lambda *n: Anchors(tuple(f"fx:{x}" for x in n), "FxTech")  # noqa: E731
P = lambda *n: Anchors(tuple(f"fx:{x}" for x in n), "FxPlace")  # noqa: E731
USES_T = Hop("FxUses", "out", "FxTech")
SUB = Hop("FxSub", "out", "FxTech")
LINK = (("FxLink", "out"),)


def _no_anchor_missing(r: Result) -> None:
    assert not r.info.get("anchor_not_found"), r.info


# --------------------------------------------------------------------------- #
# The table itself
# --------------------------------------------------------------------------- #


def named_tests() -> dict[str, list[str]]:
    """§ 8's table: rule -> test names."""
    text = DOC.read_text()
    sec = text.split("## 8. Rules to tests", 1)[1].split("\n## ", 1)[0]
    out = {}
    for line in sec.splitlines():
        m = re.match(r"^\|\s*(S\d+)\s*\|(.*)\|\s*$", line)
        if m:
            out[m.group(1)] = re.findall(r"`(test_[a-z0-9_]+)`", m.group(2))
    return out


def test_every_named_test_exists():
    table = named_tests()
    assert set(table) == {f"S{i}" for i in range(1, 13)}, sorted(table)
    missing = [t for names in table.values() for t in names if not callable(globals().get(t))]
    assert not missing, missing


# --------------------------------------------------------------------------- #
# S1 identity and deduplication
# --------------------------------------------------------------------------- #


def test_two_paths_one_node_counted_once(run):
    # t1 reaches t3 directly and through t2; depth 2 repeats FxSub 1..2 times.
    walk = Walk(T("t1"), (SUB,), 2)
    r = run(Expand(walk))
    assert sorted(ids(r)) == sorted(fx("t2", "t3")) and r.total == 2
    assert run(Count(walk)).value == 2
    # t1 is used by both g1 and g2: once.
    r = run(Expand(Walk(G("g1", "g2"), (USES_T,))))
    assert sorted(ids(r)) == sorted(fx("t1", "t2", "t3")) and r.total == 3


def test_count_is_distinct(run):
    walk = Walk(G("g1", "g2", "g3"), (USES_T,))  # {t1,t2} ∪ {t1,t3} ∪ {t2,t3,t4}
    assert run(Count(walk)).value == 4
    assert run(Aggregate(walk, "count")).value == 4
    # weights 5, 5, 7, 3 over the four distinct nodes: three distinct values.
    assert run(Aggregate(walk, "count_values", "weight")).value == 3
    # a sum over distinct nodes: t1 counted once although two groups reach it.
    assert run(Aggregate(walk, "sum", "weight")).value == 20


# --------------------------------------------------------------------------- #
# S2 label mode
# --------------------------------------------------------------------------- #


def test_extra_neo4j_labels_never_match(run):
    # t5 also carries the Neo4j labels FxObject and FxExtra; every node carries FxObject.
    assert run(Count(Scan("FxTech"))).value == 5
    assert idset(run(Nodes(Scan("FxTool")))) == fx("s1", "s2")
    for lab in ("FxObject", "FxExtra"):
        with pytest.raises(InvalidOp):
            check(Scan(lab), CARD)
        with pytest.raises(InvalidOp):
            run(Nodes(Scan(lab)))
    # a describe reports the card's properties, not the engine's labels
    r = run(Describe(T("t5")))
    assert ids(r) == ["fx:t5"]
    props = r.rows[0]["properties"]
    assert not any(v in ("FxObject", "FxExtra") for v in props.values() if isinstance(v, str))


def test_untargeted_hop_keeps_card_labels(run):
    r = run(Expand(Walk(G("g1"), (Hop("FxUses", "out", ""),))))
    assert sorted(ids(r)) == sorted(fx("s1", "t1", "t2"))
    assert idset(run(Expand(Walk(G("g4"), (Hop("FxUses", "out", ""),))))) == fx("s2")
    # targeted: only the named label
    assert idset(run(Expand(Walk(G("g1"), (Hop("FxUses", "out", "FxTool"),))))) == fx("s1")


# --------------------------------------------------------------------------- #
# S3 relationships
# --------------------------------------------------------------------------- #


def test_direction_in_and_out(run):
    assert idset(run(Expand(Walk(T("t2"), (Hop("FxUses", "in", "FxGroup"),))))) == fx("g1", "g3")
    assert idset(run(Expand(Walk(T("t2"), (Hop("FxSub", "out", "FxTech"),))))) == fx("t3")
    assert idset(run(Expand(Walk(T("t2"), (Hop("FxSub", "in", "FxTech"),))))) == fx("t1")
    assert idset(run(Expand(Walk(T("t3"), (Hop("FxSub", "out", "FxTech"),))))) == set()


def test_unknown_relationship_refused(run):
    for bad in (Hop("FxMitigates", "out", "FxTech"),  # exists, but not from FxGroup
                Hop("FxNope", "out", "FxTech"),  # not in the card
                Hop("FxUses", "in", "FxTech"),  # wrong direction for FxGroup
                Hop("FxUses", "out", "FxMit")):  # never reaches FxMit
        with pytest.raises(InvalidOp):
            run(Expand(Walk(G("g1"), (bad,))))


# --------------------------------------------------------------------------- #
# S4 filters: present and satisfying
# --------------------------------------------------------------------------- #


def test_missing_never_matches_not_equal(run):
    # note: g1 "Hello World", g2 "hello world", g3 missing, g4 "World", g5 "Hi"
    assert idset(run(Where(Scan("FxGroup"), (Cond("note", "<>", "World"),)))) == fx("g1", "g2", "g5")
    # rank: g1 3, g2 1, g3 missing, g4 3, g5 2
    assert idset(run(Where(Scan("FxGroup"), (Cond("rank", "<>", 3),)))) == fx("g2", "g5")
    assert idset(run(Where(Scan("FxGroup"), (Cond("note", "missing"),)))) == fx("g3")
    assert idset(run(Where(Scan("FxGroup"), (Cond("note", "present"),)))) == fx("g1", "g2", "g4", "g5")


def test_missing_never_matches_not_contains(run):
    # aliases: g1 [A1, Apt-1], g2 [a1], g3 missing, g4 [G], g5 [D, Dx]
    assert idset(run(Where(Scan("FxGroup"), (Cond("aliases", "not_contains", "A1"),)))) == fx("g2", "g4", "g5")
    # platforms: t1 [Linux, Windows], t2 [Windows], t3 [linux], t4 missing, t5 [macOS]
    assert idset(run(Where(Scan("FxTech"), (Cond("platforms", "not_contains", "Linux"),)))) == fx("t2", "t3", "t5")


def test_filters_are_and(run):
    # active true: g1 (score 1.5), g3 (3.0); g5 has no 'active'
    r = run(Where(Scan("FxGroup"), (Cond("active", "=", True), Cond("score", ">", 2.0))))
    assert ids(r) == ["fx:g3"]
    r = run(TypeScan("FxTech", (Cond("weight", "=", 5), Cond("platforms", "contains", "Linux"))))
    assert ids(r) == ["fx:t1"]
    # OR is union
    r = run(Union_((Where(Scan("FxGroup"), (Cond("active", "=", True),)),
                    Where(Scan("FxGroup"), (Cond("score", ">", 2.0),)))))
    assert ids(r) == ["fx:g1", "fx:g2", "fx:g3"]


# --------------------------------------------------------------------------- #
# S5 comparison by type
# --------------------------------------------------------------------------- #


def test_text_ops_case_sensitive(run):
    W = lambda *c: idset(run(Where(Scan("FxGroup"), tuple(c))))  # noqa: E731
    assert W(Cond("name", "=", "alpha")) == fx("g2")
    assert W(Cond("name", "=", "Alpha")) == fx("g1")
    assert W(Cond("name", "starts_with", "Al")) == fx("g1")
    assert W(Cond("name", "starts_with", "al")) == fx("g2")
    assert W(Cond("note", "contains_text", "World")) == fx("g1", "g4")
    assert W(Cond("note", "ends_with", "world")) == fx("g2")
    # code-point order (amendment 2): "Alpha" < "Beta" < "Delta" < "Gamma" < "alpha"
    assert W(Cond("name", "<", "Beta")) == fx("g1")
    assert W(Cond("name", ">=", "Delta")) == fx("g5", "g4", "g2")
    assert W(Cond("name", ">", "Z")) == fx("g2")


def test_bool_only_equality(run):
    W = lambda *c: idset(run(Where(Scan("FxGroup"), tuple(c))))  # noqa: E731
    assert W(Cond("active", "=", True)) == fx("g1", "g3")
    assert W(Cond("active", "=", False)) == fx("g2", "g4")
    assert W(Cond("active", "<>", True)) == fx("g2", "g4")  # g5 lacks it (S4)
    for op in ("<", ">", "<=", ">="):
        with pytest.raises(InvalidOp):
            run(Where(Scan("FxGroup"), (Cond("active", op, True),)))


def test_list_contains_and_size(run):
    W = lambda *c: idset(run(Where(Scan("FxTech"), tuple(c))))  # noqa: E731
    assert W(Cond("platforms", "contains", "Linux")) == fx("t1")
    assert W(Cond("platforms", "contains", "linux")) == fx("t3")
    assert W(Cond("platforms", "size", 2, ">=")) == fx("t1")
    assert W(Cond("platforms", "size", 1, "=")) == fx("t2", "t3", "t5")
    assert W(Cond("platforms", "size", 1, "<")) == set()  # t4 lacks the list
    assert W(Cond("platforms", "size", 1, "<>")) == fx("t1")
    assert idset(run(Where(Scan("FxGroup"), (Cond("aliases", "size", 2, "="),)))) == fx("g1", "g5")
    with pytest.raises(InvalidOp):
        run(Where(Scan("FxTech"), (Cond("platforms", "=", "Linux"),)))


# --------------------------------------------------------------------------- #
# S6 dates
# --------------------------------------------------------------------------- #
# created: g1 2020-03-15T10:00:00Z, g2 2021-07-01, g3 "15/03/2020", g4 2019-12-31, g5 2022-01-01T00:00:00Z


def test_date_compare_on_iso_prefix(run):
    W = lambda *c: idset(run(Where(Scan("FxGroup"), tuple(c))))  # noqa: E731
    assert W(Cond("created", "=", "2020-03-15")) == fx("g1")
    assert W(Cond("created", "<=", "2020-03-15")) == fx("g1", "g4")
    assert W(Cond("created", ">=", "2020-03-15")) == fx("g1", "g2", "g5")
    assert W(Cond("created", "after", "2020-03-15")) == fx("g2", "g5")
    assert W(Cond("created", "before", "2020-03-15")) == fx("g4")
    assert W(Cond("created", "between", ("2020-03-15", "2021-07-01"))) == fx("g1", "g2")


def test_year_part(run):
    W = lambda *c: idset(run(Where(Scan("FxGroup"), tuple(c))))  # noqa: E731
    assert W(Cond("created", "year", 2020, "=")) == fx("g1")  # g3 spells 2020, not ISO
    assert W(Cond("created", "year", 2021, ">=")) == fx("g2", "g5")
    assert W(Cond("created", "year", 2020, "<>")) == fx("g2", "g4", "g5")


def test_non_iso_date_never_matches(run):
    W = lambda *c: idset(run(Where(Scan("FxGroup"), tuple(c))))  # noqa: E731
    assert W(Cond("created", "<>", "2020-01-01")) == fx("g1", "g2", "g4", "g5")
    assert W(Cond("created", "<", "9999-12-31")) == fx("g1", "g2", "g4", "g5")
    # modified: t1 2020-01-01, t2 2020-06-30T.., t3 2021-01-01, t4 "not-a-date", t5 missing
    assert idset(run(Where(Scan("FxTech"), (Cond("modified", "before", "2030-01-01"),)))) == fx("t1", "t2", "t3")
    assert idset(run(Where(Scan("FxTech"), (Cond("modified", "present"),)))) == fx("t1", "t2", "t3", "t4")
    # a dated edge with a non-ISO value: g1 -> s1 since "Jan 2020"
    hop = Hop("FxUses", "out", "", (Cond("since", "year", 2020, "="),))
    assert idset(run(Expand(Walk(G("g1"), (hop,))))) == fx("t1")
    hop = Hop("FxUses", "out", "", (Cond("since", "<>", "2020-01-15"),))
    assert idset(run(Expand(Walk(G("g1"), (hop,))))) == fx("t2")


# --------------------------------------------------------------------------- #
# S7 limits
# --------------------------------------------------------------------------- #


def test_cap_bounds_rows_not_count(run):
    r = run(Nodes(Scan("FxTech")), row_cap=2)
    assert ids(r) == ["fx:t1", "fx:t2"] and r.total == 5 and r.complete is False
    assert run(Count(Scan("FxTech")), row_cap=2).value == 5
    r = run(Expand(Walk(G("g3"), (USES_T,))), row_cap=1)
    assert ids(r) == ["fx:t2"] and r.total == 3 and r.complete is False


def test_aggregate_inputs_uncapped(run):
    assert run(Aggregate(Scan("FxTech"), "sum", "weight"), row_cap=2).value == 20
    assert run(Aggregate(Scan("FxTech"), "max", "weight"), row_cap=1).value == 7
    assert run(Aggregate(Scan("FxTech"), "min", "weight"), row_cap=1).value == 3
    assert run(Aggregate(Scan("FxTech"), "count"), row_cap=1).value == 5
    r = run(GroupBy(Scan("FxGroup"), (USES_T,), "count"), row_cap=2)
    assert len(r.rows) == 2 and r.total == 5 and r.complete is False


def test_total_and_complete_flag(run):
    for cap, complete in ((10, True), (5, True), (4, False)):
        r = run(Nodes(Scan("FxTech")), row_cap=cap)
        assert r.total == 5 and r.complete is complete and len(r.rows) == min(cap, 5)
    r = run(TypeScan("FxTech", (Cond("weight", "=", 5),)), row_cap=1)
    assert ids(r) == ["fx:t1"] and r.total == 2 and r.complete is False


# --------------------------------------------------------------------------- #
# S8 ties and order
# --------------------------------------------------------------------------- #
# rank: g1 3, g2 1, g3 missing, g4 3, g5 2


def test_rank_returns_ties_at_cut(run):
    r = run(Rank(Scan("FxGroup"), "desc", 1, prop="rank"))
    assert ids(r) == ["fx:g1", "fx:g4"] and [row["value"] for row in r.rows] == [3, 3]
    assert r.info.get("unranked") == 1
    assert ids(run(Rank(Scan("FxGroup"), "asc", 2, prop="rank"))) == ["fx:g2", "fx:g5"]
    assert ids(run(Rank(Scan("FxGroup"), "asc", 3, prop="rank"))) == ["fx:g2", "fx:g5", "fx:g1", "fx:g4"]
    # by walk count: g1 2, g2 2, g3 3, g4 0, g5 0 (0 is a real value)
    r = run(Rank(Scan("FxGroup"), "desc", 2, by_walk=(USES_T,)))
    assert ids(r) == ["fx:g3", "fx:g1", "fx:g2"] and [row["value"] for row in r.rows] == [3, 2, 2]
    r = run(Rank(Scan("FxGroup"), "asc", 1, by_walk=(USES_T,)))
    assert ids(r) == ["fx:g4", "fx:g5"] and [row["value"] for row in r.rows] == [0, 0]


def test_deterministic_order(run):
    assert ids(run(Nodes(Scan("FxGroup")))) == [f"fx:g{i}" for i in range(1, 6)]
    assert ids(run(Expand(Walk(T("t1"), (SUB,), 2)))) == ["fx:t2", "fx:t3"]
    # score: g1 1.5, g2 2.25, g3 3.0, g4 missing, g5 0.1
    r = run(Rank(Scan("FxGroup"), "desc", 10, prop="score"))
    assert ids(r) == ["fx:g3", "fx:g2", "fx:g1", "fx:g5"] and r.info.get("unranked") == 1
    # strings by code point
    assert ids(run(Rank(Scan("FxGroup"), "asc", 5, prop="name"))) == ["fx:g1", "fx:g3", "fx:g5", "fx:g4", "fx:g2"]
    # running twice gives the same rows
    assert run(Rank(Scan("FxGroup"), "desc", 2, by_walk=(USES_T,))).rows == \
        run(Rank(Scan("FxGroup"), "desc", 2, by_walk=(USES_T,))).rows


# --------------------------------------------------------------------------- #
# S9 empty groups
# --------------------------------------------------------------------------- #
# FxUses -> FxTech: g1 {t1,t2}, g2 {t1,t3}, g3 {t2,t3,t4}, g4 {} (a tool only), g5 {}
# weight t1 5, t2 5, t3 7, t4 3; score t1 .1, t2 .2, t3 .3, t4 missing


def test_groupby_keeps_empty_groups(run):
    r = run(GroupBy(Scan("FxGroup"), (USES_T,), "count"))
    assert by_id(r) == {"fx:g1": 2, "fx:g2": 2, "fx:g3": 3, "fx:g4": 0, "fx:g5": 0}
    assert r.total == 5


def test_empty_group_values(run):
    g = lambda fn, prop: by_id(run(GroupBy(Scan("FxGroup"), (USES_T,), fn, prop)))  # noqa: E731
    assert g("sum", "weight") == {"fx:g1": 10, "fx:g2": 12, "fx:g3": 15, "fx:g4": 0, "fx:g5": 0}
    assert g("min", "weight") == {"fx:g1": 5, "fx:g2": 5, "fx:g3": 3, "fx:g4": None, "fx:g5": None}
    assert g("max", "weight") == {"fx:g1": 5, "fx:g2": 7, "fx:g3": 7, "fx:g4": None, "fx:g5": None}
    assert g("median", "weight") == {"fx:g1": 5, "fx:g2": 6, "fx:g3": 5, "fx:g4": None, "fx:g5": None}
    avg = g("avg", "score")
    assert avg["fx:g4"] is None and avg["fx:g5"] is None
    for k, want in (("fx:g1", 0.15), ("fx:g2", 0.2), ("fx:g3", 0.25)):
        assert avg[k] == pytest.approx(want, rel=1e-9)


def test_having_can_select_zero(run):
    r = run(GroupBy(Scan("FxGroup"), (USES_T,), "count", having=("=", 0)))
    assert by_id(r) == {"fx:g4": 0, "fx:g5": 0}
    assert by_id(run(GroupBy(Scan("FxGroup"), (USES_T,), "count", having=(">", 2)))) == {"fx:g3": 3}
    assert by_id(run(GroupBy(Scan("FxGroup"), (USES_T,), "sum", "weight", having=("<", 11)))) == \
        {"fx:g1": 10, "fx:g4": 0, "fx:g5": 0}


# --------------------------------------------------------------------------- #
# S10 paths
# --------------------------------------------------------------------------- #
# FxLink: p1->p2, p1->p3, p2->p4, p3->p4, p4->p5, p5->p1, p5->p6; p7 alone


def _paths(r: Result) -> set[tuple[tuple[str, ...], tuple[str, ...]]]:
    out = set()
    for row in r.rows:
        path = list(row["path"])
        nodes = tuple(x for x in path if str(x).startswith("fx:"))
        rels = tuple(row.get("rels") or [x for x in path if not str(x).startswith("fx:")])
        out.add((nodes, rels))
    return out


def test_reach_is_acyclic(run):
    assert idset(run(Reach(P("p1"), LINK, 6))) == fx("p2", "p3", "p4", "p5", "p6")
    assert idset(run(Reach(P("p4"), LINK, 6))) == fx("p5", "p1", "p6", "p2", "p3")
    assert run(Count(Reach(P("p1"), LINK, 6))).value == 5
    assert idset(run(Reach(P("p6"), (("FxLink", "both"),), 1))) == fx("p5")
    assert idset(run(Reach(P("p7"), LINK, 6))) == set()


def test_all_shortest_paths_returned(run):
    L = ("FxLink", "FxLink")
    assert _paths(run(Shortest(P("p1"), P("p4"), LINK, 6))) == {
        (("fx:p1", "fx:p2", "fx:p4"), L), (("fx:p1", "fx:p3", "fx:p4"), L)}
    L4 = ("FxLink",) * 4
    assert _paths(run(Shortest(P("p1"), P("p6"), LINK, 6))) == {
        (("fx:p1", "fx:p2", "fx:p4", "fx:p5", "fx:p6"), L4), (("fx:p1", "fx:p3", "fx:p4", "fx:p5", "fx:p6"), L4)}
    assert _paths(run(Shortest(P("p4"), P("p1"), LINK, 6))) == {(("fx:p4", "fx:p5", "fx:p1"), L)}
    # default: every card relationship, either direction -> also p1 <- p5 <- p4
    assert _paths(run(Shortest(P("p1"), P("p4"), (), 6))) == {
        (("fx:p1", "fx:p2", "fx:p4"), L), (("fx:p1", "fx:p3", "fx:p4"), L), (("fx:p1", "fx:p5", "fx:p4"), L)}
    r = run(Shortest(P("p1"), P("p7"), (), 6))
    assert r.rows == [] and r.total == 0


def test_depth_cap_marks_partial(run):
    r = run(Reach(P("p1"), LINK, 2))
    assert idset(r) == fx("p2", "p3", "p4") and r.partial is True and r.complete is False
    r = run(Reach(P("p1"), LINK, 6))
    assert r.partial is False and r.complete is True
    r = run(Shortest(P("p1"), P("p6"), LINK, 3))
    assert r.rows == []


# --------------------------------------------------------------------------- #
# S11 numbers
# --------------------------------------------------------------------------- #


def test_median_even_count(run):
    # rank over groups present: 3, 1, 3, 2 -> 1 2 3 3 -> (2 + 3) / 2
    assert run(Aggregate(Scan("FxGroup"), "median", "rank")).value == 2.5
    # score over techniques present: .1 .2 .3 .7 -> (.2 + .3) / 2
    assert run(Aggregate(Scan("FxTech"), "median", "score")).value == pytest.approx(0.25, rel=1e-9)
    # weight 5 5 7 3 -> 3 5 5 7 -> 5
    assert run(Aggregate(Scan("FxTech"), "median", "weight")).value == 5


def test_float_sum_tolerance(run, engines):
    s = run(Aggregate(Scan("FxTech"), "sum", "score")).value
    assert s == pytest.approx(1.3, rel=1e-9)
    assert run(Aggregate(Scan("FxTech"), "avg", "score")).value == pytest.approx(0.325, rel=1e-9)
    # integers are exact
    assert run(Aggregate(Scan("FxTech"), "sum", "weight")).value == 20
    assert run(Aggregate(Scan("FxTech"), "avg", "weight")).value == 5.0


# --------------------------------------------------------------------------- #
# S12 nothing found is an answer
# --------------------------------------------------------------------------- #


def test_empty_is_an_answer(run):
    r = run(Where(Scan("FxGroup"), (Cond("name", "=", "Nobody"),)))
    assert r.rows == [] and r.total == 0 and r.complete is True
    _no_anchor_missing(r)
    r = run(Expand(Walk(G("g5"), (USES_T,))))
    assert r.rows == [] and r.total == 0
    _no_anchor_missing(r)
    assert run(Count(Walk(G("g5"), (USES_T,)))).value == 0
    assert run(Aggregate(Walk(G("g5"), (USES_T,)), "sum", "weight")).value == 0
    assert run(Aggregate(Walk(G("g5"), (USES_T,)), "max", "weight")).value is None


def test_anchor_not_found_distinct(run):
    r = run(Expand(Walk(G("nope"), (USES_T,))))
    assert r.rows == [] and r.info.get("anchor_not_found") == ["fx:nope"]
    r = run(Describe(Anchors(("fx:g1", "fx:nope"), "FxGroup")))
    assert ids(r) == ["fx:g1"] and r.info.get("anchor_not_found") == ["fx:nope"]
    r = run(Verify(G("nope"), T("t1")))
    assert r.info.get("anchor_not_found") == ["fx:nope"]


# --------------------------------------------------------------------------- #
# Amendments (§ 9)
# --------------------------------------------------------------------------- #


def test_amendment1_path_depth_cap(run):
    # paths go beyond the card's walk cap (3), up to 10
    assert idset(run(Reach(P("p1"), LINK, 4))) == fx("p2", "p3", "p4", "p5", "p6")
    run(Reach(P("p1"), LINK, 10))
    with pytest.raises(InvalidOp):
        run(Reach(P("p1"), LINK, 11))
    with pytest.raises(InvalidOp):
        run(Expand(Walk(T("t1"), (SUB,), 4)))  # a walk keeps the card's cap
    # the default is 6: p1's whole component within 6 steps, not partial
    r = run(Reach(P("p1"), LINK))
    assert idset(r) == fx("p2", "p3", "p4", "p5", "p6") and r.partial is False


def test_amendment2_number_text(run):
    # size_text: g1 "10", g2 "9.5", g3 "n/a" (missing), g4 "100", g5 "-3"
    W = lambda *c: idset(run(Where(Scan("FxGroup"), tuple(c))))  # noqa: E731
    assert W(Cond("size_text", ">", 9)) == fx("g1", "g2", "g4")  # as text, "10" < "9"
    assert W(Cond("size_text", "<>", 10)) == fx("g2", "g4", "g5")  # "n/a" is missing
    assert W(Cond("size_text", "=", 10)) == fx("g1")
    assert run(Aggregate(Scan("FxGroup"), "sum", "size_text")).value == pytest.approx(116.5, rel=1e-9)
    assert run(Aggregate(Scan("FxGroup"), "max", "size_text")).value == 100
    assert run(Aggregate(Scan("FxGroup"), "min", "size_text")).value == -3
    r = run(Rank(Scan("FxGroup"), "desc", 2, prop="size_text"))
    assert ids(r) == ["fx:g4", "fx:g1"] and r.info.get("unranked") == 1


def test_amendment2_null_sorts_last(run):
    # avg score per group: g1 .15, g2 .2, g3 .25, g4 null, g5 null
    desc = run(GroupBy(Scan("FxGroup"), (USES_T,), "avg", "score", order="desc", k=10))
    assert ids(desc) == ["fx:g3", "fx:g2", "fx:g1", "fx:g4", "fx:g5"]
    asc = run(GroupBy(Scan("FxGroup"), (USES_T,), "avg", "score", order="asc", k=10))
    assert ids(asc) == ["fx:g1", "fx:g2", "fx:g3", "fx:g4", "fx:g5"]
    # a null is reached by top-k only when fewer than k have a value
    assert ids(run(GroupBy(Scan("FxGroup"), (USES_T,), "avg", "score", order="asc", k=3))) == \
        ["fx:g1", "fx:g2", "fx:g3"]


def test_amendment2_end_conds(run):
    r = run(GroupBy(Scan("FxGroup"), (USES_T,), "count", end_conds=(Cond("platforms", "contains", "Windows"),)))
    assert by_id(r) == {"fx:g1": 2, "fx:g2": 1, "fx:g3": 1, "fx:g4": 0, "fx:g5": 0}


def test_amendment2_values_one_per_present_node(run):
    r = run(Values(Scan("FxGroup"), "score"))
    assert {row["id"]: row["value"] for row in r.rows} == {"fx:g1": 1.5, "fx:g2": 2.25, "fx:g3": 3.0, "fx:g5": 0.1}
    assert r.info.get("lacking") == 1
    assert all(row["value"] is not None for row in r.rows)


def test_amendment3_expand_returns_every_prefix(run):
    # g3 -> {t2, t3, t4}; then FxSub: t2 -> t3; t3 and t4 go nowhere but are kept
    r = run(Expand(Walk(G("g3"), (USES_T, SUB))))
    assert idset(r) == fx("t2", "t3", "t4")
    # m1 -> {t1, t2}; then used-by: t1 <- g1, g2; t2 <- g1, g3
    r = run(Expand(Walk(Anchors(("fx:m1",), "FxMit"), (Hop("FxMitigates", "out", "FxTech"),
                                                        Hop("FxUses", "in", "FxGroup")))))
    assert idset(r) == fx("t1", "t2", "g1", "g2", "g3")
    # count is the walk's end only (distinct end nodes)
    assert run(Count(Walk(G("g3"), (USES_T, SUB)))).value == 1


def test_amendment3_repeated_hop_filters_every_step(run):
    # A repeated hop's every repetition count is a prefix; eqfilter is on the last
    # hop's label, so it applies at each count. t1 -FxSub-> t2 (weight 5) -> t3 (7),
    # t1 -> t3: only t3 passes; t2 is not added as "the route" (added after the
    # H3 check found the compilers adding it).
    r = run(Expand(Walk(T("t1"), (SUB,), 2, (Cond("weight", "=", 7),))))
    assert ids(r) == ["fx:t3"]
    assert run(Count(Walk(T("t1"), (SUB,), 2, (Cond("weight", "=", 7),)))).value == 1
    assert ids(run(Expand(Walk(T("t1"), (SUB,), 2, (Cond("weight", "=", 5),))))) == ["fx:t2"]


# --- amendment 4 -------------------------------------------------------------------
# FxRel: c1->c2, c2->c1, c2->c3, c3->c3 (self-loop), c4->c2;  FxAlt: c1->c2
# tags: c1 [a], c2 [] (not stored: missing), c3 [a, b], c4 none

C = lambda *n: Anchors(tuple(f"fx:{x}" for x in n), "FxNode")  # noqa: E731
REL = Hop("FxRel", "out", "FxNode")
REL_IN = Hop("FxRel", "in", "FxNode")
ALT_IN = Hop("FxAlt", "in", "FxNode")


def test_amendment4_walk_never_returns_to_its_start(run):
    # c1 -FxRel-> c2 -FxRel-> {c1 (the start: excluded), c3}
    assert idset(run(Nodes(Walk(C("c1"), (REL, REL))))) == fx("c3")
    assert run(Count(Walk(C("c1"), (REL, REL)))).value == 1
    assert idset(run(Expand(Walk(C("c1"), (REL, REL))))) == fx("c2", "c3")
    # A -R-> B <-R'- A with no relationship reused: c1 -FxRel-> c2 <-FxAlt- c1 returns to c1
    assert idset(run(Nodes(Walk(C("c1"), (REL, ALT_IN))))) == set()
    assert idset(run(Expand(Walk(C("c1"), (REL, ALT_IN))))) == fx("c2")
    # A -R-> B <-R- ?: c1 -> c2 <- {c1 (excluded), c4}
    assert idset(run(Nodes(Walk(C("c1"), (REL, REL_IN))))) == fx("c4")


def test_amendment4_two_cycle_and_self_loop(run):
    # c2 -> c1 -> c2 (the start) and c2 -> c3 -> c3 (c3 twice): neither walk is kept
    assert idset(run(Nodes(Walk(C("c2"), (REL, REL))))) == set()
    assert idset(run(Expand(Walk(C("c2"), (REL, REL))))) == fx("c1", "c3")
    # a self-loop never returns the start, even in one hop
    assert idset(run(Nodes(Walk(C("c3"), (REL,))))) == set()
    assert run(Count(Walk(C("c3"), (REL,)))).value == 0
    # a repeated hop: 1 step {c1, c3}; 2 steps would revisit c2 or c3
    assert idset(run(Expand(Walk(C("c2"), (REL,), 2)))) == fx("c1", "c3")
    assert idset(run(Nodes(Walk(C("c2"), (REL,), 3)))) == fx("c1", "c3")
    # from c4: c2; c1, c3; then c1 -> c2 and c3 -> c3 revisit
    assert idset(run(Expand(Walk(C("c4"), (REL,), 3)))) == fx("c2", "c1", "c3")


def test_amendment4_rank_groupby_having_walks_are_acyclic(run):
    # two FxRel hops from each: c1 {c3}, c2 {}, c3 {}, c4 {c1, c3}
    r = run(GroupBy(Scan("FxNode"), (REL, REL), "count"))
    assert by_id(r) == {"fx:c1": 1, "fx:c2": 0, "fx:c3": 0, "fx:c4": 2}
    r = run(Rank(Scan("FxNode"), "desc", 2, by_walk=(REL, REL)))
    assert ids(r) == ["fx:c4", "fx:c1"] and [row["value"] for row in r.rows] == [2, 1]
    # one hop: c3's only FxRel is its self-loop, so it has none
    assert idset(run(Having(Scan("FxNode"), REL))) == fx("c1", "c2", "c4")
    assert idset(run(Absence(Scan("FxNode"), REL))) == fx("c3")


def test_amendment4_anchor_of_another_label_is_not_found(run):
    r = run(Expand(Walk(Anchors(("fx:t1",), "FxGroup"), (USES_T,))))
    assert r.rows == [] and r.info.get("anchor_not_found") == ["fx:t1"]
    r = run(Describe(Anchors(("fx:g1", "fx:t1"), "FxGroup")))
    assert ids(r) == ["fx:g1"] and r.info.get("anchor_not_found") == ["fx:t1"]
    r = run(Count(Walk(Anchors(("fx:g1", "fx:t1"), "FxGroup"), (USES_T,))))
    assert r.value == 2 and r.info.get("anchor_not_found") == ["fx:t1"]
    r = run(Verify(Anchors(("fx:t1",), "FxGroup"), T("t2")))
    assert r.info.get("anchor_not_found") == ["fx:t1"] and r.info.get("exists") is False
    # without a label, the id alone matches
    r = run(Nodes(Anchors(("fx:t1", "fx:g1"))))
    assert idset(r) == fx("t1", "g1")
    _no_anchor_missing(r)


def test_amendment4_empty_list_is_missing(run):
    W = lambda *c: idset(run(Where(Scan("FxNode"), tuple(c))))  # noqa: E731
    assert W(Cond("tags", "present")) == fx("c1", "c3")
    assert W(Cond("tags", "missing")) == fx("c2", "c4")
    assert W(Cond("tags", "size", 0, "=")) == set()
    assert W(Cond("tags", "size", 2, "<")) == fx("c1")
    assert W(Cond("tags", "not_contains", "b")) == fx("c1")
    assert W(Cond("tags", "contains", "a")) == fx("c1", "c3")
    r = run(Values(Scan("FxNode"), "tags"))
    assert {row["id"] for row in r.rows} == fx("c1", "c3") and r.info.get("lacking") == 2
    r = run(Describe(C("c2")))
    assert ids(r) == ["fx:c2"] and "tags" not in r.rows[0]["properties"]


def test_having_needs_a_numeric_group_value(run):
    # min/max of a text or date property is text; a numeric `having` cannot select it
    with pytest.raises(InvalidOp):
        run(GroupBy(Scan("FxGroup"), (USES_T,), "min", "modified", having=(">", 0)))
    assert by_id(run(GroupBy(Scan("FxGroup"), (USES_T,), "max", "weight", having=(">=", 7)))) == \
        {"fx:g2": 7, "fx:g3": 7}


# --------------------------------------------------------------------------- #
# The other operators on the fixture (verify, common, union, absence, edge filters)
# --------------------------------------------------------------------------- #


def test_verify_witness_and_any_relationship(run):
    r = run(Verify(G("g1"), T("t1"), "FxUses", "out"))
    assert r.info.get("exists") is True and len(r.rows) == 1
    w = r.rows[0]
    assert (w["relation"], w["direction"]) == ("FxUses", "out")
    assert w["properties"].get("since") == "2020-01-15" and w["properties"].get("weight") == 0.5
    assert run(Verify(G("g1"), T("t3"))).info.get("exists") is False
    r = run(Verify(T("t1"), G("g1")))  # any relationship, either direction
    assert r.info.get("exists") is True and [(w["relation"], w["direction"]) for w in r.rows] == [("FxUses", "in")]
    r = run(Verify(T("t1"), T("t3")))
    assert r.info.get("exists") is True and [(w["relation"], w["direction"]) for w in r.rows] == [("FxSub", "out")]
    r = run(Verify(G("g1"), T("t3"), "FxUses", "out"))
    assert r.info.get("exists") is False and r.rows == []


def test_common_union_absence(run):
    assert idset(run(Common(Anchors(("fx:g1", "fx:m1"))))) == fx("t1", "t2")
    assert idset(run(Common(Anchors(("fx:g1", "fx:g3"), "FxGroup")))) == fx("t2")
    r = run(Union_((Walk(G("g1"), (USES_T,)), Walk(Anchors(("fx:m2",), "FxMit"),
                                                   (Hop("FxMitigates", "out", "FxTech"),)))))
    assert ids(r) == ["fx:t1", "fx:t2"]
    mitigated_by = Hop("FxMitigates", "in", "FxMit")
    assert idset(run(Absence(Scan("FxTech"), mitigated_by))) == fx("t3", "t4", "t5")
    # t1 is mitigated only by M-One, which fails the condition: it counts as lacking
    assert idset(run(Absence(Scan("FxTech"), mitigated_by, (Cond("name", "=", "M-Two"),)))) == \
        fx("t1", "t3", "t4", "t5")
    assert idset(run(Having(Scan("FxGroup"), USES_T, True, (Cond("platforms", "contains", "Linux"),)))) == \
        fx("g1", "g2")


def test_edge_filters_and_dated_edges(run):
    since_after = Hop("FxUses", "out", "FxTech", (Cond("since", "after", "2020-01-01"),))
    assert idset(run(Expand(Walk(G("g1", "g2", "g3"), (since_after,))))) == fx("t1", "t2", "t3")
    heavy = Hop("FxUses", "out", "FxTech", (Cond("weight", ">", 1.0),))
    assert idset(run(Expand(Walk(G("g1", "g2", "g3"), (heavy,))))) == fx("t2")
    between = Hop("FxUses", "out", "", (Cond("since", "between", ("2020-01-15", "2021-02-01")),))
    assert idset(run(Expand(Walk(G("g1", "g2", "g3"), (between,))))) == fx("t1", "t2")
    # a missing edge property never matches, not even <>
    ne = Hop("FxUses", "out", "", (Cond("via", "<>", "auto"),))
    assert idset(run(Expand(Walk(G("g1", "g2", "g3", "g4"), (ne,))))) == fx("s1")
