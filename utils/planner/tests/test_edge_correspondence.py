#!/usr/bin/env python3
"""The declared identity-to-ATT&CK bridge, and the guards that keep it honest.

The bridge is authored knowledge, so the tests it needs are different in kind
from the tests a derived artifact needs. There is no ground truth here to check
the mapping *against* — if there were, the mapping would not have to be
authored. What can be checked, and is:

* that the declaration is **complete** with respect to the schema, so a new edge
  type cannot arrive unclassified and be silently treated as carrying no
  technique;
* that it is **unambiguous**, so no edge is both mapped and disclaimed;
* that every technique it names **exists in ATT&CK**, so a typo is a test
  failure rather than a query that quietly returns nothing;
* and that the partial/whole distinction the customer's own catalog draws is
  preserved rather than flattened.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from utils.planner.edge_correspondence import (
    IDENTITY_ATTACK_CORRESPONDENCE,
    NOT_A_TECHNIQUE,
    correspondence_for,
    declared_edges,
    mapped_edges,
    technique_ids_for,
)

REPO = Path(__file__).resolve().parents[3]
_IDENTITY_CARD = REPO / "data-identity" / "source_cards" / "identity.json"
requires_identity_card = pytest.mark.skipif(
    not _IDENTITY_CARD.is_file(), reason="identity source card not built"
)


def _card_edges() -> set[str]:
    return set(json.loads(_IDENTITY_CARD.read_text())["relationship_types"])


# -- completeness ------------------------------------------------------------


@requires_identity_card
def test_every_schema_edge_is_classified() -> None:
    """No edge may be left with no opinion recorded about it.

    Absence from both tables is indistinguishable, at the call site, from "this
    edge carries no technique" -- which is a claim, and one nobody made. This
    test is what turns that silence into a failure.
    """
    missing = _card_edges() - declared_edges()
    assert not missing, f"edge types with no declared opinion: {sorted(missing)}"


@requires_identity_card
def test_the_declaration_invents_no_edges() -> None:
    """Nothing may be declared for an edge the schema does not have."""
    invented = declared_edges() - _card_edges()
    assert not invented, f"declared for edges absent from the card: {sorted(invented)}"


def test_no_edge_is_both_mapped_and_disclaimed() -> None:
    overlap = mapped_edges() & set(NOT_A_TECHNIQUE)
    assert not overlap, f"both mapped and disclaimed: {sorted(overlap)}"


def test_every_disclaimer_states_a_reason() -> None:
    for edge, reason in NOT_A_TECHNIQUE.items():
        assert len(reason.strip()) > 20, f"{edge} is disclaimed without a reason"


def test_every_mapping_cites_its_basis() -> None:
    for entry in IDENTITY_ATTACK_CORRESPONDENCE:
        assert entry.technique_ids, f"{entry.edge} maps to nothing"
        assert "catalog:" in entry.basis, (
            f"{entry.edge} does not cite the customer's own description; the "
            "mapping must be grounded in their statement of what the edge "
            "means, not in an assumption about their schema"
        )


# -- shape -------------------------------------------------------------------


def test_technique_ids_are_well_formed() -> None:
    import re

    shape = re.compile(r"^T\d{4}(\.\d{3})?$")
    for entry in IDENTITY_ATTACK_CORRESPONDENCE:
        for tid in entry.technique_ids:
            assert shape.match(tid), f"{entry.edge} -> {tid!r} is not a technique id"


def test_dcsync_halves_are_marked_partial() -> None:
    """The catalog says GET_CHANGES alone is insufficient; so must we.

    Reporting a half-right as the technique outright would assert something the
    customer's own description denies.
    """
    for edge in ("GET_CHANGES", "GET_CHANGES_ALL", "GET_CHANGES_IN_FILTERED_SET"):
        entry = correspondence_for(edge)
        assert entry is not None and entry.partial, f"{edge} must be marked partial"
    whole = correspondence_for("DC_SYNC")
    assert whole is not None and not whole.partial


def test_structural_edges_carry_no_technique() -> None:
    """Membership and trust are how directories work, not what adversaries do."""
    for edge in ("MEMBER_OF", "RUNS_AS", "TRUSTED_BY", "GP_LINK"):
        assert technique_ids_for(edge) == ()


# -- lookup ------------------------------------------------------------------


def test_lookup_is_case_insensitive_and_deduplicates() -> None:
    assert technique_ids_for("dc_sync") == ("T1003.006",)
    # WRITE_DACL and OWNS share T1222.001 and T1098; each appears once.
    both = technique_ids_for(["WRITE_DACL", "OWNS"])
    assert both == ("T1222.001", "T1098")
    assert technique_ids_for("NO_SUCH_EDGE") == ()
    assert technique_ids_for(None) == ()


# -- the ids exist -----------------------------------------------------------


def _attack_live() -> bool:
    try:
        from neo4j import GraphDatabase
    except Exception:
        return False
    uri = os.environ.get("ARIADNE_ENDPOINT_ATTACK") or "bolt://localhost:5456"
    try:
        driver = GraphDatabase.driver(
            uri,
            auth=(os.environ.get("NEO4J_USER", "neo4j"),
                  os.environ.get("NEO4J_PASSWORD", "")),
        )
        with driver.session() as session:
            session.run("RETURN 1").single()
        driver.close()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _attack_live(), reason="ATT&CK store not reachable")
def test_every_declared_technique_exists_in_attack() -> None:
    """A typo here is a query that silently returns nothing. Make it a failure."""
    from neo4j import GraphDatabase

    uri = os.environ.get("ARIADNE_ENDPOINT_ATTACK") or "bolt://localhost:5456"
    driver = GraphDatabase.driver(
        uri,
        auth=(os.environ.get("NEO4J_USER", "neo4j"),
              os.environ.get("NEO4J_PASSWORD", "")),
    )
    wanted = sorted({t for e in IDENTITY_ATTACK_CORRESPONDENCE for t in e.technique_ids})
    with driver.session() as session:
        rows = session.run(
            "MATCH (n) WHERE n.attack_id IN $ids RETURN collect(n.attack_id) AS found",
            ids=wanted,
        ).single()
    driver.close()
    found = set(rows["found"] or [])
    assert not (set(wanted) - found), f"declared but absent from ATT&CK: {sorted(set(wanted) - found)}"
