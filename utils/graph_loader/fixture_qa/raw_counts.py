#!/usr/bin/env python3
"""Independent recount of the raw MITRE sources.

The whole point of the fixture-QA harness is to catch a systematic build bug, so
this module must **not** reuse the build's preprocessors (``AttackPreprocessor``
etc.). It re-derives node counts straight from the raw STIX bundle / CAPEC XML
with its own minimal logic. If the harness called the same code that produced
the graph, a silent-drop bug would be invisible to both.

Only "primary" entities that map 1:1 from a raw object are counted here and used
for full three-way (raw == manifest == live) reconciliation:

* ATT&CK: every canonical node maps 1:1 from a STIX object, so all labels are primary.
* CAPEC: only the top-level ``Attack_Pattern`` / ``Category`` / ``View`` elements are
  primary. The other CAPEC labels (Consequence, ExecutionStep, Mitigation, Skill,
  Weakness, ExternalReference, TaxonomyEntry) are extracted sub-elements and are left
  to the manifest-vs-live check rather than re-parsed here.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from utils.kg_builder.config import BuildConfig
from utils.kg_builder.io import load_json

# Local STIX-type -> canonical-label map. Intentionally duplicated from the build
# so this recount is an independent oracle, not a mirror of the build code.
_STIX_TYPE_TO_LABEL: dict[str, str] = {
    "x-mitre-tactic": "Tactic",
    "attack-pattern": "Technique",
    "intrusion-set": "Group",
    "malware": "Software",
    "tool": "Software",
    "course-of-action": "Mitigation",
    "campaign": "Campaign",
    "x-mitre-data-component": "DataComponent",
    "x-mitre-detection-strategy": "DetectionStrategy",
    "x-mitre-matrix": "Matrix",
}

_CAPEC_NS = "http://capec.mitre.org/capec-3"
# CAPEC statuses that mark a pattern as retired. The build loads them (full
# catalog); the harness records how many so the source card can tell specialists
# to filter on the ``Status`` property.
_CAPEC_RETIRED_STATUSES = frozenset({"Deprecated", "Obsolete"})


@dataclass(frozen=True)
class RawCounts:
    """Independent counts derived directly from a raw source file."""

    dataset: str
    source_path: str
    object_count: int
    nodes_by_label: dict[str, int]
    primary_labels: frozenset[str]
    excluded: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def primary_total(self) -> int:
        return sum(self.nodes_by_label[label] for label in self.primary_labels)


def _require(path: Path, dataset: str) -> Path:
    if not path.exists():
        raise FileNotFoundError(
            f"Raw {dataset} source not found at {path}. Run `uv run main.py --download` first."
        )
    return path


def attack_raw_counts(
    config: BuildConfig,
    *,
    filter_revoked: bool = True,
    filter_deprecated: bool = True,
) -> RawCounts:
    """Recount ATT&CK node labels straight from the raw STIX bundle."""
    source_path = _require(config.paths().attack_raw_file, "attack")
    bundle: dict[str, Any] = load_json(source_path)
    objects: list[dict[str, Any]] = bundle.get("objects", [])

    label_counts: Counter[str] = Counter()
    excluded_revoked = 0
    excluded_deprecated = 0

    for obj in objects:
        stix_type = obj.get("type")
        if stix_type not in _STIX_TYPE_TO_LABEL:
            continue
        if filter_revoked and obj.get("revoked") is True:
            excluded_revoked += 1
            continue
        if filter_deprecated and obj.get("x_mitre_deprecated") is True:
            excluded_deprecated += 1
            continue
        label = _STIX_TYPE_TO_LABEL[stix_type]
        if stix_type == "attack-pattern" and obj.get("x_mitre_is_subtechnique"):
            label = "SubTechnique"
        label_counts[label] += 1

    nodes_by_label = dict(sorted(label_counts.items()))
    return RawCounts(
        dataset="attack",
        source_path=str(source_path),
        object_count=len(objects),
        nodes_by_label=nodes_by_label,
        # Every ATT&CK node maps 1:1 from a STIX object -> all labels reconcilable.
        primary_labels=frozenset(nodes_by_label),
        excluded={"revoked": excluded_revoked, "deprecated": excluded_deprecated},
        notes=[
            f"Excluded {excluded_revoked} revoked and {excluded_deprecated} deprecated "
            "STIX objects (recount policy matches build filter settings).",
        ],
    )


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def capec_raw_counts(config: BuildConfig) -> RawCounts:
    """Recount CAPEC primary entities straight from the raw XML catalog."""
    source_path = _require(config.paths().capec_raw_file, "capec")
    root = ET.parse(source_path).getroot()
    ns = {"c": _CAPEC_NS}

    attack_patterns = root.findall(".//c:Attack_Patterns/c:Attack_Pattern", ns)
    categories = root.findall(".//c:Categories/c:Category", ns)
    views = root.findall(".//c:Views/c:View", ns)

    status_counts: Counter[str] = Counter(
        ap.get("Status", "Unknown") for ap in attack_patterns
    )
    retired = sum(status_counts[s] for s in _CAPEC_RETIRED_STATUSES if s in status_counts)

    nodes_by_label = {
        "AttackPattern": len(attack_patterns),
        "Category": len(categories),
        "View": len(views),
    }
    # Rough object tally across primary + extracted collections for provenance.
    object_count = len(attack_patterns) + len(categories) + len(views)

    return RawCounts(
        dataset="capec",
        source_path=str(source_path),
        object_count=object_count,
        nodes_by_label=nodes_by_label,
        primary_labels=frozenset(nodes_by_label),
        excluded={},  # CAPEC loads the full catalog; nothing excluded.
        notes=[
            "CAPEC loads the full catalog (build_scope=full_catalog); "
            f"{retired} retired attack patterns "
            f"({', '.join(f'{s}={status_counts[s]}' for s in sorted(_CAPEC_RETIRED_STATUSES) if s in status_counts) or 'none'}) "
            "are loaded with their Status property so specialists can filter them.",
            "Only primary top-level entities (AttackPattern/Category/View) are "
            "recounted from raw; extracted child nodes are checked manifest-vs-live.",
        ],
    )


def raw_counts_for(dataset: str, config: BuildConfig, **kwargs: Any) -> RawCounts:
    """Dispatch to the dataset-specific raw recount."""
    if dataset == "attack":
        return attack_raw_counts(config, **kwargs)
    if dataset == "capec":
        return capec_raw_counts(config, **kwargs)
    raise ValueError(f"Unsupported dataset for raw recount: {dataset!r}")
