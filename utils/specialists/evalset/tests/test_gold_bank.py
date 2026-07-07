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


def test_campaign_census_matches_v19(gold: dict) -> None:
    # Enterprise ATT&CK v19 carries exactly 56 live Campaign objects —
    # confirmed against both the raw bundle and the loaded graph.
    campaigns = [
        aid for aid, obj in gold["attack"]["objects"].items() if obj["label"] == "Campaign"
    ]
    assert len(campaigns) == 56
    # 55 of them declare `uses` edges to attack-patterns; 25 are attributed.
    assert len(gold["attack"]["campaign_techniques"]) == 55
    assert len(gold["attack"]["campaign_attribution"]) == 25


def test_campaign_attribution_anchors(gold: dict) -> None:
    # Verified against attack.mitre.org (v19): C0027 (Triton SIS Attack)
    # is attributed to G1015; C0028 to G0034 (Sandworm Team).
    attribution = gold["attack"]["campaign_attribution"]
    assert attribution["C0027"] == ["G1015"]
    assert attribution["C0028"] == ["G0034"]


def test_campaign_techniques_are_technique_ids(gold: dict) -> None:
    for cid, t_ids in gold["attack"]["campaign_techniques"].items():
        assert cid.startswith("C"), cid
        assert t_ids, f"{cid} maps to no techniques"
        assert all(t.startswith("T") and not t.startswith("TA") for t in t_ids), cid


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


# -- Step 10 maps: detection remodel, software, tactics, exclusions --------------


def test_technique_tactics_anchors(gold: dict) -> None:
    # Kill-chain-phase derivation, inverse of tactic_techniques: WMI is
    # Execution-only, Phishing is Initial Access, Brute Force is Credential
    # Access (verified against attack.mitre.org v19).
    tt = gold["attack"]["technique_tactics"]
    assert tt["T1047"] == ["TA0002"]
    assert tt["T1566"] == ["TA0001"]
    assert tt["T1110"] == ["TA0006"]
    # Consistency: every technique->tactic pair mirrors tactic->technique.
    for t_id, ta_ids in tt.items():
        for ta in ta_ids:
            assert t_id in gold["attack"]["tactic_techniques"][ta]


def test_software_techniques_anchors(gold: dict) -> None:
    st = gold["attack"]["software_techniques"]
    # S0002 (Mimikatz) uses the OS Credential Dumping sub-techniques.
    assert "T1003.001" in st["S0002"]
    assert "T1003.002" in st["S0002"]
    # Every key is a software id, every value a technique id.
    for sid, t_ids in st.items():
        assert sid.startswith("S"), sid
        assert all(t.startswith("T") and not t.startswith("TA") for t in t_ids), sid


def test_detection_chain_anchors(gold: dict) -> None:
    # v19 detection remodel: T1047 is detected by strategy DET0364, whose
    # analytics include AN1031 (derived from detects + x_mitre_analytic_refs).
    assert gold["attack"]["technique_detections"]["T1047"] == ["DET0364"]
    assert "AN1031" in gold["attack"]["detection_analytics"]["DET0364"]
    # Every strategy in the technique map carries at least one analytic.
    for det_ids in gold["attack"]["technique_detections"].values():
        for det in det_ids:
            assert gold["attack"]["detection_analytics"].get(det), det


def test_datacomponent_analytics_census(gold: dict) -> None:
    dca = gold["attack"]["datacomponent_analytics"]
    # 98 of the 106 live data components are monitored by >=1 analytic.
    assert len(dca) == 98
    for dc_id, an_ids in dca.items():
        assert dc_id.startswith("DC"), dc_id
        assert all(an.startswith("AN") for an in an_ids), dc_id


def test_excluded_ids_are_honest_negatives(gold: dict) -> None:
    exc = gold["attack"]["excluded_ids"]
    # T1002 (Data Compressed) and T1004 (Winlogon Helper DLL) were retired.
    assert "T1002" in exc
    assert "T1004" in exc
    # No excluded id may still be carried by a live object (legacy
    # course-of-action objects reused technique T-numbers).
    assert not set(exc) & set(gold["attack"]["objects"])


# -- Step 10 CAPEC maps: execution flow, skills, consequences, CWE bridge --------


def test_capec_66_execution_flow(gold: dict) -> None:
    # CAPEC-66 (SQL Injection): 4 steps — Explore, Experiment x2, Exploit.
    steps = gold["capec"]["execution_steps"]["CAPEC-66"]
    assert [(s["step"], s["phase"]) for s in steps] == [
        ("1", "Explore"),
        ("2", "Experiment"),
        ("3", "Experiment"),
        ("4", "Exploit"),
    ]
    assert steps[0]["node_id"] == "capec:attack-pattern:66:step:1"


def test_capec_98_skills_and_consequences(gold: dict) -> None:
    assert gold["capec"]["skills"]["CAPEC-98"] == [
        {"level": "Medium", "node_id": "capec:attack-pattern:98:skill:1"}
    ]
    cons = gold["capec"]["consequences"]["CAPEC-66"]
    assert len(cons) == 4
    assert cons[0]["node_id"] == "capec:attack-pattern:66:consequence:1"
    assert cons[0]["scopes"] == ["Integrity"]


def test_cwe_to_capec_bridge(gold: dict) -> None:
    # CWE-89 (SQL Injection) bridges to CAPEC-66 among others; the inverse map
    # must agree with the declared related_weaknesses.
    assert "CAPEC-66" in gold["capec"]["cwe_to_capec"]["CWE-89"]
    for cwe, cids in gold["capec"]["cwe_to_capec"].items():
        for cid in cids:
            assert cwe in gold["capec"]["related_weaknesses"][cid]
    # No retired pattern may appear in the bridge.
    deprecated = set(gold["capec"]["deprecated"])
    for cids in gold["capec"]["cwe_to_capec"].values():
        assert not deprecated & set(cids)


# -- determinism ----------------------------------------------------------------


def test_regeneration_is_deterministic_and_matches_committed(gold: dict) -> None:
    regenerated = build_gold_bank()
    committed = json.loads(GOLD_BANK_PATH.read_text())
    assert regenerated == committed, (
        "gold_bank.json is stale — regenerate with "
        "`uv run python -m utils.specialists.evalset.gold_bank`"
    )
