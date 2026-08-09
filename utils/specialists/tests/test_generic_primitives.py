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
