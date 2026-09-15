"""Contract checks on a small, unrelated domain; no catalogue fixtures needed."""

import pytest

from utils.planner.cards import SourceCardView
from utils.planner.discovery_candidates import DiscoveryIndex


def card(dataset="library"):
    return SourceCardView.from_card_dict({
        "dataset": dataset, "runtime_backend": "neo4j",
        "node_labels": ["Book", "Topic"], "relationship_types": ["COVERS"],
        "node_properties": {
            "Book": {"description": {}, "aliases": {}, "catalogue_key": {}},
            "Topic": {"description": {}},
        },
        "identity": {"unique_backstop": "id", "join_key": ["catalogue_key"]},
        "safety": {"allowed_edge_patterns": {"COVERS": [["Book", "Topic"]]}},
    })


def node(id, name, label="Book", **props):
    return {"id": id, "name": name, "label": label, "properties": props}


def index(nodes, edges=()):
    return DiscoveryIndex({"library": (card(), nodes, edges)})


def test_description_and_alias_discovery_without_named_entity():
    db = index([node("b1", "Night Watch", description="Migrating birds navigate by stars", aliases=["avian astronomy"]),
                node("b2", "Day Watch", description="A history of mechanical clocks")])
    assert db.search("avian astronomy")[0].key == ("library", "b1")
    assert db.search("birds navigate stars")[0].matched_fields == ("description",)
    assert db.search("birds navigate stars")[0].exact == ()


def test_exact_before_ranking_and_identity_not_inferred_from_grammar():
    db = index([node("opaque/a", "Night Watch", catalogue_key="CAT-007"),
                node("opaque/b", "Day Watch", description="Night night watch watch")])
    assert db.search("CAT-007")[0].key == ("library", "opaque/a")
    assert db.search("Night Watch")[0].exact == ("name",)
    assert db.exact_matches("CAT-0078") == {}


def test_same_name_or_identifier_across_sources_stays_ambiguous():
    nodes = [node("1", "Night Watch")]
    db = DiscoveryIndex({s: (card(s), nodes, []) for s in ("library", "archive")})
    assert set(db.exact_matches("Night Watch")) == {("library", "1"), ("archive", "1")}
    assert len(db.search("Night Watch")) == 2


def test_same_name_within_source_stays_ambiguous():
    db = index([node("a", "Night Watch"), node("b", "Night Watch")])
    assert len(db.exact_matches("Night Watch")) == 2


def test_nested_name_occurrences_and_separate_short_name():
    db = index([node("a", "Night Watch"), node("b", "Watch")])
    assert set(db.exact_matches("Night Watch")) == {("library", "a")}
    assert len(db.exact_matches("Compare Night Watch with Watch")) == 2


def test_graph_context_finds_parent_and_carries_direction():
    db = index([node("b1", "Night Watch"), node("t1", "Celestial Navigation", "Topic", description="birds migrate")],
               [{"source_id": "b1", "target_id": "t1", "type": "COVERS"}])
    hits = {hit.key: hit for hit in db.search("birds migrate", arm="graph")}
    assert hits[("library", "b1")].context[0].direction == "out"
    assert hits[("library", "b1")].context[0].neighbour == ("library", "t1")
    assert "graph" in hits[("library", "b1")].views
    assert ("library", "b1") not in {h.key for h in db.search("birds migrate", arm="fields")}


def test_unknown_label_property_and_edge_are_excluded():
    db = index([node("b", "Night", secret="classifiedword"), node("t", "Stars", "Topic"), node("x", "Ghost", "Unknown")],
               [{"source_id": "b", "target_id": "t", "type": "INVENTED"},
                {"source_id": "t", "target_id": "b", "type": "COVERS"}])
    assert ("library", "x") not in db.documents
    assert db.search("classifiedword") == []
    assert db.contexts == {}


def test_empty_and_schema_word_names_do_not_bind():
    db = index([node("b", "Book"), node("t", "", "Topic", description=None)])
    assert db.exact_matches("List Book entries") == {}
    assert db.search("") == []
    assert db.search("unfindableword") == []


def test_graph_budget_is_deterministic_and_reports_truncation():
    nodes = [node("b", "Night"), node("a", "Stars", "Topic"), node("z", "Moon", "Topic")]
    edges = [{"source_id": "b", "target_id": x, "type": "COVERS"} for x in ("z", "a")]
    db = DiscoveryIndex({"library": (card(), nodes, edges)}, max_neighbours=1)
    assert db.contexts[("library", "b")][0].neighbour == ("library", "a")
    assert ("library", "b") in db.context_truncated


def test_canonical_identity_collision_fails_closed():
    with pytest.raises(ValueError, match="duplicate canonical"):
        index([node("a", "Night"), node("a", "Moon")])


def test_source_key_must_match_card():
    with pytest.raises(ValueError, match="source key"):
        DiscoveryIndex({"other": (card(), [], [])})


def test_determinism_and_global_budget():
    nodes = [node("b", "Night Watch"), node("a", "Night Sky")]
    assert index(nodes).search("Night") == index(reversed(nodes)).search("Night")
    assert len(index(nodes).search("Night", top_k=1)) == 1
    with pytest.raises(ValueError):
        index(nodes).search("Night", top_k=0)
