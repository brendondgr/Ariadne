#!/usr/bin/env python3
"""Anchor tests for the federated credential-theft gold (Wk 10–11).

Pins the census the pinned snapshot yields under the committed anchor-term
rule, spot-checks externally verifiable pairs, and enforces the regeneration
discipline (committed JSON == freshly derived).
"""

from __future__ import annotations

import json

from utils.specialists.evalset.federated_gold import (
    ANCHOR_TERMS,
    FEDERATED_GOLD_PATH,
    build_federated_gold,
    load_federated_gold,
)


def test_census_pinned_to_snapshot() -> None:
    gold = build_federated_gold()
    assert len(gold["selected_patterns"]) == 21
    assert len(gold["capec_to_techniques"]) == 14
    assert len(gold["technique_ids"]) == 18
    # Every mapped T-ID exists on the ATT&CK side of the pinned snapshot.
    assert gold["expected_correlation"] == gold["technique_ids"]
    with_mitigations = [t for t, m in gold["technique_mitigations"].items() if m]
    without = [t for t, m in gold["technique_mitigations"].items() if not m]
    assert len(with_mitigations) == 16
    # Input Capture (and its keylogging sub-technique) carry no MITIGATES
    # edges in v19 — an honest empty the grading must not treat as a drop.
    assert sorted(without) == ["T1056", "T1056.001"]


def test_externally_verifiable_anchors() -> None:
    gold = build_federated_gold()
    # Web-verifiable CAPEC->ATT&CK pairs (CAPEC 3.9 taxonomy mappings).
    assert gold["capec_to_techniques"]["CAPEC-600"] == ["T1110.004"]  # Credential Stuffing
    assert gold["capec_to_techniques"]["CAPEC-565"] == ["T1110.003"]  # Password Spraying
    assert gold["capec_to_techniques"]["CAPEC-49"] == ["T1110.001"]  # Password Brute Forcing
    # Brute-force sub-techniques are mitigated in v19 (account policies et al.).
    assert gold["technique_mitigations"]["T1110.001"], "T1110.001 must carry mitigations"


def test_selection_rule_is_the_committed_one() -> None:
    gold = build_federated_gold()
    assert gold["anchor_terms"] == list(ANCHOR_TERMS)
    for cid, name in gold["selected_patterns"].items():
        assert any(t in name.lower() for t in ANCHOR_TERMS), (cid, name)


def test_regeneration_matches_committed_artifact() -> None:
    committed = load_federated_gold()
    assert committed == build_federated_gold(), (
        f"{FEDERATED_GOLD_PATH} is stale — regenerate with "
        "`uv run python -m utils.specialists.evalset.federated_gold`"
    )
    # And the committed file is canonical JSON as the generator writes it.
    assert FEDERATED_GOLD_PATH.read_text() == json.dumps(committed, indent=2) + "\n"
