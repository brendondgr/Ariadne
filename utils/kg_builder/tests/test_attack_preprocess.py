#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils.kg_builder.config import BuildConfig
from utils.kg_builder.preprocess.attack import AttackPreprocessor

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    with open(FIXTURES / name, encoding="utf-8") as f:
        return json.load(f)


def test_preprocess_minimal_fixture() -> None:
    config = BuildConfig.from_data_dir("data")
    preprocessor = AttackPreprocessor(config)
    graph = preprocessor.preprocess(_load_fixture("preprocess_attack_bundle.json"))

    labels = {node.label for node in graph.nodes}
    assert labels == {"Tactic", "Technique", "SubTechnique", "Group", "Software", "Mitigation"}

    for node in graph.nodes:
        assert node.labels[0] == node.label
        assert "AttackObject" in node.labels
        assert "STIXObject" in node.labels

    rel_types = {rel.type for rel in graph.relationships}
    assert "USES" in rel_types
    assert "HAS_SUBTECHNIQUE" in rel_types
    assert "HAS_TECHNIQUE" in rel_types

    assert graph.metadata.filtered_deprecated == 1
    assert graph.counts["nodes"] == 6
    assert "metadata" in graph.to_pairs_dict()
    assert "nodes" in graph.to_pairs_dict()
    assert "relationships" in graph.to_pairs_dict()
    assert "counts" in graph.to_pairs_dict()


@pytest.mark.skipif(
    not Path("data/raw/attack/v19.0/enterprise-attack.json").exists(),
    reason="Real ATT&CK dataset not downloaded",
)
def test_preprocess_real_attack_dataset() -> None:
    from utils.kg_builder.preprocess.attack import load_attack_bundle

    config = BuildConfig.from_data_dir("data")
    loaded = load_attack_bundle(config)
    graph = AttackPreprocessor(config).preprocess(
        loaded.bundle,
        source_path=loaded.source_path,
        bundle_id=loaded.bundle_id,
    )

    pairs = graph.to_pairs_dict()
    assert pairs["metadata"]["attack_version"] == "19.0"
    assert pairs["counts"]["nodes"] > 0
    assert pairs["counts"]["relationships"] > 0
    assert "Technique" in pairs["counts"]["nodes_by_label"]


def _embedded_refs_bundle() -> dict:
    return {
        "type": "bundle",
        "id": "bundle--embedded",
        "objects": [
            {
                "type": "x-mitre-tactic",
                "id": "x-mitre-tactic--t1",
                "name": "Persistence",
                "x_mitre_shortname": "persistence",
                "external_references": [
                    {"source_name": "mitre-attack", "external_id": "TA0003"}
                ],
            },
            {
                "type": "x-mitre-matrix",
                "id": "x-mitre-matrix--m1",
                "name": "Enterprise ATT&CK",
                "tactic_refs": ["x-mitre-tactic--t1", "x-mitre-tactic--missing"],
                "external_references": [
                    {"source_name": "mitre-attack", "external_id": "enterprise-attack"}
                ],
            },
            {
                "type": "x-mitre-data-component",
                "id": "x-mitre-data-component--dc1",
                "name": "Process Creation",
                "external_references": [
                    {"source_name": "mitre-attack", "external_id": "DC0032"}
                ],
            },
            {
                "type": "x-mitre-analytic",
                "id": "x-mitre-analytic--an1",
                "name": "Analytic 1",
                "external_references": [
                    {"source_name": "mitre-attack", "external_id": "AN0001"}
                ],
                "x_mitre_log_source_references": [
                    {
                        "x_mitre_data_component_ref": "x-mitre-data-component--dc1",
                        "name": "auditd:SYSCALL",
                        "channel": "execve",
                    },
                    {
                        "x_mitre_data_component_ref": "x-mitre-data-component--dc1",
                        "name": "WinEventLog:Security",
                        "channel": "4688",
                    },
                    {
                        "x_mitre_data_component_ref": "x-mitre-data-component--gone",
                        "name": "ignored",
                        "channel": "n/a",
                    },
                ],
            },
            {
                "type": "x-mitre-analytic",
                "id": "x-mitre-analytic--an-dead",
                "name": "Deprecated Analytic",
                "x_mitre_deprecated": True,
                "external_references": [
                    {"source_name": "mitre-attack", "external_id": "AN0002"}
                ],
            },
            {
                "type": "x-mitre-detection-strategy",
                "id": "x-mitre-detection-strategy--ds1",
                "name": "Detection Strategy 1",
                "external_references": [
                    {"source_name": "mitre-attack", "external_id": "DET0001"}
                ],
                "x_mitre_analytic_refs": [
                    "x-mitre-analytic--an1",
                    "x-mitre-analytic--an-dead",
                ],
            },
        ],
    }


def test_preprocess_wires_embedded_references() -> None:
    config = BuildConfig.from_data_dir("data")
    graph = AttackPreprocessor(config).preprocess(_embedded_refs_bundle())

    by_label = {node.label: node for node in graph.nodes}
    assert "Analytic" in by_label
    assert by_label["Analytic"].properties["attack_id"] == "AN0001"
    assert "AttackObject" in by_label["Analytic"].labels
    # Deprecated analytic is excluded at load.
    assert all(node.id != "x-mitre-analytic--an-dead" for node in graph.nodes)

    edges = {(rel.type, rel.source_id, rel.target_id) for rel in graph.relationships}
    assert ("HAS_TACTIC", "x-mitre-matrix--m1", "x-mitre-tactic--t1") in edges
    assert ("HAS_ANALYTIC", "x-mitre-detection-strategy--ds1", "x-mitre-analytic--an1") in edges
    assert ("MONITORS", "x-mitre-analytic--an1", "x-mitre-data-component--dc1") in edges

    # Refs to missing or filtered objects never become edges.
    assert all("missing" not in target for _, _, target in edges)
    assert all("gone" not in target for _, _, target in edges)
    assert all("an-dead" not in target for _, _, target in edges)

    monitors = [rel for rel in graph.relationships if rel.type == "MONITORS"]
    assert len(monitors) == 1  # deduplicated per (analytic, data component)
    assert monitors[0].properties["log_source_names"] == [
        "WinEventLog:Security",
        "auditd:SYSCALL",
    ]
