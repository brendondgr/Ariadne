"""T1: normalisation, extraction, the Gremlin blocklist, and (live) the mirror proofs."""
import pytest

from utils.killtests.t1.execute import canon, gremlin_blocked, normalise, same
from utils.killtests.t1.prompts import ARMS, extract_query, messages


def test_normalise_ignores_column_and_row_order_but_counts_duplicates():
    assert same([{"a": 1, "b": "x"}, {"a": 2, "b": "y"}], [["y", 2], ["x", 1]])
    assert not same([["x"], ["x"]], [["x"]])
    assert same([[5]], [5.0])
    assert canon([3]) == "3" and canon(2.50) == "2.5"


def test_extract_query_reads_fenced_block_and_drops_thinking():
    assert extract_query("<think>hmm</think>\n```cypher\nMATCH (n) RETURN n;\n```") == "MATCH (n) RETURN n"
    assert extract_query("g.V().count()") == "g.V().count()"


def test_gremlin_blocklist():
    assert gremlin_blocked("g.addV('x')")
    assert gremlin_blocked("g.V().drop()")
    assert gremlin_blocked("graph.close()")
    assert gremlin_blocked("g.V().property('a', 1)")
    assert gremlin_blocked("System.exit(0)")
    assert not gremlin_blocked("g.V().hasLabel('Player').values('name')")


def test_prompts_share_one_schema_block():
    c = messages("cypher-3shot", "nba", "q")[1]["content"]
    g = messages("gremlin-3shot", "nba", "q")[1]["content"]
    assert c.split("Now the graph you must query:\n")[1] == g.split("Now the graph you must query:\n")[1]
    assert len(ARMS) == 4


def _live():
    from utils.config import load_env
    load_env()
    from utils.killtests import config
    from utils.killtests.t1 import load as L
    cfg = config.get()
    try:
        c = L.counts(cfg)
    except Exception:
        pytest.skip("T1 stores not running")
    if not c["neo4j_nodes"] or not c["gremlin_nodes"]:
        pytest.skip("T1 stores not loaded")
    return cfg, L


def test_mirror_parity():
    cfg, L = _live()
    p = L.parity(cfg, sample=20)
    assert p["ok"], p["mismatches"][:5]


def test_shots_and_handwritten_gremlin_match_reference_cypher():
    import json

    cfg, L = _live()
    from utils.killtests.t1.execute import run_cypher, run_gremlin
    from utils.killtests.t1.handwritten import HANDWRITTEN
    from utils.killtests.t1.shots import SHOTS

    test = {q["qid"][:8]: q for q in json.load(open(L.CB / "test.json"))}
    drv, gc = L._neo4j_driver(cfg), L._gremlin_client(cfg)
    try:
        for s in SHOTS:
            assert normalise(run_cypher(drv, s["cypher"])) == normalise(run_gremlin(gc, s["gremlin"]))
        for k, gq in HANDWRITTEN.items():
            assert normalise(run_cypher(drv, test[k]["gold_cypher"])) == normalise(run_gremlin(gc, gq)), k
    finally:
        gc.close()
        drv.close()


def test_readonly_gremlin_rejects_writes_that_slip_the_blocklist():
    cfg, L = _live()
    from utils.killtests.t1.execute import run_gremlin

    gc = L._gremlin_client(cfg)
    try:
        with pytest.raises(Exception):
            run_gremlin(gc, "g.V().limit(1).sideEffect(__.inject(1)).V().limit(1).as('x').mergeE([:])")
    finally:
        gc.close()
