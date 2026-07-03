#!/usr/bin/env python3
"""Unit tests for CAPEC -> ATT&CK composite-key resolution."""

from __future__ import annotations

import json
from pathlib import Path

from utils.graph_loader.fixture_qa.cross_db import (
    build_resolution_summary,
    cross_db_resolution_checks,
)


def _write_jsonl(path: Path, records: list[dict]) -> Path:
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return path


def _fixture_graphs(tmp_path: Path):
    capec_nodes = _write_jsonl(tmp_path / "capec_nodes.jsonl", [
        {"id": "capec:attack-pattern:555", "label": "AttackPattern", "properties": {}},
        {"id": "capec:taxonomy:ATTACK:1021", "label": "TaxonomyEntry",
         "properties": {"taxonomy_name": "ATTACK", "entry_id": "1021"}},
        {"id": "capec:taxonomy:ATTACK:1114.002", "label": "TaxonomyEntry",
         "properties": {"taxonomy_name": "ATTACK", "entry_id": "1114.002"}},
        {"id": "capec:taxonomy:ATTACK:1133", "label": "TaxonomyEntry",
         "properties": {"taxonomy_name": "ATTACK", "entry_id": "1133"}},
        {"id": "capec:taxonomy:ATTACK:9999", "label": "TaxonomyEntry",
         "properties": {"taxonomy_name": "ATTACK", "entry_id": "9999"}},
        # A non-ATTACK taxonomy entry must be ignored entirely.
        {"id": "capec:taxonomy:WASC:01", "label": "TaxonomyEntry",
         "properties": {"taxonomy_name": "WASC", "entry_id": "01"}},
    ])
    capec_rels = _write_jsonl(tmp_path / "capec_rels.jsonl", [
        {"id": "m1", "type": "MAPS_TO", "source_id": "capec:attack-pattern:555",
         "target_id": "capec:taxonomy:ATTACK:1021"},
        {"id": "m2", "type": "MAPS_TO", "source_id": "capec:attack-pattern:555",
         "target_id": "capec:taxonomy:ATTACK:1114.002"},
        {"id": "m3", "type": "MAPS_TO", "source_id": "capec:attack-pattern:555",
         "target_id": "capec:taxonomy:ATTACK:1133"},
        {"id": "m4", "type": "MAPS_TO", "source_id": "capec:attack-pattern:555",
         "target_id": "capec:taxonomy:WASC:01"},
        {"id": "m5", "type": "MAPS_TO", "source_id": "capec:attack-pattern:555",
         "target_id": "capec:taxonomy:ATTACK:9999"},
    ])
    attack_nodes = _write_jsonl(tmp_path / "attack_nodes.jsonl", [
        {"id": "ap-1", "label": "Technique",
         "properties": {"attack_id": "T1021", "stix_type": "attack-pattern"}},
        {"id": "ap-2", "label": "SubTechnique",
         "properties": {"attack_id": "T1114.002", "stix_type": "attack-pattern"}},
        {"id": "ap-3", "label": "Technique",
         "properties": {"attack_id": "T1133", "stix_type": "attack-pattern"}},
        # Same digits, wrong type: must NOT resolve T9999.
        {"id": "coa-1", "label": "Mitigation",
         "properties": {"attack_id": "T9999", "stix_type": "course-of-action"}},
    ])
    return capec_nodes, capec_rels, attack_nodes


def test_resolution_requires_the_composite_pair(tmp_path: Path) -> None:
    capec_nodes, capec_rels, attack_nodes = _fixture_graphs(tmp_path)
    summary = build_resolution_summary(capec_nodes, capec_rels, attack_nodes)
    assert summary["capec_555"] == ["T1021", "T1114.002", "T1133", "T9999"]
    # T9999 exists only as a course-of-action -> unresolved despite same digits.
    assert summary["unresolved"] == ["T9999"]
    assert summary["resolved"] == 3
    assert summary["unique_technique_ids"] == 4


def test_checks_pass_against_matching_baseline_and_flag_drift(tmp_path: Path) -> None:
    capec_nodes, capec_rels, attack_nodes = _fixture_graphs(tmp_path)
    expected_dir = tmp_path / "expected"
    expected_dir.mkdir()

    summary = build_resolution_summary(capec_nodes, capec_rels, attack_nodes)
    (expected_dir / "capec_attack_resolution.json").write_text(json.dumps(summary))
    checks, _ = cross_db_resolution_checks(
        capec_nodes, capec_rels, attack_nodes, expected_dir
    )
    by_name = {c.name: c for c in checks}
    assert by_name["capec_attack_resolution_baseline"].passed
    # CAPEC-555 here maps to an extra T9999 -> named regression must fail.
    assert not by_name["capec_555_maps_to_expected_techniques"].passed

    # Baseline drift: pretend the fixture expected full resolution.
    drifted = dict(summary, unresolved=[], resolved=4, resolution_rate=1.0)
    (expected_dir / "capec_attack_resolution.json").write_text(json.dumps(drifted))
    checks, _ = cross_db_resolution_checks(
        capec_nodes, capec_rels, attack_nodes, expected_dir
    )
    by_name = {c.name: c for c in checks}
    assert not by_name["capec_attack_resolution_baseline"].passed
