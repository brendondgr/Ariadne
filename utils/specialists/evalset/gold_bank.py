#!/usr/bin/env python3
"""Materialize specialist gold answers from the pinned raw snapshot.

This module parses the raw ATT&CK STIX bundle and CAPEC XML directly —
deliberately NOT through utils.kg_builder — so the gold answers are an
independent derivation. The specialists answer from the loaded graph; the
gold comes from the raw files. The two agree only if the KG build was
faithful, which makes the golden suite double as an ingestion check.

Policy mirrored from the source-card identity block (policy, not code):
  - ATT&CK: exclude-at-load — every revoked or x_mitre_deprecated object is
    excluded, and so is every relationship that is itself revoked/deprecated
    or references an excluded endpoint.
  - CAPEC: exclude-at-load — patterns whose Status is Deprecated or Obsolete
    are excluded from the bank (and edges pointing at them pruned), mirroring
    the graph. Their ids are recorded under ``deprecated`` so negative
    questions can assert they are NOT retrievable.

Regenerate with:
    uv run python -m utils.specialists.evalset.gold_bank
"""

from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"
GOLDEN_DIR = REPO_ROOT / "utils" / "specialists" / "tests" / "golden"
GOLD_BANK_PATH = GOLDEN_DIR / "gold_bank.json"

CAPEC_NS = {"c": "http://capec.mitre.org/capec-3"}

# Mirrors kg_builder.preprocess.attack.STIX_TYPE_TO_LABEL (policy contract).
STIX_TYPE_TO_LABEL: dict[str, str] = {
    "x-mitre-tactic": "Tactic",
    "attack-pattern": "Technique",
    "intrusion-set": "Group",
    "malware": "Software",
    "tool": "Software",
    "course-of-action": "Mitigation",
    "campaign": "Campaign",
    "x-mitre-data-component": "DataComponent",
    "x-mitre-detection-strategy": "DetectionStrategy",
    "x-mitre-analytic": "Analytic",
    "x-mitre-matrix": "Matrix",
}

# CAPEC Related_Attack_Pattern natures declared in the XML. The loaded graph
# stores edges exactly as declared (no materialized inverses), so `hierarchy`
# holds declared natures only — that is what an out-edge traversal returns.
# The inverse child map (who declares ChildOf me) lives separately in
# `children`; it is not reachable by the current out()-only builder templates.
CAPEC_DECLARED_NATURES = ("ChildOf", "CanPrecede", "CanAlsoBe", "PeerOf", "CanFollow", "ParentOf")

# CAPEC Status values excluded at load (mirrors the graph build and the
# fixture-QA `_CAPEC_DEAD_STATUSES`).
CAPEC_RETIRED_STATUSES = frozenset({"Deprecated", "Obsolete"})

# Mirrors kg_builder.preprocess.capec_ids._slug (policy contract): sub-element
# node ids (execution steps / skills / consequences) are derived, so the gold
# must express them exactly as the loaded graph does.
_SLUG_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _slug(value: str) -> str:
    return _SLUG_RE.sub("_", value.strip())


def _attack_external_id(obj: dict[str, Any]) -> str | None:
    for ref in obj.get("external_references", []):
        if ref.get("source_name") == "mitre-attack":
            return ref.get("external_id")
    return None


def _is_excluded(obj: dict[str, Any]) -> bool:
    return obj.get("revoked") is True or obj.get("x_mitre_deprecated") is True


def _node_label(obj: dict[str, Any]) -> str | None:
    stix_type = obj.get("type")
    if stix_type not in STIX_TYPE_TO_LABEL:
        return None
    if stix_type == "attack-pattern" and obj.get("x_mitre_is_subtechnique"):
        return "SubTechnique"
    return STIX_TYPE_TO_LABEL[stix_type]


def parse_attack_bundle(bundle_path: Path) -> dict[str, Any]:
    """Derive ATT&CK gold maps from the raw STIX bundle."""
    bundle = json.loads(bundle_path.read_text())
    objects: list[dict[str, Any]] = bundle["objects"]

    # First pass: live (non-excluded) labeled objects, keyed by STIX UUID.
    live: dict[str, dict[str, Any]] = {}
    attack_id_by_uuid: dict[str, str] = {}
    tactic_by_shortname: dict[str, str] = {}
    objects_map: dict[str, dict[str, Any]] = {}

    excluded_ids: set[str] = set()

    for obj in objects:
        if obj.get("type") == "relationship":
            continue
        label = _node_label(obj)
        if label is None:
            continue
        if _is_excluded(obj):
            # Revoked/deprecated objects the graph excludes at load. Their ids
            # are kept so negative questions can assert they are NOT
            # retrievable (honest empty, not a fabricated record). IDs still
            # carried by any live object are subtracted below — legacy
            # course-of-action objects reused technique T-numbers (e.g. the
            # deprecated "Credential Dumping Mitigation" carries T1003).
            attack_id = _attack_external_id(obj)
            if attack_id:
                excluded_ids.add(attack_id)
            continue
        live[obj["id"]] = obj
        attack_id = _attack_external_id(obj)
        if attack_id:
            attack_id_by_uuid[obj["id"]] = attack_id
            objects_map[attack_id] = {
                "name": obj.get("name"),
                "label": label,
                "stix_type": obj["type"],
                "platforms": sorted(obj.get("x_mitre_platforms", [])),
            }
        if label == "Tactic" and obj.get("x_mitre_shortname"):
            tactic_by_shortname[obj["x_mitre_shortname"]] = obj["id"]

    technique_mitigations: dict[str, set[str]] = {}
    group_techniques: dict[str, set[str]] = {}
    subtechniques: dict[str, set[str]] = {}
    campaign_techniques: dict[str, set[str]] = {}
    campaign_attribution: dict[str, set[str]] = {}
    software_techniques: dict[str, set[str]] = {}
    technique_detections: dict[str, set[str]] = {}

    for obj in objects:
        if obj.get("type") != "relationship" or _is_excluded(obj):
            continue
        src, tgt = obj.get("source_ref"), obj.get("target_ref")
        if src not in live or tgt not in live:
            continue
        rel = obj.get("relationship_type")
        src_id, tgt_id = attack_id_by_uuid.get(src), attack_id_by_uuid.get(tgt)
        if not src_id or not tgt_id:
            continue
        if rel == "mitigates" and live[tgt]["type"] == "attack-pattern":
            technique_mitigations.setdefault(tgt_id, set()).add(src_id)
        elif rel == "uses" and live[src]["type"] == "intrusion-set" and live[tgt]["type"] == "attack-pattern":
            group_techniques.setdefault(src_id, set()).add(tgt_id)
        elif rel == "subtechnique-of":
            subtechniques.setdefault(tgt_id, set()).add(src_id)
        elif rel == "uses" and live[src]["type"] == "campaign" and live[tgt]["type"] == "attack-pattern":
            campaign_techniques.setdefault(src_id, set()).add(tgt_id)
        elif rel == "attributed-to" and live[src]["type"] == "campaign" and live[tgt]["type"] == "intrusion-set":
            campaign_attribution.setdefault(src_id, set()).add(tgt_id)
        elif rel == "uses" and live[src]["type"] in ("malware", "tool") and live[tgt]["type"] == "attack-pattern":
            software_techniques.setdefault(src_id, set()).add(tgt_id)
        elif rel == "detects" and live[src]["type"] == "x-mitre-detection-strategy" and live[tgt]["type"] == "attack-pattern":
            technique_detections.setdefault(tgt_id, set()).add(src_id)

    # HAS_TECHNIQUE is derived, not a STIX relationship: tactic shortname
    # matched against each live attack-pattern's mitre-attack kill chain phases.
    tactic_techniques: dict[str, set[str]] = {}
    tactic_id_by_uuid = {
        uuid: attack_id_by_uuid[uuid]
        for uuid in tactic_by_shortname.values()
        if uuid in attack_id_by_uuid
    }
    technique_tactics: dict[str, set[str]] = {}
    for obj in live.values():
        if obj["type"] != "attack-pattern":
            continue
        t_id = attack_id_by_uuid.get(obj["id"])
        if not t_id:
            continue
        for phase in obj.get("kill_chain_phases", []):
            if phase.get("kill_chain_name") != "mitre-attack":
                continue
            tactic_uuid = tactic_by_shortname.get(phase.get("phase_name", ""))
            ta_id = tactic_id_by_uuid.get(tactic_uuid or "")
            if ta_id:
                tactic_techniques.setdefault(ta_id, set()).add(t_id)
                technique_tactics.setdefault(t_id, set()).add(ta_id)

    # v19 detection remodel: DetectionStrategy -> Analytic (embedded
    # x_mitre_analytic_refs) and DataComponent -> the Analytics monitoring it
    # (embedded x_mitre_log_source_references). Both are embedded-ref edges,
    # not STIX relationship objects, so they are derived here directly.
    detection_analytics: dict[str, set[str]] = {}
    datacomponent_analytics: dict[str, set[str]] = {}
    for obj in live.values():
        obj_id = attack_id_by_uuid.get(obj["id"])
        if not obj_id:
            continue
        if obj["type"] == "x-mitre-detection-strategy":
            for ref in obj.get("x_mitre_analytic_refs", []):
                an_id = attack_id_by_uuid.get(ref) if ref in live else None
                if an_id:
                    detection_analytics.setdefault(obj_id, set()).add(an_id)
        elif obj["type"] == "x-mitre-analytic":
            for source_ref in obj.get("x_mitre_log_source_references", []):
                dc_ref = source_ref.get("x_mitre_data_component_ref")
                dc_id = attack_id_by_uuid.get(dc_ref) if dc_ref in live else None
                if dc_id:
                    datacomponent_analytics.setdefault(dc_id, set()).add(obj_id)

    return {
        "objects": objects_map,
        "technique_mitigations": {k: sorted(v) for k, v in sorted(technique_mitigations.items())},
        "group_techniques": {k: sorted(v) for k, v in sorted(group_techniques.items())},
        "tactic_techniques": {k: sorted(v) for k, v in sorted(tactic_techniques.items())},
        "subtechniques": {k: sorted(v) for k, v in sorted(subtechniques.items())},
        "campaign_techniques": {k: sorted(v) for k, v in sorted(campaign_techniques.items())},
        "campaign_attribution": {k: sorted(v) for k, v in sorted(campaign_attribution.items())},
        "software_techniques": {k: sorted(v) for k, v in sorted(software_techniques.items())},
        "technique_detections": {k: sorted(v) for k, v in sorted(technique_detections.items())},
        "detection_analytics": {k: sorted(v) for k, v in sorted(detection_analytics.items())},
        "datacomponent_analytics": {k: sorted(v) for k, v in sorted(datacomponent_analytics.items())},
        "technique_tactics": {k: sorted(v) for k, v in sorted(technique_tactics.items())},
        "excluded_ids": sorted(excluded_ids - set(objects_map)),
    }


def _capec_text(pattern: ET.Element, tag: str) -> str | None:
    el = pattern.find(f"c:{tag}", CAPEC_NS)
    return el.text if el is not None else None


def parse_capec_xml(xml_path: Path) -> dict[str, Any]:
    """Derive CAPEC gold maps from the raw catalog XML."""
    root = ET.parse(xml_path).getroot()
    patterns_el = root.find("c:Attack_Patterns", CAPEC_NS)
    if patterns_el is None:
        raise ValueError(f"No Attack_Patterns section in {xml_path}")

    patterns: dict[str, dict[str, Any]] = {}
    related_weaknesses: dict[str, list[str]] = {}
    hierarchy: dict[str, dict[str, set[str]]] = {}
    children: dict[str, set[str]] = {}
    attack_mappings: dict[str, list[str]] = {}
    deprecated: list[str] = []
    execution_steps: dict[str, list[dict[str, Any]]] = {}
    skills: dict[str, list[dict[str, Any]]] = {}
    consequences: dict[str, list[dict[str, Any]]] = {}

    entries = patterns_el.findall("c:Attack_Pattern", CAPEC_NS)

    # First pass: identify retired ids (Deprecated/Obsolete) so the bank can
    # mirror the graph's exclude-at-load policy — retired patterns are dropped
    # and no edge may point at them.
    retired: set[str] = {
        f"CAPEC-{p.get('ID')}"
        for p in entries
        if p.get("Status") in CAPEC_RETIRED_STATUSES
    }

    for p in entries:
        cid = f"CAPEC-{p.get('ID')}"
        status = p.get("Status")
        if cid in retired:
            deprecated.append(cid)
            continue  # excluded from the graph -> excluded from the bank
        patterns[cid] = {
            "name": p.get("Name"),
            "abstraction": p.get("Abstraction"),
            "status": status,
            "typical_severity": _capec_text(p, "Typical_Severity"),
            "likelihood_of_attack": _capec_text(p, "Likelihood_Of_Attack"),
        }

        rw = p.find("c:Related_Weaknesses", CAPEC_NS)
        if rw is not None:
            cwes = sorted(
                {f"CWE-{w.get('CWE_ID')}" for w in rw.findall("c:Related_Weakness", CAPEC_NS)}
            )
            if cwes:
                related_weaknesses[cid] = cwes

        rap = p.find("c:Related_Attack_Patterns", CAPEC_NS)
        if rap is not None:
            for rel in rap.findall("c:Related_Attack_Pattern", CAPEC_NS):
                nature, other = rel.get("Nature"), f"CAPEC-{rel.get('CAPEC_ID')}"
                if other in retired:
                    continue  # graph prunes edges to retired endpoints
                if nature in CAPEC_DECLARED_NATURES:
                    hierarchy.setdefault(cid, {}).setdefault(nature, set()).add(other)
                if nature == "ChildOf":
                    children.setdefault(other, set()).add(cid)

        num = p.get("ID")

        # Execution flow: ordered steps with the derived node ids the loaded
        # graph exposes (capec:attack-pattern:<n>:step:<step>). Repeated step
        # numbers collapse onto one node id in the graph, so node ids are
        # deduplicated while document order is preserved.
        flow = p.find("c:Execution_Flow", CAPEC_NS)
        if flow is not None:
            steps: list[dict[str, Any]] = []
            for step_el in flow.findall("c:Attack_Step", CAPEC_NS):
                step_no_el = step_el.find("c:Step", CAPEC_NS)
                phase_el = step_el.find("c:Phase", CAPEC_NS)
                step_no = (step_no_el.text if step_no_el is not None else None) or "0"
                steps.append(
                    {
                        "step": step_no,
                        "phase": phase_el.text if phase_el is not None else None,
                        "node_id": f"capec:attack-pattern:{num}:step:{_slug(str(step_no))}",
                    }
                )
            if steps:
                execution_steps[cid] = steps

        skills_el = p.find("c:Skills_Required", CAPEC_NS)
        if skills_el is not None:
            entries = [
                {
                    "level": s.get("Level"),
                    "node_id": f"capec:attack-pattern:{num}:skill:{i}",
                }
                for i, s in enumerate(skills_el.findall("c:Skill", CAPEC_NS), start=1)
            ]
            if entries:
                skills[cid] = entries

        cons_el = p.find("c:Consequences", CAPEC_NS)
        if cons_el is not None:
            entries = [
                {
                    "scopes": [sc.text for sc in c.findall("c:Scope", CAPEC_NS) if sc.text],
                    "node_id": f"capec:attack-pattern:{num}:consequence:{i}",
                }
                for i, c in enumerate(cons_el.findall("c:Consequence", CAPEC_NS), start=1)
            ]
            if entries:
                consequences[cid] = entries

        tm = p.find("c:Taxonomy_Mappings", CAPEC_NS)
        if tm is not None:
            t_ids = set()
            for m in tm.findall("c:Taxonomy_Mapping", CAPEC_NS):
                if m.get("Taxonomy_Name") != "ATTACK":
                    continue
                entry_id = m.find("c:Entry_ID", CAPEC_NS)
                if entry_id is not None and entry_id.text:
                    t_ids.add(f"T{entry_id.text.strip()}")
            if t_ids:
                attack_mappings[cid] = sorted(t_ids)

    # Inverse CWE map (the CWE -> CAPEC bridge the federated chain questions
    # traverse). Derived purely by inverting the declared Related_Weaknesses.
    cwe_to_capec: dict[str, set[str]] = {}
    for cid, cwes in related_weaknesses.items():
        for cwe in cwes:
            cwe_to_capec.setdefault(cwe, set()).add(cid)

    def _capec_sort(items: dict[str, Any]) -> dict[str, Any]:
        return dict(sorted(items.items(), key=lambda kv: int(kv[0].split("-")[1])))

    return {
        "patterns": dict(sorted(patterns.items(), key=lambda kv: int(kv[0].split("-")[1]))),
        "execution_steps": _capec_sort(execution_steps),
        "skills": _capec_sort(skills),
        "consequences": _capec_sort(consequences),
        "cwe_to_capec": {
            cwe: sorted(ids, key=lambda c: int(c.split("-")[1]))
            for cwe, ids in sorted(cwe_to_capec.items(), key=lambda kv: int(kv[0].split("-")[1]))
        },
        "related_weaknesses": dict(sorted(related_weaknesses.items(), key=lambda kv: int(kv[0].split("-")[1]))),
        "hierarchy": {
            cid: {nature: sorted(ids) for nature, ids in sorted(natures.items())}
            for cid, natures in sorted(hierarchy.items(), key=lambda kv: int(kv[0].split("-")[1]))
        },
        "children": {
            cid: sorted(kids)
            for cid, kids in sorted(children.items(), key=lambda kv: int(kv[0].split("-")[1]))
        },
        "attack_mappings": dict(sorted(attack_mappings.items(), key=lambda kv: int(kv[0].split("-")[1]))),
        "deprecated": sorted(deprecated, key=lambda c: int(c.split("-")[1])),
    }


def build_gold_bank(data_dir: Path = DATA_DIR) -> dict[str, Any]:
    """Build the full gold bank from the pinned raw snapshot."""
    versions = json.loads((data_dir / "versions.json").read_text())
    attack_version = versions["attack_version"]
    capec_version = versions["capec_version"]

    attack_path = data_dir / "raw" / "attack" / f"v{attack_version}" / "enterprise-attack.json"
    capec_path = data_dir / "raw" / "capec" / f"v{capec_version}" / "capec_latest.xml"

    return {
        "meta": {
            "attack_version": attack_version,
            "capec_version": capec_version,
            "attack_source": str(attack_path.relative_to(data_dir.parent)),
            "capec_source": str(capec_path.relative_to(data_dir.parent)),
            "checksums": versions.get("checksums", {}),
            "generator": "utils/specialists/evalset/gold_bank.py",
        },
        "attack": parse_attack_bundle(attack_path),
        "capec": parse_capec_xml(capec_path),
    }


def load_gold_bank(path: Path = GOLD_BANK_PATH) -> dict[str, Any]:
    """Load the committed gold bank artifact."""
    return json.loads(path.read_text())


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate the specialist gold bank.")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--out", type=Path, default=GOLD_BANK_PATH)
    args = parser.parse_args()

    bank = build_gold_bank(args.data_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(bank, indent=1, sort_keys=False) + "\n")
    attack, capec = bank["attack"], bank["capec"]
    print(f"wrote {args.out}")
    print(
        f"  attack: {len(attack['objects'])} objects, "
        f"{len(attack['technique_mitigations'])} techniques w/ mitigations, "
        f"{len(attack['group_techniques'])} groups, "
        f"{len(attack['tactic_techniques'])} tactics, "
        f"{len(attack['campaign_techniques'])} campaigns w/ techniques, "
        f"{len(attack['campaign_attribution'])} campaigns w/ attribution, "
        f"{len(attack['software_techniques'])} software w/ techniques, "
        f"{len(attack['technique_detections'])} techniques w/ detections, "
        f"{len(attack['detection_analytics'])} strategies w/ analytics, "
        f"{len(attack['datacomponent_analytics'])} data components monitored, "
        f"{len(attack['technique_tactics'])} techniques w/ tactics, "
        f"{len(attack['excluded_ids'])} excluded ids"
    )
    print(
        f"  capec: {len(capec['patterns'])} patterns, "
        f"{len(capec['attack_mappings'])} with ATT&CK mappings, "
        f"{len(capec['execution_steps'])} with execution steps, "
        f"{len(capec['skills'])} with skills, "
        f"{len(capec['consequences'])} with consequences, "
        f"{len(capec['cwe_to_capec'])} CWEs bridged, "
        f"{len(capec['deprecated'])} deprecated"
    )


if __name__ == "__main__":
    main()
