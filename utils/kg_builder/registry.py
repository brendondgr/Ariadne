#!/usr/bin/env python3

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .config import BuildConfig


@dataclass
class SourceCard:
    """Metadata contract for routing specialist agents to graph backends."""

    dataset: str
    canonical_manifest: str
    schema_version: str
    runtime_backend: str
    node_labels: list[str]
    relationship_types: list[str]
    canonical_dir: str
    exports: dict[str, dict[str, str]]
    endpoints: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_attack_source_card(config: BuildConfig, manifest_path: Path) -> SourceCard:
    """Build an ATT&CK source card from build configuration and manifest."""
    paths = config.paths()
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    schema_path = paths.graph_canonical_dir / "schema.json"
    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)

    exports = manifest.get("exports", {})
    return SourceCard(
        dataset="attack",
        canonical_manifest=str(manifest_path),
        schema_version=schema.get("schema_version", config.schema_version),
        runtime_backend="neo4j",
        node_labels=schema.get("node_labels", []),
        relationship_types=schema.get("relationship_types", []),
        canonical_dir=str(paths.graph_canonical_dir),
        exports={
            "neo4j": {k: v for k, v in exports.get("neo4j", {}).items()},
            "gremlin": {k: v for k, v in exports.get("gremlin", {}).items()},
        },
        endpoints={
            "neo4j": "",
            "gremlin": "",
        },
    )


def build_capec_source_card(config: BuildConfig, manifest_path: Path) -> SourceCard:
    """Build a CAPEC source card from build configuration and manifest."""
    paths = config.paths()
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    schema_path = paths.capec_graph_canonical_dir / "schema.json"
    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)

    exports = manifest.get("exports", {})
    return SourceCard(
        dataset="capec",
        canonical_manifest=str(manifest_path),
        schema_version=schema.get("schema_version", config.schema_version),
        runtime_backend="gremlin",
        node_labels=schema.get("node_labels", []),
        relationship_types=schema.get("relationship_types", []),
        canonical_dir=str(paths.capec_graph_canonical_dir),
        exports={
            "neo4j": {k: v for k, v in exports.get("neo4j", {}).items()},
            "gremlin": {k: v for k, v in exports.get("gremlin", {}).items()},
        },
        endpoints={
            "neo4j": "",
            "gremlin": "",
        },
    )


def write_capec_source_card(config: BuildConfig, manifest_path: Path) -> Path:
    """Write the CAPEC source card JSON for planner and specialist agents."""
    paths = config.paths()
    paths.source_registry_dir.mkdir(parents=True, exist_ok=True)
    card = build_capec_source_card(config, manifest_path)
    card_path = paths.source_registry_dir / "capec.json"
    with open(card_path, "w", encoding="utf-8") as f:
        json.dump(card.to_dict(), f, indent=2, sort_keys=True)
        f.write("\n")
    return card_path


def write_attack_source_card(config: BuildConfig, manifest_path: Path) -> Path:
    """Write the ATT&CK source card JSON for planner and specialist agents."""
    paths = config.paths()
    paths.source_registry_dir.mkdir(parents=True, exist_ok=True)
    card = build_attack_source_card(config, manifest_path)
    card_path = paths.source_registry_dir / "attack.json"
    with open(card_path, "w", encoding="utf-8") as f:
        json.dump(card.to_dict(), f, indent=2, sort_keys=True)
        f.write("\n")
    return card_path
