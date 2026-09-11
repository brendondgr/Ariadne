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
    assert draft.params["ids"] == [
        "capec:attack-pattern:150",
        "capec:view:150",
        "capec:category:150",
    ]


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
    # The intermediate is retrieved in its own right, not just traversed: the
    # one-hop prefix gets its own block alongside the two-hop one.
    assert "Technique|DETECTS:in" in draft.meta["paths"]
    assert "Technique|DETECTS:in->HAS_ANALYTIC:out" in draft.meta["paths"]
    assert "<-[:DETECTS]-()-[:HAS_ANALYTIC]->" in draft.query


def test_generic_chain_uses_the_declared_direction(generic_only: None) -> None:
    """DETECTS points DetectionStrategy -> Technique, so from a Technique it is inbound.

    Both roots are emitted because the seed's real label is not known at build
    time, but each branch is guarded by the label it was derived from, so only
    the applicable one fires.
    """
    resolved = _attack(
        "How is T1047 detected?", ("Technique", "DetectionStrategy")
    )
    draft = CypherQueryBuilder().build(resolved)

    assert "Technique|DETECTS:in" in draft.meta["paths"]
    assert "<-[:DETECTS]-(m1) WHERE n:Technique OR NOT (" in draft.query


def test_generic_chain_guards_each_branch_by_its_root_label(
    generic_only: None,
) -> None:
    """A branch derived from label L must not fire on an anchor that is not L.

    Without the guard, "which techniques does Mimikatz use" also takes the
    inbound USES branch and returns the fifty-one groups that use Mimikatz as
    though they were techniques it uses — the exact conflation behind all six of
    Arm G's hallucinations.
    """
    resolved = _attack(
        "Which techniques does software S0002 use?", ("Software", "Technique")
    )
    query = CypherQueryBuilder().build(resolved).query

    assert "-[:USES]->(m0) WHERE n:Software OR NOT (n:Software OR n:Technique)" in query
    assert "<-[:USES]-(m1) WHERE n:Technique OR NOT (n:Software OR n:Technique)" in query


def test_generic_chain_falls_back_when_the_anchor_matches_no_candidate(
    generic_only: None,
) -> None:
    """A sub-technique seed resolving ["Tactic", "Technique"] carries neither.

    The guard's second disjunct is what stops that anchor from being excluded
    from every branch: when it matches no candidate label, all branches apply.
    """
    resolved = _attack(
        "Which tactics do those techniques belong to?",
        ("Tactic", "Technique"),
        seed_ids=("T1110.001",),
    )
    query = CypherQueryBuilder().build(resolved).query

    assert query.count("OR NOT (n:Tactic OR n:Technique)") == 2
    assert "<-[:HAS_TECHNIQUE]-" in query


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

    assert "-[:USES]->(m0) WHERE" in draft.query
    # The far end carries no label filter; the only labels in the query are the
    # anchor guards, which sit before the WHERE's OR NOT clause.
    assert "->(m0:Technique)" not in draft.query
    assert "-(m1:Technique)" not in draft.query


def test_generic_chain_dedupes_paths_on_edge_not_label(generic_only: None) -> None:
    """Two labels behind one edge are one branch per root, not one per label."""
    resolved = _attack(
        "Which techniques does software S0002 use?",
        ("Software", "Technique", "SubTechnique"),
    )
    paths = CypherQueryBuilder().build(resolved).meta["paths"]

    # Software reaches Technique and SubTechnique by the same edge: one branch.
    assert paths.count("Software|USES:out") == 1
    assert not any(p.startswith("Software|USES:out->") for p in paths)


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

    # One OPTIONAL MATCH per branch, each with its own collect — never several
    # patterns in one MATCH, which would take their cartesian product.
    assert query.count("OPTIONAL MATCH") == query.count("collect(DISTINCT")
    assert query.count("OPTIONAL MATCH") >= 2


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

    Since the Category/View namespace repair the anchor carries no ``hasLabel``
    at all — it matches on the canonical id, which is unique across labels, so a
    label filter on the *seed* can only be a way to be wrong. The property this
    test protects is now carried by two things instead of one: the id resolves in
    the CWE namespace, and the draft *declares* the Weakness binding so the
    pre-run gate still checks the filter the parser can no longer see.
    """
    resolved = _capec(
        "Which CAPEC patterns exploit CWE-522, and which techniques do they map to?",
        ("Weakness", "AttackPattern", "TaxonomyEntry"),
        join_key="attack-technique-id",
    )
    draft = GremlinQueryBuilder().build(resolved)

    assert draft.query.startswith('g.V().has("id", within(ids))')
    assert 'hasLabel("Weakness")' not in draft.query
    # The pattern that owns the join edge is reached, not assumed.
    assert '.in("EXPLOITS_WEAKNESS").hasLabel("AttackPattern").as("ap")' in draft.query
    assert draft.params["ids"] == ["cwe:522"]
    # A CWE seed is not a CAPEC number, so it offers one candidate, not three,
    # and the declared binding says which label the gate should check it against.
    assert draft.meta["bindings"] == [
        {"label": "Weakness", "property": "id", "param": "ids"}
    ]


def test_generic_walk_resolves_direction_from_the_registry(
    generic_only: None,
) -> None:
    """The declared facet decides in() or out(), not a hardcoded traversal."""
    resolved = _capec(
        "Which mitigations apply to CAPEC-66?", ("AttackPattern", "Mitigation")
    )
    draft = GremlinQueryBuilder().build(resolved)

    assert draft.template == "generic_walk"
    assert '__.hasLabel("AttackPattern"), __.not(' in draft.query
    assert '.out("HAS_MITIGATION")' in draft.query
    # All three CAPEC namespaces, because a bare CAPEC number cannot say which
    # kind it names — CAPEC-66 is a pattern, CAPEC-118 a category, CAPEC-284 a
    # view. Ids are unique across the store, so at most one can match.
    assert draft.params["ids"] == [
        "capec:attack-pattern:66",
        "capec:view:66",
        "capec:category:66",
    ]
    # Anchored by identifier alone: a hasLabel filter on the anchor can only be
    # wrong, since the canonical vertex id is already unique across labels.
    assert draft.query.startswith('g.V().has("id", within(ids))')


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
    # One bounded repeat, not one branch per depth: the validator counts every
    # out/in step in the whole query against max_traversal_depth, so unrolling
    # the levels reads as depth 12 and the draft is rejected before it runs.
    assert '.repeat(__.out("CHILD_OF")).times(3).emit()' in draft.query


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

    assert "AttackPattern|ChildOf:out*" in paths
    assert "AttackPattern|ChildOf:in*" in paths


def test_generic_walk_only_repeats_edges_the_task_named(
    generic_only: None,
) -> None:
    """Repeating every declared self-loop would make a lookup a hierarchy crawl."""
    resolved = _capec(
        "Which mitigations apply to CAPEC-66?", ("AttackPattern", "Mitigation")
    )
    paths = GremlinQueryBuilder().build(resolved).meta["paths"]

    assert not any("ChildOf" in p for p in paths)


def test_generic_walk_fits_the_traversal_step_budget(generic_only: None) -> None:
    """The whole query must stay inside max_traversal_depth, and say what it dropped.

    The validator counts every out/in step in the query, not the depth of any one
    branch, so a wide union is rejected outright. Branches are fitted cheapest
    first and anything dropped is named — a silently truncated walk reads as a
    complete answer when it is not.
    """
    import re

    resolved = _capec(
        "Which CAPEC patterns are children of CAPEC-98 and what mitigations do they have?",
        ("AttackPattern", "ChildOf", "Mitigation"),
    )
    draft = GremlinQueryBuilder().build(resolved)

    steps = len(re.findall(r"\.(out|in|both)\(", draft.query))
    assert steps <= resolved.task.max_depth()
    assert draft.meta["dropped_branches"]


# -- the bridge is an outer join --------------------------------------------


def test_generic_bridge_is_an_outer_join(generic_only: None) -> None:
    """The anchor must survive an empty mapping list.

    An inner join drops a pattern that maps to nothing, which is both a recall
    bug — CAPEC-116 exploits CWE-1243 and maps to no technique — and a grounding
    bug: "this pattern has no ATT&CK mapping" is a real answer and needs the
    record it was read from.
    """
    resolved = _capec(
        "Which ATT&CK techniques does CAPEC-603 map to?",
        ("AttackPattern", "MAPS_TO", "TaxonomyEntry"),
        join_key="attack-technique-id",
    )
    query = GremlinQueryBuilder().build(resolved).query

    assert '.project("ap","tax")' in query
    assert '.by(__.out("MAPS_TO").hasLabel("TaxonomyEntry").elementMap().fold())' in query
    # The inner-join form must be gone from the anchored forward shape.
    assert '.out("MAPS_TO").hasLabel("TaxonomyEntry").as("tax")' not in query


def test_bridge_outer_normalizer_keeps_an_unmapped_anchor() -> None:
    """An empty fold yields a record with no join values, not no record."""
    from utils.specialists.gremlin.normalizer import GremlinNormalizer

    rows = [{"ap": {"id": "capec:attack-pattern:603", "name": "Blockage"}, "tax": []}]
    resolved = _capec(
        "Which ATT&CK techniques does CAPEC-603 map to?",
        ("AttackPattern", "MAPS_TO", "TaxonomyEntry"),
        join_key="attack-technique-id",
    )
    records = GremlinNormalizer().normalize(
        rows, resolved, "q", fixture_card("capec")
    )

    assert len(records) == 1
    assert records[0].primary_id == "CAPEC-603"
    # No join values means the dependent federated hop correctly stands down.
    assert records[0].join_values == ()


def test_bridge_outer_normalizer_still_projects_mappings() -> None:
    """A non-empty fold produces the T-prefixed join values as before."""
    from utils.specialists.gremlin.normalizer import GremlinNormalizer

    rows = [
        {
            "ap": {"id": "capec:attack-pattern:150", "name": "Collect Data"},
            "tax": [
                {"id": "capec:taxonomy:ATTACK:1003", "entry_id": "1003",
                 "taxonomy_name": "ATTACK"},
                {"id": "capec:taxonomy:WASC:11", "entry_id": "11",
                 "taxonomy_name": "WASC"},
            ],
        }
    ]
    resolved = _capec(
        "Which ATT&CK techniques does CAPEC-150 map to?",
        ("AttackPattern", "MAPS_TO", "TaxonomyEntry"),
        join_key="attack-technique-id",
    )
    records = GremlinNormalizer().normalize(
        rows, resolved, "q", fixture_card("capec")
    )

    assert records[0].join_values == ("T1003",)
    # The non-ATTACK taxonomy entry is still carried as evidence, just not joined.
    assert len(records[0].related) == 2


def test_prefixed_bridge_inner_joins_the_first_hop_and_outer_joins_the_second(
    generic_only: None,
) -> None:
    """Only patterns that exploit the CWE belong; but they belong even unmapped.

    CWE-1243 is exploited by CAPEC-116 and CAPEC-545. CAPEC-116 maps to no
    technique, so an inner join on the second hop deleted it from the answer.
    """
    resolved = _capec(
        "Which CAPEC patterns exploit CWE-1243, and which techniques do they map to?",
        ("Weakness", "AttackPattern", "TaxonomyEntry"),
        join_key="attack-technique-id",
    )
    query = GremlinQueryBuilder().build(resolved).query

    # First hop: inner, as a traversal step.
    assert '.in("EXPLOITS_WEAKNESS").hasLabel("AttackPattern").as("ap")' in query
    # Second hop: outer, as a folded projection.
    assert '.by(__.out("MAPS_TO").hasLabel("TaxonomyEntry").elementMap().fold())' in query
    assert '.out("MAPS_TO").hasLabel("TaxonomyEntry").as("tax")' not in query


def test_bridge_outer_normalizer_carries_the_chain_seed() -> None:
    """A CWE-anchored row keeps the weakness as a related entry on each pattern."""
    from utils.specialists.gremlin.normalizer import GremlinNormalizer

    rows = [{
        "w": {"id": "cwe:1243"},
        "ap": {"id": "capec:attack-pattern:116", "name": "Excavation"},
        "tax": [],
    }]
    resolved = _capec(
        "Which CAPEC patterns exploit CWE-1243?",
        ("Weakness", "AttackPattern", "TaxonomyEntry"),
        join_key="attack-technique-id",
    )
    records = GremlinNormalizer().normalize(rows, resolved, "q", fixture_card("capec"))

    assert records[0].primary_id == "CAPEC-116"
    assert {r.get("id") for r in records[0].related} == {"CWE-1243"}
    assert records[0].join_values == ()


# -- anchor namespace: Category and View seeds ------------------------------


def test_generic_walk_binds_a_category_seed_in_every_capec_namespace(
    generic_only: None,
) -> None:
    """CAPEC numbers one sequence across patterns, categories and views.

    ``CAPEC-687`` is a Category. The walk used to send every bare CAPEC number to
    ``capec:attack-pattern:<n>``, which no Category vertex carries, so the anchor
    bound to nothing and the walk returned zero records before a single traversal
    step ran. All 21 Category-anchored development questions failed this way
    (`EXP-2026-09-017` A-2, mechanism ``ns``).
    """
    resolved = _capec(
        "Which attack patterns are members of CAPEC-687?",
        ("Category", "HAS_MEMBER", "AttackPattern"),
    )
    draft = GremlinQueryBuilder().build(resolved)

    assert draft.params["ids"] == [
        "capec:attack-pattern:687",
        "capec:view:687",
        "capec:category:687",
    ]
    # Identifier-only anchor: ids are unique across the store, so at most one of
    # the three can match and the graph does the disambiguating.
    assert draft.query.startswith('g.V().has("id", within(ids))')


def test_generic_walk_binds_a_view_seed_in_every_capec_namespace(
    generic_only: None,
) -> None:
    """``CAPEC-703`` is a View, and 18 of 20 View anchors returned nothing."""
    resolved = _capec(
        "Which attack patterns does CAPEC-703 contain?",
        ("View", "HAS_MEMBER", "AttackPattern"),
    )
    draft = GremlinQueryBuilder().build(resolved)

    assert draft.params["ids"] == [
        "capec:attack-pattern:703",
        "capec:view:703",
        "capec:category:703",
    ]
    assert draft.query.startswith('g.V().has("id", within(ids))')


def test_generic_walk_declares_the_binding_the_parser_cannot_see(
    generic_only: None,
) -> None:
    """A label-free anchor must declare its binding or the gate stops checking it.

    ``extract_bindings`` reads ``hasLabel(...).has(prop, ...)``. Dropping the
    label makes the id filter invisible to that parser, and an undeclared filter
    is what the pre-run audit calls "unchecked" — a query filtering on values
    nothing verified. One entry per candidate label, all on the same parameter,
    so the filter is satisfiable when any of them admits the seeds.
    """
    resolved = _capec(
        "Which mitigations apply to CAPEC-66?", ("AttackPattern", "Mitigation")
    )
    draft = GremlinQueryBuilder().build(resolved)

    assert draft.meta["bindings"] == [
        {"label": "AttackPattern", "property": "id", "param": "ids"},
        {"label": "View", "property": "id", "param": "ids"},
        {"label": "Category", "property": "id", "param": "ids"},
    ]


def test_a_cwe_seed_keeps_its_own_namespace(generic_only: None) -> None:
    """The namespace repair must not undo the CWE one.

    ``_capec_candidate_ids`` alone would pass ``CWE-522`` through untouched,
    where the walk needs ``cwe:522``. Five F-CWE questions scored exactly zero in
    Arm G for the mirror image of this mistake, so it is asserted rather than
    assumed.
    """
    resolved = _capec(
        "Which CAPEC patterns exploit CWE-522?", ("Weakness", "AttackPattern")
    )
    draft = GremlinQueryBuilder().build(resolved)

    assert draft.params["ids"] == ["cwe:522"]
