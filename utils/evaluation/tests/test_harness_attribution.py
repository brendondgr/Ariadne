"""Era 2 Step 4: the harness-attribution coder, one synthetic case per cause (offline)."""

from __future__ import annotations

import pytest

from utils.evaluation import harness_attribution as H


def step(source="attack", labels=("Group", "Technique"), rels=("USES",), seeds=("G0016",), template="generic_chain",
         query="MATCH (n)-[:USES]->(m)", error="", summary="Found 3"):
    return {"source": source, "sub_question": "q", "query": query, "ok": not error, "error": error, "summary": summary,
            "traces": [{"step": "resolve", "detail": {"labels": list(labels), "relationships": list(rels),
                                                      "seed_ids": list(seeds)}},
                       {"step": "gate", "detail": {"template": template}}]}


def answer(results, *, records=3, question="Which techniques does APT29 (G0016) use?", plan=None):
    return {"question": question, "logic_flow": {"results": results}, "evidence_volume": {"records": records},
            "run_meta": {"observed_plan": plan or []}}


def op(source="attack", text="Which techniques does G0016 use?", entities=None, depth=3, rows=1000):
    t = {"source": source, "text": text, "limits": {"max_traversal_depth": depth, "max_result_rows": rows}}
    if entities is not None:
        t["entities"] = list(entities)
    return t


AUTH = answer([step()])


def coded(planned, arm=H.DET, authored=AUTH):
    return H.code("D1-x", authored, planned, arm=arm)


def test_source():
    c = coded(answer([step(source="capec")], records=0, plan=[op(source="capec")]))
    assert (c.cause, c.stage) == ("source", "plan")


def test_empty_plan_is_source():
    assert coded(answer([], records=0, plan=[])).mechanism == "no_sub_questions"


def test_shape():
    auth = answer([step(template="describe", rels=())])
    c = coded(answer([step(rels=("USES",))], records=0, plan=[op()]), authored=auth)
    assert c.cause == "shape"


def test_relation_missing_in_the_deterministic_plan():
    c = coded(answer([step(rels=("MITIGATES",))], records=0, plan=[op()]))
    assert (c.cause, c.mechanism) == ("relation", "missing:USES")


def test_relation_missing_in_the_llm_plan_is_the_models():
    c = coded(answer([step(rels=("MITIGATES",))], records=0, plan=[op(entities=["Group", "MITIGATES"])]), arm=H.LLM)
    assert (c.cause, c.stage) == ("relation", "plan")


def test_llm_plan_right_but_resolver_changed_it_is_downstream():
    c = coded(answer([step(rels=("MITIGATES",))], records=0, plan=[op(entities=["Group", "USES", "Technique"])]),
              arm=H.LLM)
    assert (c.cause, c.stage, c.mechanism) == ("english_reread", "downstream", "resolver_changed_schema")


def test_depth_rejection_from_a_superfluous_plan_element():
    p = answer([step(labels=("Group", "Matrix", "Technique"), error="traversal depth 4 exceeds max_traversal_depth 3")],
               records=0, plan=[op()])
    assert (coded(p).cause, coded(p).mechanism) == ("relation", "superfluous_schema")


def test_depth_rejection_from_labels_the_resolver_added_is_downstream():
    p = answer([step(labels=("Group", "Matrix", "Technique"), error="traversal depth 4 exceeds max_traversal_depth 3")],
               records=0, plan=[op(entities=["Group", "USES", "Technique"])])
    c = coded(p, arm=H.LLM)
    assert (c.cause, c.stage) == ("english_reread", "downstream") and "Matrix" in c.mechanism


def test_decomposition_skipped_step():
    p = answer([step(), step(summary="Skipped: this sub-question depends on q1")], records=0,
               plan=[op(), op()])
    assert coded(p).cause == "decomposition"


def test_limit_depth():
    auth = answer([step(rels=("USES", "MITIGATES"), query="")])
    p = answer([step(rels=("USES", "MITIGATES"), query="")], records=0,
               plan=[op(entities=["USES", "MITIGATES"], depth=1)])
    assert coded(p, arm=H.LLM, authored=auth).cause == "limit"


def test_entity_not_in_plan_text():
    p = answer([step()], records=0, plan=[op(text="Which techniques does the group use?")])
    assert (coded(p).cause, coded(p).stage) == ("entity", "plan")


def test_seeds_dropped_is_english_reread():
    p = answer([step(seeds=())], records=0, plan=[op()])
    c = coded(p)
    assert (c.cause, c.stage, c.mechanism) == ("english_reread", "downstream", "seeds_dropped")


def test_direction():
    p = answer([step(query="MATCH (n)<-[:USES]-(m)")], records=0, plan=[op()])
    assert coded(p).cause == "direction"


def test_undirected_is_not_a_direction_error():
    p = answer([step(query="MATCH (n)-[r:USES]-(m)")], records=0, plan=[op()])
    assert coded(p).cause == "other"


def test_bound_correctly_but_empty_is_other():
    c = coded(answer([step()], records=0, plan=[op()]))
    assert (c.cause, c.stage) == ("other", "unattributed")


def test_plan_cause_wins_over_a_downstream_one_and_both_are_flagged():
    p = answer([step(rels=("MITIGATES",), seeds=())], records=0, plan=[op()])
    c = coded(p)
    assert c.cause == "relation"
    assert [f.split(":")[0] for f in c.flags] == ["relation", "english_reread"]


@pytest.mark.parametrize("query, want", [
    ("MATCH (n)-[:USES]->(m)", {">"}),
    ("MATCH (n)<-[:USES]-(m)", {"<"}),
    ("MATCH (n)-[r:USES]-(m)", {"-"}),
    ('g.V().out("USES")', {">"}),
    ('g.V().in("USES")', {"<"}),
    ("MATCH (n)-[:USES_X]->(m)", set()),
])
def test_orientations(query, want):
    assert H.orientations(query, "USES") == want


def test_anchor_prefers_ids_named_in_the_question():
    A = H.steps(answer([step(seeds=("G0016",)), step(seeds=("T1059",))]))
    assert H.anchors("What does G0016 use?", A) == {"G0016"}
    assert H.anchors("What does that group use?", A) == {"G0016"}


def test_lost_and_paired():
    auth = {"a": {"evidence_volume": {"records": 2}}, "b": {"evidence_volume": {"records": 2}},
            "c": {"evidence_volume": {"records": 0}}}
    plan = {"a": {"evidence_volume": {"records": 0}}, "b": {"evidence_volume": {"records": 1}},
            "c": {"evidence_volume": {"records": 0}}}
    assert H.lost(auth, plan) == ["a"]
    p = H.paired({"a": 1.0, "b": 1.0}, {"a": 0.0, "b": 1.0})
    assert p["diff"] == -0.5 and p["n"] == 2


def test_kappa():
    assert H.cohen_kappa(["a", "b", "a", "b"], ["a", "b", "a", "b"]) == 1.0
    assert H.cohen_kappa(["a", "a", "b", "b"], ["a", "b", "a", "b"]) == 0.0


def test_packet_hides_the_automatic_code():
    pk = H.packet("q", AUTH, answer([step(seeds=())], records=0, plan=[op()]), H.DET)
    assert "cause" not in pk and "flags" not in pk and pk["planner_executed_steps"][0]["seed_ids_bound"] == []


def test_posthoc_builder_walk_recode_only_touches_the_builders_walk():
    walk = answer([step(error="pre-run gate rejected all drafts: repeat(...).times(3) exceeds max_traversal_depth 1")],
                  records=0, plan=[op(entities=["Group", "USES", "Technique"], depth=1)])
    c = coded(walk, arm=H.LLM)
    assert (c.cause, c.mechanism) == ("relation", "superfluous_schema")          # the pre-registered rule
    r = H.recode_builder_walk(c, walk)
    assert (r.cause, r.stage, r.mechanism) == ("english_reread", "downstream", "builder_fixed_walk_depth")
    chain = answer([step(labels=("Group", "Matrix", "Technique"),
                         error="traversal depth 4 exceeds max_traversal_depth 3 (literal hop chain)")],
                   records=0, plan=[op()])
    c2 = coded(chain)
    assert H.recode_builder_walk(c2, chain) is c2
