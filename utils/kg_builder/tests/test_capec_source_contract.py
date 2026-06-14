#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from utils.download.downloader import DatasetDownloader
from utils.kg_builder.config import BuildConfig
from utils.kg_builder.source.capec import (
    CAPEC_BUILD_SCOPE,
    CAPEC_NAMESPACE,
    CAPEC_REQUIRED_COLLECTIONS,
    inspect_capec_source,
    resolve_capec_metadata_path,
    resolve_capec_xml_path,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_resolve_capec_xml_path_from_versions_json(tmp_path: Path) -> None:
    versions = {"attack_version": "19.0", "capec_version": "3.9"}
    (tmp_path / "versions.json").write_text(json.dumps(versions), encoding="utf-8")

    config = BuildConfig.from_data_dir(tmp_path)
    xml_path = resolve_capec_xml_path(config)

    assert xml_path == tmp_path / "raw" / "capec" / "v3.9" / "capec_latest.xml"
    assert resolve_capec_metadata_path(config) == tmp_path / "raw" / "capec" / "v3.9" / "metadata.json"


def test_inspect_minimal_capec_fixture(tmp_path: Path) -> None:
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
    contract = inspect_capec_source(config)

    assert contract.build_scope == CAPEC_BUILD_SCOPE
    assert contract.namespace == CAPEC_NAMESPACE
    assert contract.catalog_version == "3.9"
    assert contract.catalog_date == "2023-01-24"
    assert contract.source_path == xml_path
    assert set(contract.collection_counts) == set(CAPEC_REQUIRED_COLLECTIONS)
    assert contract.collection_counts["Attack_Patterns"] == 1
    assert contract.collection_counts["Categories"] == 1
    assert contract.collection_counts["Views"] == 1
    assert contract.collection_counts["External_References"] == 1


@pytest.mark.skipif(
    not Path("data/raw/capec/v3.9/capec_latest.xml").exists(),
    reason="Real CAPEC dataset not downloaded",
)
def test_inspect_real_capec_source_contract() -> None:
    config = BuildConfig.from_data_dir("data")
    contract = inspect_capec_source(config)

    assert contract.capec_version == "3.9"
    assert contract.catalog_version == "3.9"
    assert contract.namespace == CAPEC_NAMESPACE
    assert contract.build_scope == "full_catalog"
    assert contract.collection_counts["Attack_Patterns"] > 0
    assert contract.collection_counts["Categories"] > 0
    assert contract.collection_counts["Views"] > 0
    assert contract.collection_counts["External_References"] > 0
    assert contract.metadata_path is not None
    assert contract.metadata_path.exists()


def test_downloader_writes_versioned_capec_path(tmp_path: Path) -> None:
    downloader = DatasetDownloader(data_dir=tmp_path)

    assert downloader.capec_dir == tmp_path / "raw" / "capec" / "v3.9"

    xml_path = downloader.capec_dir / "capec_latest.xml"
    xml_path.parent.mkdir(parents=True, exist_ok=True)
    xml_path.write_text("<root/>", encoding="utf-8")

    with patch("utils.download.downloader.requests.get") as requests_get:
        downloader.download_capec()

    requests_get.assert_not_called()
    assert xml_path.exists()

    metadata_path = downloader.capec_dir / "metadata.json"
    assert metadata_path.exists()
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["source_url"] == DatasetDownloader.CAPEC_URL
