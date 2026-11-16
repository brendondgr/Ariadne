"""Era 2 Step 5: exact sets, handles and views against a live fixture graph.

Uses the kill-test stores (CypherBench graphs, loaded identically into Neo4j
:5470 and Gremlin :6470, parity checked). Skipped when they are unreachable.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.live

from utils.agent.exact import CypherBackend, GremlinBackend, SetSpec, fetch  # noqa: E402
from utils.agent.handles import HandleStore  # noqa: E402
from utils.agent.view import build_view, diagnose_empty  # noqa: E402


@pytest.fixture(scope="module")
def backends():
    try:
        from gremlin_python.driver import client as gc
        from neo4j import GraphDatabase

        from utils.config import load_env
        from utils.killtests.config import get

        load_env()
        cfg = get()
        drv = GraphDatabase.driver(cfg.t1_neo4j_uri, auth=(cfg.neo4j_user, cfg.neo4j_password))
        drv.verify_connectivity()
        cli = gc.Client(cfg.t1_gremlin_uri, "g")
        if cli.submit("g.V().limit(1).count()").all().result(timeout=10)[0] == 0:
            pytest.skip("kill-test Gremlin store is empty (reload it)")
    except pytest.skip.Exception:
        raise
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"kill-test stores unreachable: {exc}")
    cy, gr = CypherBackend(drv, id_props=("eid",)), GremlinBackend(cli, id_props=("eid",))
    yield {"cypher": cy, "gremlin": gr, "_drv": drv}
    cli.close()
    drv.close()


def _top_teams(be, k=3):
    with be["_drv"].session() as s:
        return [r["eid"] for r in s.run(
            "MATCH (p:Player)-[:playsFor]->(t:Team) WITH t, count(DISTINCT p) AS n "
            "ORDER BY n DESC, t.eid LIMIT $k RETURN t.eid AS eid", k=k)]


SPECS = [
    lambda t: SetSpec((t[0],), "playsFor", "in", "Player"),
    lambda t: SetSpec(tuple(t[:3]), "playsFor", "in", "Player"),
    lambda t: SetSpec((t[0],), "playsFor", "both", None),
    lambda t: SetSpec(("Team#does-not-exist",), "playsFor", "in", "Player"),
]


@pytest.mark.parametrize("make", SPECS)
@pytest.mark.parametrize("name", ["cypher", "gremlin"])
def test_paged_equals_unpaged_and_total_equals_the_database_count(backends, make, name):
    spec = make(_top_teams(backends))
    be = backends[name]
    whole = fetch(be, spec, mode="stream")
    paged = fetch(be, spec, mode="keyset", page_size=7)
    assert whole.ids == paged.ids and whole.complete and paged.complete
    assert whole.total == len(whole.ids) == be.count(spec)


@pytest.mark.parametrize("make", SPECS)
def test_both_backends_return_the_same_set(backends, make):
    spec = make(_top_teams(backends))
    assert fetch(backends["cypher"], spec).ids == fetch(backends["gremlin"], spec).ids


@pytest.mark.parametrize("name", ["cypher", "gremlin"])
def test_a_ceiling_is_explicit_never_silent(backends, name):
    spec = SetSpec(tuple(_top_teams(backends)), "playsFor", "in", "Player")
    full = fetch(backends[name], spec)
    capped = fetch(backends[name], spec, ceiling=5)
    assert full.total > 5
    assert not capped.complete and len(capped.ids) == 5 and capped.total == full.total
    assert capped.notes and "ceiling" in capped.notes[0]


@pytest.mark.parametrize("name", ["cypher", "gremlin"])
def test_set_op_intersect_equals_the_database_side_intersection(backends, name, tmp_path):
    a, b = _top_teams(backends, 2)
    be = backends[name]
    store = HandleStore(tmp_path / "h.sqlite", "r_test")
    sa = fetch(be, SetSpec((a,), "playsFor", "in", "Player"))
    sb = fetch(be, SetSpec((b,), "playsFor", "in", "Player"))
    ha = store.put("Player", sa.ids, query=sa.query)
    hb = store.put("Player", sb.ids, query=sb.query)
    inter = store.set_op("intersect", ha.handle, hb.handle)
    if name == "cypher":
        with backends["_drv"].session() as s:
            db = sorted(r["eid"] for r in s.run(
                "MATCH (p:Player)-[:playsFor]->(:Team {eid: $a}), (p)-[:playsFor]->(:Team {eid: $b}) "
                "RETURN DISTINCT p.eid AS eid", a=a, b=b))
    else:
        db = sorted(be.client.submit(
            "g.V().has('eid', a).in('playsFor').hasLabel('Player')"
            ".where(__.out('playsFor').has('eid', b)).values('eid').dedup()",
            bindings={"a": a, "b": b}).all().result(timeout=30))
    assert list(inter.ids) == db and inter.complete
    assert list(store.set_op("union", ha.handle, hb.handle).ids) == sorted(set(sa.ids) | set(sb.ids))
    store.close()


@pytest.mark.parametrize("name", ["cypher", "gremlin"])
def test_the_view_is_lossless(backends, name, tmp_path):
    be = backends[name]
    spec = SetSpec(tuple(_top_teams(backends)), "playsFor", "in", "Player")
    s = fetch(be, spec)
    store = HandleStore(tmp_path / "h.sqlite", "r_test")
    rec = store.put("Player", s.ids, query=s.query)
    v = build_view(rec, be)
    assert v["total"] == s.total and v["complete"]
    assert sum(v["facets"]["label"].values()) == s.total            # facets account for every member
    assert len(v["sample"]) == min(10, s.total) and v["sample_of"] == s.total
    assert v["sample"][0].startswith(s.ids[0])
    store.close()


@pytest.mark.parametrize("name", ["cypher", "gremlin"])
def test_an_empty_result_is_diagnosed_with_the_nearest_options(backends, name):
    be = backends[name]
    team = _top_teams(backends, 1)[0]
    missing = diagnose_empty(SetSpec(("Team#nope",), "playsFor", "in", "Player"), be)
    assert missing["reason"] == "anchor_not_found"
    reversed_ = diagnose_empty(SetSpec((team,), "playsFor", "out", "Player"), be)
    assert reversed_["reason"] == "direction_reversed" and reversed_["nearest"]
    absent = diagnose_empty(SetSpec((team,), "receivesAward", "in", None), be)
    assert absent["reason"] == "relation_absent"
    wrong_label = diagnose_empty(SetSpec((team,), "playsFor", "in", "Award"), be)
    assert wrong_label["reason"] == "label_excludes_all"
    assert any(o["rel"] == "playsFor" and o["direction"] == "in" for o in wrong_label["nearest"])
