#!/usr/bin/env python3

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from utils.kg_builder.config import BuildConfig

CAPEC_NAMESPACE = "http://capec.mitre.org/capec-3"
CAPEC_ROOT_LOCAL_NAME = "Attack_Pattern_Catalog"
CAPEC_REQUIRED_COLLECTIONS = (
    "Attack_Patterns",
    "Categories",
    "Views",
    "External_References",
)
# Full pinned catalog is the canonical build scope; ATT&CK-related filtering is deferred
# to query agents or optional export filters.
CAPEC_BUILD_SCOPE = "full_catalog"


@dataclass(frozen=True)
class CapecSourceContract:
    """Verified CAPEC XML source boundary for reproducible graph builds."""

    source_path: Path
    metadata_path: Path | None
    capec_version: str
    catalog_version: str
    catalog_date: str
    namespace: str
    collection_counts: dict[str, int]
    build_scope: str = CAPEC_BUILD_SCOPE


def resolve_capec_xml_path(config: BuildConfig) -> Path:
    """Resolve pinned CAPEC XML from data/versions.json."""
    return (
        config.data_dir
        / "raw"
        / "capec"
        / f"v{config.capec_version}"
        / "capec_latest.xml"
    )


def resolve_capec_metadata_path(config: BuildConfig) -> Path:
    """Resolve CAPEC download metadata alongside the pinned XML file."""
    return (
        config.data_dir
        / "raw"
        / "capec"
        / f"v{config.capec_version}"
        / "metadata.json"
    )


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _namespace_uri(tag: str) -> str | None:
    if tag.startswith("{") and "}" in tag:
        return tag[1:].rsplit("}", 1)[0]
    return None


def inspect_capec_source(
    config: BuildConfig,
    *,
    xml_path: Path | None = None,
) -> CapecSourceContract:
    """Inspect CAPEC XML and confirm the pinned source contract."""
    source_path = xml_path or resolve_capec_xml_path(config)
    if not source_path.exists():
        raise FileNotFoundError(f"CAPEC XML not found: {source_path}")

    root = ET.parse(source_path).getroot()
    if _local_name(root.tag) != CAPEC_ROOT_LOCAL_NAME:
        raise ValueError(
            f"Expected root element {CAPEC_ROOT_LOCAL_NAME!r}, got {_local_name(root.tag)!r}"
        )

    namespace = _namespace_uri(root.tag)
    if namespace != CAPEC_NAMESPACE:
        raise ValueError(
            f"Expected CAPEC namespace {CAPEC_NAMESPACE!r}, got {namespace!r}"
        )

    catalog_version = root.get("Version")
    catalog_date = root.get("Date")
    if not catalog_version:
        raise ValueError("CAPEC catalog is missing required Version attribute")
    if not catalog_date:
        raise ValueError("CAPEC catalog is missing required Date attribute")

    ns = {"c": CAPEC_NAMESPACE}
    collection_counts: dict[str, int] = {}
    for collection_name in CAPEC_REQUIRED_COLLECTIONS:
        element = root.find(f"c:{collection_name}", ns)
        if element is None:
            raise ValueError(f"CAPEC catalog is missing required collection: {collection_name}")
        collection_counts[collection_name] = len(list(element))

    metadata_path = resolve_capec_metadata_path(config)
    return CapecSourceContract(
        source_path=source_path,
        metadata_path=metadata_path if metadata_path.exists() else None,
        capec_version=config.capec_version,
        catalog_version=catalog_version,
        catalog_date=catalog_date,
        namespace=namespace,
        collection_counts=collection_counts,
    )
