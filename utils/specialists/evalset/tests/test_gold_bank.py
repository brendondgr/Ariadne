#!/usr/bin/env python3
"""Anchor regression tests for the committed gold bank.

The anchors below were independently verified against live capec.mitre.org /
attack.mitre.org during evalset design (2026-07-03, ATT&CK v19 / CAPEC 3.9).
If the materialization script disagrees with a verified anchor, the script is
wrong — not the anchor. Version bumps that move an anchor must update both the
pinned snapshot and this file deliberately.
"""

from __future__ import annotations

import json

import pytest

from utils.specialists.evalset.gold_bank import (
    GOLD_BANK_PATH,
    build_gold_bank,
    load_gold_bank,
)


@pytest.fixture(scope="module")
def gold() -> dict:
    return load_gold_bank()


# -- meta ---------------------------------------------------------------------


def test_meta_pins_snapshot_versions(gold: dict) -> None:
    assert gold["meta"]["attack_version"] == "19.0"
    assert gold["meta"]["capec_version"] == "3.9"
    assert gold["meta"]["checksums"]


# -- CAPEC anchors (verified against capec.mitre.org v3.9) ---------------------


def test_capec_555_attack_mapping(gold: dict) -> None:
    assert gold["capec"]["attack_mappings"]["CAPEC-555"] == [
        "T1021",
        "T1114.002",
        "T1133",
    ]


def test_capec_555_fields_and_cwes(gold: dict) -> None:
    p = gold["capec"]["patterns"]["CAPEC-555"]
    assert p["name"] == "Remote Services with Stolen Credentials"
    assert p["abstraction"] == "Standard"
    assert p["typical_severity"] == "Very High"
    assert gold["capec"]["related_weaknesses"]["CAPEC-555"] == [
        "CWE-262",
        "CWE-263",
        "CWE-294",
        "CWE-308",
        "CWE-309",
        "CWE-521",
        "CWE-522",
    ]


def test_capec_116_is_a_verified_negative(gold: dict) -> None:
    # CAPEC-116 (Excavation) has NO ATT&CK taxonomy mapping — the gold negative.
    assert "CAPEC-116" not in gold["capec"]["attack_mappings"]
    p = gold["capec"]["patterns"]["CAPEC-116"]
    assert p["abstraction"] == "Meta"
    assert p["typical_severity"] == "Medium"


def test_capec_98_hierarchy_and_fields(gold: dict) -> None:
    p = gold["capec"]["patterns"]["CAPEC-98"]
    assert p["name"] == "Phishing"
    assert p["typical_severity"] == "Very High"
    assert p["likelihood_of_attack"] == "High"
    hier = gold["capec"]["hierarchy"]["CAPEC-98"]
    assert hier["ChildOf"] == ["CAPEC-151"]
    # Declared out-edges only; children live in the inverse map.
    assert set(gold["capec"]["children"]["CAPEC-98"]) == {
        "CAPEC-163",
        "CAPEC-164",
        "CAPEC-656",
    }
    assert "CAPEC-89" in hier["CanPrecede"]


def test_capec_564_mapping_inherits_nothing(gold: dict) -> None:
    # Direct declared mappings only — no parent inheritance in the gold.
    assert gold["capec"]["attack_mappings"]["CAPEC-564"] == [
        "T1037",
        "T1543.001",
        "T1543.004",
        "T1547",
    ]
    assert gold["capec"]["hierarchy"]["CAPEC-564"]["ChildOf"] == ["CAPEC-542"]


def test_capec_557_is_excluded_at_load(gold: dict) -> None:
    # CAPEC-557 is Deprecated; under exclude-at-load it is recorded in the
    # deprecated ledger but dropped from the retrievable pattern set.
    assert "CAPEC-557" in gold["capec"]["deprecated"]
    assert "CAPEC-557" not in gold["capec"]["patterns"]


# -- ATT&CK anchors -------------------------------------------------------------


def test_t1021_001_lookup(gold: dict) -> None:
    obj = gold["attack"]["objects"]["T1021.001"]
    assert obj["name"] == "Remote Desktop Protocol"
    assert obj["label"] == "SubTechnique"
    assert obj["stix_type"] == "attack-pattern"
    assert obj["platforms"] == ["Windows"]


def test_t1047_mitigations_match_live_regression(gold: dict) -> None:
    # M1038 is the anchor the existing live test asserts on.
    mits = gold["attack"]["technique_mitigations"]["T1047"]
    assert "M1038" in mits
    assert all(m.startswith("M") for m in mits)


def test_t1003_subtechniques(gold: dict) -> None:
    assert gold["attack"]["subtechniques"]["T1003"] == [
        f"T1003.00{i}" for i in range(1, 9)
    ]


def test_campaign_c0027_present(gold: dict) -> None:
    # Step 7 coverage gap: Campaigns must be in the gold surface.
    assert gold["attack"]["objects"]["C0027"]["label"] == "Campaign"


def test_id_collision_hygiene(gold: dict) -> None:
    # T1055 (technique) and M1055 (mitigation) are distinct objects.
    assert gold["attack"]["objects"]["T1055"]["label"] == "Technique"
    assert gold["attack"]["objects"]["M1055"]["label"] == "Mitigation"


def test_no_excluded_objects_leak(gold: dict) -> None:
    # T1562 (Impair Defenses) was retired in the v19 Defense Evasion split;
    # exclude-at-load means it must not appear as a live object.
    assert "T1562" not in gold["attack"]["objects"]
    # Every tactic-techniques value must be a T-number.
    for t_ids in gold["attack"]["tactic_techniques"].values():
        assert all(t.startswith("T") and not t.startswith("TA") for t in t_ids)


def test_canonical_object_count_matches_fixture_qa(gold: dict) -> None:
    # 4369 is the fixture-qa verified live node count for attack — the gold
    # bank derives the same count independently from the raw bundle.
    assert len(gold["attack"]["objects"]) == 4369


# -- determinism ----------------------------------------------------------------


def test_regeneration_is_deterministic_and_matches_committed(gold: dict) -> None:
    regenerated = build_gold_bank()
    committed = json.loads(GOLD_BANK_PATH.read_text())
    assert regenerated == committed, (
        "gold_bank.json is stale — regenerate with "
        "`uv run python -m utils.specialists.evalset.gold_bank`"
    )
