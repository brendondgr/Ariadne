#!/usr/bin/env python3
"""Evidence normalizer for the MITRE ATT&CK / Neo4j Cypher specialist.

Converts raw Neo4j result rows into ``EvidenceRecord`` objects using
``emit_record`` from the shared evidence module.  The template name stored in
the ``QueryDraft`` (propagated via the normalizer's ``query`` argument as a
context string embedded in the provenance) drives the grouping logic:

  * ``technique_mitigations`` — groups rows by technique, collecting mitigations
    as ``related`` items; one record per technique.
  * All other templates — one record per row (``node_lookup`` / ``label_scan`` /
    ``group_techniques`` / ``tactic_techniques``).
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any

from ..contracts import EvidenceRecord
from ..evidence import emit_record
from ..primitives.describe import facets_from_count_rows as _facets_from_rows
from ..primitives.describe import merge_with_card as _merge_plausible
from ..resolve import ResolvedTask

_TECHNIQUE_ID_RE = re.compile(r"^T\d{4}(?:\.\d{3})?$")

# Seed-id prefix → label for the describe record when the task named no entity.
_DOSSIER_ID_LABELS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^TA\d{4}$"), "Tactic"),
    (re.compile(r"^M\d{4}$"), "Mitigation"),
    (re.compile(r"^S\d{4}$"), "Software"),
    (re.compile(r"^DC\d{4}$"), "DataComponent"),
    (re.compile(r"^DET\d{4}$"), "DetectionStrategy"),
    (re.compile(r"^G\d{4}$"), "Group"),
    (re.compile(r"^C\d{4}$"), "Campaign"),
    (re.compile(r"^T\d{4}\.\d{3}$"), "SubTechnique"),
    (re.compile(r"^T\d{4}$"), "Technique"),
)


def _is_technique_id(value: str) -> bool:
    return bool(_TECHNIQUE_ID_RE.match(value or ""))


def _label_for(aid: str, resolved: ResolvedTask) -> str:
    """Resolved primary label, else inferred from the id prefix, else Technique."""
    if resolved.primary_label():
        return resolved.primary_label()  # type: ignore[return-value]
    for pattern, label in _DOSSIER_ID_LABELS:
        if pattern.match(aid or ""):
            return label
    return "Technique"


class CypherNormalizer:
    """Shapes raw Neo4j rows into evidence records.

    The normalizer is stateless — all context comes from ``rows``, ``resolved``,
    ``query`` (the executed Cypher string), and ``card``.
    """

    def normalize(
        self,
        rows: list[dict[str, Any]],
        resolved: ResolvedTask,
        query: str,
        card: Any,
    ) -> list[EvidenceRecord]:
        """Return one ``EvidenceRecord`` per logical result entity."""
        id_scheme = card.provenance.get("id_scheme", "attack-id")

        # Detect the template from column names in the first row
        # NEW: technique_detection — technique_id + detection_id (must check before
        # the generic technique_id+mitigation_id branch)
        if rows and "technique_id" in rows[0] and "detection_id" in rows[0]:
            return self._normalize_technique_detection(rows, query, card, id_scheme)
        # NEW: tactic_technique_mitigations — tactic_id + technique_id + mitigation_id
        # (check BEFORE the generic technique_id+mitigation_id branch)
        if rows and "tactic_id" in rows[0] and "mitigation_id" in rows[0]:
            return self._normalize_tactic_technique_mitigations(rows, query, card, id_scheme)
        if rows and "technique_id" in rows[0] and "mitigation_id" in rows[0]:
            return self._normalize_technique_mitigations(rows, query, card, id_scheme)
        # campaign_attribution has campaign_id + group_id columns
        if rows and "campaign_id" in rows[0] and "group_id" in rows[0]:
            return self._normalize_campaign_attribution(rows, query, card, id_scheme)
        # NEW: software_techniques — software_id + technique_id
        if rows and "software_id" in rows[0] and "technique_id" in rows[0]:
            return self._normalize_software_techniques(rows, query, card, id_scheme)
        # NEW: subtechnique_parent — parent_id + subtechnique_id
        if rows and "parent_id" in rows[0] and "subtechnique_id" in rows[0]:
            return self._normalize_subtechnique_parent(rows, query, card, id_scheme)
        # NEW: datacomponent_analytics — datacomponent_id + analytic_id
        if rows and "datacomponent_id" in rows[0] and "analytic_id" in rows[0]:
            return self._normalize_datacomponent_analytics(rows, query, card, id_scheme)
        # NEW: technique_tactics — technique_id + in_tactic_id
        if rows and "technique_id" in rows[0] and "in_tactic_id" in rows[0]:
            return self._normalize_technique_tactics(rows, query, card, id_scheme)
        # group_techniques / tactic_techniques / campaign_techniques have technique_id
        if rows and "technique_id" in rows[0]:
            return self._normalize_technique_rows(rows, query, card, id_scheme)
        # describe — full node (properties_json) + bounded facet block
        if rows and "facets" in rows[0]:
            return self._normalize_describe(rows, resolved, query, card, id_scheme)
        # node_lookup / label_scan
        return self._normalize_flat(rows, query, card, id_scheme)

    def _normalize_technique_mitigations(
        self,
        rows: list[dict[str, Any]],
        query: str,
        card: Any,
        id_scheme: str,
    ) -> list[EvidenceRecord]:
        """Group mitigation rows by technique_id into one record per technique."""
        # Group: technique_id -> {"name": ..., mitigations: [...]}
        groups: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"technique_name": "", "mitigations": []}
        )
        for row in rows:
            tid = str(row.get("technique_id") or "")
            groups[tid]["technique_name"] = str(row.get("technique_name") or "")
            mit_id = str(row.get("mitigation_id") or "")
            mit_name = str(row.get("mitigation_name") or "")
            if mit_id:
                groups[tid]["mitigations"].append({"id": mit_id, "name": mit_name})

        records: list[EvidenceRecord] = []
        for tid, info in groups.items():
            join_values = (tid,) if _is_technique_id(tid) else ()
            records.append(
                emit_record(
                    card=card,
                    query=query,
                    record_id=tid,  # best available; STIX id not returned in this template
                    primary_id=tid,
                    id_scheme=id_scheme,
                    label="Technique",
                    name=info["technique_name"],
                    related=info["mitigations"],
                    join_values=join_values,
                )
            )
        return records

    def _normalize_technique_detection(
        self,
        rows: list[dict[str, Any]],
        query: str,
        card: Any,
        id_scheme: str,
    ) -> list[EvidenceRecord]:
        """Group detection rows by technique_id; collect detection + analytic as related."""
        groups: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"technique_name": "", "related": [], "_seen": set()}
        )
        for row in rows:
            tid = str(row.get("technique_id") or "")
            groups[tid]["technique_name"] = str(row.get("technique_name") or "")
            det_id = str(row.get("detection_id") or "")
            det_name = str(row.get("detection_name") or "")
            an_id = str(row.get("analytic_id") or "")
            an_name = str(row.get("analytic_name") or "")
            seen = groups[tid]["_seen"]
            if det_id and det_id not in seen:
                seen.add(det_id)
                groups[tid]["related"].append({"id": det_id, "name": det_name})
            if an_id and an_id not in seen:
                seen.add(an_id)
                groups[tid]["related"].append({"id": an_id, "name": an_name})

        records: list[EvidenceRecord] = []
        for tid, info in groups.items():
            join_values = (tid,) if _is_technique_id(tid) else ()
            records.append(
                emit_record(
                    card=card,
                    query=query,
                    record_id=tid,
                    primary_id=tid,
                    id_scheme=id_scheme,
                    label="Technique",
                    name=info["technique_name"],
                    related=info["related"],
                    join_values=join_values,
                )
            )
        return records

    def _normalize_tactic_technique_mitigations(
        self,
        rows: list[dict[str, Any]],
        query: str,
        card: Any,
        id_scheme: str,
    ) -> list[EvidenceRecord]:
        """Group tactic+mitigation rows by technique_id; related = unique tactic + mitigation dicts."""
        groups: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"technique_name": "", "related": [], "_seen": set()}
        )
        for row in rows:
            tid = str(row.get("technique_id") or "")
            groups[tid]["technique_name"] = str(row.get("technique_name") or "")
            seen = groups[tid]["_seen"]
            tac_id = str(row.get("tactic_id") or "")
            tac_name = str(row.get("tactic_name") or "")
            mit_id = str(row.get("mitigation_id") or "")
            mit_name = str(row.get("mitigation_name") or "")
            if tac_id and tac_id not in seen:
                seen.add(tac_id)
                groups[tid]["related"].append({"id": tac_id, "name": tac_name})
            if mit_id and mit_id not in seen:
                seen.add(mit_id)
                groups[tid]["related"].append({"id": mit_id, "name": mit_name})

        records: list[EvidenceRecord] = []
        for tid, info in groups.items():
            join_values = (tid,) if _is_technique_id(tid) else ()
            records.append(
                emit_record(
                    card=card,
                    query=query,
                    record_id=tid,
                    primary_id=tid,
                    id_scheme=id_scheme,
                    label="Technique",
                    name=info["technique_name"],
                    related=info["related"],
                    join_values=join_values,
                )
            )
        return records

    def _normalize_software_techniques(
        self,
        rows: list[dict[str, Any]],
        query: str,
        card: Any,
        id_scheme: str,
    ) -> list[EvidenceRecord]:
        """Group software_techniques rows by software_id; related = unique technique dicts."""
        groups: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"software_name": "", "techniques": [], "_seen": set()}
        )
        for row in rows:
            sid = str(row.get("software_id") or "")
            groups[sid]["software_name"] = str(row.get("software_name") or "")
            tid = str(row.get("technique_id") or "")
            tname = str(row.get("technique_name") or "")
            seen = groups[sid]["_seen"]
            if tid and tid not in seen:
                seen.add(tid)
                groups[sid]["techniques"].append({"id": tid, "name": tname})

        records: list[EvidenceRecord] = []
        for sid, info in groups.items():
            # join_values = tuple of unique technique ids matching T-pattern
            join_values = tuple(
                t["id"] for t in info["techniques"] if _is_technique_id(t["id"])
            )
            records.append(
                emit_record(
                    card=card,
                    query=query,
                    record_id=sid,
                    primary_id=sid,
                    id_scheme=id_scheme,
                    label="Software",
                    name=info["software_name"],
                    related=info["techniques"],
                    join_values=join_values,
                )
            )
        return records

    def _normalize_subtechnique_parent(
        self,
        rows: list[dict[str, Any]],
        query: str,
        card: Any,
        id_scheme: str,
    ) -> list[EvidenceRecord]:
        """Group subtechnique_parent rows by parent_id; related = unique subtechnique dicts."""
        groups: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"parent_name": "", "subtechniques": [], "_seen": set()}
        )
        for row in rows:
            pid = str(row.get("parent_id") or "")
            groups[pid]["parent_name"] = str(row.get("parent_name") or "")
            stid = str(row.get("subtechnique_id") or "")
            stname = str(row.get("subtechnique_name") or "")
            seen = groups[pid]["_seen"]
            if stid and stid not in seen:
                seen.add(stid)
                groups[pid]["subtechniques"].append({"id": stid, "name": stname})

        records: list[EvidenceRecord] = []
        for pid, info in groups.items():
            join_values = (pid,) if _is_technique_id(pid) else ()
            records.append(
                emit_record(
                    card=card,
                    query=query,
                    record_id=pid,
                    primary_id=pid,
                    id_scheme=id_scheme,
                    label="Technique",
                    name=info["parent_name"],
                    related=info["subtechniques"],
                    join_values=join_values,
                )
            )
        return records

    def _normalize_datacomponent_analytics(
        self,
        rows: list[dict[str, Any]],
        query: str,
        card: Any,
        id_scheme: str,
    ) -> list[EvidenceRecord]:
        """Group datacomponent_analytics rows by datacomponent_id; related = unique analytic dicts."""
        groups: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"datacomponent_name": "", "analytics": [], "_seen": set()}
        )
        for row in rows:
            dcid = str(row.get("datacomponent_id") or "")
            groups[dcid]["datacomponent_name"] = str(row.get("datacomponent_name") or "")
            aid = str(row.get("analytic_id") or "")
            aname = str(row.get("analytic_name") or "")
            seen = groups[dcid]["_seen"]
            if aid and aid not in seen:
                seen.add(aid)
                groups[dcid]["analytics"].append({"id": aid, "name": aname})

        records: list[EvidenceRecord] = []
        for dcid, info in groups.items():
            records.append(
                emit_record(
                    card=card,
                    query=query,
                    record_id=dcid,
                    primary_id=dcid,
                    id_scheme=id_scheme,
                    label="DataComponent",
                    name=info["datacomponent_name"],
                    related=info["analytics"],
                    join_values=(),
                )
            )
        return records

    def _normalize_technique_tactics(
        self,
        rows: list[dict[str, Any]],
        query: str,
        card: Any,
        id_scheme: str,
    ) -> list[EvidenceRecord]:
        """Group technique_tactics rows by technique_id; related = unique tactic dicts."""
        groups: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"technique_name": "", "tactics": [], "_seen": set()}
        )
        for row in rows:
            tid = str(row.get("technique_id") or "")
            groups[tid]["technique_name"] = str(row.get("technique_name") or "")
            itac_id = str(row.get("in_tactic_id") or "")
            itac_name = str(row.get("in_tactic_name") or "")
            seen = groups[tid]["_seen"]
            if itac_id and itac_id not in seen:
                seen.add(itac_id)
                groups[tid]["tactics"].append({"id": itac_id, "name": itac_name})

        records: list[EvidenceRecord] = []
        for tid, info in groups.items():
            join_values = (tid,) if _is_technique_id(tid) else ()
            records.append(
                emit_record(
                    card=card,
                    query=query,
                    record_id=tid,
                    primary_id=tid,
                    id_scheme=id_scheme,
                    label="Technique",
                    name=info["technique_name"],
                    related=info["tactics"],
                    join_values=join_values,
                )
            )
        return records

    def _normalize_campaign_attribution(
        self,
        rows: list[dict[str, Any]],
        query: str,
        card: Any,
        id_scheme: str,
    ) -> list[EvidenceRecord]:
        """Group attribution rows by campaign_id into one record per campaign."""
        groups: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"campaign_name": "", "groups": []}
        )
        for row in rows:
            cid = str(row.get("campaign_id") or "")
            groups[cid]["campaign_name"] = str(row.get("campaign_name") or "")
            gid = str(row.get("group_id") or "")
            gname = str(row.get("group_name") or "")
            if gid:
                groups[cid]["groups"].append({"id": gid, "name": gname})

        records: list[EvidenceRecord] = []
        for cid, info in groups.items():
            records.append(
                emit_record(
                    card=card,
                    query=query,
                    record_id=cid,
                    primary_id=cid,
                    id_scheme=id_scheme,
                    label="Campaign",
                    name=info["campaign_name"],
                    related=info["groups"],
                )
            )
        return records

    def _normalize_technique_rows(
        self,
        rows: list[dict[str, Any]],
        query: str,
        card: Any,
        id_scheme: str,
    ) -> list[EvidenceRecord]:
        """One record per row for group_techniques / tactic_techniques."""
        seen: dict[str, bool] = {}
        records: list[EvidenceRecord] = []
        for row in rows:
            tid = str(row.get("technique_id") or "")
            if tid in seen:
                continue
            seen[tid] = True
            name = str(row.get("technique_name") or "")
            join_values = (tid,) if _is_technique_id(tid) else ()
            records.append(
                emit_record(
                    card=card,
                    query=query,
                    record_id=tid,
                    primary_id=tid,
                    id_scheme=id_scheme,
                    label="Technique",
                    name=name,
                    join_values=join_values,
                )
            )
        return records

    def _normalize_flat(
        self,
        rows: list[dict[str, Any]],
        query: str,
        card: Any,
        id_scheme: str,
    ) -> list[EvidenceRecord]:
        """One record per row for node_lookup / label_scan."""
        records: list[EvidenceRecord] = []
        for row in rows:
            # Support both column names: "id" (node_lookup) and "attack_id"
            aid = str(row.get("id") or row.get("attack_id") or "")
            stix_id = str(row.get("stix_id") or "")
            record_id = stix_id if stix_id else aid
            name = str(row.get("name") or "")
            join_values = (aid,) if _is_technique_id(aid) else ()
            records.append(
                emit_record(
                    card=card,
                    query=query,
                    record_id=record_id if record_id else aid,
                    primary_id=aid,
                    id_scheme=id_scheme,
                    label="Technique",
                    name=name,
                    join_values=join_values,
                )
            )
        return records

    def _normalize_describe(
        self,
        rows: list[dict[str, Any]],
        resolved: ResolvedTask,
        query: str,
        card: Any,
        id_scheme: str,
    ) -> list[EvidenceRecord]:
        """One record per anchor: **every** property + the bounded facet block.

        ``properties`` carries the whole parsed ``properties_json`` — no allow-list
        deciding in advance which keys are worth returning (that allow-list was the
        neighbour cap's twin). ``facets`` carries the count of adjacent nodes
        grouped by ``(relationship, direction, neighbour label)``, folded with the
        registry's plausible facets so an unobserved-but-plausible facet appears as
        an honest ``count: 0`` — letting the model assert "no sub-techniques"
        rather than merely failing to observe one.
        """
        records: list[EvidenceRecord] = []
        for row in rows:
            aid = str(row.get("id") or row.get("attack_id") or "")
            name = str(row.get("name") or "")
            properties = self._parse_properties(row.get("properties_json"))
            label = _label_for(aid, resolved)

            observed = _facets_from_rows(row.get("facets"))
            facets = _merge_plausible(observed, card, label)

            join_values = (aid,) if _is_technique_id(aid) else ()
            records.append(
                emit_record(
                    card=card,
                    query=query,
                    record_id=aid,
                    primary_id=aid,
                    id_scheme=id_scheme,
                    label=label,
                    name=name,
                    properties=dict(properties),
                    facets=[f.to_dict() for f in facets],
                    join_values=join_values,
                )
            )
        return records

    @staticmethod
    def _parse_properties(blob: Any) -> dict[str, Any]:
        """Parse the node's ``properties_json`` string into a dict (empty on failure)."""
        if isinstance(blob, dict):
            return blob
        if not blob:
            return {}
        try:
            parsed = json.loads(blob)
            return parsed if isinstance(parsed, dict) else {}
        except (ValueError, TypeError):
            return {}

    def summarize(
        self, records: list[EvidenceRecord], resolved: ResolvedTask
    ) -> str:
        """Return a short grounded sentence citing real ids found."""
        if not records:
            return "No records found in ATT&CK for this query."

        # Pull a few representative ids for the summary
        sample_ids = [r.primary_id for r in records[:3] if r.primary_id]
        id_text = ", ".join(sample_ids) if sample_ids else "unknown"

        total = len(records)
        if total == 1:
            rec = records[0]
            related_count = len(rec.related)
            if related_count:
                related_ids = ", ".join(
                    r.get("id", "") for r in rec.related[:3] if r.get("id")
                )
                return (
                    f"Found {related_count} item(s) related to {rec.primary_id} "
                    f"(e.g. {related_ids}) in MITRE ATT&CK."
                )
            return f"Found ATT&CK record {rec.primary_id}: {rec.name}."

        return (
            f"Found {total} ATT&CK record(s) including {id_text}"
            + (" and more" if total > 3 else "")
            + "."
        )
