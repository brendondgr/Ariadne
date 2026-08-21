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


# -- the merged graph (C-015) ------------------------------------------------
#
# `merged` fell through to the ATT&CK arm of the ruleset selector before
# 2026-08-20, so every CAPEC edge in the merged dataset read as an illegal
# pattern. The data was correct; the rule set was the wrong one. These pin the
# fix and, more importantly, pin that it is a union rather than a relaxation —
# a validator that stops objecting is worth nothing.


def _merged_nodes() -> list[dict]:
    return [
        _node("t1", "Technique", "T1000"),
        _node("m1", "Mitigation", "M1000"),
        {
            "id": "capec:attack-pattern:1",
            "label": "AttackPattern",
            "labels": ["AttackPattern", "CapecObject"],
            "properties": {"attack_id": "CAPEC-1"},
        },
        {
            "id": "capec:attack-pattern:2",
            "label": "AttackPattern",
            "labels": ["AttackPattern", "CapecObject"],
            "properties": {"attack_id": "CAPEC-2"},
        },
        {
            "id": "capec:attack-pattern:1:mitigation:0",
            "label": "Mitigation",
            "labels": ["Mitigation", "CapecObject"],
            "properties": {},
        },
    ]


def test_both_catalogues_pass_together_under_the_merged_ruleset() -> None:
    edges = [
        {"id": "e1", "type": "MITIGATES", "source_id": "m1", "target_id": "t1"},
        {"id": "e2", "type": "ChildOf",
         "source_id": "capec:attack-pattern:1", "target_id": "capec:attack-pattern:2"},
        {"id": "e3", "type": "HAS_MITIGATION",
         "source_id": "capec:attack-pattern:1",
         "target_id": "capec:attack-pattern:1:mitigation:0"},
    ]
    result = validate_semantic_graph(_merged_nodes(), edges, schema={"dataset": "merged"})
    assert result.valid, result.errors


def test_the_merged_ruleset_is_a_union_not_an_amnesty() -> None:
    """A pattern neither catalogue declares must still fail."""
    edges = [
        {"id": "bad", "type": "MITIGATES",
         "source_id": "capec:attack-pattern:1", "target_id": "t1"},
    ]
    result = validate_semantic_graph(_merged_nodes(), edges, schema={"dataset": "merged"})
    assert not result.valid
    assert any("Illegal edge pattern" in e for e in result.errors)


def test_a_capec_mitigation_is_not_asked_for_an_attack_id() -> None:
    """`Mitigation` is the one label both catalogues use, and only one half has ids."""
    result = validate_semantic_graph(_merged_nodes(), [], schema={"dataset": "merged"})
    assert not [e for e in result.errors if "missing attack_id" in e]


def test_an_attack_mitigation_is_still_asked_for_one() -> None:
    """The marker label decides, so the ATT&CK half keeps the check it always had."""
    nodes = _merged_nodes()
    nodes[1]["properties"].pop("attack_id")
    result = validate_semantic_graph(nodes, [], schema={"dataset": "merged"})
    assert any("missing attack_id" in e for e in result.errors)


def test_the_real_merged_artifacts_pass_semantic_validation() -> None:
    """The whole thing, against what `utils.kg_builder.merge` actually wrote."""
    from pathlib import Path

    from utils.graph_loader.validation.semantic import validate_semantic_artifacts

    canon = Path("data-merged/graphs/merged/canonical")
    if not (canon / "nodes.jsonl").is_file():
        pytest.skip("merged dataset not built — run `python -m utils.kg_builder.merge`")
    result = validate_semantic_artifacts(
        canon / "nodes.jsonl", canon / "relationships.jsonl", canon / "schema.json"
    )
    assert result.valid, result.errors[:5]
