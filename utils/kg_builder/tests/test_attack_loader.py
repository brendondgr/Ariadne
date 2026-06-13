#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path

import pytest

from utils.kg_builder.config import BuildConfig
from utils.kg_builder.preprocess.attack import load_attack_bundle

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_minimal_stix_bundle(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw" / "attack" / "v19.0"
    raw_dir.mkdir(parents=True)
    bundle_path = raw_dir / "enterprise-attack.json"
    bundle_path.write_text(
        (FIXTURES / "minimal_attack_bundle.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    config = BuildConfig.from_data_dir(tmp_path)
    result = load_attack_bundle(config)

    assert result.bundle_id == "bundle--test-attack-loader"
    assert result.object_count == 1
    assert result.attack_version == "19.0"
    assert result.source_path == bundle_path
    assert isinstance(result.bundle["objects"], list)


@pytest.mark.skipif(
    not Path("data/raw/attack/v19.0/enterprise-attack.json").exists(),
    reason="Real ATT&CK dataset not downloaded",
)
def test_load_real_attack_bundle() -> None:
    config = BuildConfig.from_data_dir("data")
    result = load_attack_bundle(config)

    assert result.object_count > 0
    assert result.bundle_id is not None
    assert result.bundle["type"] == "bundle"
    assert isinstance(result.bundle["objects"], list)
