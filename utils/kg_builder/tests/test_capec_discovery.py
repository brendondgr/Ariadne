#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils.kg_builder.config import BuildConfig
from utils.kg_builder.discovery.capec_xml import discover_capec_xml, write_capec_discovery_report
from utils.kg_builder.preprocess.capec import run_capec_discovery
from utils.kg_builder.source.capec import CAPEC_REQUIRED_COLLECTIONS

FIXTURES = Path(__file__).parent / "fixtures"


def test_discover_minimal_capec_fixture(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw" / "capec" / "v3.9"
    raw_dir.mkdir(parents=True)
    xml_path = raw_dir / "capec_latest.xml"
    xml_path.write_text(
        (FIXTURES / "minimal_capec_catalog.xml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (tmp_path / "versions.json").write_text(
        json.dumps({"attack_version": "19.0", "capec_version": "3.9"}),
        encoding="utf-8",
    )

    config = BuildConfig.from_data_dir(tmp_path)
    report = discover_capec_xml(config)

    assert report.catalog_version == "3.9"
    assert report.catalog_date == "2023-01-24"
    assert set(report.known_collections) == set(CAPEC_REQUIRED_COLLECTIONS)
    assert report.path_counts["Attack_Pattern_Catalog/Attack_Patterns/Attack_Pattern"] == 1
    assert "Attack_Pattern_Catalog/Attack_Patterns/Attack_Pattern/Description" in report.text_bearing_paths
    assert report.unknown_paths == []


def test_write_discovery_report_is_deterministic(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw" / "capec" / "v3.9"
    raw_dir.mkdir(parents=True)
    xml_path = raw_dir / "capec_latest.xml"
    xml_path.write_text(
        (FIXTURES / "minimal_capec_catalog.xml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (tmp_path / "versions.json").write_text(
        json.dumps({"attack_version": "19.0", "capec_version": "3.9"}),
        encoding="utf-8",
    )

    config = BuildConfig.from_data_dir(tmp_path)
    report = discover_capec_xml(config)
    output_path = config.paths().capec_discovery_report_path("inventory")
    write_capec_discovery_report(report, output_path)

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["summary"]["distinct_paths"] == len(report.path_counts)
    assert "path_counts" in payload
    assert "path_attributes" in payload
    assert "known_collections" in payload


def test_run_capec_discovery_writes_processed_discovery_artifact(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw" / "capec" / "v3.9"
    raw_dir.mkdir(parents=True)
    xml_path = raw_dir / "capec_latest.xml"
    xml_path.write_text(
        (FIXTURES / "minimal_capec_catalog.xml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (tmp_path / "versions.json").write_text(
        json.dumps({"attack_version": "19.0", "capec_version": "3.9"}),
        encoding="utf-8",
    )

    config = BuildConfig.from_data_dir(tmp_path)
    output_path = run_capec_discovery(config)

    assert output_path == tmp_path / "processed" / "discovery" / "capec-inventory.json"
    assert output_path.exists()


@pytest.mark.skipif(
    not Path("data/raw/capec/v3.9/capec_latest.xml").exists(),
    reason="Real CAPEC dataset not downloaded",
)
def test_discover_real_capec_catalog() -> None:
    config = BuildConfig.from_data_dir("data")
    report = discover_capec_xml(config)

    assert report.path_counts["Attack_Pattern_Catalog/Attack_Patterns/Attack_Pattern"] > 0
    assert report.known_collections["Attack_Patterns"] > 0
    assert report.known_collections["Categories"] > 0
    assert report.known_collections["Views"] > 0
    assert report.known_collections["External_References"] > 0
    assert "Attack_Pattern_Catalog/Attack_Patterns" in report.repeated_paths
    assert any(path.endswith("/Description") for path in report.text_bearing_paths)
    assert any("xhtml" in path.lower() or "Mitigation" in path for path in report.xhtml_paths)
