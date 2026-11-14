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
