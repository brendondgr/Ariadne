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


def execution_step_node_id(attack_pattern_id: str, position: int) -> str:
    """Id for one step of one pattern's execution flow, keyed by **position**.

    Not by step number. CAPEC restarts `<Step>` numbering at 1 in each phase
    (Explore / Experiment / Exploit), and a few patterns repeat a number inside
    one phase as well, so neither the number nor number-plus-phase is unique
    within a flow. Keying on the number silently dropped 21 steps across 11
    patterns — the loader's `add_node` returns early on a duplicate id, so the
    *first* step with a number won and later ones vanished, with the loss
    systematically biased toward Exploit-phase steps, the terminal and
    highest-value part of each flow. Found by reconciling the census against the
    load (EXP-2026-09-001 A-2).

    Document position is unique by construction and stable under re-parse. The
    step number and phase remain node properties, so a question can still ask
    about them.
    """
    return f"capec:attack-pattern:{attack_pattern_id}:step:{position}"


def skill_node_id(attack_pattern_id: str, index: int) -> str:
    return f"capec:attack-pattern:{attack_pattern_id}:skill:{index}"


def consequence_node_id(attack_pattern_id: str, index: int) -> str:
    return f"capec:attack-pattern:{attack_pattern_id}:consequence:{index}"


def mitigation_node_id(attack_pattern_id: str, index: int) -> str:
    return f"capec:attack-pattern:{attack_pattern_id}:mitigation:{index}"


def prerequisite_node_id(attack_pattern_id: str, index: int) -> str:
    return f"capec:attack-pattern:{attack_pattern_id}:prerequisite:{index}"


def indicator_node_id(attack_pattern_id: str, index: int) -> str:
    return f"capec:attack-pattern:{attack_pattern_id}:indicator:{index}"


def example_node_id(attack_pattern_id: str, index: int) -> str:
    return f"capec:attack-pattern:{attack_pattern_id}:example:{index}"


def resource_node_id(attack_pattern_id: str, index: int) -> str:
    return f"capec:attack-pattern:{attack_pattern_id}:resource:{index}"


def alternate_term_node_id(attack_pattern_id: str, index: int) -> str:
    return f"capec:attack-pattern:{attack_pattern_id}:alternate-term:{index}"


def relationship_id(rel_type: str, source_id: str, target_id: str) -> str:
    return f"capec:rel:{rel_type}:{source_id}->{target_id}"
