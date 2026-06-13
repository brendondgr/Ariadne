#!/usr/bin/env python3

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import BuildConfig
from .exporters.cypher import export_cypher_artifacts
from .exporters.gremlin import GREMLIN_PROPERTY_SERIALIZATION, export_gremlin_artifacts
from .exporters.jsonl import export_canonical_artifacts
from .exporters.neo4j_csv import export_neo4j_csv_artifacts
from .io import ensure_dir, file_sha256, write_json
from .preprocess.attack import AttackPreprocessor, load_attack_bundle
from .preprocess.capec import CAPEC_NOT_IMPLEMENTED_MSG
from .registry import write_attack_source_card
from .validate import (
    validate_canonical_artifacts,
    validate_cross_backend_exports,
    validate_graph,
    validate_jsonl_artifacts,
)

logger = logging.getLogger(__name__)


def _build_manifest(
    graph_counts: dict[str, Any],
    metadata: dict[str, Any],
    canonical_paths: dict[str, str],
    export_paths: dict[str, dict[str, str]],
    config: BuildConfig,
) -> dict[str, Any]:
    all_artifacts = dict(canonical_paths)
    for backend, paths in export_paths.items():
        for name, path in paths.items():
            all_artifacts[f"{backend}_{name}"] = path

    hashes = {name: file_sha256(Path(path)) for name, path in all_artifacts.items()}
    return {
        "build_timestamp": datetime.now(timezone.utc).isoformat(),
        "attack_version": config.attack_version,
        "schema_version": config.schema_version,
        "settings": {
            "filter_deprecated": config.filter_deprecated,
            "filter_revoked": config.filter_revoked,
        },
        "metadata": metadata,
        "counts": graph_counts,
        "canonical": canonical_paths,
        "exports": export_paths,
        "property_transformations": {
            "neo4j": {"nested_properties": "json_string_in_csv_properties_json_column"},
            "gremlin": {"nested_properties": GREMLIN_PROPERTY_SERIALIZATION},
        },
        "hashes": hashes,
    }


class KGBuildRunner:
    """Orchestrates portable graph artifact generation from raw MITRE datasets."""

    def __init__(self, data_dir: str = "data", dry_run: bool = False) -> None:
        self.config = BuildConfig.from_data_dir(data_dir)
        self.dry_run = dry_run

    def build_attack(self) -> None:
        """Build canonical ATT&CK graph artifacts and backend exports."""
        paths = self.config.paths()
        if self.dry_run:
            logger.info(
                "Dry run: would build ATT&CK canonical graph artifacts "
                f"from {paths.attack_raw_file} into {paths.graph_canonical_dir} "
                f"with exports under {paths.graph_output_dir / 'exports'}"
            )
            return

        loaded = load_attack_bundle(self.config)
        graph = AttackPreprocessor(self.config).preprocess(
            loaded.bundle,
            source_path=loaded.source_path,
            bundle_id=loaded.bundle_id,
        )
        validate_graph(graph)

        ensure_dir(paths.processed_pairs_file.parent)
        write_json(paths.processed_pairs_file, graph.to_pairs_dict())
        logger.info("Wrote processed pairs checkpoint: %s", paths.processed_pairs_file)

        canonical_dir = paths.graph_canonical_dir
        ensure_dir(canonical_dir)

        canonical_file_paths = export_canonical_artifacts(graph, canonical_dir)
        validate_jsonl_artifacts(
            canonical_file_paths["nodes"],
            canonical_file_paths["relationships"],
        )

        node_records = [n.to_dict() for n in graph.nodes]
        edge_records = [r.to_dict() for r in graph.relationships]

        neo4j_dir = paths.graph_neo4j_export_dir
        cypher_paths = export_cypher_artifacts(neo4j_dir)
        csv_paths = export_neo4j_csv_artifacts(node_records, edge_records, neo4j_dir)

        gremlin_dir = paths.graph_gremlin_export_dir
        gremlin_paths = export_gremlin_artifacts(node_records, edge_records, gremlin_dir)

        canonical_paths = {
            "processed_pairs": str(paths.processed_pairs_file),
            "nodes_jsonl": str(canonical_file_paths["nodes"]),
            "relationships_jsonl": str(canonical_file_paths["relationships"]),
            "schema_json": str(canonical_file_paths["schema"]),
        }
        export_paths = {
            "neo4j": {
                "nodes_csv": str(csv_paths["nodes"]),
                "relationships_csv": str(csv_paths["relationships"]),
                "schema_cypher": str(cypher_paths["schema"]),
                "constraints_cypher": str(cypher_paths["constraints"]),
            },
            "gremlin": {
                "nodes_jsonl": str(gremlin_paths["nodes"]),
                "relationships_jsonl": str(gremlin_paths["relationships"]),
            },
        }

        manifest = _build_manifest(
            graph_counts=graph.counts,
            metadata=graph.metadata.to_dict(),
            canonical_paths=canonical_paths,
            export_paths=export_paths,
            config=self.config,
        )
        manifest_path = canonical_dir / "manifest.json"
        write_json(manifest_path, manifest)

        validate_canonical_artifacts(canonical_dir)
        validate_cross_backend_exports(canonical_dir, paths.graph_output_dir / "exports")
        write_attack_source_card(self.config, manifest_path)

        logger.info(
            "Built ATT&CK artifacts: nodes=%d relationships=%d -> canonical=%s exports=%s",
            graph.counts["nodes"],
            graph.counts["relationships"],
            canonical_dir,
            paths.graph_output_dir / "exports",
        )

    def build_capec(self) -> None:
        """CAPEC graph artifact build — reserved for a future implementation phase."""
        logger.info(CAPEC_NOT_IMPLEMENTED_MSG)
        sys.exit(2)

    def build_all(self) -> None:
        """Build all available graph artifacts; CAPEC remains future work."""
        self.build_attack()
        logger.info("Skipping CAPEC build (future work).")
