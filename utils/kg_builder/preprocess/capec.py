#!/usr/bin/env python3

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from pathlib import Path

from utils.kg_builder.config import BuildConfig
from utils.kg_builder.discovery.capec_xml import discover_capec_xml, write_capec_discovery_report
from utils.kg_builder.io import ensure_dir, write_json
from utils.kg_builder.preprocess.capec_models import CapecPairsCheckpoint, CapecPairsMetadata
from utils.kg_builder.preprocess.capec_parse import (
    local_name,
    normalize_attack_pattern,
    normalize_category,
    normalize_external_reference,
    normalize_view,
)
from utils.kg_builder.source.capec import inspect_capec_source

logger = logging.getLogger(__name__)

CAPEC_NOT_IMPLEMENTED_MSG = (
    "CAPEC graph artifact build is not yet implemented. "
    "Reserved output: data/processed/pairs/capec.json and data/graphs/capec/."
)


def run_capec_discovery(
    config: BuildConfig,
    *,
    xml_path: Path | None = None,
    output_path: Path | None = None,
) -> Path:
    """Discover CAPEC XML structure and write a drift-tolerant inventory report."""
    paths = config.paths()
    report = discover_capec_xml(config, xml_path=xml_path)
    destination = output_path or paths.capec_discovery_report_path("inventory")
    write_capec_discovery_report(report, destination)
    logger.info(
        "Wrote CAPEC discovery report: %s (%d distinct paths)",
        destination,
        len(report.path_counts),
    )
    return destination


def normalize_capec_catalog(
    config: BuildConfig,
    *,
    xml_path: Path | None = None,
    discovery_report_path: Path | None = None,
) -> CapecPairsCheckpoint:
    """Normalize CAPEC XML entities into deterministic intermediate records."""
    contract = inspect_capec_source(config, xml_path=xml_path)
    source_path = str(contract.source_path)
    root = ET.parse(contract.source_path).getroot()
    unmapped_fields: list[dict] = []

    attack_patterns = [
        normalize_attack_pattern(
            element,
            source_path=source_path,
            unmapped_fields=unmapped_fields,
        )
        for element in _collection_elements(root, "Attack_Patterns", "Attack_Pattern")
    ]
    categories = [
        normalize_category(
            element,
            source_path=source_path,
            unmapped_fields=unmapped_fields,
        )
        for element in _collection_elements(root, "Categories", "Category")
    ]
    views = [
        normalize_view(
            element,
            source_path=source_path,
            unmapped_fields=unmapped_fields,
        )
        for element in _collection_elements(root, "Views", "View")
    ]
    external_references = [
        normalize_external_reference(
            element,
            source_path=source_path,
            unmapped_fields=unmapped_fields,
        )
        for element in _collection_elements(root, "External_References", "External_Reference")
    ]

    attack_patterns.sort(key=lambda item: int(item["id"]))
    categories.sort(key=lambda item: int(item["id"]))
    views.sort(key=lambda item: int(item["id"]))
    external_references.sort(key=lambda item: item["id"])

    metadata = CapecPairsMetadata(
        source_path=source_path,
        capec_version=contract.capec_version,
        catalog_version=contract.catalog_version,
        catalog_date=contract.catalog_date,
        namespace=contract.namespace,
        build_scope=contract.build_scope,
        discovery_report_path=str(discovery_report_path) if discovery_report_path else None,
    )
    return CapecPairsCheckpoint(
        metadata=metadata,
        attack_patterns=attack_patterns,
        categories=categories,
        views=views,
        external_references=external_references,
        unmapped_fields=sorted(unmapped_fields, key=lambda item: (item["entity_type"], item["entity_id"], item["field_name"])),
    )


def write_capec_pairs_checkpoint(
    checkpoint: CapecPairsCheckpoint,
    output_path: Path,
) -> Path:
    """Write the CAPEC processed-pairs checkpoint JSON."""
    ensure_dir(output_path.parent)
    write_json(output_path, checkpoint.to_dict())
    return output_path


def preprocess_capec(config: BuildConfig, *, xml_path: Path | None = None) -> CapecPairsCheckpoint:
    """Run CAPEC discovery and normalization, writing processed artifacts."""
    discovery_path = run_capec_discovery(config, xml_path=xml_path)
    checkpoint = normalize_capec_catalog(
        config,
        xml_path=xml_path,
        discovery_report_path=discovery_path,
    )
    pairs_path = config.paths().capec_processed_pairs_file
    write_capec_pairs_checkpoint(checkpoint, pairs_path)
    logger.info(
        "Wrote CAPEC processed pairs checkpoint: %s (attack_patterns=%d)",
        pairs_path,
        checkpoint.counts["attack_patterns"],
    )
    return checkpoint


def _collection_elements(
    root: ET.Element,
    collection_name: str,
    item_name: str,
) -> list[ET.Element]:
    for child in list(root):
        if local_name(child.tag) == collection_name:
            return [item for item in list(child) if local_name(item.tag) == item_name]
    return []


def build_capec_placeholder() -> None:
    """Reserved entry point for future CAPEC preprocessing."""
    logger.info(CAPEC_NOT_IMPLEMENTED_MSG)
