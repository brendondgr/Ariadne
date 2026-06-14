#!/usr/bin/env python3

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EdgePattern:
    """Allowed source label, relationship type, and target label triple."""

    source_label: str
    relationship_type: str
    target_label: str


ATTACK_EDGE_PATTERNS: frozenset[EdgePattern] = frozenset(
    {
        EdgePattern("Group", "USES", "Technique"),
        EdgePattern("Group", "USES", "SubTechnique"),
        EdgePattern("Group", "USES", "Software"),
        EdgePattern("Software", "USES", "Technique"),
        EdgePattern("Software", "USES", "SubTechnique"),
        EdgePattern("Campaign", "USES", "Technique"),
        EdgePattern("Campaign", "USES", "SubTechnique"),
        EdgePattern("Campaign", "USES", "Software"),
        EdgePattern("Mitigation", "MITIGATES", "Technique"),
        EdgePattern("Mitigation", "MITIGATES", "SubTechnique"),
        EdgePattern("Campaign", "ATTRIBUTED_TO", "Group"),
        EdgePattern("Technique", "HAS_SUBTECHNIQUE", "SubTechnique"),
        EdgePattern("Tactic", "HAS_TECHNIQUE", "Technique"),
        EdgePattern("Tactic", "HAS_TECHNIQUE", "SubTechnique"),
    }
)

REQUIRED_NODE_PROPERTIES = ("id",)

LABELS_REQUIRING_ATTACK_ID = frozenset(
    {"Technique", "SubTechnique", "Mitigation", "Tactic", "Group", "Software", "Campaign"}
)

CAPEC_EDGE_PATTERNS: frozenset[EdgePattern] = frozenset(
    {
        EdgePattern("AttackPattern", "ChildOf", "AttackPattern"),
        EdgePattern("AttackPattern", "ParentOf", "AttackPattern"),
        EdgePattern("AttackPattern", "CanPrecede", "AttackPattern"),
        EdgePattern("AttackPattern", "CanFollow", "AttackPattern"),
        EdgePattern("AttackPattern", "PeerOf", "AttackPattern"),
        EdgePattern("AttackPattern", "CanAlsoBe", "AttackPattern"),
        EdgePattern("AttackPattern", "EXPLOITS_WEAKNESS", "Weakness"),
        EdgePattern("AttackPattern", "MAPS_TO", "TaxonomyEntry"),
        EdgePattern("AttackPattern", "MEMBER_OF", "Category"),
        EdgePattern("AttackPattern", "IN_VIEW", "View"),
        EdgePattern("Category", "IN_VIEW", "View"),
        EdgePattern("AttackPattern", "HAS_EXECUTION_STEP", "ExecutionStep"),
        EdgePattern("ExecutionStep", "NEXT_STEP", "ExecutionStep"),
        EdgePattern("AttackPattern", "REQUIRES_SKILL", "Skill"),
        EdgePattern("AttackPattern", "HAS_CONSEQUENCE", "Consequence"),
        EdgePattern("AttackPattern", "HAS_MITIGATION", "Mitigation"),
        EdgePattern("AttackPattern", "HAS_REFERENCE", "ExternalReference"),
        EdgePattern("Category", "HAS_REFERENCE", "ExternalReference"),
        EdgePattern("View", "HAS_REFERENCE", "ExternalReference"),
    }
)
