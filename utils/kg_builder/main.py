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
from .exporters.jsonl import export_jsonl_artifacts
from .exporters.neo4j_csv import export_neo4j_csv_artifacts
from .io import ensure_dir, file_sha256, write_json
from .preprocess.attack import AttackPreprocessor, load_attack_bundle
from .preprocess.capec import CAPEC_NOT_IMPLEMENTED_MSG
from .schema.attack import ATTACK_NODE_LABELS, ATTACK_RELATIONSHIP_TYPES
from .validate import validate_graph, validate_jsonl_artifacts

logger = logging.getLogger(__name__)


def _schema_dict() -> dict[str, Any]:
    return {
        "node_labels": sorted(ATTACK_NODE_LABELS),
        "relationship_types": sorted(ATTACK_RELATIONSHIP_TYPES),
    }


def _build_manifest(
    graph_counts: dict[str, Any],
    metadata: dict[str, Any],
    artifact_paths: dict[str, str],
    config: BuildConfig,
) -> dict[str, Any]:
    hashes = {name: file_sha256(Path(path)) for name, path in artifact_paths.items()}
    return {
        "build_timestamp": datetime.now(timezone.utc).isoformat(),
        "attack_version": config.attack_version,
        "settings": {
            "filter_deprecated": config.filter_deprecated,
            "filter_revoked": config.filter_revoked,
        },
        "metadata": metadata,
        "counts": graph_counts,
        "artifacts": artifact_paths,
        "hashes": hashes,
    }


class KGBuildRunner:
    """Orchestrates portable graph artifact generation from raw MITRE datasets."""

    def __init__(self, data_dir: str = "data", dry_run: bool = False) -> None:
        self.config = BuildConfig.from_data_dir(data_dir)
        self.dry_run = dry_run

    def build_attack(self) -> None:
        """Build portable ATT&CK graph artifacts under data/graphs/attack/."""
        paths = self.config.paths()
        if self.dry_run:
            logger.info(
                "Dry run: would build ATT&CK portable graph artifacts "
                f"from {paths.attack_raw_file} into {paths.graph_output_dir}"
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

        output_dir = paths.graph_output_dir
        ensure_dir(output_dir)

        jsonl_paths = export_jsonl_artifacts(graph, output_dir)
        validate_jsonl_artifacts(jsonl_paths["nodes"], jsonl_paths["relationships"])

        cypher_paths = export_cypher_artifacts(output_dir)
        csv_paths = export_neo4j_csv_artifacts(graph, paths.graph_neo4j_csv_dir)

        schema_path = output_dir / "schema.json"
        write_json(schema_path, _schema_dict(), sort_keys=True)

        artifact_paths = {
            "processed_pairs": str(paths.processed_pairs_file),
            "nodes_jsonl": str(jsonl_paths["nodes"]),
            "relationships_jsonl": str(jsonl_paths["relationships"]),
            "schema_json": str(schema_path),
            "schema_cypher": str(cypher_paths["schema"]),
            "constraints_cypher": str(cypher_paths["constraints"]),
            "neo4j_csv_nodes": str(csv_paths["nodes"]),
            "neo4j_csv_relationships": str(csv_paths["relationships"]),
        }

        manifest = _build_manifest(
            graph_counts=graph.counts,
            metadata=graph.metadata.to_dict(),
            artifact_paths=artifact_paths,
            config=self.config,
        )
        manifest_path = output_dir / "manifest.json"
        write_json(manifest_path, manifest)
        logger.info(
            "Built ATT&CK artifacts: nodes=%d relationships=%d -> %s",
            graph.counts["nodes"],
            graph.counts["relationships"],
            output_dir,
        )

    def build_capec(self) -> None:
        """CAPEC graph artifact build — reserved for a future implementation phase."""
        logger.info(CAPEC_NOT_IMPLEMENTED_MSG)
        sys.exit(2)

    def build_all(self) -> None:
        """Build all available graph artifacts; CAPEC remains future work."""
        self.build_attack()
        logger.info("Skipping CAPEC build (future work).")
