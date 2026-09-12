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


def test_a_neighbour_whose_content_is_not_a_description_still_reaches_the_judge():
    """I-15. The content keys were an allow-list, and it named only `description`.

    That is right for a mitigation and wrong for every CAPEC node whose prose
    lives elsewhere: a Consequence carries `scopes` and `impacts` and nothing
    else, an ExecutionStep its `phase`. The composer renders a neighbour from
    every non-identity key it carries, so the answer said "CAPEC-295 has 1
    consequence: Other Confidentiality" over evidence that reached the judge as
    nothing but `capec:attack-pattern:295:consequence:1` — and the judge flagged
    the text as unsupported, correctly, because from where it sat the claim had
    no warrant. Identity keys are named; everything else is content.
    """
    out = _record_dict(_record(related=[
        {"id": "capec:attack-pattern:295:consequence:1",
         "name": "capec:attack-pattern:295:consequence:1",
         "label": "Consequence", "type": "HAS_CONSEQUENCE",
         "scopes": ["Confidentiality"], "impacts": ["Other"]},
        {"id": "capec:attack-pattern:568:step:1", "label": "ExecutionStep",
         "step": "1", "phase": "Explore",
         "description": "Determine which user's credentials to capture."},
    ]))
    consequence, step = out["related"]
    assert consequence["scopes"] == ["Confidentiality"]
    assert consequence["impacts"] == ["Other"]
    # Identity keys keep their place, and the step's own position still leads.
    assert consequence["type"] == "HAS_CONSEQUENCE"
    assert step["step"] == "1" and step["phase"] == "Explore"
    assert step["description"].startswith("Determine which user")


def test_related_content_is_bounded_like_every_other_property():
    """Inverting the rule must not let one neighbour flood the judge's prompt."""
    out = _record_dict(_record(related=[
        {"id": "x:1", "label": "Consequence", "scopes": [str(i) for i in range(50)],
         "impacts": "z" * 5000},
    ]))
    entry = out["related"][0]
    assert len(entry["scopes"]) <= 11 and "more)" in entry["scopes"][-1]
    assert len(entry["impacts"]) < 5000
