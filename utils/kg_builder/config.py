#!/usr/bin/env python3

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BuildPaths:
    """Resolved input and output paths for a KG build."""

    data_dir: Path
    attack_raw_dir: Path
    attack_raw_file: Path
    processed_pairs_file: Path
    graph_output_dir: Path
    graph_canonical_dir: Path
    graph_neo4j_export_dir: Path
    graph_gremlin_export_dir: Path
    source_registry_dir: Path
    capec_processed_pairs_file: Path


@dataclass(frozen=True)
class BuildConfig:
    """Configuration for portable graph artifact generation."""

    data_dir: Path
    attack_version: str
    capec_version: str
    filter_deprecated: bool = True
    filter_revoked: bool = True
    schema_version: str = "1.0"

    @classmethod
    def from_data_dir(cls, data_dir: str | Path = "data") -> BuildConfig:
        root = Path(data_dir)
        versions_file = root / "versions.json"
        attack_version = "19.0"
        capec_version = "3.9"

        if versions_file.exists():
            with open(versions_file, encoding="utf-8") as f:
                versions = json.load(f)
            attack_version = str(versions.get("attack_version", attack_version))
            capec_version = str(versions.get("capec_version", capec_version))

        return cls(
            data_dir=root,
            attack_version=attack_version,
            capec_version=capec_version,
        )

    def paths(self) -> BuildPaths:
        attack_raw_dir = self.data_dir / "raw" / "attack" / f"v{self.attack_version}"
        graph_output_dir = self.data_dir / "graphs" / "attack"
        return BuildPaths(
            data_dir=self.data_dir,
            attack_raw_dir=attack_raw_dir,
            attack_raw_file=attack_raw_dir / "enterprise-attack.json",
            processed_pairs_file=self.data_dir / "processed" / "pairs" / "enterprise-attack.json",
            graph_output_dir=graph_output_dir,
            graph_canonical_dir=graph_output_dir / "canonical",
            graph_neo4j_export_dir=graph_output_dir / "exports" / "neo4j",
            graph_gremlin_export_dir=graph_output_dir / "exports" / "gremlin",
            source_registry_dir=self.data_dir / "source_cards",
            capec_processed_pairs_file=self.data_dir / "processed" / "pairs" / "capec.json",
        )
