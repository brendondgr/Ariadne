"""Typed arm: request validation, conversion from gold Cypher, and compilation.

No database: the end-to-end checks are ``utils.killtests.typed.verify`` (gold
answers on terrorist_attack, and the Cypher/Gremlin differential on the fixture).
"""

import json

import pytest

from utils.killtests.t1.shots import SHOTS
from utils.killtests.typed import fixture
from utils.killtests.typed.cypher import compile_cypher
from utils.killtests.typed.from_gold import Unsupported, convert
from utils.killtests.typed.gremlin import compile_gremlin, finish
from utils.killtests.typed.prompts import extract_request, messages, shot_requests
from utils.killtests.typed.request import Card, InvalidRequest, validate

TA = Card("terrorist_attack")


def test_shots_convert_validate_and_round_trip_to_cypher():
    for s in SHOTS:
        req = validate(convert(s["cypher"]), TA)
        cy = compile_cypher(req, TA)
        assert "MATCH" in cy
        assert compile_gremlin(req, TA).script.startswith("g.")
    assert [r["request"]["answer"]["kind"] for r in shot_requests()] == ["names_with", "count_per", "compare"]


def test_validation_rejects_wrong_direction_and_unknown_names():
    good = convert(SHOTS[0]["cypher"])
    bad = json.loads(json.dumps(good))
    e = bad["edges"][0]
    e["from"], e["to"] = e["to"], e["from"]
    with pytest.raises(InvalidRequest, match="does not go from"):
        validate(bad, TA)
    bad = json.loads(json.dumps(good))
    bad["answer"]["prop"] = "nope"
    with pytest.raises(InvalidRequest):
        validate(bad, TA)
    with pytest.raises(InvalidRequest, match="'n'"):
        validate({"nodes": {"a": {"label": "Terrorist"}}, "answer": {"kind": "names"}}, TA)


def test_converter_rejects_unknown_templates():
    with pytest.raises(Unsupported):
        convert("MATCH (n:Terrorist) RETURN n.name LIMIT 5")


def test_cyclic_pattern_compiles_to_a_walk_with_a_join():
    c = fixture.card()
    req = validate({"nodes": {"n": {"label": "Beta"}, "m0": {"label": "Alpha"}},
                    "edges": [{"from": "m0", "type": "linkA", "to": "n"}, {"from": "m0", "type": "linkB", "to": "n"}],
                    "answer": {"kind": "count"}}, c)
    g = compile_gremlin(req, c).script
    assert "match(" not in g and "where(eq('n'))" in g


def test_same_type_edges_must_differ():
    req = validate(convert("MATCH (n:TerroristAttack)-[r0:targets]->(m0:Target)<-[r1:targets]-"
                           "(m1:TerroristAttack {name: 'X'}) WITH DISTINCT n RETURN n.name"), TA)
    assert "neq(" in compile_gremlin(req, TA).script


def test_generator_requests_are_valid_and_compile():
    gen = fixture.Generator(fixture.build())
    c = fixture.card()
    for _ in range(300):
        req = validate(gen.request(), c)
        compile_cypher(req, c)
        compile_gremlin(req, c)


def test_finish_post_steps():
    assert finish([], "agg_null") == [None]
    assert finish([], "agg_zero") == [0]
    assert finish(["1987-03-01"], "year_null") == [1987]
    assert finish([5], None) == [5]


def test_prompt_and_extraction():
    m = messages("typed-3shot", "nba", "Who?")
    assert "Worked examples" in m[1]["content"] and "Graph: nba" in m[1]["content"]
    assert extract_request('x\n```json\n{"nodes": {}}\n```') == {"nodes": {}}
    assert extract_request('sure: {"a": 1}') == {"a": 1}


# ---- format v2 -------------------------------------------------------------------------------

def test_v2_any_of_edge_references_move_edges_into_branches():
    req = {"nodes": {"n": {"label": "TerroristAttack"}, "m0": {"label": "Country", "name": "A"},
                     "m1": {"label": "Country", "name": "B"}},
           "edges": [{"from": "n", "type": "occursIn", "to": "m0", "var": "r0"},
                     {"from": "n", "type": "occursIn", "to": "m1", "var": "r1"}],
           "any_of": [["r0"], ["r1"]], "answer": {"kind": "names"}}
    v = validate(req, TA)
    assert v.get("edges") == [] and [b[0]["var"] for b in v["any_of"]] == ["r0", "r1"]
    assert "UNION" in compile_cypher(v, TA)


def test_v2_edge_var_may_repeat_across_branches():
    e = {"from": "n", "type": "occursIn", "to": "m0", "var": "r"}
    req = {"nodes": {"n": {"label": "TerroristAttack"}, "m0": {"label": "Country", "name": "A"},
                     "m1": {"label": "Weapon", "name": "B"}},
           "any_of": [[e], [{"from": "n", "type": "employs", "to": "m1", "var": "r"}]], "answer": {"kind": "count"}}
    validate(req, TA)


def test_v2_key_property_and_multi_props():
    c = fixture.card()
    assert c.keys["Delta"] == "title" and c.keys["Alpha"] == "name"
    req = validate({"nodes": {"n": {"label": "Delta", "name": "X"}},
                    "answer": {"kind": "names_with", "props": ["year", "genre"]}}, c)
    cy = compile_cypher(req, c)
    assert "{`title`: 'X'}" in cy and "AS c2" in cy
    assert ".has('title', 'X')" in compile_gremlin(req, c).script


def test_v2_text_ops_and_aggregate_over_edge():
    c = fixture.card()
    req = validate({"nodes": {"n": {"label": "Delta"}, "m0": {"label": "Alpha", "name": "alpha 1"}},
                    "edges": [{"from": "m0", "type": "rated", "to": "n", "var": "r"}],
                    "where": [{"var": "n", "prop": "title", "op": "starts_with", "value": "The"}],
                    "answer": {"kind": "aggregate", "fn": "avg", "prop": "stars", "var": "r"}}, c)
    assert "STARTS WITH 'The'" in compile_cypher(req, c) and "WITH DISTINCT r RETURN avg(r.`stars`)" in compile_cypher(req, c)
    g = compile_gremlin(req, c).script
    assert "startingWith('The')" in g and ".as('r')" in g and "select('r').dedup().values('stars').mean()" in g


FX = fixture.card()


def test_v3_count_per_becomes_per_count():
    req = validate({"nodes": {"n": {"label": "Alpha"}, "m": {"label": "Beta"}},
                    "edges": [{"from": "n", "type": "linkB", "to": "m"}],
                    "answer": {"kind": "count_per", "of": "m"}}, FX)
    assert req["answer"]["kind"] == "per" and req["answer"]["fn"] == "count"
    assert "count(DISTINCT m)" in compile_cypher(req, FX)


def test_v3_per_with_having_order_limit_and_edge_aggregate():
    req = validate({"nodes": {"n": {"label": "Alpha"}, "d": {"label": "Delta"}},
                    "edges": [{"from": "n", "type": "rated", "to": "d", "var": "r"}],
                    "answer": {"kind": "per", "of": "r", "fn": "avg", "prop": "stars",
                               "having": {"op": ">", "value": 2}, "order": "desc", "limit": 3}}, FX)
    cy = compile_cypher(req, FX)
    assert "avg(r.`stars`)" in cy and "WHERE num > 2" in cy and cy.endswith("ORDER BY num DESC, n.`name` ASC LIMIT 3")
    gr = compile_gremlin(req, FX).script
    assert ".group()" in gr and ".limit(3)" in gr and "is(gt(2))" in gr
    with pytest.raises(InvalidRequest, match="limit needs"):
        validate({"nodes": {"n": {"label": "Alpha"}, "d": {"label": "Delta"}},
                  "edges": [{"from": "n", "type": "rated", "to": "d"}],
                  "answer": {"kind": "per", "of": "d", "fn": "count", "limit": 3}}, FX)


def test_v3_optional_and_none_accept_edge_references():
    req = validate({"nodes": {"n": {"label": "Alpha"}, "b": {"label": "Beta"}},
                    "edges": [{"from": "n", "type": "linkB", "to": "b", "var": "e1"}],
                    "optional": ["e1"], "answer": {"kind": "per", "of": "b", "fn": "count"}}, FX)
    assert req["edges"] == [] and req["optional"][0]["var"] == "e1"
    assert "OPTIONAL MATCH" in compile_cypher(req, FX)
    req = validate({"nodes": {"n": {"label": "Alpha"}, "g": {"label": "Gamma", "name": "gamma 1"}},
                    "edges": [{"from": "g", "type": "fromG", "to": "n", "var": "x"}], "none": ["x"],
                    "answer": {"kind": "names"}}, FX)
    assert "NOT EXISTS { MATCH (g:`Gamma`" in compile_cypher(req, FX)
    assert ".not(__.in('fromG')" in compile_gremlin(req, FX).script


def test_v3_ref_size_and_numbers_stored_as_text():
    req = validate({"nodes": {"n": {"label": "Alpha"}},
                    "where": [{"var": "n", "prop": "score", "op": ">", "ref": {"var": "n", "prop": "weight"}},
                              {"var": "n", "prop": "tags", "op": ">=", "value": 2, "part": "size"},
                              {"var": "n", "prop": "price", "op": "<", "value": 50}],
                    "answer": {"kind": "top", "prop": "price", "order": "desc", "limit": 2, "props": ["price"]}}, FX)
    cy = compile_cypher(req, FX)
    assert "n.`score` > n.`weight`" in cy and "size(n.`tags`) >= 2" in cy
    assert "toFloat(n.`price`) < 50" in cy and "ORDER BY toFloat(n.`price`) DESC" in cy
    gr = compile_gremlin(req, FX).script
    assert "asNumber(GType.DOUBLE)" in gr and "properties('tags').count()" in gr and ".by('score').by('weight')" in gr
    with pytest.raises(InvalidRequest, match="stored as text"):
        validate({"nodes": {"n": {"label": "Alpha"}},
                  "where": [{"var": "n", "prop": "price", "op": "=", "value": "50"}], "answer": {"kind": "count"}}, FX)


def test_v3_prompt_keeps_v2_text_for_typed2():
    from utils.killtests.typed.prompts import FORMAT, FORMAT_V3

    assert messages("typed2-3shot", "terrorist_attack", "q")[1]["content"].startswith(FORMAT)
    assert messages("typed3-0shot", "terrorist_attack", "q")[1]["content"].startswith(FORMAT_V3)


def test_v3_generator_requests_are_valid_and_compile():
    gen = fixture.Generator(fixture.build(), v3=True)
    for _ in range(400):
        req = validate(gen.request(), FX)
        compile_cypher(req, FX)
        compile_gremlin(req, FX)
