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
  - CAPEC: load-and-tag — Deprecated patterns stay in the bank with their
    Status so negative questions can target them.

Regenerate with:
    uv run python -m utils.specialists.evalset.gold_bank
"""

from __future__ import annotations

import argparse
import json
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

    for obj in objects:
        if obj.get("type") == "relationship":
            continue
        label = _node_label(obj)
        if label is None or _is_excluded(obj):
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

    # HAS_TECHNIQUE is derived, not a STIX relationship: tactic shortname
    # matched against each live attack-pattern's mitre-attack kill chain phases.
    tactic_techniques: dict[str, set[str]] = {}
    tactic_id_by_uuid = {
        uuid: attack_id_by_uuid[uuid]
        for uuid in tactic_by_shortname.values()
        if uuid in attack_id_by_uuid
    }
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

    return {
        "objects": objects_map,
        "technique_mitigations": {k: sorted(v) for k, v in sorted(technique_mitigations.items())},
        "group_techniques": {k: sorted(v) for k, v in sorted(group_techniques.items())},
        "tactic_techniques": {k: sorted(v) for k, v in sorted(tactic_techniques.items())},
        "subtechniques": {k: sorted(v) for k, v in sorted(subtechniques.items())},
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

    entries = patterns_el.findall("c:Attack_Pattern", CAPEC_NS)
    for p in entries:
        cid = f"CAPEC-{p.get('ID')}"
        status = p.get("Status")
        patterns[cid] = {
            "name": p.get("Name"),
            "abstraction": p.get("Abstraction"),
            "status": status,
            "typical_severity": _capec_text(p, "Typical_Severity"),
            "likelihood_of_attack": _capec_text(p, "Likelihood_Of_Attack"),
        }
        if status == "Deprecated":
            deprecated.append(cid)

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
                if nature in CAPEC_DECLARED_NATURES:
                    hierarchy.setdefault(cid, {}).setdefault(nature, set()).add(other)
                if nature == "ChildOf":
                    children.setdefault(other, set()).add(cid)

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

    return {
        "patterns": dict(sorted(patterns.items(), key=lambda kv: int(kv[0].split("-")[1]))),
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
        f"{len(attack['tactic_techniques'])} tactics"
    )
    print(
        f"  capec: {len(capec['patterns'])} patterns, "
        f"{len(capec['attack_mappings'])} with ATT&CK mappings, "
        f"{len(capec['deprecated'])} deprecated"
    )


if __name__ == "__main__":
    main()
