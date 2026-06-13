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
