#!/usr/bin/env python3

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from utils.kg_builder.config import BuildConfig
from utils.kg_builder.io import write_json
from utils.kg_builder.source.capec import (
    CAPEC_NAMESPACE,
    CAPEC_REQUIRED_COLLECTIONS,
    CAPEC_ROOT_LOCAL_NAME,
    inspect_capec_source,
)

XHTML_NAMESPACE = "http://www.w3.org/1999/xhtml"

KNOWN_CAPEC_PATHS = {
    "Attack_Pattern_Catalog",
    "Attack_Pattern_Catalog/Attack_Patterns",
    "Attack_Pattern_Catalog/Attack_Patterns/Attack_Pattern",
    "Attack_Pattern_Catalog/Categories",
    "Attack_Pattern_Catalog/Categories/Category",
    "Attack_Pattern_Catalog/Views",
    "Attack_Pattern_Catalog/Views/View",
    "Attack_Pattern_Catalog/External_References",
    "Attack_Pattern_Catalog/External_References/External_Reference",
}


@dataclass
class CapecXmlDiscoveryReport:
    """Inventory of CAPEC XML structure for drift-tolerant downstream parsing."""

    source_path: str
    capec_version: str
    catalog_version: str
    catalog_date: str
    namespace: str
    build_scope: str
    root_metadata: dict[str, str]
    path_counts: dict[str, int]
    path_attributes: dict[str, list[str]]
    repeated_paths: list[str]
    text_bearing_paths: list[str]
    known_collections: dict[str, int]
    xhtml_paths: list[str]
    unknown_paths: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "capec_version": self.capec_version,
            "catalog_version": self.catalog_version,
            "catalog_date": self.catalog_date,
            "namespace": self.namespace,
            "build_scope": self.build_scope,
            "root_metadata": self.root_metadata,
            "path_counts": self.path_counts,
            "path_attributes": self.path_attributes,
            "repeated_paths": sorted(self.repeated_paths),
            "text_bearing_paths": sorted(self.text_bearing_paths),
            "known_collections": self.known_collections,
            "xhtml_paths": sorted(self.xhtml_paths),
            "unknown_paths": sorted(self.unknown_paths),
            "summary": {
                "distinct_paths": len(self.path_counts),
                "unknown_path_count": len(self.unknown_paths),
                "repeated_path_count": len(self.repeated_paths),
                "text_bearing_path_count": len(self.text_bearing_paths),
                "xhtml_path_count": len(self.xhtml_paths),
            },
        }


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _namespace_uri(tag: str) -> str | None:
    if tag.startswith("{") and "}" in tag:
        return tag[1:].rsplit("}", 1)[0]
    return None


def _element_path(element_path: list[str]) -> str:
    return "/".join(element_path)


def _has_text_content(element: ET.Element) -> bool:
    if (element.text or "").strip():
        return True
    if (element.tail or "").strip():
        return True
    return any((child.text or "").strip() or (child.tail or "").strip() for child in element)


def discover_capec_xml(
    config: BuildConfig,
    *,
    xml_path: Path | None = None,
) -> CapecXmlDiscoveryReport:
    """Walk CAPEC XML and inventory element paths without failing on new elements."""
    contract = inspect_capec_source(config, xml_path=xml_path)
    source_path = contract.source_path
    root = ET.parse(source_path).getroot()

    if _local_name(root.tag) != CAPEC_ROOT_LOCAL_NAME:
        raise ValueError(f"Unexpected CAPEC root element: {_local_name(root.tag)}")

    path_counts: Counter[str] = Counter()
    path_attributes: dict[str, set[str]] = defaultdict(set)
    sibling_group_sizes: dict[str, list[int]] = defaultdict(list)
    text_bearing_paths: set[str] = set()
    xhtml_paths: set[str] = set()

    def walk(element: ET.Element, element_path: list[str]) -> None:
        path = _element_path(element_path)
        path_counts[path] += 1

        for attr_name in sorted(element.attrib):
            path_attributes[path].add(attr_name)

        namespace = _namespace_uri(element.tag)
        if namespace == XHTML_NAMESPACE or _local_name(element.tag).startswith("xhtml:"):
            xhtml_paths.add(path)

        if _has_text_content(element):
            text_bearing_paths.add(path)

        child_groups: Counter[str] = Counter()
        for child in list(element):
            child_name = _local_name(child.tag)
            child_groups[child_name] += 1
            walk(child, [*element_path, child_name])

        if child_groups:
            sibling_group_sizes[path].append(max(child_groups.values()))

    walk(root, [_local_name(root.tag)])

    repeated_paths = sorted(
        path
        for path, count in path_counts.items()
        if count > 1 or any(size > 1 for size in sibling_group_sizes.get(path, []))
    )

    unknown_paths = sorted(
        path
        for path in path_counts
        if path.startswith("Attack_Pattern_Catalog/")
        and path.count("/") == 1
        and _local_name(path.split("/", 1)[1]) not in CAPEC_REQUIRED_COLLECTIONS
    )

    root_metadata = {
        key: value
        for key, value in sorted(root.attrib.items())
        if key in {"Name", "Version", "Date"}
    }

    return CapecXmlDiscoveryReport(
        source_path=str(source_path),
        capec_version=contract.capec_version,
        catalog_version=contract.catalog_version,
        catalog_date=contract.catalog_date,
        namespace=contract.namespace,
        build_scope=contract.build_scope,
        root_metadata=root_metadata,
        path_counts=dict(sorted(path_counts.items())),
        path_attributes={path: sorted(attrs) for path, attrs in sorted(path_attributes.items())},
        repeated_paths=repeated_paths,
        text_bearing_paths=sorted(text_bearing_paths),
        known_collections=contract.collection_counts,
        xhtml_paths=sorted(xhtml_paths),
        unknown_paths=unknown_paths,
    )


def write_capec_discovery_report(
    report: CapecXmlDiscoveryReport,
    output_path: Path,
) -> Path:
    """Write a deterministic CAPEC discovery report JSON artifact."""
    write_json(output_path, report.to_dict())
    return output_path
