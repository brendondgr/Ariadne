"""Step 8 tools over an in-memory graph: wrappers, validation, refusals, and a scripted run.

The graph and card here are invented for the test (a test may name labels;
the agent code may not). The backend implements the interface of
:mod:`utils.agent.exact`'s backends, so ``fetch``, ``build_view`` and
``diagnose_empty`` run unchanged.
"""

from __future__ import annotations

import pytest

from utils.agent.catalog import IMPLEMENTED, catalog_for
from utils.agent.handles import HandleStore
from utils.agent.tools import Tools, build_toolbox

CARD = {"name": "toy",
        "entities": [{"label": "Person", "key": "name", "properties": {"name": "str", "age": "int"}},
                     {"label": "City", "key": "name", "properties": {"name": "str", "pop": "float_text"}}],
        "relations": [{"label": "livesIn", "subj_label": "Person", "obj_label": "City", "properties": {}},
                      {"label": "knows", "subj_label": "Person", "obj_label": "Person", "properties": {}}]}
NODES = {"p1": ("Person", "Ann"), "p2": ("Person", "Bo"), "p3": ("Person", "Cy"), "p4": ("Person", "Di"),
         "c1": ("City", "Oslo"), "c2": ("City", "Rome")}
EDGES = [("p1", "livesIn", "c1"), ("p2", "livesIn", "c2"), ("p3", "livesIn", "c1"),
         ("p1", "knows", "p2"), ("p2", "knows", "p3")]


class MemoryBackend:
    name = "cypher"

    def _hop(self, spec, src):
        out = set()
        for a, r, b in EDGES:
            if r != spec.rel:
                continue
            for x, y, d in ((a, b, "out"), (b, a, "in")):
                if x == src and spec.direction in (d, "both") and \
                        (spec.target_label is None or NODES[y][0] == spec.target_label) and \
                        (spec.seed_label is None or NODES[x][0] == spec.seed_label):
                    out.add(y)
        return out

    def stream(self, spec, ceiling):
        ids = sorted(set().union(*[self._hop(spec, s) for s in spec.seeds]) if spec.seeds else set())
        return ids[:ceiling], len(ids) <= ceiling

    def count(self, spec):
        return len(self.stream(spec, 10**9)[0])

    def set_query(self, spec):
        return f"memory {spec}"

    def page(self, spec, after, size):
        ids = [i for i in self.stream(spec, 10**9)[0] if after is None or i > after]
        return ids[:size]

    def describe_ids(self, ids, props=("name",)):
        return [{"id": i, "label": NODES[i][0], "name": NODES[i][1]} for i in ids if i in NODES]

    def facet_counts(self, ids, prop):
        out: dict[str, int] = {}
        for i in ids:
            k = NODES[i][0] if prop is None else NODES[i][1]
            out[k] = out.get(k, 0) + 1
        return out

    def anchor_facets(self, seeds):
        acc: dict[tuple, set] = {}
        for a, r, b in EDGES:
            if a in seeds:
                acc.setdefault((r, "out", NODES[b][0]), set()).add(b)
            if b in seeds:
                acc.setdefault((r, "in", NODES[a][0]), set()).add(a)
        return [{"rel": r, "direction": d, "label": lab, "n": len(v)} for (r, d, lab), v in acc.items()]

    def anchors_found(self, seeds):
        return [s for s in seeds if s in NODES]


@pytest.fixture()
def tools(tmp_path):
    cat = catalog_for(CARD)
    store = HandleStore(tmp_path / "h.db", "r1")
    t = Tools(cat, MemoryBackend(), store)
    store.put("Person", ["p1"])          # set:1
    store.put("Person", ["p4"])          # set:2, a person with no edges
    yield t
    store.close()


def test_expand_fills_a_unique_direction_and_returns_a_handle_and_a_view(tools):
    out = tools.call("expand", {"from": "set:1", "relation": "lives_in"})
    assert out["ok"] and out["handle"] == "set:3" and out["kind"] == "City" and out["total"] == 1
    assert out["sample"] == ["c1 Oslo"] and out["reading"] == "the city that this person lives in"
    assert {f["filled_by"] for f in out["coerced"]} == {"case_separator", "option_rules"}


def test_a_relation_that_runs_both_ways_needs_a_direction(tools):
    out = tools.call("expand", {"from": "set:1", "relation": "knows"})
    assert out["code"] == "invalid_request" and "out" in out["fix"] and "in" in out["fix"]
    assert "the person that knows this person" in out["fix"]


def test_depth_follows_a_repeating_relation(tools):
    one = tools.call("expand", {"from": "set:1", "relation": "knows", "direction": "out"})
    two = tools.call("expand", {"from": "set:1", "relation": "knows", "direction": "out", "depth": "2"})
    assert one["total"] == 1 and two["total"] == 2
    assert {"field": "depth", "from": "2", "to": 2, "filled_by": "int_from_text"} in two["coerced"]
    bad = tools.call("expand", {"from": "set:1", "relation": "livesIn", "depth": 2})
    assert bad["code"] == "invalid_request" and "choose depth from: 1" in bad["fix"]


def test_an_empty_set_carries_the_diagnosis_and_the_nearest_options(tools):
    out = tools.call("expand", {"from": ["p1"], "relation": "livesIn", "direction": "in"})
    assert out["code"] == "empty" and out["reason"] == "direction_reversed"
    assert "livesIn exists here only as direction=out" in out["fix"] and "knows out -> Person (1)" in out["fix"]
    gone = tools.call("expand", {"from": ["nobody"], "relation": "livesIn", "direction": "out"})
    assert gone["code"] == "empty" and gone["reason"] == "anchor_not_found"
    lonely = tools.call("expand", {"from": "set:2", "relation": "livesIn"})
    assert lonely["code"] == "empty" and lonely["reason"] == "relation_absent"


def test_a_repeated_call_is_refused_with_the_handle_it_made(tools):
    first = tools.call("expand", {"from": "set:1", "relation": "livesIn"})
    again = tools.call("expand", {"from": "set:1", "relation": "livesIn", "direction": "out"})
    assert again["code"] == "repeated_call" and first["handle"] in again["fix"]


def test_count_set_op_and_not_expressible(tools):
    a = tools.call("expand", {"from": "set:1", "relation": "knows", "direction": "out", "depth": 2})["handle"]
    b = tools.call("expand", {"from": "set:1", "relation": "knows", "direction": "out"})["handle"]
    m = tools.call("set_op", {"op": "MINUS", "a": a, "b": b})
    assert m["ok"] and m["total"] == 1 and m["sample"] == ["p3 Cy"]
    assert tools.call("count", {"set": m["handle"]}) == {"ok": True, "handle": m["handle"], "total": 1,
                                                         "complete": True}
    r = tools.call("not_expressible", {"part": "average age", "needs": "aggregate"})
    assert r["ok"] and tools.records == [{"part": "average age", "needs": "aggregate"}]


def test_schema_only_tools_validate_then_name_the_available_tools(tools):
    out = tools.call("filter", {"set": "set:1", "property": "age", "op": ">", "value": "30"})
    assert out["code"] == "invalid_request" and "Step 9" in out["detail"]
    assert all(t in out["fix"] for t in IMPLEMENTED)
    assert {"field": "value", "from": "30", "to": 30, "filled_by": "number_from_text"} in out["coerced"]
    bad = tools.call("filter", {"set": "set:1", "property": "age", "op": "contains", "value": 3})
    assert bad["code"] == "invalid_request" and ">=" in bad["fix"]
    agg = tools.call("aggregate", {"set": "set:1", "fn": "sum", "property": "name"})
    assert agg["code"] == "invalid_request" and "age" in agg["fix"]


def test_find_schema_ranks_the_cards_words(tools):
    out = tools.call("find_schema", {"text": "which city a person lives in"})  # BM25: no stemming
    assert out["ok"] and out["method"] == "bm25" and out["matches"][0]["name"] == "livesIn"


def test_describe_a_label_a_relation_a_handle_and_an_id(tools):
    assert "livesIn out -> City" in tools.call("describe", {"target": "Person"})["text"]
    assert tools.call("describe", {"target": "knows"})["kind"] == "relation"
    assert tools.call("describe", {"target": "set:1"})["total"] == 1
    ent = tools.call("describe", {"target": "p2"})
    assert ent["kind"] == "entity" and {e["relation"] for e in ent["edges"]} == {"livesIn", "knows"}
    assert tools.call("describe", {"target": "Persn"})["name"] == "Person"
    assert tools.call("describe", {"target": "zzzz"})["code"] == "not_in_card"


def test_resolve_entity_without_a_name_index_says_so(tools):
    out = tools.call("resolve_entity", {"text": "Ann"})
    assert out["code"] == "empty" and out["reason"] == "no_entity_match" and "Person" in out["fix"]


def test_the_toolbox_drives_a_scripted_run(tmp_path):
    from utils.agent.contracts import AgentRequest
    from utils.agent.log import RunLog
    from utils.agent.runner import drive, start
    from utils.agent.tests.scripted import ScriptedModel

    path = tmp_path / "runs.sqlite"
    with RunLog(path, commit="c") as log:
        rid = start(log, AgentRequest(question="Where does Ann live?", graph="toy"))
        store = HandleStore(path, rid)
        store.put("Person", ["p1"])
        box, _ = build_toolbox(catalog_for(CARD), MemoryBackend(), store)
        names = {s["function"]["name"] for s in box.specs(interactive=True)}
        assert {"expand", "find_schema", "finish", "ask_caller", "filter"} <= names
        model = ScriptedModel([[("expand", {"from": "set:1", "relation": "livesIn"})],
                               [("finish", {"answer": "Oslo.", "handles": ["set:2"]})]])
        env = drive(log, rid, model, box)
        assert env.status == "answered" and env.answer.sets[0].total == 1
        store.close()
