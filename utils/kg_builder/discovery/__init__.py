"""CAPEC XML discovery helpers for schema-drift-tolerant parsing."""

from utils.kg_builder.discovery.capec_xml import (
    CapecXmlDiscoveryReport,
    discover_capec_xml,
    write_capec_discovery_report,
)

__all__ = [
    "CapecXmlDiscoveryReport",
    "discover_capec_xml",
    "write_capec_discovery_report",
]
