#!/usr/bin/env python3

from __future__ import annotations

import pytest

from utils.graph_loader.validation import validate_semantic_graph
from utils.graph_loader.validation.semantic import SemanticValidationError, require_semantic_validation


def _node(node_id: str, label: str, attack_id: str | None = None) -> dict:
    props = {"stix_type": "x-mitre-" + label.lower()}
    if attack_id:
        props["attack_id"] = attack_id
    return {
        "id": node_id,
        "label": label,
        "labels": [label, "AttackObject", "STIXObject"],
        "properties": props,
    }


def test_valid_attack_patterns_pass() -> None:
    nodes = [
        _node("g1", "Group", "G0001"),
        _node("t1", "Technique", "T1000"),
        _node("m1", "Mitigation", "M1000"),
        _node("ta1", "Tactic", "TA0001"),
        _node("s1", "SubTechnique", "T1000.001"),
        _node("tech1", "Technique", "T1001"),
    ]
    edges = [
        {"id": "e1", "type": "USES", "source_id": "g1", "target_id": "t1"},
        {"id": "e2", "type": "MITIGATES", "source_id": "m1", "target_id": "t1"},
        {"id": "e3", "type": "HAS_TECHNIQUE", "source_id": "ta1", "target_id": "t1"},
        {"id": "e4", "type": "HAS_SUBTECHNIQUE", "source_id": "tech1", "target_id": "s1"},
    ]
    result = validate_semantic_graph(nodes, edges)
    assert result.valid, result.errors


def test_valid_capec_patterns_pass() -> None:
    nodes = [
        {
            "id": "capec:attack-pattern:1",
            "label": "AttackPattern",
            "labels": ["AttackPattern", "CapecObject"],
            "name": "Pattern 1",
            "properties": {"id": "1"},
        },
        {
            "id": "capec:attack-pattern:2",
            "label": "AttackPattern",
            "labels": ["AttackPattern", "CapecObject"],
            "name": "Pattern 2",
            "properties": {"id": "2"},
        },
    ]
    edges = [
        {
            "id": "e1",
            "type": "ChildOf",
            "source_id": "capec:attack-pattern:1",
            "target_id": "capec:attack-pattern:2",
        }
    ]
    schema = {"dataset": "capec"}
    result = validate_semantic_graph(nodes, edges, schema=schema)
    assert result.valid, result.errors


def test_illegal_edge_pattern_fails() -> None:
    nodes = [_node("t1", "Technique", "T1000"), _node("m1", "Mitigation", "M1000")]
    edges = [{"id": "e1", "type": "USES", "source_id": "t1", "target_id": "m1"}]
    result = validate_semantic_graph(nodes, edges)
    assert not result.valid
    assert any("Illegal edge pattern" in err for err in result.errors)


def test_missing_attack_id_fails() -> None:
    nodes = [{"id": "t1", "label": "Technique", "labels": ["Technique"], "properties": {}}]
    result = validate_semantic_graph(nodes, [])
    assert not result.valid
    assert any("attack_id" in err for err in result.errors)


def test_unknown_label_fails() -> None:
    nodes = [{"id": "x1", "label": "Alien", "labels": ["Alien"], "properties": {"id": "x1"}}]
    result = validate_semantic_graph(nodes, [])
    assert not result.valid


def test_dangling_reference_fails() -> None:
    nodes = [_node("g1", "Group", "G0001")]
    edges = [{"id": "e1", "type": "USES", "source_id": "g1", "target_id": "missing"}]
    result = validate_semantic_graph(nodes, edges)
    assert not result.valid


def test_require_semantic_validation_raises() -> None:
    nodes = [{"id": "x1", "label": "Alien", "labels": ["Alien"], "properties": {"id": "x1"}}]
    result = validate_semantic_graph(nodes, [])
    with pytest.raises(SemanticValidationError):
        require_semantic_validation(result)


@pytest.mark.skipif(
    __import__("pathlib").Path("data/graphs/attack/canonical/nodes.jsonl").exists() is False,
    reason="ATT&CK artifacts not built",
)
def test_real_attack_artifacts_pass_semantic_validation() -> None:
    from pathlib import Path

    from utils.graph_loader.validation import validate_semantic_artifacts

    result = validate_semantic_artifacts(
        Path("data/graphs/attack/canonical/nodes.jsonl"),
        Path("data/graphs/attack/canonical/relationships.jsonl"),
        Path("data/graphs/attack/canonical/schema.json"),
    )
    assert result.valid, result.errors[:3]
