#!/usr/bin/env python3

from __future__ import annotations

from typing import Any

from utils.kg_builder.models import CapecGraphMetadata, EdgeRecord, NodeRecord, NormalizedGraph
from utils.kg_builder.preprocess.capec_ids import (
    alternate_term_node_id,
    attack_pattern_node_id,
    category_node_id,
    consequence_node_id,
    example_node_id,
    execution_step_node_id,
    external_reference_node_id,
    indicator_node_id,
    mitigation_node_id,
    prerequisite_node_id,
    relationship_id,
    resource_node_id,
    skill_node_id,
    taxonomy_node_id,
    view_node_id,
    weakness_node_id,
)
from utils.kg_builder.preprocess.capec_models import CapecPairsCheckpoint
from utils.kg_builder.schema.capec import capec_canonical_labels

# CAPEC ``Status`` values that mark an entry as retired. Mirrors ATT&CK's
# exclude-at-load policy for deprecated/revoked objects: retired attack patterns,
# categories, and views (and their exclusive children/edges) are dropped during
# the canonical build so they never surface as islands downstream. Kept in sync
# with ``utils.graph_loader.fixture_qa`` (``_CAPEC_DEAD_STATUSES``).
CAPEC_RETIRED_STATUSES = frozenset({"Deprecated", "Obsolete"})


def materialize_capec_graph(
    checkpoint: CapecPairsCheckpoint,
    *,
    filter_deprecated: bool = True,
) -> NormalizedGraph:
    """Translate normalized CAPEC checkpoint records into canonical graph records.

    When ``filter_deprecated`` is true (the default) every attack pattern,
    category, and view whose ``Status`` is ``Deprecated`` or ``Obsolete`` is
    excluded, along with its exclusive child nodes and any edge that would point
    at it — mirroring ATT&CK's exclude-at-load policy so retired entries never
    enter the canonical graph.
    """
    nodes: list[NodeRecord] = []
    relationships: list[EdgeRecord] = []
    node_index: dict[str, NodeRecord] = {}
    edge_ids: set[str] = set()

    def _retired(records: list[dict[str, Any]]) -> set[str]:
        if not filter_deprecated:
            return set()
        return {
            str(record["id"])
            for record in records
            if record.get("Status") in CAPEC_RETIRED_STATUSES
        }

    retired_pattern_ids = _retired(checkpoint.attack_patterns)
    retired_category_ids = _retired(checkpoint.categories)
    retired_view_ids = _retired(checkpoint.views)
    skipped_count = (
        len(retired_pattern_ids) + len(retired_category_ids) + len(retired_view_ids)
    )

    def add_node(node: NodeRecord) -> None:
        if node.id in node_index:
            return
        node_index[node.id] = node
        nodes.append(node)

    def add_edge(rel_type: str, source_id: str, target_id: str, **properties: Any) -> None:
        edge_id = relationship_id(rel_type, source_id, target_id)
        if edge_id in edge_ids:
            return
        edge_ids.add(edge_id)
        relationships.append(
            EdgeRecord(
                id=edge_id,
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

    def ensure_attack_pattern_node(capec_id: str, *, name: str | None = None) -> str | None:
        """Create/return an AttackPattern node id, or ``None`` if the id is retired."""
        if str(capec_id) in retired_pattern_ids:
            return None
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
        if str(attack_pattern["id"]) in retired_pattern_ids:
            continue
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
        if str(category["id"]) in retired_category_ids:
            continue
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
            if member_node_id is None:
                continue
            add_edge(
                "MEMBER_OF",
                member_node_id,
                node_id,
            )

    for view in checkpoint.views:
        if str(view["id"]) in retired_view_ids:
            continue
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
        if str(ap_id) in retired_pattern_ids:
            continue
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
                    # The five added 2026-09-01 are materialized as nodes, so
                    # they are excluded here for the same reason skills and
                    # consequences are: carrying them as list properties too
                    # would give a retrieval path two representations of one
                    # fact and no rule for which is authoritative.
                    "prerequisites",
                    "indicators",
                    "examples",
                    "resources",
                    "alternate_terms",
                    "related_weaknesses",
                    "taxonomy_mappings",
                    "references",
                }
            },
        )

        for related in attack_pattern.get("related_attack_patterns", []):
            nature = related.get("nature")
            target_ap = related.get("capec_id")
            if nature and target_ap and str(target_ap) not in retired_pattern_ids:
                add_edge(
                    nature,
                    ap_node_id,
                    attack_pattern_node_id(str(target_ap)),
                )

        previous_step_id: str | None = None
        for position, step in enumerate(attack_pattern.get("execution_steps", []), start=1):
            step_number = step.get("step") or "0"
            step_id = execution_step_node_id(ap_id, position)
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
            # Guard the chain link. When two steps collided on an id the
            # previous version emitted `NEXT_STEP` from a node to itself — 9
            # self-loops — and, where the collision was non-adjacent, a back
            # edge that turned the flow into a 2-cycle.
            if previous_step_id and previous_step_id != step_id:
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

        # Five sub-element kinds CAPEC declares that the load previously
        # dropped -- 1,545 instances that no question could reach because the
        # rows were not there. Materialized the same way as skills and
        # consequences: one node per instance, keyed by position, with the
        # pattern owning the edge.
        for field, id_fn, label, rel_type in (
            ("prerequisites", prerequisite_node_id, "Prerequisite", "HAS_PREREQUISITE"),
            ("indicators", indicator_node_id, "Indicator", "HAS_INDICATOR"),
            ("examples", example_node_id, "Example", "HAS_EXAMPLE"),
            ("resources", resource_node_id, "Resource", "REQUIRES_RESOURCE"),
            ("alternate_terms", alternate_term_node_id, "AlternateTerm", "HAS_ALTERNATE_TERM"),
        ):
            for index, item in enumerate(attack_pattern.get(field, []), start=1):
                node_id = id_fn(ap_id, index)
                add_node(
                    NodeRecord(
                        id=node_id,
                        label=label,
                        labels=capec_canonical_labels(label),
                        name=item.get("term") or None,
                        properties={k: v for k, v in item.items() if v is not None},
                    )
                )
                add_edge(rel_type, ap_node_id, node_id)

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
            # OWASP Attacks entries carry only `Entry_Name`. Requiring
            # `Entry_ID` dropped all 39 of them and the 40 MAPS_TO edges that
            # would have reached them — the whole taxonomy, silently. Same bug
            # class as the census hit; see EXP-2026-09-001 I-1 and A-2.
            entry_id = mapping.get("entry_id") or mapping.get("entry_name")
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

    # View members share the CAPEC-ID number space between categories and
    # attack patterns, so each member is resolved against the checkpoint sets.
    # Retired categories/patterns are excluded from the resolvable sets so no
    # IN_VIEW edge is drawn to a node that was dropped.
    known_category_ids = {
        str(category["id"])
        for category in checkpoint.categories
        if str(category["id"]) not in retired_category_ids
    }
    known_pattern_ids = {
        str(attack_pattern["id"])
        for attack_pattern in checkpoint.attack_patterns
        if str(attack_pattern["id"]) not in retired_pattern_ids
    }
    for view in checkpoint.views:
        if str(view["id"]) in retired_view_ids:
            continue
        view_id = view_node_id(view["id"])
        for member in view.get("members", []):
            member_id = str(member)
            if member_id in known_category_ids:
                add_edge("IN_VIEW", category_node_id(member_id), view_id)
            elif member_id in known_pattern_ids:
                add_edge("IN_VIEW", attack_pattern_node_id(member_id), view_id)

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
        skipped_count=skipped_count,
    )
    return NormalizedGraph(metadata=metadata, nodes=nodes, relationships=relationships)
