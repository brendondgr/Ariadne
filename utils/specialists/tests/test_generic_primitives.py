#!/usr/bin/env python3
"""Tests for the schema-driven primitives used when templates are disabled.

These cover the capabilities the Arm G control was missing — join projection,
composition (chaining and intersection), and anchor/direction resolution — each
of which is reachable only under ``SPECIALIST_GENERIC_ONLY``. The companion
suite ``test_generic_only_isolation.py`` asserts the other half of the contract:
that none of this changes what the default cascade emits.
"""

from __future__ import annotations

import pytest

from utils.specialists.contracts import SpecialistTask
from utils.specialists.cypher.builder import CypherQueryBuilder
from utils.specialists.gremlin.builder import GremlinQueryBuilder
from utils.specialists.resolve import resolve
from utils.specialists.tests._fixtures import fixture_card


@pytest.fixture
def generic_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPECIALIST_GENERIC_ONLY", "true")


def _capec(text: str, entities: tuple[str, ...], **kw):
    return resolve(
        SpecialistTask(
            sub_question_id="q1", source="capec", text=text, entities=entities, **kw
        ),
        fixture_card("capec"),
    )


def _attack(text: str, entities: tuple[str, ...], **kw):
    return resolve(
        SpecialistTask(
            sub_question_id="q1", source="attack", text=text, entities=entities, **kw
        ),
        fixture_card("attack"),
    )


# -- join projection --------------------------------------------------------


def test_generic_bridge_walks_the_declared_join_edge(generic_only: None) -> None:
    """A bridge question must traverse MAPS_TO, not describe the anchor.

    Describing returns facet counts, which carry no neighbour ids, so the
    dependent federated sub-question is skipped for want of seeds. This is the
    single largest source of Arm G's lost correctness.
    """
    resolved = _capec(
        "Which ATT&CK techniques does CAPEC-150 map to?",
        ("AttackPattern", "MAPS_TO", "TaxonomyEntry"),
        join_key="attack-technique-id",
    )
    draft = GremlinQueryBuilder().build(resolved)

    assert draft.template == "generic_bridge"
    assert '.out("MAPS_TO")' in draft.query
    assert 'hasLabel("TaxonomyEntry")' in draft.query
    assert draft.params["ids"] == ["capec:attack-pattern:150"]


def test_generic_bridge_reverses_when_seeded_on_the_key(generic_only: None) -> None:
    """Seeded on ATT&CK ids, the bridge enters at the key and walks backwards."""
    resolved = _capec(
        "Which CAPEC patterns map to T1021?",
        ("AttackPattern", "MAPS_TO", "TaxonomyEntry"),
        join_key="attack-technique-id",
    )
    draft = GremlinQueryBuilder().build(resolved)

    assert draft.template == "generic_bridge"
    assert '.in("MAPS_TO")' in draft.query
    # Entry ids are stored without the 'T' prefix on the CAPEC side.
    assert draft.params["entryIds"] == ["1021"]
    assert draft.meta["direction"] == "in"


def test_generic_bridge_is_built_from_the_declared_endpoint(
    generic_only: None,
) -> None:
    """No MITRE literal decides the edge — the join registry does."""
    resolved = _capec(
        "Which ATT&CK techniques does CAPEC-150 map to?",
        ("AttackPattern", "MAPS_TO", "TaxonomyEntry"),
        join_key="attack-technique-id",
    )
    endpoint = resolved.join_endpoint
    assert endpoint is not None
    draft = GremlinQueryBuilder().build(resolved)

    assert f'.out("{endpoint.via_edge}")' in draft.query
    assert f'hasLabel("{endpoint.labels[0]}")' in draft.query


# -- composition: chaining --------------------------------------------------


def test_generic_chain_reaches_a_two_hop_label(generic_only: None) -> None:
    """Analytics sit behind a DetectionStrategy; one hop never reaches them."""
    resolved = _attack(
        "How is T1047 detected, and via which analytics?",
        ("Technique", "DetectionStrategy", "Analytic"),
    )
    draft = CypherQueryBuilder().build(resolved)

    assert draft.template == "generic_chain"
    assert draft.meta["paths"] == ["DETECTS:in", "DETECTS:in->HAS_ANALYTIC:out"]
    # The intermediate is retrieved in its own right, not just traversed: the
    # one-hop prefix gets its own block alongside the two-hop one.
    assert "<-[:DETECTS]-(m0)" in draft.query
    assert "<-[:DETECTS]-()-[:HAS_ANALYTIC]->(m1)" in draft.query


def test_generic_chain_uses_the_declared_direction(generic_only: None) -> None:
    """DETECTS points DetectionStrategy -> Technique, so the walk is inbound."""
    resolved = _attack(
        "How is T1047 detected?", ("Technique", "DetectionStrategy")
    )
    draft = CypherQueryBuilder().build(resolved)

    assert "<-[:DETECTS]-" in draft.query
    assert "-[:DETECTS]->" not in draft.query


def test_generic_chain_does_not_filter_the_far_end_by_label(
    generic_only: None,
) -> None:
    """The edge decides what is on the other side, not the question's wording.

    "Which techniques does Mimikatz use" resolves the label ``Technique``, but
    ``USES`` out of ``Software`` lands on ``Technique`` *and* ``SubTechnique``.
    Constraining the pattern to the named label drops thirteen of the seventeen
    gold ids, so the far end is left unlabelled.
    """
    resolved = _attack(
        "Which techniques does software S0002 use?", ("Software", "Technique")
    )
    draft = CypherQueryBuilder().build(resolved)

    assert "-[:USES]->(m0)" in draft.query
    assert ":Technique)" not in draft.query


def test_generic_chain_dedupes_paths_on_edge_not_label(generic_only: None) -> None:
    """Two labels behind one edge are one branch, not two."""
    resolved = _attack(
        "Which techniques does software S0002 use?",
        ("Software", "Technique", "SubTechnique"),
    )
    draft = CypherQueryBuilder().build(resolved)

    assert draft.meta["paths"] == ["USES:out"]


def test_generic_chain_aggregates_branches_independently(
    generic_only: None,
) -> None:
    """Each branch gets its own OPTIONAL MATCH + collect, never one MATCH.

    Two branches in a single pattern take the cartesian product of their
    neighbours, duplicating every related entry.
    """
    resolved = _attack(
        "How is T1047 detected, and via which analytics?",
        ("Technique", "DetectionStrategy", "Analytic"),
    )
    query = CypherQueryBuilder().build(resolved).query

    assert query.count("OPTIONAL MATCH") == 2
    assert query.count("collect(DISTINCT") == 2


def test_generic_chain_keeps_the_anchor_when_the_path_is_empty(
    generic_only: None,
) -> None:
    """An empty neighbourhood is an answer; losing the anchor row is not."""
    resolved = _attack(
        "How is T1047 detected?", ("Technique", "DetectionStrategy")
    )
    query = CypherQueryBuilder().build(resolved).query

    assert "OPTIONAL MATCH" in query
    assert "CASE WHEN size(hops) = 0" in query


# -- composition: intersection ----------------------------------------------


def test_generic_intersect_fires_on_heterogeneous_seeds(generic_only: None) -> None:
    """Two anchors of different kinds ask for what they have in common.

    "Techniques in TA0006 mitigated by M1027" is 7 techniques; walking the
    tactic alone returns all 67 under it, which is a different question.
    """
    resolved = _attack(
        "Which techniques in tactic TA0006 are mitigated by M1027?",
        ("Tactic", "Technique", "Mitigation"),
    )
    draft = CypherQueryBuilder().build(resolved)

    assert draft.template == "generic_intersect"
    assert draft.params["anchorCount"] == 2
    assert "size(anchors) = $anchorCount" in draft.query


def test_generic_intersect_stands_down_for_a_fan_out(generic_only: None) -> None:
    """Six technique seeds are 'each of these', not 'common to all of these'."""
    resolved = _attack(
        "What mitigations apply to T1003 and T1119?", ("Technique", "Mitigation")
    )
    draft = CypherQueryBuilder().build(resolved)

    assert draft.template != "generic_intersect"


# -- anchor and direction resolution ----------------------------------------


def test_generic_bridge_anchors_on_the_seeds_own_label(generic_only: None) -> None:
    """A CWE seed is a Weakness, not an AttackPattern.

    Anchoring on the pattern matches zero vertices and returns nothing, which is
    exactly how five F-CWE questions scored zero in Arm G.
    """
    resolved = _capec(
        "Which CAPEC patterns exploit CWE-522, and which techniques do they map to?",
        ("Weakness", "AttackPattern", "TaxonomyEntry"),
        join_key="attack-technique-id",
    )
    draft = GremlinQueryBuilder().build(resolved)

    assert draft.query.startswith('g.V().hasLabel("Weakness")')
    # The pattern that owns the join edge is reached, not assumed.
    assert '.in("EXPLOITS_WEAKNESS").hasLabel("AttackPattern").as("ap")' in draft.query
    assert draft.params["ids"] == ["cwe:522"]


def test_generic_walk_resolves_direction_from_the_registry(
    generic_only: None,
) -> None:
    """The declared facet decides in() or out(), not a hardcoded traversal."""
    resolved = _capec(
        "Which mitigations apply to CAPEC-66?", ("AttackPattern", "Mitigation")
    )
    draft = GremlinQueryBuilder().build(resolved)

    assert draft.template == "generic_walk"
    assert 'union(__.out("HAS_MITIGATION"))' in draft.query
    assert draft.params["ids"] == ["capec:attack-pattern:66"]


def test_generic_walk_repeats_a_self_referential_edge(generic_only: None) -> None:
    """An abstraction hierarchy is the whole ancestry, not the first step.

    ``AttackPattern -ChildOf-> AttackPattern`` loops on its own label, so
    breadth-first search stops there: the parent is retrieved and the
    grandparent never is. Repeating the edge per depth is the transitive walk.
    """
    resolved = _capec(
        "Walk the abstraction hierarchy up from CAPEC-7: what are its ancestors?",
        ("AttackPattern", "ChildOf"),
    )
    draft = GremlinQueryBuilder().build(resolved)

    assert draft.template == "generic_walk"
    assert '__.out("CHILD_OF").out("CHILD_OF")' in draft.query


def test_generic_walk_emits_both_directions_of_a_self_loop(
    generic_only: None,
) -> None:
    """Nothing in the schema says which direction of a self-loop means "up".

    Ancestor-versus-descendant is the domain nuance a hand-written template
    encodes; a generic primitive returns both rather than guessing one.
    """
    resolved = _capec(
        "Walk the abstraction hierarchy up from CAPEC-7: what are its ancestors?",
        ("AttackPattern", "ChildOf"),
    )
    paths = GremlinQueryBuilder().build(resolved).meta["paths"]

    assert "ChildOf:out" in paths
    assert "ChildOf:in" in paths


def test_generic_walk_only_repeats_edges_the_task_named(
    generic_only: None,
) -> None:
    """Repeating every declared self-loop would make a lookup a hierarchy crawl."""
    resolved = _capec(
        "Which mitigations apply to CAPEC-66?", ("AttackPattern", "Mitigation")
    )
    paths = GremlinQueryBuilder().build(resolved).meta["paths"]

    assert not any("ChildOf" in p for p in paths)
