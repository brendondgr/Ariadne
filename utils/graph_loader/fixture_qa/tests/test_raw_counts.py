#!/usr/bin/env python3
"""Tests for the independent raw recount oracle."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils.graph_loader.fixture_qa.raw_counts import (
    attack_raw_counts,
    capec_raw_counts,
    raw_counts_for,
)
from utils.kg_builder.config import BuildConfig


def _write_attack_bundle(tmp_path: Path) -> BuildConfig:
    raw_dir = tmp_path / "raw" / "attack" / "v19.0"
    raw_dir.mkdir(parents=True)
    bundle = {
        "type": "bundle",
        "id": "bundle--test",
        "objects": [
            # 1 tactic
            {"type": "x-mitre-tactic", "id": "ta1", "x_mitre_shortname": "exec"},
            # 2 live techniques + 1 subtechnique
            {"type": "attack-pattern", "id": "t1"},
            {"type": "attack-pattern", "id": "t2"},
            {"type": "attack-pattern", "id": "t3", "x_mitre_is_subtechnique": True},
            # excluded: revoked + deprecated
            {"type": "attack-pattern", "id": "t-rev", "revoked": True},
            {"type": "attack-pattern", "id": "t-dep", "x_mitre_deprecated": True},
            # 1 group, 1 malware + 1 tool -> Software x2
            {"type": "intrusion-set", "id": "g1"},
            {"type": "malware", "id": "s1"},
            {"type": "tool", "id": "s2"},
            # relationships are not nodes
            {"type": "relationship", "id": "r1", "source_ref": "g1", "target_ref": "t1"},
            # non-mappable object type ignored
            {"type": "marking-definition", "id": "m1"},
        ],
    }
    (raw_dir / "enterprise-attack.json").write_text(json.dumps(bundle), encoding="utf-8")
    return BuildConfig.from_data_dir(tmp_path)


def test_attack_raw_counts_maps_labels_and_excludes(tmp_path: Path) -> None:
    config = _write_attack_bundle(tmp_path)
    counts = attack_raw_counts(config)

    assert counts.dataset == "attack"
    assert counts.nodes_by_label == {
        "Group": 1,
        "Software": 2,
        "SubTechnique": 1,
        "Tactic": 1,
        "Technique": 2,
    }
    assert counts.primary_total == 7
    assert counts.excluded == {"revoked": 1, "deprecated": 1}
    # all attack labels are primary (1:1 with STIX objects)
    assert counts.primary_labels == frozenset(counts.nodes_by_label)


def test_attack_raw_counts_can_disable_filters(tmp_path: Path) -> None:
    config = _write_attack_bundle(tmp_path)
    counts = attack_raw_counts(config, filter_revoked=False, filter_deprecated=False)
    # revoked + deprecated attack-patterns now counted as Technique
    assert counts.nodes_by_label["Technique"] == 4
    assert counts.excluded == {"revoked": 0, "deprecated": 0}


def _write_capec_xml(tmp_path: Path) -> BuildConfig:
    raw_dir = tmp_path / "raw" / "capec" / "v3.9"
    raw_dir.mkdir(parents=True)
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<Attack_Pattern_Catalog xmlns="http://capec.mitre.org/capec-3">
  <Attack_Patterns>
    <Attack_Pattern ID="1" Name="A" Status="Stable"/>
    <Attack_Pattern ID="2" Name="B" Status="Draft"/>
    <Attack_Pattern ID="3" Name="C" Status="Deprecated"/>
    <Attack_Pattern ID="4" Name="D" Status="Obsolete"/>
  </Attack_Patterns>
  <Categories>
    <Category ID="100" Name="Cat"/>
  </Categories>
  <Views>
    <View ID="1000" Name="V"/>
    <View ID="1001" Name="V2"/>
  </Views>
</Attack_Pattern_Catalog>
"""
    (raw_dir / "capec_latest.xml").write_text(xml, encoding="utf-8")
    return BuildConfig.from_data_dir(tmp_path)


def test_capec_raw_counts_primary_entities(tmp_path: Path) -> None:
    config = _write_capec_xml(tmp_path)
    counts = capec_raw_counts(config)

    assert counts.dataset == "capec"
    assert counts.nodes_by_label == {"AttackPattern": 4, "Category": 1, "View": 2}
    assert counts.primary_labels == frozenset({"AttackPattern", "Category", "View"})
    assert counts.excluded == {}  # full catalog, nothing excluded
    # retired count surfaced in notes (Deprecated=1, Obsolete=1)
    assert any("Deprecated=1" in n and "Obsolete=1" in n for n in counts.notes)


def test_raw_counts_for_dispatch_and_missing(tmp_path: Path) -> None:
    config = _write_attack_bundle(tmp_path)
    assert raw_counts_for("attack", config).dataset == "attack"
    with pytest.raises(ValueError):
        raw_counts_for("unknown", config)


def test_attack_missing_raw_file_raises(tmp_path: Path) -> None:
    config = BuildConfig.from_data_dir(tmp_path)
    with pytest.raises(FileNotFoundError):
        attack_raw_counts(config)
