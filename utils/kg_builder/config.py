#!/usr/bin/env python3

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

DatasetName = Literal["attack", "capec"]


@dataclass(frozen=True)
class DatasetBuildPaths:
    """Resolved input and output paths for one graph dataset build."""

    dataset: DatasetName
    raw_dir: Path
    raw_file: Path
    processed_pairs_file: Path
    discovery_dir: Path
    graph_output_dir: Path
    graph_canonical_dir: Path
    graph_neo4j_export_dir: Path
    graph_gremlin_export_dir: Path


@dataclass(frozen=True)
class BuildPaths:
    """Resolved input and output paths for KG builds across datasets."""

    data_dir: Path
    attack_raw_dir: Path
    attack_raw_file: Path
    processed_pairs_file: Path
    graph_output_dir: Path
    graph_canonical_dir: Path
    graph_neo4j_export_dir: Path
    graph_gremlin_export_dir: Path
    source_registry_dir: Path
    capec_raw_dir: Path
    capec_raw_file: Path
    capec_processed_pairs_file: Path
    capec_discovery_dir: Path
    capec_graph_output_dir: Path
    capec_graph_canonical_dir: Path
    capec_graph_neo4j_export_dir: Path
    capec_graph_gremlin_export_dir: Path

    def for_dataset(self, dataset: DatasetName) -> DatasetBuildPaths:
        if dataset == "attack":
            return DatasetBuildPaths(
                dataset="attack",
                raw_dir=self.attack_raw_dir,
                raw_file=self.attack_raw_file,
                processed_pairs_file=self.processed_pairs_file,
                discovery_dir=self.data_dir / "processed" / "discovery" / "attack",
                graph_output_dir=self.graph_output_dir,
                graph_canonical_dir=self.graph_canonical_dir,
                graph_neo4j_export_dir=self.graph_neo4j_export_dir,
                graph_gremlin_export_dir=self.graph_gremlin_export_dir,
            )
        if dataset == "capec":
            return DatasetBuildPaths(
                dataset="capec",
                raw_dir=self.capec_raw_dir,
                raw_file=self.capec_raw_file,
                processed_pairs_file=self.capec_processed_pairs_file,
                discovery_dir=self.capec_discovery_dir,
                graph_output_dir=self.capec_graph_output_dir,
                graph_canonical_dir=self.capec_graph_canonical_dir,
                graph_neo4j_export_dir=self.capec_graph_neo4j_export_dir,
                graph_gremlin_export_dir=self.capec_graph_gremlin_export_dir,
            )
        raise ValueError(f"Unsupported dataset: {dataset}")

    def capec_discovery_report_path(self, report_name: str) -> Path:
        """Resolve a CAPEC discovery artifact under data/processed/discovery/."""
        if not report_name.startswith("capec-"):
            report_name = f"capec-{report_name}"
        if not report_name.endswith(".json"):
            report_name = f"{report_name}.json"
        return self.capec_discovery_dir / report_name


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
        capec_raw_dir = self.data_dir / "raw" / "capec" / f"v{self.capec_version}"
        capec_graph_output_dir = self.data_dir / "graphs" / "capec"
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
            capec_raw_dir=capec_raw_dir,
            capec_raw_file=capec_raw_dir / "capec_latest.xml",
            capec_processed_pairs_file=self.data_dir / "processed" / "pairs" / "capec.json",
            capec_discovery_dir=self.data_dir / "processed" / "discovery",
            capec_graph_output_dir=capec_graph_output_dir,
            capec_graph_canonical_dir=capec_graph_output_dir / "canonical",
            capec_graph_neo4j_export_dir=capec_graph_output_dir / "exports" / "neo4j",
            capec_graph_gremlin_export_dir=capec_graph_output_dir / "exports" / "gremlin",
        )
