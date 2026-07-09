#!/usr/bin/env python3
"""Tests for id scanning + canonicalisation (hermetic)."""

from __future__ import annotations

from utils.evaluation.harness.ids import canonical, canonical_set, scan_ids


def test_scan_ids_pulls_prose_mentions_in_order():
    text = "Found 4 item(s) related to T1047 (e.g. M1038, M1040, M1018) in ATT&CK."
    assert scan_ids(text) == ["T1047", "M1038", "M1040", "M1018"]


def test_scan_ids_handles_capec_cwe_and_subtechniques():
    text = "CAPEC-98 and capec 150 map to T1021.001; see CWE-200."
    assert scan_ids(text) == ["CAPEC-98", "CAPEC-150", "T1021.001", "CWE-200"]


def test_scan_ids_disambiguates_tactic_from_technique():
    assert scan_ids("Tactic TA0006 covers T1003") == ["TA0006", "T1003"]


def test_scan_ids_dedupes_and_empty():
    assert scan_ids("T1047 T1047 M1018") == ["T1047", "M1018"]
    assert scan_ids("") == []
    assert scan_ids(None) == []  # type: ignore[arg-type]


def test_canonical_normalises_capec_spacing():
    assert canonical("capec 98") == "CAPEC-98"
    assert canonical("CAPEC-98") == "CAPEC-98"
    assert canonical(" t1047 ") == "T1047"


def test_canonical_set():
    assert canonical_set(["t1047", "M1018", ""]) == {"T1047", "M1018"}
