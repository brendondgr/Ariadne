#!/usr/bin/env python3

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from utils.kg_builder.main import KGBuildRunner
from utils.kg_builder.validate import (
    ArtifactValidationError,
    compute_artifact_hashes,
    validate_deterministic_ordering,
    validate_manifest_counts,
    validate_reproducibility,
)


def test_cli_build_attack_dry_run() -> None:
    result = subprocess.run(
        [sys.executable, "main.py", "--build", "attack", "--dry-run"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Dry run" in result.stdout


def test_cli_build_capec_future_work() -> None:
    result = subprocess.run(
        [sys.executable, "main.py", "--build", "capec"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "not yet implemented" in result.stdout


@pytest.mark.skipif(
    not Path("data/raw/attack/v19.0/enterprise-attack.json").exists(),
    reason="Real ATT&CK dataset not downloaded",
)
def test_reproducible_attack_build() -> None:
    runner = KGBuildRunner()
    runner.build_attack()

    manifest_path = Path("data/graphs/attack/manifest.json")
    with open(manifest_path, encoding="utf-8") as f:
        first_manifest = json.load(f)

    runner.build_attack()
    with open(manifest_path, encoding="utf-8") as f:
        second_manifest = json.load(f)

    validate_reproducibility(first_manifest, second_manifest)
    validate_manifest_counts(
        manifest_path,
        Path("data/processed/pairs/enterprise-attack.json"),
    )
    validate_deterministic_ordering(
        Path("data/graphs/attack/nodes.jsonl"),
        Path("data/graphs/attack/relationships.jsonl"),
    )

    recomputed = compute_artifact_hashes(first_manifest["artifacts"])
    assert recomputed == first_manifest["hashes"]


def test_validate_reproducibility_detects_hash_change() -> None:
    first = {"counts": {"nodes": 1}, "hashes": {"nodes_jsonl": "abc"}}
    second = {"counts": {"nodes": 1}, "hashes": {"nodes_jsonl": "def"}}
    with pytest.raises(ArtifactValidationError, match="Artifact hashes changed"):
        validate_reproducibility(first, second)
