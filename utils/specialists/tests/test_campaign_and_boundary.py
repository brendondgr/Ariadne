#!/usr/bin/env python3
"""Step 7 hermetic tests: campaign query templates + the schema-boundary refusal.

Two behaviors landed together because they close the same class of failure —
answering a *different* question than the one asked:

  * Campaign relationship questions used to fall through to ``node_lookup``;
    now they route to dedicated ``campaign_techniques`` /
    ``campaign_attribution`` templates.
  * A task naming an entity the source card doesn't model (e.g. ``Asset``,
    which exists only in ICS ATT&CK) used to degrade silently to whatever the
    known entities could express; now the shared specialist returns an honest
    empty — ok, zero records, **no query executed** — with the boundary named
    in the trace.
"""

from __future__ import annotations

from utils.specialists.cypher.builder import CypherQueryBuilder
from utils.specialists.cypher.normalizer import CypherNormalizer
from utils.specialists.cypher.validator import CypherValidator
from utils.specialists.resolve import resolve
from utils.specialists.tests._fixtures import (
    StubConnector,
    fixture_card,
    make_task,
)
from utils.specialists.tests.test_loop import _specialist, _steps

_LIMITS = {"max_traversal_depth": 3, "max_result_rows": 300, "query_timeout_ms": 5000}


def _draft(entities: tuple[str, ...], text: str, seed_ids: tuple[str, ...] = ()):
    card = fixture_card("attack")
    task = make_task(entities=entities, text=text, seed_ids=seed_ids)
    return CypherQueryBuilder().build(resolve(task, card)), card


# -- routing -----------------------------------------------------------------


def test_campaign_techniques_routes_and_validates() -> None:
    draft, card = _draft(
        ("Campaign", "Technique"), "Which techniques did campaign C0027 use?"
    )
    assert draft.template == "campaign_techniques"
    assert "(c:Campaign)-[:USES]->(t:Technique)" in draft.query
    assert draft.params == {"ids": ["C0027"]}
    verdict = CypherValidator().validate(draft, card, _LIMITS)
    assert verdict.ok, verdict.reasons


def test_campaign_attribution_outranks_group_branch() -> None:
    # Campaign+Group must NOT be captured by group_techniques.
    draft, card = _draft(
        ("Campaign", "Group"), "Which group is campaign C0028 attributed to?"
    )
    assert draft.template == "campaign_attribution"
    assert "(c:Campaign)-[:ATTRIBUTED_TO]->(g:Group)" in draft.query
    assert draft.params == {"ids": ["C0028"]}
    verdict = CypherValidator().validate(draft, card, _LIMITS)
    assert verdict.ok, verdict.reasons


def test_campaign_only_lookup_still_routes_to_describe() -> None:
    draft, _ = _draft(("Campaign",), "What is campaign C0027 in ATT&CK?")
    assert draft.template == "describe"


def test_group_only_still_routes_to_group_techniques() -> None:
    draft, _ = _draft(("Group", "Technique"), "Which techniques does group G0016 use?")
    assert draft.template == "group_techniques"


# -- attribution normalization -------------------------------------------------


def test_attribution_rows_group_by_campaign_with_related_groups() -> None:
    card = fixture_card("attack")
    rows = [
        {
            "campaign_id": "C0028",
            "campaign_name": "2015 Ukraine Electric Power Attack",
            "group_id": "G0034",
            "group_name": "Sandworm Team",
        }
    ]
    task = make_task(
        entities=("Campaign", "Group"),
        text="Which group is campaign C0028 attributed to?",
    )
    records = CypherNormalizer().normalize(
        rows, resolve(task, card), "MATCH ...", card
    )
    assert len(records) == 1
    rec = records[0]
    assert rec.primary_id == "C0028"
    assert rec.label == "Campaign"
    assert [g["id"] for g in rec.related] == ["G0034"]


# -- schema-boundary refusal ----------------------------------------------------


def test_unknown_entity_returns_honest_empty_without_touching_db() -> None:
    card = fixture_card("attack")
    connector = StubConnector(rows=[{"id": "x", "attack_id": "T1047", "name": "WMI"}])
    spec = _specialist(card, connector=connector)
    result = spec.run(
        make_task(
            entities=("Technique", "Asset"),
            text="What assets does technique T1047 target?",
        )
    )
    assert result.ok and not result.partial and result.error is None
    assert result.records == []
    assert result.query == ""  # no substitute query was executed
    assert "Asset" in result.summary and "doesn't model" in result.summary
    assert _steps(result) == ["intake", "resolve", "boundary"]
    assert not connector.connected


def test_boundary_trace_names_every_unknown_entity() -> None:
    card = fixture_card("attack")
    spec = _specialist(card)
    result = spec.run(
        make_task(entities=("Asset", "OperationalSegment"), text="ICS-only ask")
    )
    boundary = result.traces[-1]
    assert boundary.step == "boundary" and boundary.ok
    assert boundary.detail["unknown_entities"] == ["Asset", "OperationalSegment"]


def test_known_entities_never_trigger_the_boundary() -> None:
    card = fixture_card("attack")
    connector = StubConnector(rows=[{"id": "x", "attack_id": "T1047", "name": "WMI"}])
    spec = _specialist(card, connector=connector)
    result = spec.run(make_task())  # Technique + Mitigation, both in the card
    assert result.ok
    assert "boundary" not in _steps(result)
    assert connector.connected
