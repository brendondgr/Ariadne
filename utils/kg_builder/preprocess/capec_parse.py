#!/usr/bin/env python3

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from utils.kg_builder.source.capec import CAPEC_NAMESPACE

XHTML_NAMESPACE = "http://www.w3.org/1999/xhtml"
NS = {"c": CAPEC_NAMESPACE, "xhtml": XHTML_NAMESPACE}


def local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def element_text(element: ET.Element) -> str:
    """Extract deterministic trimmed text, including nested XHTML content."""
    parts: list[str] = []

    def collect(node: ET.Element) -> None:
        if node.text:
            parts.append(node.text)
        for child in list(node):
            collect(child)
            if child.tail:
                parts.append(child.tail)

    collect(element)
    return " ".join(" ".join(parts).split())


def child_elements(parent: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in list(parent) if local_name(child.tag) == name]


def child_texts(parent: ET.Element, name: str) -> list[str]:
    return [element_text(child) for child in child_elements(parent, name) if element_text(child)]


def attributes_dict(element: ET.Element, keys: tuple[str, ...]) -> dict[str, str]:
    return {key: value for key in keys if (value := element.attrib.get(key))}


def record_unmapped(
    unmapped_fields: list[dict[str, Any]],
    *,
    entity_type: str,
    entity_id: str,
    source_path: str,
    field_name: str,
    value: Any,
) -> None:
    unmapped_fields.append(
        {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "source_path": source_path,
            "field_name": field_name,
            "value": value,
        }
    )


def normalize_attack_pattern(
    element: ET.Element,
    *,
    source_path: str,
    unmapped_fields: list[dict[str, Any]],
) -> dict[str, Any]:
    entity_id = element.attrib["ID"]
    record: dict[str, Any] = {
        "id": entity_id,
        "source_path": f"{source_path}/Attack_Patterns/Attack_Pattern[@ID='{entity_id}']",
        **attributes_dict(element, ("Name", "Abstraction", "Status")),
        "description": element_text(child_elements(element, "Description")[0])
        if child_elements(element, "Description")
        else None,
        "related_attack_patterns": [],
        "execution_steps": [],
        "skills": [],
        "consequences": [],
        "mitigations": [],
        "related_weaknesses": [],
        "taxonomy_mappings": [],
        "references": [],
    }

    if child_elements(element, "Related_Attack_Patterns"):
        record["related_attack_patterns"] = [
            {
                "nature": rel.attrib.get("Nature"),
                "capec_id": rel.attrib.get("CAPEC_ID"),
            }
            for rel in child_elements(
                child_elements(element, "Related_Attack_Patterns")[0],
                "Related_Attack_Pattern",
            )
        ]

    execution_flow = child_elements(element, "Execution_Flow")
    if execution_flow:
        for step in child_elements(execution_flow[0], "Attack_Step"):
            step_number = child_texts(step, "Step")
            record["execution_steps"].append(
                {
                    "step": step_number[0] if step_number else None,
                    "phase": child_texts(step, "Phase")[0] if child_texts(step, "Phase") else None,
                    "description": child_texts(step, "Description")[0]
                    if child_texts(step, "Description")
                    else None,
                    "techniques": child_texts(step, "Technique"),
                }
            )

    for skill in child_elements(child_elements(element, "Skills_Required")[0], "Skill") if child_elements(element, "Skills_Required") else []:
        record["skills"].append(
            {
                "level": skill.attrib.get("Level"),
                "description": element_text(skill),
            }
        )

    for consequence in child_elements(child_elements(element, "Consequences")[0], "Consequence") if child_elements(element, "Consequences") else []:
        record["consequences"].append(
            {
                "scopes": child_texts(consequence, "Scope"),
                "impacts": child_texts(consequence, "Impact"),
            }
        )

    for mitigation in child_elements(child_elements(element, "Mitigations")[0], "Mitigation") if child_elements(element, "Mitigations") else []:
        record["mitigations"].append({"description": element_text(mitigation)})

    for weakness in child_elements(child_elements(element, "Related_Weaknesses")[0], "Related_Weakness") if child_elements(element, "Related_Weaknesses") else []:
        record["related_weaknesses"].append({"cwe_id": weakness.attrib.get("CWE_ID")})

    for mapping in child_elements(child_elements(element, "Taxonomy_Mappings")[0], "Taxonomy_Mapping") if child_elements(element, "Taxonomy_Mappings") else []:
        record["taxonomy_mappings"].append(
            {
                "taxonomy_name": mapping.attrib.get("Taxonomy_Name"),
                "entry_id": child_texts(mapping, "Entry_ID")[0] if child_texts(mapping, "Entry_ID") else None,
                "entry_name": child_texts(mapping, "Entry_Name")[0]
                if child_texts(mapping, "Entry_Name")
                else None,
            }
        )

    for reference in child_elements(child_elements(element, "References")[0], "Reference") if child_elements(element, "References") else []:
        record["references"].append(
            {"external_reference_id": reference.attrib.get("External_Reference_ID")}
        )

    mapped_children = {
        "Description",
        "Related_Attack_Patterns",
        "Execution_Flow",
        "Skills_Required",
        "Consequences",
        "Mitigations",
        "Related_Weaknesses",
        "Taxonomy_Mappings",
        "References",
    }
    for child in list(element):
        name = local_name(child.tag)
        if name not in mapped_children:
            record_unmapped(
                unmapped_fields,
                entity_type="attack_pattern",
                entity_id=entity_id,
                source_path=record["source_path"],
                field_name=name,
                value=element_text(child) or dict(child.attrib),
            )

    return record


def normalize_category(
    element: ET.Element,
    *,
    source_path: str,
    unmapped_fields: list[dict[str, Any]],
) -> dict[str, Any]:
    entity_id = element.attrib["ID"]
    record: dict[str, Any] = {
        "id": entity_id,
        "source_path": f"{source_path}/Categories/Category[@ID='{entity_id}']",
        **attributes_dict(element, ("Name", "Status")),
        "summary": child_texts(element, "Summary")[0] if child_texts(element, "Summary") else None,
        "members": [],
    }

    relationships = child_elements(element, "Relationships")
    if relationships:
        record["members"] = [
            member.attrib.get("CAPEC_ID")
            for member in child_elements(relationships[0], "Has_Member")
        ]

    for child in list(element):
        name = local_name(child.tag)
        if name not in {"Summary", "Relationships"}:
            record_unmapped(
                unmapped_fields,
                entity_type="category",
                entity_id=entity_id,
                source_path=record["source_path"],
                field_name=name,
                value=element_text(child) or dict(child.attrib),
            )

    return record


def normalize_view(
    element: ET.Element,
    *,
    source_path: str,
    unmapped_fields: list[dict[str, Any]],
) -> dict[str, Any]:
    entity_id = element.attrib["ID"]
    record: dict[str, Any] = {
        "id": entity_id,
        "source_path": f"{source_path}/Views/View[@ID='{entity_id}']",
        **attributes_dict(element, ("Name", "Type", "Status")),
        "objective": child_texts(element, "Objective")[0] if child_texts(element, "Objective") else None,
        "members": [],
    }

    # Graph-type views enumerate members as <Members><Has_Member CAPEC_ID=...>;
    # filter-type views define membership implicitly and stay member-less.
    members = child_elements(element, "Members")
    if members:
        record["members"] = [
            member.attrib.get("CAPEC_ID")
            for member in child_elements(members[0], "Has_Member")
        ]

    for child in list(element):
        name = local_name(child.tag)
        if name not in {"Objective", "Members"}:
            record_unmapped(
                unmapped_fields,
                entity_type="view",
                entity_id=entity_id,
                source_path=record["source_path"],
                field_name=name,
                value=element_text(child) or dict(child.attrib),
            )

    return record


def normalize_external_reference(
    element: ET.Element,
    *,
    source_path: str,
    unmapped_fields: list[dict[str, Any]],
) -> dict[str, Any]:
    entity_id = element.attrib["Reference_ID"]
    record: dict[str, Any] = {
        "id": entity_id,
        "source_path": f"{source_path}/External_References/External_Reference[@Reference_ID='{entity_id}']",
        "author": child_texts(element, "Author")[0] if child_texts(element, "Author") else None,
        "title": child_texts(element, "Title")[0] if child_texts(element, "Title") else None,
        "publication_year": child_texts(element, "Publication_Year")[0]
        if child_texts(element, "Publication_Year")
        else None,
    }

    for child in list(element):
        name = local_name(child.tag)
        if name not in {"Author", "Title", "Publication_Year"}:
            record_unmapped(
                unmapped_fields,
                entity_type="external_reference",
                entity_id=entity_id,
                source_path=record["source_path"],
                field_name=name,
                value=element_text(child) or dict(child.attrib),
            )

    return record
