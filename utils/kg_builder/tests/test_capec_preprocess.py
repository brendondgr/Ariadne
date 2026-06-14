#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils.kg_builder.config import BuildConfig
from utils.kg_builder.preprocess.capec import normalize_capec_catalog, preprocess_capec, write_capec_pairs_checkpoint

FIXTURES = Path(__file__).parent / "fixtures"


def _write_fixture_catalog(tmp_path: Path) -> Path:
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
    return xml_path


def test_normalize_fixture_attack_pattern_fields(tmp_path: Path) -> None:
    _write_fixture_catalog(tmp_path)
    config = BuildConfig.from_data_dir(tmp_path)
    checkpoint = normalize_capec_catalog(config)

    attack_pattern = checkpoint.attack_patterns[0]
    assert attack_pattern["id"] == "560"
    assert attack_pattern["Name"] == "Use Alternate Authentication Material"
    assert attack_pattern["related_attack_patterns"] == [{"nature": "ChildOf", "capec_id": "122"}]
    assert len(attack_pattern["execution_steps"]) == 2
    assert attack_pattern["execution_steps"][0]["step"] == "1"
    assert attack_pattern["skills"][0]["level"] == "Medium"
    assert attack_pattern["consequences"][0]["scopes"] == ["Confidentiality"]
    assert "MFA" in attack_pattern["mitigations"][0]["description"]
    assert attack_pattern["related_weaknesses"] == [{"cwe_id": "522"}]
    assert attack_pattern["taxonomy_mappings"][0]["entry_id"] == "1550.002"
    assert attack_pattern["references"] == [{"external_reference_id": "REF-42"}]


def test_normalize_fixture_supports_external_reference_links(tmp_path: Path) -> None:
    _write_fixture_catalog(tmp_path)
    checkpoint = normalize_capec_catalog(BuildConfig.from_data_dir(tmp_path))

    external_reference = checkpoint.external_references[0]
    assert external_reference["id"] == "REF-42"
    assert external_reference["title"] == "Fixture Reference"


def test_preprocess_writes_deterministic_pairs_checkpoint(tmp_path: Path) -> None:
    _write_fixture_catalog(tmp_path)
    config = BuildConfig.from_data_dir(tmp_path)
    checkpoint = preprocess_capec(config)

    pairs_path = config.paths().capec_processed_pairs_file
    assert pairs_path.exists()
    payload = json.loads(pairs_path.read_text(encoding="utf-8"))
    assert payload["counts"]["attack_patterns"] == checkpoint.counts["attack_patterns"]
    assert payload["metadata"]["catalog_version"] == "3.9"
    assert Path(payload["metadata"]["discovery_report_path"]).exists()


def test_write_pairs_checkpoint_is_idempotent(tmp_path: Path) -> None:
    _write_fixture_catalog(tmp_path)
    config = BuildConfig.from_data_dir(tmp_path)
    checkpoint = normalize_capec_catalog(config)
    output_path = config.paths().capec_processed_pairs_file

    write_capec_pairs_checkpoint(checkpoint, output_path)
    first = output_path.read_text(encoding="utf-8")
    write_capec_pairs_checkpoint(checkpoint, output_path)
    second = output_path.read_text(encoding="utf-8")
    assert first == second


@pytest.mark.skipif(
    not Path("data/raw/capec/v3.9/capec_latest.xml").exists(),
    reason="Real CAPEC dataset not downloaded",
)
def test_preprocess_real_capec_catalog() -> None:
    config = BuildConfig.from_data_dir("data")
    checkpoint = preprocess_capec(config)

    assert checkpoint.counts["attack_patterns"] > 0
    assert checkpoint.counts["categories"] > 0
    assert checkpoint.counts["views"] > 0
    assert checkpoint.counts["external_references"] > 0
    assert config.paths().capec_processed_pairs_file.exists()
