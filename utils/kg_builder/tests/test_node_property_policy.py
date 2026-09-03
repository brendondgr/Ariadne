"""The build must not silently discard facts the source carries.

Until 2026-09-03 `_node_properties` kept a hand-maintained allowlist of ten keys
and dropped the other twenty-odd without trace. It went unnoticed because the
question sets were themselves written from the graph, so nothing could ask for a
property the graph lacked. The census-derived expansion bank reads the raw STIX
snapshot instead and immediately asked 24 questions the build had made
unanswerable -- who contributed a campaign, what else a group is called, when a
campaign ran. The system retrieved the right node every time and still scored
zero, because the fact was never loaded.

These tests pin the inverted policy: keep what is flat, name what is excluded.
"""

from __future__ import annotations

from utils.kg_builder.preprocess.attack import (
    EXCLUDED_PROPERTY_KEYS,
    LEGACY_NODE_PROPERTY_KEYS,
    _node_properties,
)

# Trimmed from the real C0057 object -- the worked example of the defect.
CAMPAIGN = {
    "type": "campaign",
    "id": "campaign--4fd53ccc-c6b1-4e3c-abe8-a456d46d789e",
    "name": "3CX Supply Chain Attack",
    "description": "The 3CX Supply Chain Attack was the first publicly reported case...",
    "aliases": ["3CX Supply Chain Attack"],
    "first_seen": "2022-11-01T06:00:00.000Z",
    "last_seen": "2023-03-01T05:00:00.000Z",
    "x_mitre_contributors": ["Austin Larsen and the Google Threat Intelligence Group"],
    "revoked": False,
    "x_mitre_version": "1.0",
    "external_references": [{"source_name": "mitre-attack", "external_id": "C0057"}],
    # excluded below
    "spec_version": "2.1",
    "created_by_ref": "identity--c78cb6e5-0c4b-4611-8297-d1b8b55e40b5",
    "object_marking_refs": ["marking-definition--fa42a846"],
    "kill_chain_phases": [{"kill_chain_name": "mitre-attack", "phase_name": "impact"}],
    "x_mitre_log_sources": [{"name": "huge", "channel": "x" * 4000}],
}


class TestTheRegression:
    def test_the_property_that_started_this_survives_the_build(self):
        assert _node_properties(CAMPAIGN)["x_mitre_contributors"] == [
            "Austin Larsen and the Google Threat Intelligence Group"
        ]

    def test_so_do_the_others_the_bank_asked_for(self):
        props = _node_properties(CAMPAIGN)
        for key in ("aliases", "first_seen", "last_seen"):
            assert key in props, f"{key} was dropped by the build"


class TestThePolicy:
    def test_every_legacy_key_still_survives(self):
        # The inversion must be a superset: nothing the old allowlist kept may
        # be lost, or answers that used to work would silently stop working.
        props = _node_properties(CAMPAIGN)
        for key in LEGACY_NODE_PROPERTY_KEYS:
            if key in CAMPAIGN:
                assert key in props, f"legacy key {key} lost"

    def test_named_exclusions_are_dropped(self):
        props = _node_properties(CAMPAIGN)
        for key in EXCLUDED_PROPERTY_KEYS:
            assert key not in props

    def test_structural_fields_do_not_become_attributes(self):
        # kill_chain_phases is an edge in this graph; keeping the raw refs on the
        # node too would let the two disagree.
        assert "kill_chain_phases" not in _node_properties(CAMPAIGN)

    def test_bulk_nested_detail_stays_out(self):
        assert "x_mitre_log_sources" not in _node_properties(CAMPAIGN)

    def test_external_references_is_kept_despite_being_nested(self):
        # The id extraction and the citation surface both read it.
        assert "external_references" in _node_properties(CAMPAIGN)

    def test_an_unlisted_nested_field_is_not_kept(self):
        obj = {"name": "x", "something_new": [{"a": 1}]}
        assert "something_new" not in _node_properties(obj)

    def test_an_unlisted_flat_field_is_kept_without_anyone_editing_a_list(self):
        # The point of inverting: a new scalar property in a future ATT&CK
        # release arrives in the graph instead of being silently discarded.
        obj = {"name": "x", "x_mitre_something_new": "value"}
        assert _node_properties(obj)["x_mitre_something_new"] == "value"
