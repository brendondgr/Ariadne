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
