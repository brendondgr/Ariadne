"""E4 (EXP-2026-11-015): coercion unit cases, and a replay of the kill tests' refused typed requests.

The replay takes every typed request that EXP-2026-11-006 refused as ``invalid``
(``logs/killtests-2026-11/exp006/{A,B,C}-execute.json``; parts A = CypherBench,
B = Text2Cypher, C = Mind the Query; arms ``typed2-3shot``, ``typed3-3shot`` and
``typed3-3shot-repair``), applies the same coercions the tools apply to every
name, enum and number in the request (against the card the run used), and
validates the result with the kill tests' own validator.

A coerced request that now validates is **fixed**. It is judged against every
request for the same question that executed **correctly** (``correct: true``) in
that part: **right** if it equals one of them, or if every coerced value is one
a correct request uses in the same role; **wrong** if a correct request exists
and some coerced value is used by none of them; **unjudged** if the question has
no correct request. The run outputs are under ``logs/`` (not in git), so the
replay skips when they are absent.
"""

from __future__ import annotations

import copy
import json
import re
from collections import Counter
from pathlib import Path

import pytest

from utils.agent.coerce import (Ambiguous, Coercions, NoMatch, coerce_bool, coerce_enum, coerce_int, coerce_name,
                                coerce_value, distance, max_distance)

REPO = Path(__file__).resolve().parents[3]
EXP = REPO / "logs" / "killtests-2026-11" / "exp006"


# --------------------------------------------------------------------------- #
# Unit cases
# --------------------------------------------------------------------------- #

OPTS = ["Person", "Movie", "ACTED_IN", "worksAt", "HAS_PART", "Part", "Parts2"]


@pytest.mark.parametrize("got,want,how", [
    ("Person", "Person", None),
    ("person", "Person", "case_separator"),
    ("acted in", "ACTED_IN", "case_separator"),
    ("acted-in", "ACTED_IN", "case_separator"),
    ("works_at", "worksAt", "case_separator"),
    ("Persn", "Person", "edit_distance"),
    ("Persons", "Person", "edit_distance"),
    ("ACTED_ON", "ACTED_IN", "edit_distance"),
    ("Moive", "Movie", "edit_distance"),
])
def test_near_miss_names_are_fixed_and_recorded(got, want, how):
    log = Coercions()
    assert coerce_name(got, OPTS, "label", log) == want
    if how is None:
        assert not log
    else:
        assert log.fixes == [{"field": "label", "from": got, "to": want, "filled_by": how}]


@pytest.mark.parametrize("got", ["Pers", "Film", "x", "", None, 3, "ACTS", "Partz", "m1.Person", "m1.name"])
def test_far_or_short_names_are_not_guessed(got):
    with pytest.raises((NoMatch, Ambiguous)):
        coerce_name(got, OPTS + ["Partx"], "label")


def test_two_candidates_are_ambiguous_never_guessed():
    with pytest.raises(Ambiguous) as exc:
        coerce_name("Parts", ["Part", "Parts2"], "label")
    assert exc.value.candidates == ["Part", "Parts2"]
    with pytest.raises(Ambiguous):
        coerce_name("has part", ["HAS_PART", "hasPart"], "relation")


def test_short_names_get_a_smaller_edit_budget():
    assert max_distance("in") == 0 and max_distance("name") == 0 and max_distance("names") == 1
    assert max_distance("person") == 2
    with pytest.raises(NoMatch):
        coerce_name("game", ["name"], "property")  # one edit, but a different word
    assert distance("abcd", "abdc") == 1


def test_enums_take_case_only():
    log = Coercions()
    assert coerce_enum("OUT", ["out", "in"], "direction", log) == "out"
    assert log.fixes[0]["filled_by"] == "enum_case"
    with pytest.raises(NoMatch):
        coerce_enum("outward", ["out", "in"], "direction")


def test_numbers():
    log = Coercions()
    assert coerce_int("8", "depth", log) == 8 and coerce_int(2.0, "depth", log) == 2
    assert [f["filled_by"] for f in log.fixes] == ["int_from_text", "int_from_number"]
    for bad in ("8.5", "eight", True, None, [8]):
        with pytest.raises(NoMatch):
            coerce_int(bad, "depth")


@pytest.mark.parametrize("value,vtype,want,how", [
    ("12.5", "number_text", 12.5, "number_from_text"),
    ("7", "integer", 7, "number_from_text"),
    ("7.0", "integer", 7, "number_from_text"),
    (7, "string", "7", "text_from_number"),
    ("true", "boolean", True, "bool_from_text"),
    (3, "number", 3, None),
    ("abc", "string", "abc", None),
])
def test_values_follow_the_cards_types(value, vtype, want, how):
    log = Coercions()
    assert coerce_value(value, vtype, "value", log) == want
    assert [f["filled_by"] for f in log.fixes] == ([how] if how else [])


@pytest.mark.parametrize("value,vtype", [("7.5", "integer"), ("abc", "number"), (True, "number"),
                                         ("maybe", "boolean"), ({"a": 1}, "string"), (None, "list")])
def test_values_that_do_not_fit_are_refused(value, vtype):
    with pytest.raises(NoMatch):
        coerce_value(value, vtype, "value")


def test_bool():
    assert coerce_bool("FALSE", "ties") is False
    with pytest.raises(NoMatch):
        coerce_bool("no", "ties")


# --------------------------------------------------------------------------- #
# Replay of EXP-2026-11-006's refused typed requests
# --------------------------------------------------------------------------- #


def _cards(part: str) -> dict:
    from utils.killtests.t1.load import TEST_GRAPHS
    from utils.killtests.t2c import load as T
    from utils.killtests.typed.request import Card

    if part == "A":
        return {g: Card(g) for g in TEST_GRAPHS}
    src = T.OUT_MTQ if part == "C" else T.OUT
    graphs = T.MTQ if part == "C" else T.GRAPHS
    return {g: Card(g, json.loads((src / "cards-v3" / f"card-{g}.json").read_text())) for g in graphs}


def _gold(part: str) -> dict[str, dict]:
    from utils.killtests.t2c import load as T

    path = (REPO / "logs/killtests-2026-11/t1/gold.json" if part == "A" else
            (T.OUT_MTQ if part == "C" else T.OUT) / "gold.json")
    return {q["qid"]: q for q in json.loads(path.read_text())["questions"]}


def coerce_request(req: dict, card, log: Coercions) -> dict:
    """The tools' coercions over a typed request: every name, enum and number, by the card."""
    from utils.killtests.typed.request import AGG, ANSWERS, OPS, TESTS

    req = copy.deepcopy(req)
    nodes = req.get("nodes") if isinstance(req.get("nodes"), dict) else {}
    for v, spec in nodes.items():
        if isinstance(spec, dict) and isinstance(spec.get("label"), str):
            spec["label"] = coerce_name(spec["label"], list(card.labels), f"nodes.{v}.label", log)

    def label(var):
        spec = nodes.get(var)
        return spec.get("label") if isinstance(spec, dict) else None

    def fix_filter(f, ptypes, where):
        if not isinstance(f, dict):
            return
        if isinstance(f.get("op"), str) and f["op"] not in ("current", "during"):
            f["op"] = coerce_enum(f["op"], sorted(OPS), f"{where}.op", log)
        if isinstance(f.get("prop"), str) and ptypes:
            f["prop"] = coerce_name(f["prop"], list(ptypes), f"{where}.prop", log)
            t = ptypes.get(f["prop"])
            if "value" in f and t in ("int", "float", "float_text") and isinstance(f["value"], str) \
                    and f.get("part") is None:
                f["value"] = coerce_value(f["value"], "number", f"{where}.value", log)
        if f.get("part") in ("year", "size") and isinstance(f.get("value"), str):
            f["value"] = coerce_int(f["value"], f"{where}.value", log)

    edge_types: dict[str, dict] = {}

    def fix_edges(es, where):
        if not isinstance(es, list):
            return
        for i, e in enumerate(es):
            if not isinstance(e, dict):
                continue
            if isinstance(e.get("type"), str):
                e["type"] = coerce_name(e["type"], list(card.rels), f"{where}[{i}].type", log)
            p = card.rel_props(e.get("type"), label(e.get("from")), label(e.get("to"))) or {}
            if e.get("var"):
                edge_types[e["var"]] = p
            for j, f in enumerate(e.get("filters") or []):
                fix_filter(f, p, f"{where}[{i}].filters[{j}]")

    fix_edges(req.get("edges"), "edges")
    for i, br in enumerate(req.get("any_of") or []):
        fix_edges(br if isinstance(br, list) else [br], f"any_of[{i}]")
    fix_edges(req.get("optional"), "optional")
    fix_edges(req.get("none"), "none")
    for i, f in enumerate(req.get("where") or []):
        if isinstance(f, dict):
            fix_filter(f, card.labels.get(label(f.get("var"))) or {}, f"where[{i}]")
    ans = req.get("answer")
    if isinstance(ans, dict):
        if isinstance(ans.get("kind"), str):
            ans["kind"] = coerce_enum(ans["kind"], sorted(ANSWERS), "answer.kind", log)
        if isinstance(ans.get("fn"), str):
            ans["fn"] = coerce_enum(ans["fn"], sorted(AGG | {"count"}), "answer.fn", log)
        for k, opts in (("order", ["asc", "desc"]), ("test", sorted(TESTS))):
            if isinstance(ans.get(k), str):
                ans[k] = coerce_enum(ans[k], opts, f"answer.{k}", log)
        if ans.get("limit") is not None:
            ans["limit"] = coerce_int(ans["limit"], "answer.limit", log)
        var = ans.get("of") if ans.get("kind") in ("per", "count_per") else ans.get("var") or "n"
        ptypes = card.labels.get(label(var)) if var in nodes else edge_types.get(var) or {}
        nprops = card.labels.get(label("n")) or {}
        if isinstance(ans.get("prop"), str) and ptypes:
            ans["prop"] = coerce_name(ans["prop"], list(ptypes), "answer.prop", log)
        if isinstance(ans.get("props"), list):
            ans["props"] = [coerce_name(p, list(nprops), f"answer.props[{i}]", log) if isinstance(p, str) else p
                            for i, p in enumerate(ans["props"])]
        h = ans.get("having")
        if isinstance(h, dict) and isinstance(h.get("value"), str):
            h["value"] = coerce_value(h["value"], "number", "answer.having.value", log)
    return req


def _values(req: dict) -> set[str]:
    """Every name and enum a request uses (labels, relation types, properties, ops, answer words)."""
    out: set[str] = set()

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in ("label", "type", "prop", "op", "kind", "fn", "order", "test") and isinstance(v, str):
                    out.add(v)
                elif k == "props" and isinstance(v, list):
                    out.update(p for p in v if isinstance(p, str))
                elif k in ("value", "limit") and isinstance(v, (int, float, str)):
                    out.add(repr(v))
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk(req)
    return out


def _clean(req: dict) -> str:
    def strip(x):
        if isinstance(x, dict):
            return {k: strip(v) for k, v in x.items() if not k.startswith("_")}
        if isinstance(x, list):
            return [strip(v) for v in x]
        return x

    return json.dumps(strip(req), sort_keys=True)


@pytest.mark.skipif(not (EXP / "B-execute.json").exists(), reason=f"EXP-2026-11-006 run outputs absent ({EXP})")
def test_replay_of_exp006_refused_typed_requests():
    from utils.killtests.typed.request import InvalidRequest, validate

    tally: Counter = Counter()
    by_arm: Counter = Counter()
    rows = []
    for part in "ABC":
        ex = json.loads((EXP / f"{part}-execute.json").read_text())["executions"]
        cards, gold = _cards(part), _gold(part)
        correct: dict[str, list[dict]] = {}
        for key, v in ex.items():
            qid, arm, _ = key.split("|")
            if arm.startswith("typed") and v.get("status") == "ok" and v.get("correct") and v.get("request"):
                correct.setdefault(qid, []).append(v["request"])
        for key, v in sorted(ex.items()):
            qid, arm, model = key.split("|")
            if not arm.startswith("typed") or v.get("status") != "invalid" or not isinstance(v.get("request"), dict):
                continue
            tally["refused"] += 1
            card = cards[gold[qid]["graph"]]
            log = Coercions()
            try:
                fixed = coerce_request(v["request"], card, log)
            except Ambiguous:
                tally["ambiguous (refused, not guessed)"] += 1
                continue
            except NoMatch:
                fixed = None
            if fixed is None or not log:
                tally["not fixed: no near-miss repair applies"] += 1
                continue
            try:
                norm = validate(fixed, card)
            except (InvalidRequest, Exception):  # noqa: BLE001 - the validator's own failures count as refusals
                tally["not fixed: coerced but still invalid"] += 1
                continue
            tally["fixed"] += 1
            by_arm[f"{part}/{arm}"] += 1
            refs = correct.get(qid, [])
            gold_q = re.findall(r"[A-Za-z0-9_]+", gold[qid].get("gold_cypher") or "")
            names = [f for f in log.fixes if f["filled_by"] in ("case_separator", "edit_distance")]
            if not refs and not names:
                verdict = "unjudged"
            elif not refs:
                verdict = ("right (the gold query uses every repaired name)"
                           if all(str(f["to"]) in gold_q for f in names)
                           else "wrong (the gold query does not use a repaired name)")
            elif any(_clean(norm) == _clean(validate(r, card)) for r in refs):
                verdict = "right (equals a correct request)"
            elif all(any(str(f["to"]) in _values(r) or repr(f["to"]) in _values(r) for r in refs)
                     for f in log.fixes):
                verdict = "right (every coerced value used by a correct request)"
            else:
                verdict = "wrong"
            tally[verdict] += 1
            rows.append({"key": key, "graph": gold[qid]["graph"], "fixes": log.fixes, "verdict": verdict,
                         "detail": v.get("detail")})
    print("\nE4 replay:", json.dumps(dict(tally)))
    print("E4 fixed by part/arm:", dict(by_arm))
    for r in rows:
        print("E4 fix:", json.dumps(r)[:400])
    assert tally["refused"] > 0
    assert sum(n for k, n in tally.items() if k.startswith("wrong")) == 0
