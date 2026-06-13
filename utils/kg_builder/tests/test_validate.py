#!/usr/bin/env python3

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from utils.kg_builder.config import BuildConfig
from utils.kg_builder.main import KGBuildRunner
from utils.kg_builder.validate import (
    ArtifactValidationError,
    compute_artifact_hashes,
    validate_canonical_artifacts,
    validate_cross_backend_exports,
    validate_deterministic_ordering,
    validate_gremlin_export,
    validate_manifest_counts,
    validate_reproducibility,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_cli_build_attack_dry_run() -> None:
    result = subprocess.run(
        [sys.executable, "main.py", "--build", "attack", "--dry-run"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Dry run" in result.stdout
    assert "canonical" in result.stdout


def test_cli_build_capec_future_work() -> None:
    result = subprocess.run(
        [sys.executable, "main.py", "--build", "capec"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "not yet implemented" in result.stdout


def test_build_paths_separate_canonical_and_exports(tmp_path: Path) -> None:
    config = BuildConfig.from_data_dir(tmp_path)
    paths = config.paths()
    assert paths.graph_canonical_dir == tmp_path / "graphs" / "attack" / "canonical"
    assert paths.graph_neo4j_export_dir == tmp_path / "graphs" / "attack" / "exports" / "neo4j"
    assert paths.graph_gremlin_export_dir == tmp_path / "graphs" / "attack" / "exports" / "gremlin"


@pytest.mark.skipif(
    not Path("data/raw/attack/v19.0/enterprise-attack.json").exists(),
    reason="Real ATT&CK dataset not downloaded",
)
def test_reproducible_attack_build() -> None:
    runner = KGBuildRunner()
    runner.build_attack()

    canonical = Path("data/graphs/attack/canonical")
    manifest_path = canonical / "manifest.json"
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
        canonical / "nodes.jsonl",
        canonical / "relationships.jsonl",
    )
    validate_canonical_artifacts(canonical)
    validate_cross_backend_exports(canonical, Path("data/graphs/attack/exports"))

    all_hashes = dict(first_manifest["hashes"])
    artifact_paths = dict(first_manifest["canonical"])
    for backend, paths in first_manifest["exports"].items():
        for name, path in paths.items():
            artifact_paths[f"{backend}_{name}"] = path
    recomputed = compute_artifact_hashes(artifact_paths)
    assert recomputed == first_manifest["hashes"]


def test_validate_reproducibility_detects_hash_change() -> None:
    first = {"counts": {"nodes": 1}, "hashes": {"nodes_jsonl": "abc"}}
    second = {"counts": {"nodes": 1}, "hashes": {"nodes_jsonl": "def"}}
    with pytest.raises(ArtifactValidationError, match="Artifact hashes changed"):
        validate_reproducibility(first, second)


def test_cross_backend_validation_fails_when_export_drops_node(tmp_path: Path) -> None:
    from utils.kg_builder.exporters.gremlin import export_gremlin_artifacts
    from utils.kg_builder.exporters.jsonl import export_canonical_artifacts
    from utils.kg_builder.preprocess.attack import AttackPreprocessor

    config = BuildConfig.from_data_dir("data")
    with open(FIXTURES / "preprocess_attack_bundle.json", encoding="utf-8") as f:
        bundle = json.load(f)
    graph = AttackPreprocessor(config).preprocess(bundle)

    canonical_dir = tmp_path / "canonical"
    export_canonical_artifacts(graph, canonical_dir)

    nodes = [
        json.loads(line)
        for line in (canonical_dir / "nodes.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rels = [
        json.loads(line)
        for line in (canonical_dir / "relationships.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    gremlin_dir = tmp_path / "exports" / "gremlin"
    export_gremlin_artifacts(nodes[1:], rels, gremlin_dir)

    with pytest.raises(ArtifactValidationError, match="gremlin export node count"):
        validate_gremlin_export(canonical_dir, gremlin_dir)
