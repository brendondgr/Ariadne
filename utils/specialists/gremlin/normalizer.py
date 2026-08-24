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

from utils.graph_loader.stores.gremlin import gremlin_edge_label
from utils.specialists.contracts import EvidenceRecord
from utils.specialists.evidence import emit_record
from utils.specialists.primitives.describe import fold_facets, merge_zero_facets
from utils.specialists.primitives.expand import ExpandRequest, ExpandResult, paginate
from utils.specialists.resolve import ResolvedTask
from utils.specialists.schema.registry import PlausibleFacet

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


# A bounded expand-member description keeps a large fan-out a page of summaries
# rather than full records (the primitive's scale guarantee). Read through the
# env at call time so an un-truncated retrieval profile can lift it
# (``SPECIALIST_EXPAND_DESC_CHARS``) without touching the default behaviour.
_EXPAND_DESC_CHARS = 400


def _bound_expand_desc(desc: str) -> str:
    from utils.config import env_int

    cap = env_int("SPECIALIST_EXPAND_DESC_CHARS", _EXPAND_DESC_CHARS)
    return desc[:cap] + ("…" if len(desc) > cap else "")


#: The single edge a neighbours query traverses, e.g. ``.out("CHILD_OF")``. The
#: builder emits exactly one such step for the neighbours template, so reading it
#: back is deterministic — and the rows themselves never carry the edge.
_TRAVERSAL_EDGE_RE = re.compile(r'\.(?:out|in|both)\(\s*"([A-Z_]+)"\s*\)')


def _traversal_edge(query: str) -> str:
    """The relationship a neighbours query walked, or '' when it is ambiguous."""
    found = _TRAVERSAL_EDGE_RE.findall(query or "")
    unique = list(dict.fromkeys(found))
    return unique[0] if len(unique) == 1 else ""


_CAPEC_AP_FULL_RE = re.compile(r"^capec:attack-pattern:(\d+)$")


def _expand_member_id(gremlin_id: str) -> str:
    """Member identity for expand: convert a *clean* CAPEC/CWE id, else keep raw.

    Unlike ``_primary_id_from_gremlin_id`` (which prefix-matches and so collapses a
    composite child id like ``capec:attack-pattern:66:mitigation:0`` to its parent
    ``CAPEC-66``), this fullmatches — so a Mitigation/Consequence/ExecutionStep
    member keeps its own honest id instead of masquerading as its parent pattern.
    """
    gid = gremlin_id or ""
    m = _CAPEC_AP_FULL_RE.match(gid)
    if m:
        return f"CAPEC-{m.group(1)}"
    m = _CWE_GREMLIN_RE.match(gid)
    if m:
        return f"CWE-{m.group(1)}"
    return gid


#: Public alias for the rule above. The merged-graph build (C-015) has to give
#: its CAPEC half the *same* public-id surface the federated Gremlin path gives
#: it — ``CAPEC-<n>`` and ``CWE-<n>`` and nothing else, with composite children
#: keeping their raw ids — or the merged arm answers with identifiers no gold
#: assertion can match, and the comparison measures a formatting difference
#: rather than an architecture one. Reused rather than copied: two copies of an
#: id-normalisation rule drift, and the drift is invisible until a figure moves.
public_member_id = _expand_member_id


def _card_plausible_gremlin(card: Any, label: str) -> list[PlausibleFacet]:
    """Plausible facets for ``label`` with rel types in the loaded gremlin form.

    The registry keeps CAPEC's source vocabulary (``CanFollow``); the loaded graph
    labels edges SCREAMING_SNAKE (``CAN_FOLLOW``). Converting the plausible facets
    to the loaded form lets the honest-zero merge dedupe against observed edges.
    Degrades to no zeros when the registry is unavailable.
    """
    try:
        return [
            PlausibleFacet(gremlin_edge_label(p.rel_type), p.direction, p.neighbour_label)
            for p in card.label_facets(label)
        ]
    except Exception:  # noqa: BLE001 — a missing registry must never sink a result
        return []


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
        # Outer-join bridge: ``tax`` is a *folded list* of mappings, possibly
        # empty, rather than a single element. Checked before every other shape
        # because it is the only one whose ``tax`` is a list — the inner-join
        # shapes below are untouched and still route where they always did.
        if "ap" in first and isinstance(first.get("tax"), list):
            return self._normalize_bridge_outer(rows, resolved, query, card)
        if "w" in first and "ap" in first and "tax" in first:
            return self._normalize_cwe_chain(rows, resolved, query, card)
        if "ap" in first and "parent" in first and "grandparent" in first:
            return self._normalize_hierarchy_chain(rows, resolved, query, card)
        if "ap" in first and "tax" in first:
            return self._normalize_maps_to(rows, resolved, query, card)
        if "node" in first and "out" in first and "in" in first:
            return self._normalize_describe(rows, resolved, query, card)
        if "ap" in first and "nbr" in first:
            return self._normalize_neighbors(rows, resolved, query, card)
        # Single flat rows (capec_scan).
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

    def normalize_expand(
        self, rows: list[dict[str, Any]], request: ExpandRequest
    ) -> ExpandResult:
        """Shape expand member rows (``{id, name, label}`` each) into an ExpandResult.

        The Gremlin ``expand`` query returns every member (CAPEC facets are small),
        so the true total is the row count and the page slice + truncation flag are
        computed here. CAPEC vertex ids are normalised back to ``CAPEC-N`` form.
        """
        members: list[dict[str, Any]] = []
        for row in rows:
            m = _row_as_dict(row)
            member = {
                "id": _expand_member_id(_safe_str(m.get("id"))),
                "name": _safe_str(m.get("name")),
                "label": _safe_str(m.get("label")),
            }
            desc = _safe_str(m.get("description"))
            if desc:
                member["description"] = _bound_expand_desc(desc)
            members.append(member)
        return paginate(members, request)

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

    def _normalize_describe(
        self,
        rows: list[dict[str, Any]],
        resolved: ResolvedTask,
        query: str,
        card: Any,
    ) -> list[EvidenceRecord]:
        """describe rows: ``{"node":<elementMap>, "out":[{rel,label}], "in":[...]}``.

        One record per anchor: **every** vertex property (no allow-list) into
        ``properties``, and every 1-hop edge folded into a bounded ``facets`` count
        by ``(rel, direction, neighbour label)``. The registry's plausible facets
        are folded in as honest zeros — but converted through ``gremlin_edge_label``
        first, because the loaded graph carries the SCREAMING_SNAKE edge label
        (``CAN_FOLLOW``) while the canonical registry keeps CAPEC's source
        vocabulary (``CanFollow``); without the conversion the same facet would
        appear twice.
        """
        id_scheme: str = card.provenance.get("id_scheme", "capec-id")
        records: list[EvidenceRecord] = []
        for row in rows:
            node = _row_as_dict(row.get("node", {}))
            gid = _safe_str(node.get("id", ""))
            primary_id = _primary_id_from_gremlin_id(gid)
            name = _safe_str(node.get("name", ""))
            label = _get_label(node) or "AttackPattern"
            properties = _string_props(node)

            edges: list[tuple[str, str, str]] = []
            for entry, direction in ((row.get("out") or [], "out"), (row.get("in") or [], "in")):
                for e in entry:
                    e = _row_as_dict(e)
                    rel = _safe_str(e.get("rel"))
                    if rel:
                        edges.append((rel, direction, _safe_str(e.get("label"))))
            observed = fold_facets(edges)
            facets = merge_zero_facets(observed, _card_plausible_gremlin(card, label))

            records.append(
                emit_record(
                    card=card,
                    query=query,
                    record_id=_get_record_id(node) or gid,
                    primary_id=primary_id,
                    id_scheme=id_scheme,
                    label=label,
                    name=name,
                    properties=dict(properties),
                    facets=[f.to_dict() for f in facets],
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
        # The traversal edge, recovered from the query the builder emitted. The
        # rows carry the neighbour vertices but not the edge that reached them,
        # and the relationship IS the answer for a hierarchy question.
        edge_type = _traversal_edge(query)
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
            # The anchor's id is canonicalised above, but the neighbour's was left
            # raw — so a CHILD_OF parent surfaced as "capec:attack-pattern:560"
            # instead of "CAPEC-560" and no gold assertion could match it.
            # ``_expand_member_id`` fullmatches, so a clean AttackPattern/CWE id is
            # canonicalised while a composite child (mitigation/step/consequence)
            # keeps its own identity rather than collapsing to its parent.
            nbr_id = _expand_member_id(_safe_str(nbr_m.get("id", "")))
            nbr_name = _safe_str(nbr_m.get("name", "")) or nbr_id
            nbr_label = _get_label(nbr_m)
            related_entry: dict[str, Any] = {
                "id": nbr_id,
                "name": nbr_name,
                "label": nbr_label,
                **{k: v for k, v in nbr_props.items() if k not in ("id", "name")},
            }
            # Carry the edge type. Without it the record says only *that* CAPEC-98
            # has a related AttackPattern, not that CAPEC-151 is its CHILD_OF
            # parent — so an answer bound to the claims cannot name the
            # relationship the question asked about, and honestly reports that it
            # cannot confirm one.
            if edge_type:
                related_entry["type"] = edge_type
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

    def _normalize_bridge_outer(
        self,
        rows: list[dict[str, Any]],
        resolved: ResolvedTask,
        query: str,
        card: Any,
    ) -> list[EvidenceRecord]:
        """Outer-join bridge rows: ``{"ap":.., "tax":[..]}`` (+ optional ``"w"``).

        One record per anchor, always — including anchors whose mapping list is
        **empty**. That empty case is the whole point: it is what lets an answer
        say "this pattern maps to nothing" and cite the record it read, instead
        of having no record at all and abstaining without provenance.

        ``join_values`` follows the same rule as the inner-join paths: only
        ATTACK taxonomy entries contribute, T-prefixed. An anchor with no
        mappings contributes none, which is what correctly stands the dependent
        federated hop down.
        """
        id_scheme: str = card.provenance.get("id_scheme", "capec-id")
        records: list[EvidenceRecord] = []
        for row in rows:
            ap_m = _row_as_dict(row.get("ap", {}))
            gid = _safe_str(ap_m.get("id", ""))
            primary_id = _primary_id_from_gremlin_id(gid)

            join_values: list[str] = []
            related: list[dict[str, Any]] = []

            # The seed the chain started from, when the anchor was reached
            # through a prefix (a CWE-anchored question).
            w_m = _row_as_dict(row.get("w", {}))
            if w_m:
                related.append({"id": _cwe_primary_id(_safe_str(w_m.get("id", "")))})

            for entry in row.get("tax") or []:
                tax_m = _row_as_dict(entry)
                taxonomy_name = _safe_str(tax_m.get("taxonomy_name", ""))
                entry_id = _safe_str(tax_m.get("entry_id", ""))
                if taxonomy_name == "ATTACK" and entry_id:
                    t_value = (
                        f"T{entry_id}" if not entry_id.startswith("T") else entry_id
                    )
                    if t_value not in join_values:
                        join_values.append(t_value)
                related.append(
                    {
                        "id": _safe_str(tax_m.get("id", "")),
                        "name": _safe_str(tax_m.get("name", "")),
                        "label": _get_label(tax_m) or "TaxonomyEntry",
                        "entry_id": entry_id,
                        "taxonomy_name": taxonomy_name,
                    }
                )

            records.append(
                emit_record(
                    card=card,
                    query=query,
                    record_id=_get_record_id(ap_m) or gid,
                    primary_id=primary_id,
                    id_scheme=id_scheme,
                    label=_get_label(ap_m) or "AttackPattern",
                    name=_safe_str(ap_m.get("name", "")),
                    properties=_string_props(ap_m),
                    related=related,
                    join_values=tuple(join_values),
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

            # Parent is the standard ancestor, grandparent the meta ancestor.
            # Carry the role (and the ancestor's own Abstraction/name) so the
            # composer can label which is which — flattening these to bare ids
            # left the narrator unable to distinguish them and, worse, claiming
            # the ancestors were absent when they were right here in ``related``.
            for position, ancestor_m in (("standard", parent_m), ("meta", gp_m)):
                anc_gid = _safe_str(ancestor_m.get("id", ""))
                anc_primary = _primary_id_from_gremlin_id(anc_gid)
                if anc_primary and anc_primary not in groups[primary_id]["_related_ids_seen"]:
                    groups[primary_id]["_related_ids_seen"].add(anc_primary)
                    abstraction = _safe_str(ancestor_m.get("Abstraction", ""))
                    entry: dict[str, Any] = {
                        "id": anc_primary,
                        "role": abstraction.lower() if abstraction else position,
                        "label": _get_label(ancestor_m) or "AttackPattern",
                    }
                    anc_name = _safe_str(ancestor_m.get("name", ""))
                    if anc_name:
                        entry["name"] = anc_name
                    if abstraction:
                        entry["abstraction"] = abstraction
                    groups[primary_id]["related"].append(entry)

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
