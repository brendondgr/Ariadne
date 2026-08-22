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
from ..primitives.expand import ExpandRequest, ExpandResult, paginate
from ..resolve import ResolvedTask, subsumed_sources

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


# Max chars of a hydrated neighbour description (bounded — a record can carry many).
# Read through the env at call time so an un-truncated retrieval profile can lift
# it (``SPECIALIST_RELATED_DESC_CHARS``) without touching the default behaviour.
_RELATED_DESC_CHARS = 400


def _related_desc_chars() -> int:
    from utils.config import env_int

    return env_int("SPECIALIST_RELATED_DESC_CHARS", _RELATED_DESC_CHARS)


def _bound_related_desc(desc: str) -> str:
    cap = _related_desc_chars()
    return desc[:cap] + ("…" if len(desc) > cap else "")


def _description_from_props(props_json: Any) -> str:
    """Pull the ``description`` out of an ATT&CK node's ``properties_json`` blob."""
    if not props_json:
        return ""
    try:
        obj = json.loads(props_json) if isinstance(props_json, str) else props_json
    except (ValueError, TypeError):
        return ""
    if not isinstance(obj, dict):
        return ""
    desc = obj.get("description")
    return str(desc) if desc else ""


class CypherNormalizer:
    """Shapes raw Neo4j rows into evidence records.

    The normalizer is stateless — all context comes from ``rows``, ``resolved``,
    ``query`` (the executed Cypher string), and ``card``.
    """

    def enrich_descriptions(self, records: list[EvidenceRecord], connector: Any) -> list[EvidenceRecord]:
        """Backfill each related neighbour's description from its ``properties_json``.

        The compound templates return a neighbour's id + name but leave its
        description inside the unretrieved ``properties_json`` blob — and a bare
        id/name can't answer "tell me about it". One bounded lookup hydrates every
        neighbour the records reference, so a question's substance always reaches
        synthesis regardless of which listing template ran. Called by the shared
        specialist loop after ``normalize``; best-effort (never sinks the result).
        """
        wanted = sorted({
            str(rel["id"])
            for rec in records
            for rel in (rec.related or [])
            if rel.get("id") and not rel.get("description")
        })
        if not wanted:
            return records
        rows = connector.run(
            "MATCH (m) WHERE coalesce(m.attack_id, m.id) IN $ids "
            "RETURN coalesce(m.attack_id, m.id) AS id, m.properties_json AS pj",
            {"ids": wanted},
            {"max_result_rows": len(wanted)},
        )
        by_id: dict[str, str] = {}
        for row in rows or []:
            desc = _description_from_props(row.get("pj"))
            if desc:
                by_id[str(row.get("id"))] = _bound_related_desc(desc)
        for rec in records:
            for rel in (rec.related or []):
                if not rel.get("description") and str(rel.get("id")) in by_id:
                    rel["description"] = by_id[str(rel["id"])]
        return records

    def normalize(
        self,
        rows: list[dict[str, Any]],
        resolved: ResolvedTask,
        query: str,
        card: Any,
    ) -> list[EvidenceRecord]:
        """Return one ``EvidenceRecord`` per logical result entity."""
        id_scheme = card.provenance.get("id_scheme", "attack-id")

        # generic_neighbors — the schema-driven walk. Its columns are named for
        # their ROLE (anchor/neighbour) rather than for an ATT&CK entity, because
        # the compiler does not know what the edge means; that is the whole point
        # of the template. Checked first: no other shape carries ``anchor_id``.
        if rows and "anchor_id" in rows[0] and "neighbour_id" in rows[0]:
            return self._normalize_generic_neighbors(rows, query, card, id_scheme)

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
        # NEW: group_software / campaign_software — an actor and its software.
        # Must sit after the software_id + technique_id branch above (these rows
        # carry no technique_id, so the two cannot both match) and before the
        # flat fallback, which reads neither column and emits `unknown` ids —
        # the failure this branch exists to close.
        if rows and "software_id" in rows[0] and (
            "group_id" in rows[0] or "campaign_id" in rows[0]
        ):
            return self._normalize_actor_software(rows, query, card, id_scheme)
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
            return self._normalize_technique_rows(rows, resolved, query, card, id_scheme)
        # describe — full node (properties_json) + bounded facet block
        if rows and "facets" in rows[0]:
            return self._normalize_describe(rows, resolved, query, card, id_scheme)
        # node_lookup / label_scan
        return self._normalize_flat(rows, resolved, query, card, id_scheme)

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

    def _normalize_generic_neighbors(
        self,
        rows: list[dict[str, Any]],
        query: str,
        card: Any,
        id_scheme: str,
    ) -> list[EvidenceRecord]:
        """Group a schema-driven walk into one record per anchor.

        The counterpart to :meth:`CypherQueryBuilder._generic_neighbors`: it knows
        the *roles* (anchor, neighbour, edge type) but nothing about what the edge
        means, so it carries the edge type through on each related entry and lets
        the composer name the relationship. Join values still fall out for free
        wherever the anchor's id is a technique — the cross-source bridge does not
        need a bespoke template to notice a shared identifier.
        """
        groups: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"name": "", "label": "", "related": []}
        )
        for row in rows:
            anchor = str(row.get("anchor_id") or "")
            if not anchor:
                continue
            group = groups[anchor]
            group["name"] = str(row.get("anchor_name") or "") or group["name"]
            group["label"] = str(row.get("anchor_label") or "") or group["label"]
            nid = str(row.get("neighbour_id") or "")
            if not nid:
                continue  # OPTIONAL MATCH miss: an honest empty neighbourhood
            entry = {
                "id": nid,
                "name": str(row.get("neighbour_name") or ""),
                "label": str(row.get("neighbour_label") or ""),
            }
            rel = str(row.get("rel_type") or "")
            if rel:
                entry["type"] = rel
            group["related"].append(entry)

        # In a store that holds only one catalogue, a *neighbour* carrying
        # another catalogue's identifier is a dead end: this specialist cannot
        # query the other store, so the value is noise. In a store that holds
        # both — the merged card declares which sources it subsumes — that same
        # neighbour IS the cross-source link, reachable in the next hop without
        # leaving the engine. The asymmetry is a real difference between the two
        # architectures rather than a concession to either, and gating on the
        # card keeps it a property of the data. Nothing changes for a card that
        # subsumes nothing, which is every card but the merged one.
        cross_catalogue = len(subsumed_sources(card)) > 1

        records: list[EvidenceRecord] = []
        for anchor, info in groups.items():
            join_values = (anchor,) if _is_technique_id(anchor) else ()
            if cross_catalogue:
                seen = set(join_values)
                for entry in info["related"]:
                    nid = str(entry.get("id") or "")
                    if _is_technique_id(nid) and nid not in seen:
                        seen.add(nid)
                        join_values = (*join_values, nid)
            records.append(
                emit_record(
                    card=card,
                    query=query,
                    record_id=anchor,
                    primary_id=anchor,
                    id_scheme=id_scheme,
                    label=info["label"] or "Technique",
                    name=info["name"],
                    related=info["related"],
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

    def _normalize_actor_software(
        self,
        rows: list[dict[str, Any]],
        query: str,
        card: Any,
        id_scheme: str,
    ) -> list[EvidenceRecord]:
        """Group `group_software` / `campaign_software` rows by the actor.

        Grouped on the actor rather than the software so the shape matches
        `_normalize_software_techniques`: one record per anchor, its software in
        `related`. Both directions of the question produce readable output —
        "what software does G0003 use" gives one group with four software, and
        "what groups use S0089" gives one group per user, each naming S0089.

        `join_values` is empty deliberately. The cross-catalogue join runs on
        ATT&CK technique identifiers, and neither end of this edge is one;
        emitting software ids as join values would seed a CAPEC query that
        cannot match them.
        """
        actor_key = "group_id" if "group_id" in rows[0] else "campaign_id"
        name_key = actor_key.replace("_id", "_name")
        label = "Group" if actor_key == "group_id" else "Campaign"

        groups: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"name": "", "software": [], "_seen": set()}
        )
        for row in rows:
            aid = str(row.get(actor_key) or "")
            groups[aid]["name"] = str(row.get(name_key) or "")
            sid = str(row.get("software_id") or "")
            seen = groups[aid]["_seen"]
            if sid and sid not in seen:
                seen.add(sid)
                groups[aid]["software"].append(
                    {"id": sid, "name": str(row.get("software_name") or "")}
                )

        return [
            emit_record(
                card=card,
                query=query,
                record_id=aid,
                primary_id=aid,
                id_scheme=id_scheme,
                label=label,
                name=info["name"],
                related=info["software"],
                join_values=(),
            )
            for aid, info in groups.items()
        ]

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

    # The other end these listing templates project, in the order the columns
    # are looked for. Nothing here is a routing decision — the pivot below is
    # made by asking which column the caller's seeds appear in.
    _COUNTERPART_COLUMNS = (
        ("group_id", "group_name", "Group"),
        ("campaign_id", "campaign_name", "Campaign"),
        ("tactic_id", "tactic_name", "Tactic"),
    )

    def _normalize_technique_rows(
        self,
        rows: list[dict[str, Any]],
        resolved: ResolvedTask,
        query: str,
        card: Any,
        id_scheme: str,
    ) -> list[EvidenceRecord]:
        """One record per row for group_techniques / tactic_techniques.

        Unless the *technique* is what was seeded. "Which techniques does G0082
        use" and "which groups use T1003" run the same query and return the same
        rows; only the question differs, and the answer to the second is the
        column this dedupe used to throw away. The pivot reads which column
        carries a seed, so it needs no knowledge of which template ran.
        """
        seeds = {str(seed) for seed in (resolved.seed_ids or ())}
        if seeds and any(str(row.get("technique_id") or "") in seeds for row in rows):
            counterpart = next(
                (cols for cols in self._COUNTERPART_COLUMNS if rows and cols[0] in rows[0]),
                None,
            )
            if counterpart is not None:
                return self._normalize_seeded_technique_rows(
                    rows, counterpart, query, card, id_scheme
                )
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

    def _normalize_seeded_technique_rows(
        self,
        rows: list[dict[str, Any]],
        counterpart: tuple[str, str, str],
        query: str,
        card: Any,
        id_scheme: str,
    ) -> list[EvidenceRecord]:
        """One record per seeded technique, carrying the other end as ``related``."""
        id_col, name_col, label = counterpart
        groups: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"technique_name": "", "related": [], "seen": set()}
        )
        for row in rows:
            tid = str(row.get("technique_id") or "")
            if not tid:
                continue
            bucket = groups[tid]
            bucket["technique_name"] = bucket["technique_name"] or str(
                row.get("technique_name") or ""
            )
            other_id = str(row.get(id_col) or "")
            if not other_id or other_id in bucket["seen"]:
                continue
            bucket["seen"].add(other_id)
            bucket["related"].append(
                {"id": other_id, "name": str(row.get(name_col) or ""), "label": label}
            )
        records: list[EvidenceRecord] = []
        for tid, info in groups.items():
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
                    join_values=(tid,) if _is_technique_id(tid) else (),
                )
            )
        return records

    def _normalize_flat(
        self,
        rows: list[dict[str, Any]],
        resolved: ResolvedTask,
        query: str,
        card: Any,
        id_scheme: str,
    ) -> list[EvidenceRecord]:
        """One record per row for node_lookup / label_scan.

        The label comes from ``_label_for`` -- the resolved label first, then the
        id prefix -- rather than the constant ``"Technique"`` this emitted for
        every row of every source. That constant was not cosmetic: the label is
        carried into the evidence record and read back out by synthesis, so a
        DEVICE named ``srv000`` was being asserted to the judge as an ATT&CK
        Technique. Same species as the hardcoded "ATT&CK record(s)" wording in
        the composer, and found the same way -- by running the template against
        a graph it was not written for.
        """
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
                    label=_label_for(aid, resolved),
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

    def normalize_expand(
        self, rows: list[dict[str, Any]], request: ExpandRequest
    ) -> ExpandResult:
        """Shape the server-sliced expand rows into an ``ExpandResult``.

        The Cypher ``expand`` query returns one row: ``members`` already sliced to
        the page and ``total`` the true member count, so paging is not re-applied —
        the truncation flag is computed from the real total.
        """
        if not rows:
            return paginate([], request, total=0, pre_sliced=True)
        row = rows[0]
        members: list[dict[str, Any]] = []
        for m in row.get("members") or []:
            if not isinstance(m, dict):
                continue
            member = {
                "id": str(m.get("id") or ""),
                "name": str(m.get("name") or ""),
                "label": str(m.get("label") or ""),
            }
            # The ATT&CK description lives in properties_json; carry a bounded slice
            # so an expand page reads as summaries, not full records.
            desc = _description_from_props(m.get("props"))
            if desc:
                member["description"] = _bound_related_desc(desc)
            members.append(member)
        total = row.get("total")
        total = int(total) if isinstance(total, (int, float)) else len(members)
        return paginate(members, request, total=total, pre_sliced=True)

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

    @staticmethod
    def _source_label(
        records: list[EvidenceRecord], resolved: ResolvedTask
    ) -> str:
        """The human-readable name of the source these records came from.

        Read from the records' own provenance, which ``emit_record`` fills from
        the source card, so it is whatever that card declares rather than a
        literal in this file.

        This was hard-coded to "ATT&CK" on all four branches below, with no card
        lookup and no dataset branch. Every answer from every source therefore
        described its records as ATT&CK records, so an identity graph reported
        ``GROUP``, ``GPO``, ``DOMAIN`` and ``AWS_EC2_SECURITY_GROUP`` objects as
        "ATT&CK record(s)" -- a statement about what the evidence *is* that was
        simply false, and one that several independent judges in
        EXP-2026-08-011 caught and marked down as unfaithful even when every
        identifier in the answer was correct (ISSUES I-9).

        Falls back to the dataset key, then to no name at all. Returning an
        empty string is deliberate: a summary that cannot name its source should
        say "Found 5 record(s)", not guess at one.
        """
        for record in records:
            provenance = record.provenance
            if provenance is not None and provenance.source:
                return provenance.source
        return getattr(resolved, "dataset", "") or ""

    def summarize(
        self, records: list[EvidenceRecord], resolved: ResolvedTask
    ) -> str:
        """Return a short grounded sentence citing real ids found."""
        source = self._source_label(records, resolved)
        # The source name is always rendered after "in", never welded into a
        # noun phrase. A card is free to call itself "the ReliaQuest identity
        # graph", and "Found 5 the ReliaQuest identity graph record(s)" is not a
        # sentence -- whereas "in the ReliaQuest identity graph" reads correctly
        # for any name a card might declare, including MITRE ATT&CK's.
        of_source = f" in {source}" if source else ""

        if not records:
            return f"No records found{of_source} for this query."

        total = len(records)
        if total == 1:
            rec = records[0]
            related_count = len(rec.related)
            if related_count:
                related_ids = ", ".join(
                    r.get("id", "") for r in rec.related[:3] if r.get("id")
                )
                return (
                    f"Found {related_count} item(s) related to "
                    f"{rec.primary_id or rec.name}"
                    f"{f' (e.g. {related_ids})' if related_ids else ''}"
                    f"{of_source}."
                )
            # Name first, identifier only when there is one. The identifier was
            # interpolated unconditionally, so a record without one rendered as
            # "Found record : Database Admins" -- a dangling colon that reads as
            # a missing citation, which is how independent judges scored it.
            label = rec.name or rec.primary_id or "unnamed record"
            ident = f" ({rec.primary_id})" if rec.primary_id and rec.name else ""
            return f"Found 1 record{of_source}: {label}{ident}."

        sample_ids = [r.primary_id for r in records[:3] if r.primary_id]
        if not sample_ids:
            sample_ids = [r.name for r in records[:3] if r.name]
        id_text = ", ".join(sample_ids)
        including = f" including {id_text}" if id_text else ""
        return (
            f"Found {total} record(s){of_source}{including}"
            + (" and more" if id_text and total > 3 else "")
            + "."
        )
