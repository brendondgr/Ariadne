#!/usr/bin/env python3

from __future__ import annotations

import re


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())


def attack_pattern_node_id(capec_id: str) -> str:
    return f"capec:attack-pattern:{capec_id}"


def category_node_id(category_id: str) -> str:
    return f"capec:category:{category_id}"


def view_node_id(view_id: str) -> str:
    return f"capec:view:{view_id}"


def weakness_node_id(cwe_id: str) -> str:
    return f"cwe:{cwe_id}"


def taxonomy_node_id(taxonomy_name: str, entry_id: str) -> str:
    return f"capec:taxonomy:{_slug(taxonomy_name)}:{_slug(entry_id)}"


def external_reference_node_id(reference_id: str) -> str:
    return f"capec:external-reference:{reference_id}"


def execution_step_node_id(attack_pattern_id: str, step_number: str) -> str:
    return f"capec:attack-pattern:{attack_pattern_id}:step:{_slug(step_number)}"


def skill_node_id(attack_pattern_id: str, index: int) -> str:
    return f"capec:attack-pattern:{attack_pattern_id}:skill:{index}"


def consequence_node_id(attack_pattern_id: str, index: int) -> str:
    return f"capec:attack-pattern:{attack_pattern_id}:consequence:{index}"


def mitigation_node_id(attack_pattern_id: str, index: int) -> str:
    return f"capec:attack-pattern:{attack_pattern_id}:mitigation:{index}"


def relationship_id(rel_type: str, source_id: str, target_id: str) -> str:
    return f"capec:rel:{rel_type}:{source_id}->{target_id}"
