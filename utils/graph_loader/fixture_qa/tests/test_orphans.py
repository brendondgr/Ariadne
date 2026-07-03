#!/usr/bin/env python3
"""Unit tests for orphan scanning, allow-list matching, and hierarchy checks."""

from __future__ import annotations

import json
from pathlib import Path

from utils.graph_loader.fixture_qa.orphans import (
    capec_hierarchy_checks,
    live_orphan_check,
    orphan_checks,
    scan_canonical_orphans,
)


def _write_jsonl(path: Path, records: list[dict]) -> Path:
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return path


def _write_expected(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_scan_splits_dead_and_live(tmp_path: Path) -> None:
    nodes = _write_jsonl(tmp_path / "nodes.jsonl", [
        {"id": "a", "label": "Technique", "properties": {}},
        {"id": "b", "label": "Technique", "properties": {}},
        {"id": "dead", "label": "Mitigation", "properties": {"x_mitre_deprecated": True}},
        {"id": "island", "label": "DataComponent", "properties": {}, "name": "Island"},
    ])
    rels = _write_jsonl(tmp_path / "rels.jsonl", [
        {"id": "e1", "type": "USES", "source_id": "a", "target_id": "b"},
    ])
    scan = scan_canonical_orphans("attack", nodes, rels)
    assert scan["orphan_ids"] == ["dead", "island"]
    assert scan["dead_by_label"] == {"Mitigation": 1}
    assert set(scan["live_orphans"]) == {"island"}


def test_orphan_checks_allowlist_exact_match(tmp_path: Path) -> None:
    nodes = _write_jsonl(tmp_path / "nodes.jsonl", [
        {"id": "a", "label": "Technique", "properties": {}},
        {"id": "island", "label": "DataComponent", "properties": {}},
    ])
    rels = _write_jsonl(tmp_path / "rels.jsonl", [])
    expected_dir = tmp_path / "expected"
    expected_dir.mkdir()

    # a) declared -> passes (both a and island declared; nothing dead)
    _write_expected(expected_dir / "attack_orphans.json", {
        "policy": "exclude-at-load",
        "expected_dead_orphans": {},
        "allowed_orphan_label_counts": {},
        "allowed_live_orphans": {"a": {"label": "Technique"}, "island": {"label": "DataComponent"}},
    })
    checks, _ = orphan_checks("attack", nodes, rels, expected_dir)
    by_name = {c.name: c for c in checks}
    assert by_name["bug_orphans_zero_or_declared"].passed
    assert by_name["dead_orphans_match_policy"].passed

    # b) undeclared orphan -> fails
    _write_expected(expected_dir / "attack_orphans.json", {
        "policy": "exclude-at-load",
        "expected_dead_orphans": {},
        "allowed_orphan_label_counts": {},
        "allowed_live_orphans": {"a": {"label": "Technique"}},
    })
    checks, _ = orphan_checks("attack", nodes, rels, expected_dir)
    by_name = {c.name: c for c in checks}
    assert not by_name["bug_orphans_zero_or_declared"].passed
    assert "island" in by_name["bug_orphans_zero_or_declared"].detail

    # c) stale allow-list entry -> fails (exact-match, not subset)
    _write_expected(expected_dir / "attack_orphans.json", {
        "policy": "exclude-at-load",
        "expected_dead_orphans": {},
        "allowed_orphan_label_counts": {},
        "allowed_live_orphans": {
            "a": {"label": "Technique"},
            "island": {"label": "DataComponent"},
            "fixed-long-ago": {"label": "Matrix"},
        },
    })
    checks, _ = orphan_checks("attack", nodes, rels, expected_dir)
    by_name = {c.name: c for c in checks}
    assert not by_name["bug_orphans_zero_or_declared"].passed
    assert "stale" in by_name["bug_orphans_zero_or_declared"].detail


def test_capec_dead_orphans_and_label_counts(tmp_path: Path) -> None:
    nodes = _write_jsonl(tmp_path / "nodes.jsonl", [
        {"id": "dep", "label": "AttackPattern", "properties": {"Status": "Deprecated"}},
        {"id": "ref1", "label": "ExternalReference", "properties": {}},
        {"id": "ref2", "label": "ExternalReference", "properties": {}},
    ])
    rels = _write_jsonl(tmp_path / "rels.jsonl", [])
    expected_dir = tmp_path / "expected"
    expected_dir.mkdir()
    _write_expected(expected_dir / "capec_orphans.json", {
        "policy": "load-and-tag",
        "expected_dead_orphans": {"AttackPattern": 1},
        "allowed_orphan_label_counts": {"ExternalReference": 2},
        "allowed_live_orphans": {},
    })
    checks, _ = orphan_checks("capec", nodes, rels, expected_dir)
    assert all(c.passed for c in checks), [(c.name, c.detail) for c in checks]

    # Label-count drift fails.
    _write_expected(expected_dir / "capec_orphans.json", {
        "policy": "load-and-tag",
        "expected_dead_orphans": {"AttackPattern": 1},
        "allowed_orphan_label_counts": {"ExternalReference": 1},
        "allowed_live_orphans": {},
    })
    checks, _ = orphan_checks("capec", nodes, rels, expected_dir)
    by_name = {c.name: c for c in checks}
    assert not by_name["bug_orphans_zero_or_declared"].passed


def test_capec_hierarchy_cycle_detection(tmp_path: Path) -> None:
    nodes = _write_jsonl(tmp_path / "nodes.jsonl", [
        {"id": "p1", "label": "AttackPattern", "properties": {}},
        {"id": "p2", "label": "AttackPattern", "properties": {}},
        {"id": "cat", "label": "Category", "properties": {}},
    ])
    rels = _write_jsonl(tmp_path / "rels.jsonl", [
        {"id": "e1", "type": "ChildOf", "source_id": "p1", "target_id": "p2"},
        {"id": "e2", "type": "ChildOf", "source_id": "p2", "target_id": "p1"},
        {"id": "e3", "type": "ChildOf", "source_id": "p1", "target_id": "cat"},
    ])
    checks = capec_hierarchy_checks(nodes, rels)
    by_name = {c.name: c for c in checks}
    assert not by_name["childof_endpoints_are_attack_patterns"].passed
    assert not by_name["childof_hierarchy_acyclic"].passed

    rels_ok = _write_jsonl(tmp_path / "rels_ok.jsonl", [
        {"id": "e1", "type": "ChildOf", "source_id": "p1", "target_id": "p2"},
    ])
    checks = capec_hierarchy_checks(nodes, rels_ok)
    assert all(c.passed for c in checks)


def test_live_orphan_check_exact_set() -> None:
    ok = live_orphan_check("neo4j", ["a", "b"], ["b", "a"])
    assert ok.passed
    drift = live_orphan_check("neo4j", ["a", "c"], ["a", "b"])
    assert not drift.passed
    assert "live-only" in drift.detail and "canonical-only" in drift.detail
