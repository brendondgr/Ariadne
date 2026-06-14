#!/usr/bin/env python3

from __future__ import annotations

from typing import Any

from utils.kg_builder.models import CapecGraphMetadata, EdgeRecord, NodeRecord, NormalizedGraph
from utils.kg_builder.preprocess.capec_ids import (
    attack_pattern_node_id,
    category_node_id,
    consequence_node_id,
    execution_step_node_id,
    external_reference_node_id,
    mitigation_node_id,
    relationship_id,
    skill_node_id,
    taxonomy_node_id,
    view_node_id,
    weakness_node_id,
)
from utils.kg_builder.preprocess.capec_models import CapecPairsCheckpoint
from utils.kg_builder.schema.capec import capec_canonical_labels


def materialize_capec_graph(checkpoint: CapecPairsCheckpoint) -> NormalizedGraph:
    """Translate normalized CAPEC checkpoint records into canonical graph records."""
    nodes: list[NodeRecord] = []
    relationships: list[EdgeRecord] = []
    node_index: dict[str, NodeRecord] = {}

    def add_node(node: NodeRecord) -> None:
        if node.id in node_index:
            return
        node_index[node.id] = node
        nodes.append(node)

    def add_edge(rel_type: str, source_id: str, target_id: str, **properties: Any) -> None:
        relationships.append(
            EdgeRecord(
                id=relationship_id(rel_type, source_id, target_id),
                type=rel_type,
                source_id=source_id,
                target_id=target_id,
                properties=properties,
            )
        )

    def ensure_external_reference_node(reference_id: str) -> str:
        node_id = external_reference_node_id(reference_id)
        if node_id not in node_index:
            add_node(
                NodeRecord(
                    id=node_id,
                    label="ExternalReference",
                    labels=capec_canonical_labels("ExternalReference"),
                    properties={
                        "id": reference_id,
                        "resolved_from_reference": True,
                    },
                )
            )
        return node_id

    for external_reference in checkpoint.external_references:
        node_id = external_reference_node_id(external_reference["id"])
        add_node(
            NodeRecord(
                id=node_id,
                label="ExternalReference",
                labels=capec_canonical_labels("ExternalReference"),
                name=external_reference.get("title"),
                properties={
                    key: value
                    for key, value in external_reference.items()
                    if key not in {"id", "source_path"}
                },
            )
        )

    def ensure_attack_pattern_node(capec_id: str, *, name: str | None = None) -> str:
        node_id = attack_pattern_node_id(str(capec_id))
        if node_id not in node_index:
            add_node(
                NodeRecord(
                    id=node_id,
                    label="AttackPattern",
                    labels=capec_canonical_labels("AttackPattern"),
                    name=name,
                    properties={"capec_id": str(capec_id), "resolved_from_reference": name is None},
                )
            )
        return node_id

    for attack_pattern in checkpoint.attack_patterns:
        ensure_attack_pattern_node(attack_pattern["id"], name=attack_pattern.get("Name"))
        for related in attack_pattern.get("related_attack_patterns", []):
            target_ap = related.get("capec_id")
            if target_ap:
                ensure_attack_pattern_node(str(target_ap))
        for reference in attack_pattern.get("references", []):
            ref_id = reference.get("external_reference_id")
            if ref_id:
                ensure_external_reference_node(ref_id)

    for category in checkpoint.categories:
        node_id = category_node_id(category["id"])
        add_node(
            NodeRecord(
                id=node_id,
                label="Category",
                labels=capec_canonical_labels("Category"),
                name=category.get("Name"),
                properties={
                    key: value
                    for key, value in category.items()
                    if key not in {"id", "Name", "source_path", "members"}
                },
            )
        )
        for member_id in category.get("members", []):
            member_node_id = ensure_attack_pattern_node(str(member_id))
            add_edge(
                "MEMBER_OF",
                member_node_id,
                node_id,
            )

    for view in checkpoint.views:
        node_id = view_node_id(view["id"])
        add_node(
            NodeRecord(
                id=node_id,
                label="View",
                labels=capec_canonical_labels("View"),
                name=view.get("Name"),
                properties={
                    key: value
                    for key, value in view.items()
                    if key not in {"id", "Name", "source_path", "member_of"}
                },
            )
        )

    for attack_pattern in checkpoint.attack_patterns:
        ap_id = attack_pattern["id"]
        ap_node_id = ensure_attack_pattern_node(ap_id, name=attack_pattern.get("Name"))
        existing = node_index[ap_node_id]
        node_index[ap_node_id] = NodeRecord(
            id=existing.id,
            label=existing.label,
            labels=existing.labels,
            name=attack_pattern.get("Name"),
            properties={
                key: value
                for key, value in attack_pattern.items()
                if key
                not in {
                    "id",
                    "Name",
                    "source_path",
                    "related_attack_patterns",
                    "execution_steps",
                    "skills",
                    "consequences",
                    "mitigations",
                    "related_weaknesses",
                    "taxonomy_mappings",
                    "references",
                }
            },
        )

        for related in attack_pattern.get("related_attack_patterns", []):
            nature = related.get("nature")
            target_ap = related.get("capec_id")
            if nature and target_ap:
                add_edge(
                    nature,
                    ap_node_id,
                    attack_pattern_node_id(str(target_ap)),
                )

        previous_step_id: str | None = None
        for step in attack_pattern.get("execution_steps", []):
            step_number = step.get("step") or "0"
            step_id = execution_step_node_id(ap_id, str(step_number))
            add_node(
                NodeRecord(
                    id=step_id,
                    label="ExecutionStep",
                    labels=capec_canonical_labels("ExecutionStep"),
                    name=f"Step {step_number}",
                    properties={"step": step_number, **{key: value for key, value in step.items() if key != "step"}},
                )
            )
            add_edge("HAS_EXECUTION_STEP", ap_node_id, step_id, step=step_number)
            if previous_step_id:
                add_edge("NEXT_STEP", previous_step_id, step_id)
            previous_step_id = step_id

        for index, skill in enumerate(attack_pattern.get("skills", []), start=1):
            skill_id = skill_node_id(ap_id, index)
            add_node(
                NodeRecord(
                    id=skill_id,
                    label="Skill",
                    labels=capec_canonical_labels("Skill"),
                    properties=skill,
                )
            )
            add_edge("REQUIRES_SKILL", ap_node_id, skill_id)

        for index, consequence in enumerate(attack_pattern.get("consequences", []), start=1):
            consequence_id = consequence_node_id(ap_id, index)
            add_node(
                NodeRecord(
                    id=consequence_id,
                    label="Consequence",
                    labels=capec_canonical_labels("Consequence"),
                    properties=consequence,
                )
            )
            add_edge("HAS_CONSEQUENCE", ap_node_id, consequence_id)

        for index, mitigation in enumerate(attack_pattern.get("mitigations", []), start=1):
            mitigation_id = mitigation_node_id(ap_id, index)
            add_node(
                NodeRecord(
                    id=mitigation_id,
                    label="Mitigation",
                    labels=capec_canonical_labels("Mitigation"),
                    properties=mitigation,
                )
            )
            add_edge("HAS_MITIGATION", ap_node_id, mitigation_id)

        for weakness in attack_pattern.get("related_weaknesses", []):
            cwe_id = weakness.get("cwe_id")
            if not cwe_id:
                continue
            weakness_id = weakness_node_id(str(cwe_id))
            add_node(
                NodeRecord(
                    id=weakness_id,
                    label="Weakness",
                    labels=capec_canonical_labels("Weakness"),
                    name=f"CWE-{cwe_id}",
                    properties={"cwe_id": str(cwe_id)},
                )
            )
            add_edge("EXPLOITS_WEAKNESS", ap_node_id, weakness_id)

        for mapping in attack_pattern.get("taxonomy_mappings", []):
            taxonomy_name = mapping.get("taxonomy_name")
            entry_id = mapping.get("entry_id")
            if not taxonomy_name or not entry_id:
                continue
            tax_id = taxonomy_node_id(taxonomy_name, entry_id)
            add_node(
                NodeRecord(
                    id=tax_id,
                    label="TaxonomyEntry",
                    labels=capec_canonical_labels("TaxonomyEntry"),
                    name=mapping.get("entry_name"),
                    properties={
                        "taxonomy_name": taxonomy_name,
                        "entry_id": entry_id,
                        "entry_name": mapping.get("entry_name"),
                    },
                )
            )
            add_edge("MAPS_TO", ap_node_id, tax_id)

        for reference in attack_pattern.get("references", []):
            ref_id = reference.get("external_reference_id")
            if not ref_id:
                continue
            ref_node_id = ensure_external_reference_node(ref_id)
            add_edge("HAS_REFERENCE", ap_node_id, ref_node_id)

    for view in checkpoint.views:
        view_id = view_node_id(view["id"])
        for member in view.get("member_of", []):
            category_id = category_node_id(str(member))
            add_edge("IN_VIEW", category_id, view_id)

    nodes = sorted(node_index.values(), key=lambda node: node.id)
    relationships.sort(key=lambda rel: (rel.type, rel.id))

    metadata = CapecGraphMetadata(
        source_path=checkpoint.metadata.source_path,
        source_version=checkpoint.metadata.catalog_version,
        source_date=checkpoint.metadata.catalog_date,
        namespace=checkpoint.metadata.namespace,
        build_scope=checkpoint.metadata.build_scope,
        object_count=sum(checkpoint.counts.values()),
        quarantined_count=checkpoint.counts["unmapped_fields"],
    )
    return NormalizedGraph(metadata=metadata, nodes=nodes, relationships=relationships)
