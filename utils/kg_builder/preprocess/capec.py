#!/usr/bin/env python3

from __future__ import annotations

import logging
from pathlib import Path

from utils.kg_builder.config import BuildConfig
from utils.kg_builder.discovery.capec_xml import discover_capec_xml, write_capec_discovery_report

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


def build_capec_placeholder() -> None:
    """Reserved entry point for future CAPEC preprocessing."""
    logger.info(CAPEC_NOT_IMPLEMENTED_MSG)
