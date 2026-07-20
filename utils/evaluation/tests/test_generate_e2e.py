#!/usr/bin/env python3
"""Serializer tests for the generate-only e2e phase.

The judging artifact must show the judge *the same evidence the narrator saw* —
a record's own scalar properties (Abstraction/Status/…) and its facet adjacency
counts — or a faithful, grounded answer is falsely flagged as a hallucination.
These lock the serializer against regressing back to a description-only view.
"""

from __future__ import annotations

from utils.evaluation.generate_e2e import (
    _MAX_RECORDS_PER_RESULT,
    _bounded_properties,
    _record_dict,
)
from utils.specialists.contracts import EvidenceRecord


def _record(**over) -> EvidenceRecord:
    base = dict(
        primary_id="CAPEC-555",
        id_scheme="capec-id",
        label="AttackPattern",
        name="Remote Services with Stolen Credentials",
        properties={
            "description": "Adversaries use stolen credentials.",
            "Abstraction": "Standard",
            "Status": "Stable",
        },
        related=[{"id": "CAPEC-560", "role": "parent", "name": "Use of Known Credentials"}],
        facets=[{"rel": "ChildOf", "direction": "out", "label": "AttackPattern", "count": 1}],
    )
    base.update(over)
    return EvidenceRecord(**base)


def test_record_dict_keeps_scalar_properties():
    """Abstraction/Status survive — the values C-LKP answers were dinged for."""
    out = _record_dict(_record())
    assert out["properties"]["Abstraction"] == "Standard"
    assert out["properties"]["Status"] == "Stable"
    # description still surfaced at top level for readability
    assert out["description"] == "Adversaries use stolen credentials."


def test_record_dict_keeps_facets():
    """Facet adjacency counts survive — the A-CMP 'fabricated counts' source."""
    out = _record_dict(_record())
    assert out["facets"] == [
        {"rel": "ChildOf", "direction": "out", "neighbour_label": "AttackPattern", "count": 1}
    ]


def test_record_dict_carries_related_role():
    """A related neighbour's role (parent/grandparent) reaches the judge."""
    out = _record_dict(_record())
    assert out["related"][0]["role"] == "parent"
    assert out["related"][0]["id"] == "CAPEC-560"


def test_bounded_properties_drops_noise_with_marker():
    props = _bounded_properties(
        {"description": "d", "Abstraction": "Meta", "external_references": [1, 2, 3]}
    )
    assert props["Abstraction"] == "Meta"
    assert "external_references" not in props
    assert props["_omitted_properties"] == ["external_references"]


def test_bounded_properties_trims_long_list():
    props = _bounded_properties({"tags": list(range(25))})
    assert len(props["tags"]) == 11  # 10 shown + 1 marker
    assert props["tags"][-1].startswith("…(+15 more")


def test_record_cap_matches_narrator():
    """The record cap is lifted to the narrator's 50 so nothing it saw is hidden."""
    assert _MAX_RECORDS_PER_RESULT == 50
