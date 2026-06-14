#!/usr/bin/env python3

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class CapecPairsMetadata:
    """Metadata for the CAPEC processed-pairs checkpoint."""

    source_path: str
    capec_version: str
    catalog_version: str
    catalog_date: str
    namespace: str
    build_scope: str
    discovery_report_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CapecPairsCheckpoint:
    """Deterministic intermediate CAPEC records before graph materialization."""

    metadata: CapecPairsMetadata
    attack_patterns: list[dict[str, Any]] = field(default_factory=list)
    categories: list[dict[str, Any]] = field(default_factory=list)
    views: list[dict[str, Any]] = field(default_factory=list)
    external_references: list[dict[str, Any]] = field(default_factory=list)
    unmapped_fields: list[dict[str, Any]] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        return {
            "attack_patterns": len(self.attack_patterns),
            "categories": len(self.categories),
            "views": len(self.views),
            "external_references": len(self.external_references),
            "unmapped_fields": len(self.unmapped_fields),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata.to_dict(),
            "attack_patterns": self.attack_patterns,
            "categories": self.categories,
            "views": self.views,
            "external_references": self.external_references,
            "unmapped_fields": self.unmapped_fields,
            "counts": self.counts,
        }
