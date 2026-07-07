#!/usr/bin/env python3
"""Gremlin result normalizer for the CAPEC specialist.

Converts raw elementMap() rows (plain dicts from gremlin-python) into
EvidenceRecord instances using the shared emit_record helper.  Handles the
three result shapes produced by GremlinQueryBuilder:

  - single  : each row is a flat {T.id:.., T.label:.., "id":.., "name":..}
  - pair    : each row is {"ap": {...}, "nbr": {...}}   (capec_neighbors)
  - maps_to : each row is {"ap": {...}, "tax": {...}}   (capec_maps_to)
"""

from __future__ import annotations

import re
from typing import Any

from utils.specialists.contracts import EvidenceRecord
from utils.specialists.evidence import emit_record
from utils.specialists.resolve import ResolvedTask

_CAPEC_ID_FROM_STR_RE = re.compile(r"capec:attack-pattern:(\d+)")
_CWE_GREMLIN_RE = re.compile(r"^cwe:(\d+)$")

try:
    from gremlin_python.process.traversal import T as GremlinT
    _T_ID = GremlinT.id
    _T_LABEL = GremlinT.label
except Exception:  # noqa: BLE001 — gremlin_python may not be installed in unit tests
    _T_ID = None
    _T_LABEL = None


def _primary_id_from_gremlin_id(gremlin_id: str) -> str:
    """Convert 'capec:attack-pattern:66' -> 'CAPEC-66'.

    Falls back to the raw string when the pattern does not match.
    """
    m = _CAPEC_ID_FROM_STR_RE.match(gremlin_id or "")
    if m:
        return f"CAPEC-{m.group(1)}"
    return gremlin_id


def _cwe_primary_id(gremlin_id: str) -> str:
    """Convert 'cwe:89' -> 'CWE-89'. Falls back to raw string."""
    m = _CWE_GREMLIN_RE.match(gremlin_id or "")
    if m:
        return f"CWE-{m.group(1)}"
    return gremlin_id


def _get_label(m: dict[str, Any]) -> str:
    """Extract T.label from an elementMap row (enum key or string fallback)."""
    if _T_LABEL is not None and _T_LABEL in m:
        return str(m[_T_LABEL])
    # Fallback: look for a plain "label" key (unit-test fake rows).
    return str(m.get("label", ""))


def _get_record_id(m: dict[str, Any]) -> str:
    """Extract the backend vertex id (T.id enum key or fallback)."""
    if _T_ID is not None and _T_ID in m:
        return str(m[_T_ID])
    return str(m.get("id", ""))


def _string_props(m: dict[str, Any]) -> dict[str, Any]:
    """Copy only string-keyed entries (skip gremlin T.* enum keys)."""
    return {k: v for k, v in m.items() if isinstance(k, str)}


def _row_as_dict(m: Any) -> dict[str, Any]:
    """Defensively coerce a row to dict."""
    if isinstance(m, dict):
        return m
    return {}


def _safe_str(v: Any) -> str:
    """Return the first element if v is a list, else str(v)."""
    if isinstance(v, list):
        return str(v[0]) if v else ""
    return str(v) if v is not None else ""


class GremlinNormalizer:
    """Shapes elementMap rows into EvidenceRecord instances (Normalizer protocol)."""

    # -- Normalizer protocol -------------------------------------------------

    def normalize(
        self,
        rows: list[dict[str, Any]],
        resolved: ResolvedTask,
        query: str,
        card: Any,
    ) -> list[EvidenceRecord]:
        """Dispatch to the appropriate per-template normalization path."""
        if not rows:
            return []

        # Detect result shape from the first non-empty row.
        # Check most-specific shapes first.
        first = rows[0]
        if "w" in first and "ap" in first and "tax" in first:
            return self._normalize_cwe_chain(rows, resolved, query, card)
        if "ap" in first and "parent" in first and "grandparent" in first:
            return self._normalize_hierarchy_chain(rows, resolved, query, card)
        if "ap" in first and "tax" in first:
            return self._normalize_maps_to(rows, resolved, query, card)
        if "ap" in first and "nbr" in first:
            return self._normalize_neighbors(rows, resolved, query, card)
        # Single flat rows (capec_lookup, capec_scan).
        return self._normalize_single(rows, resolved, query, card)

    def summarize(
        self, records: list[EvidenceRecord], resolved: ResolvedTask
    ) -> str:
        """One grounded sentence citing CAPEC ids and mapped T-numbers."""
        if not records:
            return "No CAPEC records found."

        primary_ids = [r.primary_id for r in records if r.primary_id]
        join_vals: list[str] = []
        for r in records:
            join_vals.extend(r.join_values)

        capec_part = ", ".join(sorted(set(primary_ids))[:5])
        if len(primary_ids) > 5:
            capec_part += f" … (+{len(primary_ids) - 5} more)"

        if join_vals:
            t_part = ", ".join(sorted(set(join_vals))[:5])
            return (
                f"Found {len(records)} CAPEC record(s) for {capec_part}; "
                f"ATT&CK mappings: {t_part}."
            )
        return f"Found {len(records)} CAPEC record(s): {capec_part}."

    # -- per-shape helpers --------------------------------------------------

    def _normalize_single(
        self,
        rows: list[dict[str, Any]],
        resolved: ResolvedTask,
        query: str,
        card: Any,
    ) -> list[EvidenceRecord]:
        id_scheme: str = card.provenance.get("id_scheme", "capec-id")
        records: list[EvidenceRecord] = []
        for row in rows:
            m = _row_as_dict(row)
            gid = _safe_str(m.get("id", ""))
            primary_id = _primary_id_from_gremlin_id(gid)
            name = _safe_str(m.get("name", ""))
            label = _get_label(m) or "AttackPattern"
            record_id = _get_record_id(m) or gid
            props = _string_props(m)
            records.append(
                emit_record(
                    card=card,
                    query=query,
                    record_id=record_id,
                    primary_id=primary_id,
                    id_scheme=id_scheme,
                    label=label,
                    name=name,
                    properties=props,
                )
            )
        return records

    def _normalize_neighbors(
        self,
        rows: list[dict[str, Any]],
        resolved: ResolvedTask,
        query: str,
        card: Any,
    ) -> list[EvidenceRecord]:
        """Group neighbours under their anchor AttackPattern."""
        id_scheme: str = card.provenance.get("id_scheme", "capec-id")
        # Group by anchor CAPEC id.
        groups: dict[str, dict[str, Any]] = {}  # primary_id -> record_dict
        for row in rows:
            ap_m = _row_as_dict(row.get("ap", {}))
            nbr_m = _row_as_dict(row.get("nbr", {}))

            gid = _safe_str(ap_m.get("id", ""))
            primary_id = _primary_id_from_gremlin_id(gid)
            name = _safe_str(ap_m.get("name", ""))
            label = _get_label(ap_m) or "AttackPattern"
            record_id = _get_record_id(ap_m) or gid

            if primary_id not in groups:
                groups[primary_id] = {
                    "record_id": record_id,
                    "primary_id": primary_id,
                    "name": name,
                    "label": label,
                    "props": _string_props(ap_m),
                    "related": [],
                }

            # Build a lightweight neighbour summary.
            nbr_props = _string_props(nbr_m)
            nbr_id = _safe_str(nbr_m.get("id", ""))
            nbr_name = _safe_str(nbr_m.get("name", "")) or nbr_id
            nbr_label = _get_label(nbr_m)
            related_entry: dict[str, Any] = {
                "id": nbr_id,
                "name": nbr_name,
                "label": nbr_label,
                **{k: v for k, v in nbr_props.items() if k not in ("id", "name")},
            }
            groups[primary_id]["related"].append(related_entry)

        records: list[EvidenceRecord] = []
        for grp in groups.values():
            records.append(
                emit_record(
                    card=card,
                    query=query,
                    record_id=grp["record_id"],
                    primary_id=grp["primary_id"],
                    id_scheme=id_scheme,
                    label=grp["label"],
                    name=grp["name"],
                    properties=grp["props"],
                    related=grp["related"],
                )
            )
        return records

    def _normalize_maps_to(
        self,
        rows: list[dict[str, Any]],
        resolved: ResolvedTask,
        query: str,
        card: Any,
    ) -> list[EvidenceRecord]:
        """One record per anchor AttackPattern, join_values = T-prefixed entry_ids."""
        id_scheme: str = card.provenance.get("id_scheme", "capec-id")
        groups: dict[str, dict[str, Any]] = {}
        for row in rows:
            ap_m = _row_as_dict(row.get("ap", {}))
            tax_m = _row_as_dict(row.get("tax", {}))

            gid = _safe_str(ap_m.get("id", ""))
            primary_id = _primary_id_from_gremlin_id(gid)
            name = _safe_str(ap_m.get("name", ""))
            label = _get_label(ap_m) or "AttackPattern"
            record_id = _get_record_id(ap_m) or gid

            if primary_id not in groups:
                groups[primary_id] = {
                    "record_id": record_id,
                    "primary_id": primary_id,
                    "name": name,
                    "label": label,
                    "props": _string_props(ap_m),
                    "join_values": [],
                    "related": [],
                }

            # Only ATTACK taxonomy entries contribute to join_values.
            taxonomy_name = _safe_str(tax_m.get("taxonomy_name", ""))
            entry_id = _safe_str(tax_m.get("entry_id", ""))
            if taxonomy_name == "ATTACK" and entry_id:
                t_value = f"T{entry_id}" if not entry_id.startswith("T") else entry_id
                groups[primary_id]["join_values"].append(t_value)

            # Include as a related entry regardless.
            tax_props = _string_props(tax_m)
            related_entry = {
                "id": _safe_str(tax_m.get("id", "")),
                "name": _safe_str(tax_m.get("name", "")),
                "label": _get_label(tax_m) or "TaxonomyEntry",
                "entry_id": entry_id,
                "taxonomy_name": taxonomy_name,
            }
            groups[primary_id]["related"].append(related_entry)
            _ = tax_props  # available but not spread to keep related lean

        records: list[EvidenceRecord] = []
        for grp in groups.values():
            records.append(
                emit_record(
                    card=card,
                    query=query,
                    record_id=grp["record_id"],
                    primary_id=grp["primary_id"],
                    id_scheme=id_scheme,
                    label=grp["label"],
                    name=grp["name"],
                    properties=grp["props"],
                    related=grp["related"],
                    join_values=tuple(grp["join_values"]),
                )
            )
        return records

    def _normalize_cwe_chain(
        self,
        rows: list[dict[str, Any]],
        resolved: ResolvedTask,
        query: str,
        card: Any,
    ) -> list[EvidenceRecord]:
        """cwe_chain rows: {"w":.., "ap":.., "tax":..}

        One record per unique AttackPattern anchor.
        related = unique CWE ids from w elements.
        join_values = T-prefixed ATTACK taxonomy entry_ids (same rule as maps_to).
        """
        id_scheme: str = card.provenance.get("id_scheme", "capec-id")
        groups: dict[str, dict[str, Any]] = {}
        for row in rows:
            ap_m = _row_as_dict(row.get("ap", {}))
            w_m = _row_as_dict(row.get("w", {}))
            tax_m = _row_as_dict(row.get("tax", {}))

            gid = _safe_str(ap_m.get("id", ""))
            primary_id = _primary_id_from_gremlin_id(gid)
            name = _safe_str(ap_m.get("name", ""))
            label = _get_label(ap_m) or "AttackPattern"
            record_id = _get_record_id(ap_m) or gid

            if primary_id not in groups:
                groups[primary_id] = {
                    "record_id": record_id,
                    "primary_id": primary_id,
                    "name": name,
                    "label": label,
                    "props": _string_props(ap_m),
                    "join_values": [],
                    "related": [],
                    "_cwe_ids_seen": set(),
                }

            # Collect CWE related entries (deduplicated).
            w_gid = _safe_str(w_m.get("id", ""))
            cwe_primary = _cwe_primary_id(w_gid)
            if cwe_primary not in groups[primary_id]["_cwe_ids_seen"]:
                groups[primary_id]["_cwe_ids_seen"].add(cwe_primary)
                groups[primary_id]["related"].append({"id": cwe_primary})

            # Collect T-prefixed ATTACK join_values (same logic as maps_to).
            taxonomy_name = _safe_str(tax_m.get("taxonomy_name", ""))
            entry_id = _safe_str(tax_m.get("entry_id", ""))
            if taxonomy_name == "ATTACK" and entry_id:
                t_value = f"T{entry_id}" if not entry_id.startswith("T") else entry_id
                if t_value not in groups[primary_id]["join_values"]:
                    groups[primary_id]["join_values"].append(t_value)

        records: list[EvidenceRecord] = []
        for grp in groups.values():
            records.append(
                emit_record(
                    card=card,
                    query=query,
                    record_id=grp["record_id"],
                    primary_id=grp["primary_id"],
                    id_scheme=id_scheme,
                    label=grp["label"],
                    name=grp["name"],
                    properties=grp["props"],
                    related=grp["related"],
                    join_values=tuple(grp["join_values"]),
                )
            )
        return records

    def _normalize_hierarchy_chain(
        self,
        rows: list[dict[str, Any]],
        resolved: ResolvedTask,
        query: str,
        card: Any,
    ) -> list[EvidenceRecord]:
        """hierarchy_chain rows: {"ap":.., "parent":.., "grandparent":..}

        One record per unique ap anchor.
        related = unique [{"id": CAPEC-nn of parent}, {"id": CAPEC-nn of grandparent}].
        No join_values.
        """
        id_scheme: str = card.provenance.get("id_scheme", "capec-id")
        groups: dict[str, dict[str, Any]] = {}
        for row in rows:
            ap_m = _row_as_dict(row.get("ap", {}))
            parent_m = _row_as_dict(row.get("parent", {}))
            gp_m = _row_as_dict(row.get("grandparent", {}))

            gid = _safe_str(ap_m.get("id", ""))
            primary_id = _primary_id_from_gremlin_id(gid)
            name = _safe_str(ap_m.get("name", ""))
            label = _get_label(ap_m) or "AttackPattern"
            record_id = _get_record_id(ap_m) or gid

            if primary_id not in groups:
                groups[primary_id] = {
                    "record_id": record_id,
                    "primary_id": primary_id,
                    "name": name,
                    "label": label,
                    "props": _string_props(ap_m),
                    "related": [],
                    "_related_ids_seen": set(),
                }

            for ancestor_m in (parent_m, gp_m):
                anc_gid = _safe_str(ancestor_m.get("id", ""))
                anc_primary = _primary_id_from_gremlin_id(anc_gid)
                if anc_primary and anc_primary not in groups[primary_id]["_related_ids_seen"]:
                    groups[primary_id]["_related_ids_seen"].add(anc_primary)
                    groups[primary_id]["related"].append({"id": anc_primary})

        records: list[EvidenceRecord] = []
        for grp in groups.values():
            records.append(
                emit_record(
                    card=card,
                    query=query,
                    record_id=grp["record_id"],
                    primary_id=grp["primary_id"],
                    id_scheme=id_scheme,
                    label=grp["label"],
                    name=grp["name"],
                    properties=grp["props"],
                    related=grp["related"],
                )
            )
        return records
