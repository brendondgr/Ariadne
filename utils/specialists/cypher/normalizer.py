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

import re
from collections import defaultdict
from typing import Any

from ..contracts import EvidenceRecord
from ..evidence import emit_record
from ..resolve import ResolvedTask

_TECHNIQUE_ID_RE = re.compile(r"^T\d{4}(?:\.\d{3})?$")


def _is_technique_id(value: str) -> bool:
    return bool(_TECHNIQUE_ID_RE.match(value or ""))


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
        if rows and "technique_id" in rows[0] and "mitigation_id" in rows[0]:
            return self._normalize_technique_mitigations(rows, query, card, id_scheme)
        # campaign_attribution has campaign_id + group_id columns
        if rows and "campaign_id" in rows[0] and "group_id" in rows[0]:
            return self._normalize_campaign_attribution(rows, query, card, id_scheme)
        # group_techniques / tactic_techniques / campaign_techniques have technique_id
        if rows and "technique_id" in rows[0]:
            return self._normalize_technique_rows(rows, query, card, id_scheme)
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
