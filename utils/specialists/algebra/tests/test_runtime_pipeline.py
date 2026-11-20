"""Algebra steps through the real pipeline, with a stub drafter and no model (Step 9, Phase G).

The typed planner's step check builds the plan (as ``TypedPlanner`` would after
the model's emission); a stub drafter hands it to the planning agent, and
everything after runs as in a measured arm: federation, the specialists, the
builders' dispatch to the algebra compilers, the deterministic composer. Each
expected value comes from a direct query on the same store.

Live, read-only: Neo4j (ATT&CK) and Gremlin (CAPEC) from ``.env``; skipped when
unreachable. ``ARIADNE_LLM_BASE_URL`` points at a closed port, so any model call
would fail rather than reach the relay; ``ORCH_MAX_HOPS=1`` keeps the run to one
pass.
"""

from __future__ import annotations

import dataclasses
import os
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[4]


def _reachable(uri: str) -> bool:
    import socket
    from urllib.parse import urlparse

    u = urlparse(uri)
    try:
        with socket.create_connection((u.hostname or "localhost", u.port or 7687), timeout=1.5):
            return True
    except OSError:
        return False


@pytest.fixture(scope="module")
def stores():
    from utils.config import load_env

    load_env()
    neo, grem = os.environ.get("NEO4J_URI", ""), os.environ.get("GREMLIN_URI", "")
    if not (REPO / "data" / "source_cards" / "attack.json").exists():
        pytest.skip("needs the source cards under data/")
    if not (neo and grem and _reachable(neo) and _reachable(grem)):
        pytest.skip("live Neo4j/Gremlin not reachable")
    return neo, grem


@pytest.fixture
def env(monkeypatch, stores):
    monkeypatch.setenv("ARIADNE_ALGEBRA_CORE", "1")
    monkeypatch.delenv("ARIADNE_ALGEBRA_EXTENDED", raising=False)
    for k, v in {"PLANNER_LLM_ENABLED": "false", "SPECIALIST_LLM_ENABLED": "false",
                 "SYNTHESIS_LLM_ENABLED": "false", "CONVERSATION_LLM_ENABLED": "false", "ORCH_MAX_HOPS": "1",
                 "ARIADNE_LLM_BASE_URL": "http://127.0.0.1:9/v1"}.items():
        monkeypatch.setenv(k, v)
    return stores


class _Stub:
    def __init__(self, plan):
        self.plan, self.last_used, self.logs = plan, "TypedDrafter", []

    def draft(self, request, cards, live_view, feedback=None, intent=None):
        p = dataclasses.replace(self.plan, sub_questions=list(self.plan.sub_questions), joins=list(self.plan.joins))
        p.typed = {"mode": "stub"}
        return p


def _run(steps):
    """Check ``steps`` as the typed planner does, then run the plan through ``iter_pipeline``."""
    from utils.orchestration.main import PipelineRun, iter_pipeline
    from utils.planner.agent import PlanningAgent
    from utils.planner.cards import load_source_cards
    from utils.planner.config import PlannerConfig
    from utils.planner.typed import PlanContext, catalogs_for, check_plan, to_plan
    from utils.specialists.config import SpecialistConfig
    from utils.synthesis.config import SynthesisConfig

    cards = load_source_cards(REPO / "data")
    with tempfile.TemporaryDirectory() as d:
        ctx = PlanContext(cards, catalogs_for(cards), Path(d), request="")
        try:
            checks, _ = check_plan({"steps": steps}, ctx)
        finally:
            ctx.close()
    assert all(c.ok for c in checks), [c.refusals for c in checks]
    plan = to_plan("Q", checks, {}, cards, [], "lazy")
    agent = PlanningAgent(dataclasses.replace(PlannerConfig.from_env(), llm_enabled=True), drafter=_Stub(plan))
    spec = dataclasses.replace(SpecialistConfig.from_env(), llm_enabled=False, llm_query_builder=False)
    cfg = dataclasses.replace(SynthesisConfig.from_env(), llm_enabled=False)
    run = PipelineRun(question="Q", mode="query")
    evidence = answer = None
    for event, payload in iter_pipeline("Q", mode="query", run=run, synthesis_config=cfg, use_llm=True,
                                        agent=agent, specialist_config=spec):
        if event == "answer":
            evidence, answer = payload["evidence"], payload["synthesized"]
    assert evidence is not None and answer is not None
    return evidence, answer


def _neo4j(query, **params):
    from neo4j import GraphDatabase

    drv = GraphDatabase.driver(os.environ["NEO4J_URI"], auth=(os.environ.get("NEO4J_USER", "neo4j"),
                                                                os.environ.get("NEO4J_PASSWORD", "")))
    try:
        with drv.session() as s:
            return [r.data() for r in s.run(query, params)]
    finally:
        drv.close()


def _gremlin(query):
    from gremlin_python.driver import client as gclient
    from gremlin_python.driver.serializer import GraphSONSerializersV3d0

    c = gclient.Client(os.environ["GREMLIN_URI"], "g", message_serializer=GraphSONSerializersV3d0())
    try:
        return c.submit(query).all().result()
    finally:
        c.close()


CONTRACT_KEYS = {"step", "kind", "value", "ids", "rows", "total", "complete", "info"}
USES_T = [{"relation": "USES", "direction": "out", "target_label": "Technique"}]


def test_a_count_on_attack(env):
    from utils.specialists.algebra.runtime import algebra_results

    want = _neo4j("MATCH (g:Group {attack_id: 'G0007'})-[:USES]->(t:Technique) RETURN count(DISTINCT t) AS n")[0]["n"]
    evidence, answer = _run([{"id": "q1", "graph": "attack", "kind": "aggregate", "anchor": {"id": "G0007"},
                              "path": USES_T, "fn": "count"}])
    res = algebra_results(evidence)
    assert len(res) == 1 and set(res[0]) == CONTRACT_KEYS
    assert res[0] == {"step": "q1", "kind": "count", "value": want, "ids": [], "rows": [{"value": want}],
                      "total": 1, "complete": True, "info": {"anchor_not_found": []}}
    texts = [c.text for c in answer.claims]
    assert f"The count is {want} (distinct entities, exact)." in texts
    assert all(v.verdict == "supported" for v in answer.verification.verdicts)


def test_a_verify_on_attack(env):
    from utils.specialists.algebra.runtime import algebra_results

    evidence, answer = _run([{"id": "q1", "graph": "attack", "kind": "verify", "anchor": {"id": "G0007"},
                              "other": {"id": "T1047"}}])
    res = algebra_results(evidence)[0]
    want = bool(_neo4j("MATCH (g {attack_id: 'G0007'})--(t {attack_id: 'T1047'}) RETURN count(*) AS n")[0]["n"])
    assert res["kind"] == "verify" and res["value"] is want and res["info"]["anchor_not_found"] == []
    assert any(c.text.startswith("Yes:" if want else "No:") for c in answer.claims)


def test_an_unknown_anchor_is_reported_not_found_by_its_public_id(env):
    from utils.specialists.algebra.runtime import algebra_results

    evidence, _ = _run([{"id": "q1", "graph": "attack", "kind": "verify", "anchor": {"id": "G0007"},
                         "other": {"id": "G9999"}}])
    res = algebra_results(evidence)[0]
    assert res["kind"] == "verify" and res["value"] is False
    assert res["info"]["anchor_not_found"] == ["G9999"] and res["info"]["b_found"] is False


def _capec_counts():
    rows = _gremlin("g.V().hasLabel('AttackPattern').project('id', 'n').by(values('id'))"
                    ".by(out('EXPLOITS_WEAKNESS').hasLabel('Weakness').dedup().count())")
    from utils.specialists.gremlin.normalizer import _expand_member_id

    return {_expand_member_id(r["id"]): int(r["n"]) for r in rows}


def _top(counts, k):
    order = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    cut = order[k - 1][1]
    return [kv for kv in order if kv[1] >= cut]


def test_a_groupby_on_capec(env):
    from utils.specialists.algebra.runtime import algebra_results

    counts = _capec_counts()
    evidence, answer = _run([{"id": "q1", "graph": "capec", "kind": "groupby", "anchor_label": "AttackPattern",
                              "path": [{"relation": "EXPLOITS_WEAKNESS", "direction": "out",
                                        "target_label": "Weakness"}], "having": {"op": ">", "value": 10}}])
    res = algebra_results(evidence)[0]
    want = {k: v for k, v in counts.items() if v > 10}
    assert res["kind"] == "groupby" and res["total"] == len(want) and res["complete"]
    assert res["ids"] == sorted(want)
    assert {r["id"]: r["value"] for r in res["rows"]} == want
    # the members are evidence records, with public ids
    got = {r.primary_id for x in evidence.results for r in x.records}
    assert got == set(want)
    assert any(c.text.startswith(f"{len(want)} member(s), with their count:") for c in answer.claims)


def test_a_rank_on_capec_keeps_ties(env):
    from utils.specialists.algebra.runtime import algebra_results

    counts = _capec_counts()
    evidence, _ = _run([{"id": "q1", "graph": "capec", "kind": "rank", "anchor_label": "AttackPattern", "k": 3,
                         "by_path": [{"relation": "EXPLOITS_WEAKNESS", "direction": "out",
                                      "target_label": "Weakness"}]}])
    res = algebra_results(evidence)[0]
    top = _top(counts, 3)
    assert res["kind"] == "rank" and [(r["id"], r["value"]) for r in res["rows"]] == top


def test_from_step_chains_through_the_seeds(env):
    from utils.specialists.algebra.runtime import algebra_results

    want = _neo4j("MATCH (g:Group {attack_id: 'G0007'})-[:USES]->(s:Software) WHERE 'Linux' IN s.x_mitre_platforms "
                  "RETURN collect(DISTINCT s.attack_id) AS ids")[0]["ids"]
    evidence, _ = _run([
        {"id": "q1", "graph": "attack", "kind": "expand", "anchor": {"id": "G0007"},
         "path": [{"relation": "USES", "direction": "out", "target_label": "Software"}]},
        {"id": "q2", "graph": "attack", "kind": "filter", "from_step": "q1",
         "where": [{"property": "x_mitre_platforms", "op": "contains", "value": "Linux"}]},
    ])
    res = algebra_results(evidence)
    assert [r["step"] for r in res] == ["q2"]
    assert res[0]["kind"] == "nodes" and res[0]["ids"] == sorted(want) and res[0]["total"] == len(want)


def test_an_expand_from_an_operator_step_on_capec(env):
    """Stage 1's lost control (D6 ... T1491): a typescan, then an expand from it on the same graph."""
    from utils.specialists.algebra.runtime import algebra_results
    from utils.specialists.gremlin.normalizer import _expand_member_id, _taxonomy_public_id

    rows = _gremlin("g.V().hasLabel('TaxonomyEntry').has('taxonomy_name', 'ATTACK').has('entry_id', '1491').as('s')"
                    ".in('MAPS_TO').hasLabel('AttackPattern').dedup()"
                    ".union(identity(), out('MAPS_TO').hasLabel('TaxonomyEntry').where(neq('s'))).dedup()"
                    ".project('id', 'tn', 'eid').by(values('id'))"
                    ".by(coalesce(values('taxonomy_name'), constant('')))"
                    ".by(coalesce(values('entry_id'), constant('')))")
    want = sorted(_taxonomy_public_id({"taxonomy_name": r["tn"], "entry_id": r["eid"]}, _expand_member_id(r["id"]))
                  if r["tn"] else _expand_member_id(r["id"]) for r in rows)
    assert any(w.startswith("OWASP Attacks:") for w in want)
    evidence, _ = _run([
        {"id": "q1", "graph": "capec", "kind": "typescan", "anchor_label": "TaxonomyEntry",
         "where": [{"property": "taxonomy_name", "op": "=", "value": "ATTACK"},
                   {"property": "entry_id", "op": "=", "value": "1491"}]},
        {"id": "q2", "graph": "capec", "kind": "expand", "from_step": "q1",
         "path": [{"relation": "MAPS_TO", "direction": "in", "target_label": "AttackPattern"},
                  {"relation": "MAPS_TO", "direction": "out", "target_label": "TaxonomyEntry"}]},
    ])
    res = {r["step"]: r for r in algebra_results(evidence)}
    assert res["q1"]["ids"] == ["T1491"]
    assert res["q2"]["kind"] == "nodes" and res["q2"]["ids"] == want and not res["q2"]["info"].get("anchor_not_found")
    got = {r.primary_id for x in evidence.results if x.task.sub_question_id == "q2" for r in x.records}
    assert got == set(want)
