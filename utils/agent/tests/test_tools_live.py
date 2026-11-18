"""Step 8 live smoke: the tools against the loaded ATT&CK (Neo4j) and CAPEC (Gremlin) stores.

Read-only; nothing is loaded or wiped. Skipped when a store is unreachable.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.live

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def views():
    from utils.config import load_env
    from utils.planner.cards import load_source_cards

    load_env()
    return load_source_cards(REPO / "data")


@pytest.fixture(scope="module")
def neo4j_driver(views):
    try:
        from neo4j import GraphDatabase

        drv = GraphDatabase.driver(os.environ["NEO4J_URI"], auth=(os.environ["NEO4J_USER"],
                                                                 os.environ["NEO4J_PASSWORD"]),
                                   notifications_min_severity="OFF")
        drv.verify_connectivity()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Neo4j store unreachable: {exc}")
    yield drv
    drv.close()


@pytest.fixture(scope="module")
def gremlin_client(views):
    try:
        from gremlin_python.driver import client as gc
        from gremlin_python.driver.serializer import GraphSONSerializersV3d0

        cli = gc.Client(os.environ["GREMLIN_URI"], "g", message_serializer=GraphSONSerializersV3d0())
        if cli.submit("g.V().limit(1).count()").all().result(timeout=10)[0] == 0:
            pytest.skip("Gremlin store is empty")
    except pytest.skip.Exception:
        raise
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Gremlin store unreachable: {exc}")
    yield cli
    cli.close()


def _tools(view, client, tmp_path):
    from utils.agent.catalog import catalog_for
    from utils.agent.handles import HandleStore
    from utils.agent.tools import Tools, backend_for

    cat = catalog_for(view)
    return Tools(cat, backend_for(cat, client), HandleStore(tmp_path / "h.db", "live"))


def test_cypher_store_expand_view_and_wrong_direction(views, neo4j_driver, tmp_path):
    t = _tools(views["attack"], neo4j_driver, tmp_path)
    r = t.call("resolve_entity", {"text": "Windows Management Instrumentation"})
    assert r["ok"] and r["status"] == "found" and r["total"] == 1
    out = t.call("expand", {"from": r["handle"], "relation": "uses", "to_label": "Group"})
    assert out["ok"] and out["total"] > 0 and out["sample"] and out["handle"].startswith("set:")
    assert out["reading"] == "the groups that use this technique"
    wrong = t.call("expand", {"from": r["ids"], "relation": "USES", "direction": "out"})
    assert wrong["code"] == "empty" and wrong["reason"] == "direction_reversed"
    assert "only as direction=in" in wrong["fix"] and "USES in -> Group" in wrong["fix"]


def test_gremlin_store_expand_view_depth_and_wrong_direction(views, gremlin_client, tmp_path):
    t = _tools(views["capec"], gremlin_client, tmp_path)
    r = t.call("resolve_entity", {"text": "SQL Injection", "label": "AttackPattern"})
    assert r["ok"] and r["status"] == "found"
    weak = t.call("expand", {"from": r["handle"], "relation": "EXPLOITS_WEAKNESS"})
    assert weak["ok"] and weak["total"] > 0 and weak["kind"] == "Weakness"
    one = t.call("expand", {"from": r["handle"], "relation": "ChildOf", "direction": "in"})
    two = t.call("expand", {"from": r["handle"], "relation": "ChildOf", "direction": "in", "depth": 2})
    assert one["ok"] and two["ok"] and two["total"] >= one["total"] > 0
    wrong = t.call("expand", {"from": r["ids"], "relation": "EXPLOITS_WEAKNESS", "direction": "in"})
    assert wrong["code"] == "empty" and wrong["reason"] == "direction_reversed"
    assert "EXPLOITS_WEAKNESS out -> Weakness" in wrong["fix"]  # card names, not the store's
