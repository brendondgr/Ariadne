"""The semantics fixture graph (EXP-2026-11-021, Phase E), written from the semantics document alone.

``docs/era-2-expansion/operator-algebra.md`` is the only source for the expected
answers in ``test_semantics.py``. Every label starts with ``Fx`` so nothing collides
with ATT&CK or CAPEC, which share the verification pair (Neo4j bolt 5480, Gremlin
6480). The measured stores are refused.

**Encoding.** Nodes and edges go through the loader's own stores
(``Neo4jGraphStore``/``GremlinGraphStore`` ``upsert_nodes``/``upsert_edges``), with
records shaped like the canonical/Gremlin export records (``id``, ``label``,
``labels``, ``name``, ``properties``; edges ``id``, ``type``, ``source_id``,
``target_id``). Lists, dates and numbers are therefore stored exactly as real data
is. Every node carries a second, non-card Neo4j label ``FxObject`` (as ATT&CK carries
``AttackObject``); ``fx:t5`` carries a third, ``FxExtra``.

**Fixture-only: edge properties.** The loader writes only ``id`` on a relationship
today (operator-algebra.md O4, O7a), so edge filters cannot be tested on real data.
:func:`load` writes the ``EDGE_PROPS`` below itself, in both engines, after the
loader's upsert. Nothing outside this fixture does that.

The graph (hand-checked answers live beside each test):

    FxGroup  g1 Alpha, g2 alpha, g3 Beta, g4 Gamma, g5 Delta
    FxTech   t1..t5        FxTool s1, s2        FxMit m1, m2
    FxPlace  p1..p7

    FxUses (FxGroup -> FxTech | FxTool)
        g1->t1 {since 2020-01-15, weight 0.5}   g1->t2 {since 2021-02-01T00:00:00Z, weight 1.5}
        g1->s1 {since "Jan 2020", via "manual"} g2->t1 {since 2019-05-05}   g2->t3 {}
        g3->t2 {weight 2.0}   g3->t3 {since 2022-12-31}   g3->t4 {}   g4->s2 {}   (g5: none)
    FxSub (FxTech -> FxTech):          t1->t2, t2->t3, t1->t3
    FxMitigates (FxMit -> FxTech):     m1->t1, m1->t2, m2->t2
    FxLink (FxPlace -> FxPlace):       p1->p2, p1->p3, p2->p4, p3->p4, p4->p5, p5->p1, p5->p6   (p7 alone)

Amendment 4 (walks never visit a node twice; an empty list is missing):

    FxNode   c1..c4        tags: c1 [a], c2 [] (declared, never stored), c3 [a, b], c4 none
    FxRel (FxNode -> FxNode):  c1->c2, c2->c1 (a 2-cycle), c2->c3, c3->c3 (a self-loop), c4->c2
    FxAlt (FxNode -> FxNode):  c1->c2 (parallel to c1-FxRel->c2, so c1 -FxRel-> c2 <-FxAlt- c1
                               returns to its start with no relationship reused)

**Empty lists.** ``c2`` declares ``tags=[]``. :func:`load` drops empty lists before the
upsert (§ 1: neither engine stores an empty list), so it reads as missing.
"""

from __future__ import annotations

from typing import Any

from utils.agent.catalog import CardModel, LabelModel, PropertyModel, RelationModel, _build_options

FX_LABELS = ("FxGroup", "FxTech", "FxTool", "FxMit", "FxPlace", "FxNode")
FX_EXTRA = ("FxObject", "FxExtra")


def _n(id_: str, label: str, name: str, extra: tuple[str, ...] = (), **props: Any) -> dict[str, Any]:
    return {"id": id_, "label": label, "labels": [label, "FxObject", *extra], "name": name,
            "properties": {"stix_type": "fx", **props}}


NODES: list[dict[str, Any]] = [
    _n("fx:g1", "FxGroup", "Alpha", aliases=["A1", "Apt-1"], created="2020-03-15T10:00:00Z", score=1.5, rank=3,
       active=True, size_text="10", note="Hello World"),
    _n("fx:g2", "FxGroup", "alpha", aliases=["a1"], created="2021-07-01", score=2.25, rank=1, active=False,
       size_text="9.5", note="hello world"),
    _n("fx:g3", "FxGroup", "Beta", created="15/03/2020", score=3.0, active=True, size_text="n/a"),
    _n("fx:g4", "FxGroup", "Gamma", aliases=["G"], created="2019-12-31", rank=3, active=False, size_text="100",
       note="World"),
    _n("fx:g5", "FxGroup", "Delta", aliases=["D", "Dx"], created="2022-01-01T00:00:00Z", score=0.1, rank=2,
       size_text="-3", note="Hi"),
    _n("fx:t1", "FxTech", "T-One", platforms=["Linux", "Windows"], score=0.1, weight=5, modified="2020-01-01"),
    _n("fx:t2", "FxTech", "T-Two", platforms=["Windows"], score=0.2, weight=5, modified="2020-06-30T12:00:00Z"),
    _n("fx:t3", "FxTech", "T-Three", platforms=["linux"], score=0.3, weight=7, modified="2021-01-01"),
    _n("fx:t4", "FxTech", "T-Four", weight=3, modified="not-a-date"),
    _n("fx:t5", "FxTech", "T-Five", ("FxExtra",), platforms=["macOS"], score=0.7),
    _n("fx:s1", "FxTool", "Tool-1"),
    _n("fx:s2", "FxTool", "Tool-2"),
    _n("fx:m1", "FxMit", "M-One"),
    _n("fx:m2", "FxMit", "M-Two"),
    *[_n(f"fx:p{i}", "FxPlace", f"P{i}") for i in range(1, 8)],
    _n("fx:c1", "FxNode", "C1", tags=["a"]),
    _n("fx:c2", "FxNode", "C2", tags=[]),
    _n("fx:c3", "FxNode", "C3", tags=["a", "b"]),
    _n("fx:c4", "FxNode", "C4"),
]


def _e(rel: str, s: str, t: str) -> dict[str, Any]:
    return {"id": f"fx:rel:{rel}:{s}->{t}", "type": rel, "source_id": s, "target_id": t, "properties": {}}


EDGES: list[dict[str, Any]] = [
    _e("FxUses", "fx:g1", "fx:t1"), _e("FxUses", "fx:g1", "fx:t2"), _e("FxUses", "fx:g1", "fx:s1"),
    _e("FxUses", "fx:g2", "fx:t1"), _e("FxUses", "fx:g2", "fx:t3"),
    _e("FxUses", "fx:g3", "fx:t2"), _e("FxUses", "fx:g3", "fx:t3"), _e("FxUses", "fx:g3", "fx:t4"),
    _e("FxUses", "fx:g4", "fx:s2"),
    _e("FxSub", "fx:t1", "fx:t2"), _e("FxSub", "fx:t2", "fx:t3"), _e("FxSub", "fx:t1", "fx:t3"),
    _e("FxMitigates", "fx:m1", "fx:t1"), _e("FxMitigates", "fx:m1", "fx:t2"), _e("FxMitigates", "fx:m2", "fx:t2"),
    _e("FxLink", "fx:p1", "fx:p2"), _e("FxLink", "fx:p1", "fx:p3"), _e("FxLink", "fx:p2", "fx:p4"),
    _e("FxLink", "fx:p3", "fx:p4"), _e("FxLink", "fx:p4", "fx:p5"), _e("FxLink", "fx:p5", "fx:p1"),
    _e("FxLink", "fx:p5", "fx:p6"),
    _e("FxRel", "fx:c1", "fx:c2"), _e("FxRel", "fx:c2", "fx:c1"), _e("FxRel", "fx:c2", "fx:c3"),
    _e("FxRel", "fx:c3", "fx:c3"), _e("FxRel", "fx:c4", "fx:c2"),
    _e("FxAlt", "fx:c1", "fx:c2"),
]

#: Written by :func:`load` itself (the loader drops relationship properties).
EDGE_PROPS: dict[str, dict[str, Any]] = {
    "fx:rel:FxUses:fx:g1->fx:t1": {"since": "2020-01-15", "weight": 0.5},
    "fx:rel:FxUses:fx:g1->fx:t2": {"since": "2021-02-01T00:00:00Z", "weight": 1.5},
    "fx:rel:FxUses:fx:g1->fx:s1": {"since": "Jan 2020", "via": "manual"},
    "fx:rel:FxUses:fx:g2->fx:t1": {"since": "2019-05-05"},
    "fx:rel:FxUses:fx:g3->fx:t2": {"weight": 2.0},
    "fx:rel:FxUses:fx:g3->fx:t3": {"since": "2022-12-31"},
}


def _p(name: str, vtype: str) -> PropertyModel:
    return PropertyModel(name, vtype, vtype)


def card() -> CardModel:
    """The fixture's card: ``created``/``modified``/``since`` are dates, ``size_text`` is a
    number written as text (``float_text`` -> ``number_text``)."""
    props = {
        "FxGroup": {"name": "string", "aliases": "list", "created": "date", "score": "number", "rank": "integer",
                    "active": "boolean", "size_text": "number_text", "note": "string"},
        "FxTech": {"name": "string", "platforms": "list", "score": "number", "weight": "integer",
                   "modified": "date"},
        "FxTool": {"name": "string"},
        "FxMit": {"name": "string"},
        "FxPlace": {"name": "string"},
        "FxNode": {"name": "string", "tags": "list"},
    }
    labels = {lab: LabelModel(lab, "", "name", {p: _p(p, t) for p, t in ps.items()}) for lab, ps in props.items()}
    rels = {
        "FxUses": RelationModel("FxUses", patterns=(("FxGroup", "FxTech"), ("FxGroup", "FxTool")),
                                properties={"since": _p("since", "date"), "weight": _p("weight", "number"),
                                            "via": _p("via", "string")}),
        "FxSub": RelationModel("FxSub", patterns=(("FxTech", "FxTech"),)),
        "FxMitigates": RelationModel("FxMitigates", patterns=(("FxMit", "FxTech"),)),
        "FxLink": RelationModel("FxLink", patterns=(("FxPlace", "FxPlace"),)),
        "FxRel": RelationModel("FxRel", patterns=(("FxNode", "FxNode"),)),
        "FxAlt": RelationModel("FxAlt", patterns=(("FxNode", "FxNode"),)),
    }
    m = CardModel("fx", "test", "neo4j+gremlin", labels, rels, 3, "test")
    _build_options(m, {})
    return m


# --------------------------------------------------------------------------- #
# Loading (idempotent; wipes only Fx-labelled data)
# --------------------------------------------------------------------------- #


def stored(node: dict[str, Any]) -> dict[str, Any]:
    """The record as the stores hold it: no empty list (amendment 4, § 1)."""
    props = {k: v for k, v in node["properties"].items() if not (isinstance(v, list) and not v)}
    return {**node, "properties": props}


def wipe(engines: Any) -> None:
    engines.neo4j_raw("MATCH (n:FxObject) DETACH DELETE n")
    engines.gremlin_raw("g.V().hasLabel(within(" + ",".join(f"'{lab}'" for lab in FX_LABELS) + ")).drop().iterate()")


def load(engines: Any) -> dict[str, Any]:
    """Wipe the Fx data and load it again into both engines of the verification pair."""
    from utils.graph_loader.stores.gremlin import GremlinGraphStore, gremlin_edge_label
    from utils.graph_loader.stores.neo4j import Neo4jGraphStore
    from utils.specialists.algebra.differential import GREMLIN_URI, MEASURED, NEO4J_URI
    import os

    for uri in (NEO4J_URI, GREMLIN_URI):
        if any(f":{p}" in uri for p in MEASURED):
            raise RuntimeError(f"refusing a measured store: {uri}")
    wipe(engines)
    neo = Neo4jGraphStore(uri=NEO4J_URI, user=os.environ.get("NEO4J_USER", "neo4j"),
                          password=os.environ.get("NEO4J_PASSWORD", ""), export_files={})
    grem = GremlinGraphStore(uri=GREMLIN_URI, export_files={})
    for store in (neo, grem):
        store.connect()
        try:
            store.upsert_nodes([stored(n) for n in NODES])
            store.upsert_edges(EDGES)
        finally:
            store.close()
    # Fixture-only: relationship properties, which the loader does not write.
    for eid, props in EDGE_PROPS.items():
        engines.neo4j_raw("MATCH ()-[r {id: $id}]->() SET r += $props", {"id": eid, "props": props})
        q = "g.E().has('id', eid)" + "".join(f".property('{k}', v{i})" for i, k in enumerate(props)) + ".iterate()"
        engines.gremlin_raw(q, {"eid": eid, **{f"v{i}": v for i, v in enumerate(props.values())}})
    n_neo = engines.neo4j_raw("MATCH (n:FxObject) RETURN count(n) AS c")[0]["c"]
    e_neo = engines.neo4j_raw("MATCH (:FxObject)-[r]->(:FxObject) RETURN count(r) AS c")[0]["c"]
    labs = ",".join(f"'{lab}'" for lab in FX_LABELS)
    n_gr = engines.gremlin_raw(f"g.V().hasLabel(within({labs})).count()")[0]
    e_gr = engines.gremlin_raw(f"g.V().hasLabel(within({labs})).outE().count()")[0]
    _ = gremlin_edge_label
    return {"neo4j": (n_neo, e_neo), "gremlin": (n_gr, e_gr), "want": (len(NODES), len(EDGES))}
