"""``from_v3``: kill-test v3 requests as the internal form (hand-written cases and a sweep)."""

from __future__ import annotations

import collections

import pytest

from utils.agent.catalog import from_killtest_card
from utils.killtests.typed import fixture, request
from utils.specialists.algebra import (Aggregate, Cond, Count, GroupBy, Having, Hop, Nodes, Rank, Scan, Union_,
                                       Values, Where, check)
from utils.specialists.algebra.from_v3 import NotExpressible, from_v3, semantic_differences

CARD = fixture.card()
MODEL = from_killtest_card(CARD)


def convert(req: dict):
    norm = request.validate(req, CARD)
    tree = from_v3(norm, CARD)
    assert check(tree, MODEL) is None
    return tree, semantic_differences(norm)


def test_names_with_named_far_node_two_hops():
    tree, diffs = convert({
        "nodes": {"n": {"label": "Alpha"}, "m0": {"label": "Beta"}, "m1": {"label": "Gamma", "name": "gamma 3"}},
        "edges": [{"from": "n", "type": "linkB", "to": "m0"}, {"from": "m0", "type": "toG", "to": "m1"}],
        "answer": {"kind": "names"}})
    target = Having(Scan("Beta"), Hop("toG", "out", "Gamma"), True, (Cond("name", "=", "gamma 3"),))
    assert tree == Nodes(Having(Scan("Alpha"), Hop("linkB", "out", "Beta"), True, (), target))
    assert diffs == []


def test_where_and_key_name_and_edge_filter():
    tree, _ = convert({
        "nodes": {"n": {"label": "Alpha", "name": "alpha 3"}, "m0": {"label": "Delta", "name": "The Red Story 1"}},
        "edges": [{"from": "n", "type": "rated", "to": "m0", "var": "r",
                   "filters": [{"prop": "stars", "op": ">", "value": 2}]}],
        "where": [{"var": "n", "prop": "born", "op": ">=", "value": 1990, "part": "year"},
                  {"var": "n", "prop": "tags", "op": "contains", "value": "red"}],
        "answer": {"kind": "count"}})
    base = Where(Scan("Alpha"), (Cond("name", "=", "alpha 3"), Cond("born", "year", 1990, cmp=">="),
                                 Cond("tags", "contains", "red")))
    hop = Hop("rated", "out", "Delta", (Cond("stars", ">", 2),))
    # Delta's key is ``title``: a v3 name is a key value, never a stored id.
    assert tree == Count(Having(base, hop, True, (Cond("title", "=", "The Red Story 1"),)))


def test_incoming_edge_and_size():
    tree, _ = convert({
        "nodes": {"n": {"label": "Beta"}, "m0": {"label": "Alpha"}},
        "edges": [{"from": "m0", "type": "linkB", "to": "n"}],
        "where": [{"var": "n", "prop": "colors", "op": ">=", "value": 2, "part": "size"}],
        "answer": {"kind": "values", "prop": "rank", "distinct": True}})
    assert tree == Values(Having(Where(Scan("Beta"), (Cond("colors", "size", 2, cmp=">="),)),
                                 Hop("linkB", "in", "Alpha")), "rank", True)


def test_any_of_is_a_union_of_whole_patterns():
    tree, _ = convert({
        "nodes": {"n": {"label": "Alpha"}, "m0": {"label": "Beta", "name": "beta 1"},
                  "m1": {"label": "Delta", "name": "The Red Story 1"}},
        "any_of": [[{"from": "n", "type": "linkB", "to": "m0"}], [{"from": "n", "type": "rated", "to": "m1"}]],
        "answer": {"kind": "names"}})
    assert tree == Nodes(Union_((
        Having(Scan("Alpha"), Hop("linkB", "out", "Beta"), True, (Cond("name", "=", "beta 1"),)),
        Having(Scan("Alpha"), Hop("rated", "out", "Delta"), True, (Cond("title", "=", "The Red Story 1"),)))))


def test_none_is_absence_with_far_conditions():
    tree, _ = convert({
        "nodes": {"n": {"label": "Alpha"}, "m0": {"label": "Beta"}},
        "none": [{"from": "n", "type": "linkB", "to": "m0"}],
        "where": [{"var": "m0", "prop": "rank", "op": "<", "value": 100}],
        "answer": {"kind": "names"}})
    assert tree == Nodes(Having(Scan("Alpha"), Hop("linkB", "out", "Beta"), False, (Cond("rank", "<", 100),)))


def test_count_per_with_optional_edge():
    tree, diffs = convert({
        "nodes": {"n": {"label": "Alpha"}, "m1": {"label": "Delta"}},
        "optional": [{"from": "n", "type": "rated", "to": "m1"}],
        "answer": {"kind": "count_per", "of": "m1"}})
    assert tree == GroupBy(Scan("Alpha"), (Hop("rated", "out", "Delta"),), "count")
    assert diffs == []


def test_per_over_required_chain_keeps_the_edges_in_members():
    tree, diffs = convert({
        "nodes": {"n": {"label": "Alpha"}, "m0": {"label": "Beta"}, "m1": {"label": "Gamma"}},
        "edges": [{"from": "n", "type": "linkB", "to": "m0"}, {"from": "m0", "type": "toG", "to": "m1"}],
        "answer": {"kind": "per", "of": "m1", "fn": "max", "prop": "size", "order": "desc", "limit": 2}})
    members = Having(Scan("Alpha"), Hop("linkB", "out", "Beta"), True, (),
                     Having(Scan("Beta"), Hop("toG", "out", "Gamma")))
    assert tree == GroupBy(members, (Hop("linkB", "out", "Beta"), Hop("toG", "out", "Gamma")), "max", "size",
                           None, "desc", 2)
    assert diffs == ["ties", "missing_values"]


def test_top_with_limit_flags_ties():
    tree, diffs = convert({"nodes": {"n": {"label": "Beta"}},
                           "answer": {"kind": "top", "prop": "rank", "order": "asc", "limit": 3}})
    assert tree == Rank(Scan("Beta"), "asc", 3, "rank")
    assert "ties" in diffs


def test_aggregate_and_refusals():
    tree, _ = convert({"nodes": {"n": {"label": "Alpha"}}, "answer": {"kind": "aggregate", "fn": "avg", "prop": "score"}})
    assert tree == Aggregate(Scan("Alpha"), "avg", "score")
    cases = {
        "not_tree": {"nodes": {"n": {"label": "Alpha"}, "m0": {"label": "Beta"}},
                     "edges": [{"from": "n", "type": "linkA", "to": "m0"}, {"from": "n", "type": "linkB", "to": "m0"}],
                     "answer": {"kind": "names"}},
        "same_type_twice": {"nodes": {"n": {"label": "Alpha"}, "m0": {"label": "Beta"}, "m1": {"label": "Alpha"}},
                            "edges": [{"from": "n", "type": "linkB", "to": "m0"},
                                      {"from": "m1", "type": "linkB", "to": "m0"}],
                            "answer": {"kind": "names"}},
        "top_without_limit": {"nodes": {"n": {"label": "Beta"}},
                              "answer": {"kind": "top", "prop": "rank", "order": "asc"}},
        "aggregate_year": {"nodes": {"n": {"label": "Alpha"}},
                           "answer": {"kind": "aggregate", "fn": "max", "prop": "born", "part": "year"}},
        "edge_time_window": {"nodes": {"n": {"label": "Alpha"}, "m0": {"label": "Beta"}},
                             "edges": [{"from": "n", "type": "linkA", "to": "m0", "var": "r",
                                        "filters": [{"op": "current", "start": "start_year", "end": "end_year"}]}],
                             "answer": {"kind": "names"}},
        "float_text": {"nodes": {"n": {"label": "Alpha"}},
                       "where": [{"var": "n", "prop": "price", "op": ">", "value": 10}], "answer": {"kind": "count"}},
    }
    for reason, req in cases.items():
        with pytest.raises(NotExpressible) as exc:
            from_v3(request.validate(req, CARD), CARD)
        assert exc.value.reason == reason


def test_same_type_twice_allowed_when_ends_provably_differ():
    tree, _ = convert({
        "nodes": {"n": {"label": "Alpha"}, "m0": {"label": "Beta", "name": "beta 1"},
                  "m1": {"label": "Beta", "name": "beta 2"}},
        "edges": [{"from": "n", "type": "linkB", "to": "m0"}, {"from": "n", "type": "linkB", "to": "m1"}],
        "answer": {"kind": "names"}})
    assert isinstance(tree.of, Having) and isinstance(tree.of.of, Having)


def test_sweep_generated_requests():
    gen = fixture.Generator(fixture.build(), seed=11, v3=True)
    reasons: collections.Counter = collections.Counter()
    diffs: collections.Counter = collections.Counter()
    converted = 0
    total = 2000
    for _ in range(total):
        req = request.validate(gen.request(), CARD)
        try:
            tree = from_v3(req, CARD)
        except NotExpressible as exc:
            reasons[exc.reason] += 1
            continue
        assert check(tree, MODEL) is None, req
        converted += 1
        diffs.update(semantic_differences(req))
    share = converted / total
    print(f"\nconverted {converted}/{total} = {share:.3f}; refused {dict(reasons.most_common())}; "
          f"differences {dict(diffs)}")
    assert converted + sum(reasons.values()) == total
    assert share > 0.5
