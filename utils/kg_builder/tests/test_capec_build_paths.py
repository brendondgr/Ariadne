#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path

from utils.kg_builder.config import BuildConfig


def test_attack_paths_unchanged(tmp_path: Path) -> None:
    versions = {"attack_version": "19.0", "capec_version": "3.9"}
    (tmp_path / "versions.json").write_text(json.dumps(versions), encoding="utf-8")

    config = BuildConfig.from_data_dir(tmp_path)
    paths = config.paths()

    assert paths.attack_raw_dir == tmp_path / "raw" / "attack" / "v19.0"
    assert paths.attack_raw_file == tmp_path / "raw" / "attack" / "v19.0" / "enterprise-attack.json"
    assert paths.processed_pairs_file == tmp_path / "processed" / "pairs" / "enterprise-attack.json"
    assert paths.graph_output_dir == tmp_path / "graphs" / "attack"
    assert paths.graph_canonical_dir == tmp_path / "graphs" / "attack" / "canonical"
    assert paths.graph_neo4j_export_dir == tmp_path / "graphs" / "attack" / "exports" / "neo4j"
    assert paths.graph_gremlin_export_dir == tmp_path / "graphs" / "attack" / "exports" / "gremlin"
    assert paths.source_registry_dir == tmp_path / "source_cards"


def test_capec_build_paths_resolve_from_versions_json(tmp_path: Path) -> None:
    versions = {"attack_version": "19.0", "capec_version": "3.9"}
    (tmp_path / "versions.json").write_text(json.dumps(versions), encoding="utf-8")

    config = BuildConfig.from_data_dir(tmp_path)
    paths = config.paths()

    assert paths.capec_raw_dir == tmp_path / "raw" / "capec" / "v3.9"
    assert paths.capec_raw_file == tmp_path / "raw" / "capec" / "v3.9" / "capec_latest.xml"
    assert paths.capec_processed_pairs_file == tmp_path / "processed" / "pairs" / "capec.json"
    assert paths.capec_discovery_dir == tmp_path / "processed" / "discovery"
    assert paths.capec_graph_output_dir == tmp_path / "graphs" / "capec"
    assert paths.capec_graph_canonical_dir == tmp_path / "graphs" / "capec" / "canonical"
    assert paths.capec_graph_neo4j_export_dir == tmp_path / "graphs" / "capec" / "exports" / "neo4j"
    assert paths.capec_graph_gremlin_export_dir == tmp_path / "graphs" / "capec" / "exports" / "gremlin"


def test_dataset_paths_helpers(tmp_path: Path) -> None:
    (tmp_path / "versions.json").write_text(
        json.dumps({"attack_version": "19.0", "capec_version": "3.9"}),
        encoding="utf-8",
    )
    paths = BuildConfig.from_data_dir(tmp_path).paths()

    attack_paths = paths.for_dataset("attack")
    capec_paths = paths.for_dataset("capec")

    assert attack_paths.dataset == "attack"
    assert attack_paths.raw_file == paths.attack_raw_file
    assert capec_paths.dataset == "capec"
    assert capec_paths.raw_file == paths.capec_raw_file
    assert capec_paths.discovery_dir == paths.capec_discovery_dir

    discovery_report = paths.capec_discovery_report_path("inventory")
    assert discovery_report == tmp_path / "processed" / "discovery" / "capec-inventory.json"

    prefixed_report = paths.capec_discovery_report_path("capec-paths")
    assert prefixed_report == tmp_path / "processed" / "discovery" / "capec-paths.json"
