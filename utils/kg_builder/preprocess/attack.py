#!/usr/bin/env python3

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import BuildConfig
from ..io import load_json
from ..models import GraphMetadata, GraphNode, GraphRelationship, NormalizedGraph
from ..schema.attack import neo4j_relationship_type

logger = logging.getLogger(__name__)

STIX_TYPE_TO_LABEL: dict[str, str] = {
    "x-mitre-tactic": "Tactic",
    "attack-pattern": "Technique",
    "intrusion-set": "Group",
    "malware": "Software",
    "tool": "Software",
    "course-of-action": "Mitigation",
    "campaign": "Campaign",
    "x-mitre-data-source": "DataSource",
    "x-mitre-data-component": "DataComponent",
    "x-mitre-asset": "Asset",
    "x-mitre-matrix": "Matrix",
}

NODE_PROPERTY_KEYS = (
    "id",
    "name",
    "description",
    "external_references",
    "x_mitre_platforms",
    "x_mitre_version",
    "x_mitre_deprecated",
    "revoked",
    "x_mitre_shortname",
    "x_mitre_is_subtechnique",
)


@dataclass(frozen=True)
class AttackBundleLoadResult:
    """Result of loading a raw ATT&CK STIX bundle."""

    bundle: dict[str, Any]
    source_path: Path
    bundle_id: str | None
    object_count: int
    attack_version: str


def load_attack_bundle(config: BuildConfig) -> AttackBundleLoadResult:
    """Locate and load the pinned ATT&CK Enterprise STIX bundle."""
    paths = config.paths()
    source_path = paths.attack_raw_file

    if not source_path.exists():
        raise FileNotFoundError(
            f"ATT&CK raw dataset not found at {source_path}. "
            "Run `uv run main.py --download` first."
        )

    bundle = load_json(source_path)
    if bundle.get("type") != "bundle":
        raise ValueError(f"Expected STIX bundle at {source_path}, got type={bundle.get('type')!r}")

    objects = bundle.get("objects")
    if not isinstance(objects, list):
        raise ValueError(f"STIX bundle at {source_path} is missing an objects array.")

    logger.info(
        "Loaded ATT&CK bundle id=%s objects=%d version=%s from %s",
        bundle.get("id"),
        len(objects),
        config.attack_version,
        source_path,
    )

    return AttackBundleLoadResult(
        bundle=bundle,
        source_path=source_path,
        bundle_id=bundle.get("id"),
        object_count=len(objects),
        attack_version=config.attack_version,
    )


def _attack_external_id(obj: dict[str, Any]) -> str | None:
    for ref in obj.get("external_references", []):
        if ref.get("source_name") == "mitre-attack":
            return ref.get("external_id")
    return None


def _node_label(obj: dict[str, Any]) -> str | None:
    stix_type = obj.get("type")
    if stix_type not in STIX_TYPE_TO_LABEL:
        return None
    if stix_type == "attack-pattern" and obj.get("x_mitre_is_subtechnique"):
        return "SubTechnique"
    return STIX_TYPE_TO_LABEL[stix_type]


def _should_filter(obj: dict[str, Any], config: BuildConfig) -> str | None:
    if config.filter_revoked and obj.get("revoked") is True:
        return "revoked"
    if config.filter_deprecated and obj.get("x_mitre_deprecated") is True:
        return "deprecated"
    return None


def _node_properties(obj: dict[str, Any]) -> dict[str, Any]:
    props: dict[str, Any] = {}
    for key in NODE_PROPERTY_KEYS:
        if key in obj:
            props[key] = obj[key]
    return props


class AttackPreprocessor:
    """Convert ATT&CK STIX bundle objects into a normalized graph model."""

    def __init__(self, config: BuildConfig) -> None:
        self.config = config

    def preprocess(
        self,
        bundle: dict[str, Any],
        *,
        source_path: str | Path | None = None,
        bundle_id: str | None = None,
    ) -> NormalizedGraph:
        objects: list[dict[str, Any]] = bundle.get("objects", [])
        filtered_deprecated = 0
        filtered_revoked = 0

        nodes: list[GraphNode] = []
        relationships: list[GraphRelationship] = []
        node_by_id: dict[str, GraphNode] = {}
        tactic_by_shortname: dict[str, str] = {}

        for obj in objects:
            if obj.get("type") == "relationship":
                continue

            label = _node_label(obj)
            if label is None:
                continue

            reason = _should_filter(obj, self.config)
            if reason == "deprecated":
                filtered_deprecated += 1
                continue
            if reason == "revoked":
                filtered_revoked += 1
                continue

            node = GraphNode(
                id=obj["id"],
                label=label,
                attack_id=_attack_external_id(obj),
                name=obj.get("name"),
                description=obj.get("description"),
                stix_type=obj.get("type"),
                properties=_node_properties(obj),
            )
            nodes.append(node)
            node_by_id[node.id] = node

            if label == "Tactic":
                shortname = obj.get("x_mitre_shortname")
                if shortname:
                    tactic_by_shortname[shortname] = node.id

        for obj in objects:
            if obj.get("type") != "relationship":
                continue

            reason = _should_filter(obj, self.config)
            if reason:
                continue

            source_id = obj.get("source_ref")
            target_id = obj.get("target_ref")
            rel_type_raw = obj.get("relationship_type", "")
            rel_type = neo4j_relationship_type(rel_type_raw)

            if rel_type_raw == "subtechnique-of":
                source_id, target_id = target_id, source_id
                rel_type = "HAS_SUBTECHNIQUE"

            if source_id not in node_by_id or target_id not in node_by_id:
                continue

            relationships.append(
                GraphRelationship(
                    id=obj["id"],
                    type=rel_type,
                    source_id=source_id,
                    target_id=target_id,
                    stix_type="relationship",
                    properties={
                        "relationship_type": rel_type_raw,
                        "description": obj.get("description"),
                    },
                )
            )

        for obj in objects:
            if obj.get("type") != "attack-pattern":
                continue
            if _should_filter(obj, self.config):
                continue
            if obj["id"] not in node_by_id:
                continue

            for phase in obj.get("kill_chain_phases", []):
                if phase.get("kill_chain_name") != "mitre-attack":
                    continue
                tactic_id = tactic_by_shortname.get(phase.get("phase_name", ""))
                if tactic_id is None:
                    continue
                rel_id = f"derived--has-technique--{tactic_id}--{obj['id']}"
                relationships.append(
                    GraphRelationship(
                        id=rel_id,
                        type="HAS_TECHNIQUE",
                        source_id=tactic_id,
                        target_id=obj["id"],
                        stix_type="derived",
                        properties={"phase_name": phase.get("phase_name")},
                    )
                )

        nodes.sort(key=lambda n: n.id)
        relationships.sort(key=lambda r: (r.type, r.source_id, r.target_id, r.id))

        metadata = GraphMetadata(
            source_path=str(source_path or self.config.paths().attack_raw_file),
            bundle_id=bundle_id or bundle.get("id"),
            attack_version=self.config.attack_version,
            object_count=len(objects),
            filtered_deprecated=filtered_deprecated,
            filtered_revoked=filtered_revoked,
        )

        return NormalizedGraph(metadata=metadata, nodes=nodes, relationships=relationships)
