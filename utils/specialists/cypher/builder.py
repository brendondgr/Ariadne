#!/usr/bin/env python3
"""Deterministic Cypher query builder for the MITRE ATT&CK / Neo4j specialist.

Picks one of fifteen intent templates based on the resolved task and always
produces a query that will pass ``CypherValidator`` by construction — real
card labels/edges, parameterised values, an explicit LIMIT placeholder.
"""

from __future__ import annotations

import re
from typing import Any

from ...planner.intent import is_definitional_request
from ..primitives.expand import ExpandRequest
from ..resolve import ResolvedTask
from ..validation import QueryDraft

_SAFE_LABEL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_SAFE_REL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def _safe_ident(value: str, pattern: re.Pattern[str], kind: str) -> str:
    """Guard a facet-sourced label/rel before inlining it into a query string."""
    if not pattern.match(value or ""):
        raise ValueError(f"unsafe {kind} for expand: {value!r}")
    return value

_TECHNIQUE_RE = re.compile(r"^T\d{4}(?:\.\d{3})?$")
_SUBTECHNIQUE_RE = re.compile(r"^T\d{4}\.\d{3}$")
_TACTIC_RE = re.compile(r"^TA\d{4}$")
_MITIGATION_RE = re.compile(r"^M\d{4}$")
_SOFTWARE_RE = re.compile(r"^S\d{4}$")
_DATACOMPONENT_RE = re.compile(r"^DC\d{4}$")

# When a seedless scan must pick one anchor label, prefer the substantive ATT&CK
# objects over the single administrative nodes (Matrix) and detection internals.
_SCAN_LABEL_PRIORITY = (
    "Technique",
    "SubTechnique",
    "Group",
    "Software",
    "Mitigation",
    "Tactic",
    "Campaign",
)


def _preferred_scan_label(resolved: ResolvedTask) -> str:
    """Pick the most query-worthy resolved label for a seedless scan."""
    labels = set(resolved.labels)
    for label in _SCAN_LABEL_PRIORITY:
        if label in labels:
            return label
    return resolved.primary_label() or "Technique"


# Description-bearing ATT&CK labels a name lookup may resolve to. Explicit (not
# card-derived) so the multi-label OR guard is fixed and validator-safe; every
# one carries a ``name`` and a description inside ``properties_json``.
_NAME_DESCRIBE_LABELS: tuple[str, ...] = (
    "Technique",
    "SubTechnique",
    "Mitigation",
    "Tactic",
    "Group",
    "Software",
    "Campaign",
    "DataComponent",
    "DetectionStrategy",
)

# Seed-id prefix → node label, so a dossier anchors on the right label even when
# the planner did not name the entity type explicitly.
_ID_PREFIX_LABELS: tuple[tuple[re.Pattern[str], str], ...] = (
    (_TACTIC_RE, "Tactic"),
    (_MITIGATION_RE, "Mitigation"),
    (_SOFTWARE_RE, "Software"),
    (_DATACOMPONENT_RE, "DataComponent"),
    (re.compile(r"^DET\d{4}$"), "DetectionStrategy"),
    (re.compile(r"^G\d{4}$"), "Group"),
    (re.compile(r"^C\d{4}$"), "Campaign"),
    (_SUBTECHNIQUE_RE, "SubTechnique"),
    (_TECHNIQUE_RE, "Technique"),
)


def _describe_label(resolved: ResolvedTask) -> str:
    """Anchor label for describe: the resolved label, else inferred from the id."""
    label = resolved.primary_label()
    if label:
        return label
    for aid in resolved.seed_ids:
        for pattern, inferred in _ID_PREFIX_LABELS:
            if pattern.match(aid):
                return inferred
    return "Technique"


def _is_technique_id(aid: str) -> bool:
    return bool(_TECHNIQUE_RE.match(aid))


def _all_subtechnique(ids: tuple[str, ...]) -> bool:
    return bool(ids) and all(bool(_SUBTECHNIQUE_RE.match(i)) for i in ids)


class CypherQueryBuilder:
    """Drafts a bounded Cypher query from a resolved task.

    The fifteen intent templates — ``technique_detection``,
    ``technique_mitigations``, ``campaign_attribution``, ``campaign_techniques``,
    ``group_techniques``, ``subtechnique_parent``, ``software_techniques``,
    ``tactic_technique_mitigations``, ``technique_tactics``,
    ``tactic_techniques``, ``datacomponent_analytics``, ``node_lookup``,
    ``node_dossier``, ``node_dossier_by_name``, and ``label_scan`` — cover the
    common ATT&CK query patterns.  The builder picks deterministically;
    ``feedback`` from a failed gate attempt is accepted but the deterministic
    path should already pass without needing it.
    """

    def build(
        self, resolved: ResolvedTask, feedback: list[str] | None = None
    ) -> QueryDraft:
        """Return a ``QueryDraft`` whose query string is valid Cypher."""
        # Choose intent deterministically from the resolved task context.
        technique_ids = [aid for aid in resolved.seed_ids if _is_technique_id(aid)]
        has_technique_seeds = bool(technique_ids)
        has_mitigation = "Mitigation" in resolved.labels or "Mitigation" in (
            resolved.task.entities or ()
        )
        has_group = "Group" in resolved.labels or "Group" in (
            resolved.task.entities or ()
        )
        has_tactic = "Tactic" in resolved.labels or "Tactic" in (
            resolved.task.entities or ()
        )
        has_campaign = "Campaign" in resolved.labels or "Campaign" in (
            resolved.task.entities or ()
        )
        has_technique_entity = bool(
            {"Technique", "SubTechnique"}
            & (set(resolved.labels) | set(resolved.task.entities or ()))
        )
        has_detection = "DetectionStrategy" in resolved.labels or "DetectionStrategy" in (
            resolved.task.entities or ()
        )
        has_datacomponent = "DataComponent" in resolved.labels or "DataComponent" in (
            resolved.task.entities or ()
        )
        has_analytic = "Analytic" in resolved.labels or "Analytic" in (
            resolved.task.entities or ()
        )
        has_software_entity = "Software" in resolved.labels or "Software" in (
            resolved.task.entities or ()
        )
        has_subtechnique_rel = "HAS_SUBTECHNIQUE" in resolved.relationships

        # Partition seeds by prefix
        tactic_seed_ids = [aid for aid in resolved.seed_ids if _TACTIC_RE.match(aid)]
        mitigation_seed_ids = [aid for aid in resolved.seed_ids if _MITIGATION_RE.match(aid)]
        software_seed_ids = [aid for aid in resolved.seed_ids if _SOFTWARE_RE.match(aid)]
        dc_seed_ids = [aid for aid in resolved.seed_ids if _DATACOMPONENT_RE.match(aid)]

        # 0a. technique_detection — technique seeds + DetectionStrategy in scope
        if has_technique_seeds and has_detection:
            return self._technique_detection(technique_ids, resolved)

        # 1. Technique → mitigations (most specific: seeds + Mitigation in scope)
        if has_technique_seeds and has_mitigation:
            return self._technique_mitigations(technique_ids, resolved)

        # 2. Campaign edges — must outrank the Group branch, which would
        # otherwise capture a Campaign+Group attribution task.
        if has_campaign and has_group:
            return self._campaign_attribution(resolved)
        if has_campaign and has_technique_entity:
            return self._campaign_techniques(resolved)

        # 3. Group → techniques
        if has_group:
            return self._group_techniques(resolved)

        # 4a. subtechnique_parent — HAS_SUBTECHNIQUE relationship in scope + seeds
        if has_subtechnique_rel and resolved.seed_ids:
            return self._subtechnique_parent(resolved)

        # 4b. software_techniques — Software + Technique/SubTechnique entities + S-seeds
        #     (must NOT capture node_lookup for Software-only or label_scan with no seeds)
        if (
            has_software_entity
            and has_technique_entity
            and bool(software_seed_ids)
        ):
            return self._software_techniques(software_seed_ids, resolved)

        # 4c. tactic_technique_mitigations — both TA and M seeds present
        if has_tactic and has_mitigation and tactic_seed_ids and mitigation_seed_ids:
            return self._tactic_technique_mitigations(
                tactic_seed_ids, mitigation_seed_ids, resolved
            )

        # 4d. technique_tactics (reverse rollup) — tactic scope + T-seeds
        if has_tactic and has_technique_seeds:
            return self._technique_tactics(technique_ids, resolved)

        # 5a. datacomponent_analytics — DataComponent + Analytic + DC seeds
        if has_datacomponent and has_analytic and bool(dc_seed_ids):
            return self._datacomponent_analytics(dc_seed_ids, resolved)

        # 4. Tactic → techniques
        if has_tactic:
            return self._tactic_techniques(resolved)

        # 5. Seed ids present but no compound edge intent → describe the anchor:
        #    every property + a bounded facet block. describe subsumes the old
        #    node_lookup and node_dossier — it always returns the full record, so
        #    there is no cheap "lean lookup" path left to protect and no
        #    describe-verb intent left to gate on.
        if resolved.seed_ids:
            return self._describe(resolved)

        # 6. No seeds but a definitional question that names an entity ("What is
        #    User Training?") → describe by name. The definitional cue keeps a
        #    broad enumeration ("scan all techniques") on the label-scan path
        #    rather than mistaking an incidental capitalized word for an anchor.
        if (
            resolved.name_terms
            and not resolved.has_join
            and is_definitional_request(resolved.task.text)
        ):
            return self._describe(resolved)

        # 7. Fallback: label scan (no anchor at all).
        return self._label_scan(resolved)

    # -- intent builders -------------------------------------------------------

    def _technique_mitigations(
        self, technique_ids: list[str], resolved: ResolvedTask
    ) -> QueryDraft:
        """MATCH (Technique/SubTechnique) with OPTIONAL MITIGATES mitigations.

        The anchor covers both labels so a mixed seed set (parents plus
        sub-techniques, e.g. one harvested from a CAPEC producer) misses
        nothing, and the mitigation hop is OPTIONAL so a technique with no
        MITIGATES edges still returns — an honest empty mitigation list, not
        a silently dropped technique.
        """
        if _all_subtechnique(tuple(technique_ids)):
            anchor = "SubTechnique"
            match = f"MATCH (t:{anchor}) WHERE t.attack_id IN $ids "
        elif all(not _SUBTECHNIQUE_RE.match(i) for i in technique_ids):
            anchor = "Technique"
            match = f"MATCH (t:{anchor}) WHERE t.attack_id IN $ids "
        else:
            anchor = "Technique|SubTechnique"
            match = (
                "MATCH (t) WHERE (t:Technique OR t:SubTechnique) "
                "AND t.attack_id IN $ids "
            )
        query = (
            f"{match}"
            f"OPTIONAL MATCH (t)<-[:MITIGATES]-(m:Mitigation) "
            f"RETURN t.attack_id AS technique_id, t.name AS technique_name, "
            f"m.attack_id AS mitigation_id, m.name AS mitigation_name"
        )
        return QueryDraft(
            query=query,
            params={"ids": list(technique_ids)},
            template="technique_mitigations",
            expected_nonempty=True,
            meta={"anchor_label": anchor, "seed_ids": list(technique_ids)},
        )

    def _group_techniques(self, resolved: ResolvedTask) -> QueryDraft:
        """MATCH (Group)-[:USES]->(Technique)."""
        seed_ids = list(resolved.seed_ids)
        if seed_ids:
            query = (
                "MATCH (g:Group)-[:USES]->(t:Technique) "
                "WHERE g.attack_id IN $ids "
                "RETURN g.attack_id AS group_id, g.name AS group_name, "
                "t.attack_id AS technique_id, t.name AS technique_name"
            )
            params: dict[str, Any] = {"ids": seed_ids}
        else:
            query = (
                "MATCH (g:Group)-[:USES]->(t:Technique) "
                "RETURN g.attack_id AS group_id, g.name AS group_name, "
                "t.attack_id AS technique_id, t.name AS technique_name"
            )
            params = {}
        return QueryDraft(
            query=query,
            params=params,
            template="group_techniques",
            meta={"seed_ids": seed_ids},
        )

    def _campaign_techniques(self, resolved: ResolvedTask) -> QueryDraft:
        """MATCH (Campaign)-[:USES]->(Technique)."""
        seed_ids = list(resolved.seed_ids)
        if seed_ids:
            query = (
                "MATCH (c:Campaign)-[:USES]->(t:Technique) "
                "WHERE c.attack_id IN $ids "
                "RETURN c.attack_id AS campaign_id, c.name AS campaign_name, "
                "t.attack_id AS technique_id, t.name AS technique_name"
            )
            params: dict[str, Any] = {"ids": seed_ids}
        else:
            query = (
                "MATCH (c:Campaign)-[:USES]->(t:Technique) "
                "RETURN c.attack_id AS campaign_id, c.name AS campaign_name, "
                "t.attack_id AS technique_id, t.name AS technique_name"
            )
            params = {}
        return QueryDraft(
            query=query,
            params=params,
            template="campaign_techniques",
            meta={"seed_ids": seed_ids},
        )

    def _campaign_attribution(self, resolved: ResolvedTask) -> QueryDraft:
        """MATCH (Campaign)-[:ATTRIBUTED_TO]->(Group)."""
        seed_ids = list(resolved.seed_ids)
        if seed_ids:
            query = (
                "MATCH (c:Campaign)-[:ATTRIBUTED_TO]->(g:Group) "
                "WHERE c.attack_id IN $ids "
                "RETURN c.attack_id AS campaign_id, c.name AS campaign_name, "
                "g.attack_id AS group_id, g.name AS group_name"
            )
            params: dict[str, Any] = {"ids": seed_ids}
        else:
            query = (
                "MATCH (c:Campaign)-[:ATTRIBUTED_TO]->(g:Group) "
                "RETURN c.attack_id AS campaign_id, c.name AS campaign_name, "
                "g.attack_id AS group_id, g.name AS group_name"
            )
            params = {}
        return QueryDraft(
            query=query,
            params=params,
            template="campaign_attribution",
            meta={"seed_ids": seed_ids},
        )

    def _tactic_techniques(self, resolved: ResolvedTask) -> QueryDraft:
        """MATCH (Tactic)-[:HAS_TECHNIQUE]->(Technique)."""
        seed_ids = list(resolved.seed_ids)
        if seed_ids:
            query = (
                "MATCH (ta:Tactic)-[:HAS_TECHNIQUE]->(t:Technique) "
                "WHERE ta.attack_id IN $ids "
                "RETURN ta.attack_id AS tactic_id, ta.name AS tactic_name, "
                "t.attack_id AS technique_id, t.name AS technique_name"
            )
            params: dict[str, Any] = {"ids": seed_ids}
        else:
            query = (
                "MATCH (ta:Tactic)-[:HAS_TECHNIQUE]->(t:Technique) "
                "RETURN ta.attack_id AS tactic_id, ta.name AS tactic_name, "
                "t.attack_id AS technique_id, t.name AS technique_name"
            )
            params = {}
        return QueryDraft(
            query=query,
            params=params,
            template="tactic_techniques",
            meta={"seed_ids": seed_ids},
        )

    def _node_lookup(self, resolved: ResolvedTask) -> QueryDraft:
        """MATCH (n:<Label>) WHERE n.attack_id IN $ids RETURN id and name."""
        label = resolved.primary_label() or "Technique"
        seed_ids = list(resolved.seed_ids)
        query = (
            f"MATCH (n:{label}) "
            f"WHERE n.attack_id IN $ids "
            f"RETURN n.attack_id AS id, n.name AS name"
        )
        return QueryDraft(
            query=query,
            params={"ids": seed_ids},
            template="node_lookup",
            meta={"label": label, "seed_ids": seed_ids},
        )

    # The facet-block aggregation shared by both describe shapes: group every
    # 1-hop edge by (rel type, direction, neighbour label) and count. Server-side
    # aggregation keeps the payload a fraction of a KB even for an 858-degree hub
    # — the facet block is a count, never a neighbour list. The untyped ``-[r]-``
    # surfaces every edge kind and sidesteps the gate's relationship-type check;
    # a zero-degree node yields an empty block (the CASE filters the null group).
    _FACET_AGGREGATION = (
        "OPTIONAL MATCH (n)-[r]-(m) "
        "WITH n, "
        "CASE WHEN m IS NULL THEN NULL ELSE type(r) END AS rel, "
        "CASE WHEN m IS NULL THEN NULL ELSE startNode(r) = n END AS outgoing, "
        "CASE WHEN m IS NULL THEN NULL ELSE head(labels(m)) END AS neighbour_label, "
        "count(m) AS cnt "
        "WITH n, collect(CASE WHEN rel IS NULL THEN NULL ELSE "
        "{rel: rel, outgoing: outgoing, label: neighbour_label, count: cnt} END) AS raw "
        "WITH n, [f IN raw WHERE f IS NOT NULL] AS facets "
        "RETURN n.attack_id AS id, n.name AS name, "
        "n.properties_json AS properties_json, facets AS facets"
    )

    def _describe(self, resolved: ResolvedTask) -> QueryDraft:
        """The universal ``describe`` compiler: full node + bounded facet block.

        By id when the task carries seeds, else by name across the
        description-bearing labels. Returns ``n.properties_json`` (unpacked whole
        by the normalizer — no allow-list) alongside the aggregated facet block.
        There is no neighbour cap: the block is a count, so it cannot blow up.
        """
        if resolved.seed_ids:
            label = _describe_label(resolved)
            match = f"MATCH (n:{label}) WHERE n.attack_id IN $ids "
            return QueryDraft(
                query=match + self._FACET_AGGREGATION,
                params={"ids": list(resolved.seed_ids)},
                template="describe",
                expected_nonempty=True,
                meta={"label": label, "seed_ids": list(resolved.seed_ids)},
            )
        names = [term.lower() for term in resolved.name_terms]
        label_guard = " OR ".join(f"n:{label}" for label in _NAME_DESCRIBE_LABELS)
        match = (
            f"MATCH (n) WHERE ({label_guard}) "
            "AND any(term IN $names WHERE toLower(n.name) CONTAINS term) "
        )
        return QueryDraft(
            query=match + self._FACET_AGGREGATION,
            params={"names": names},
            template="describe_by_name",
            expected_nonempty=False,
            meta={"name_terms": list(resolved.name_terms)},
        )

    def expand(self, request: ExpandRequest) -> QueryDraft:
        """The ``expand`` compiler: one page of one facet's members, identity-only.

        Server-side sliced (``members[$skip..$end]``) with the true ``total`` from
        ``size(members)``, so a hub facet returns a bounded page while still
        reporting how many members exist — the honest truncation signal. The
        relationship type and both labels come from a facet the model saw, so they
        are real; they are guarded before inlining as belt-and-suspenders.
        """
        anchor = _safe_ident(request.anchor_label, _SAFE_LABEL_RE, "anchor label")
        rel = _safe_ident(request.rel_type, _SAFE_REL_RE, "relationship type")
        target = _safe_ident(request.target_label, _SAFE_LABEL_RE, "target label")
        hop = f"(n)-[:{rel}]->(m:{target})" if request.direction == "out" else f"(n)<-[:{rel}]-(m:{target})"
        query = (
            f"MATCH (n:{anchor}) WHERE n.attack_id = $id "
            f"MATCH {hop} "
            "WITH m ORDER BY coalesce(m.attack_id, m.id) "
            "WITH collect({id: coalesce(m.attack_id, m.id), name: m.name, "
            "label: head(labels(m))}) AS members "
            "RETURN members[$skip..$end] AS members, size(members) AS total"
        )
        return QueryDraft(
            query=query,
            params={"id": request.anchor_id, "skip": request.skip(), "end": request.end()},
            template="expand",
            expected_nonempty=False,
            meta=request.to_dict(),
        )

    def _technique_detection(
        self, technique_ids: list[str], resolved: ResolvedTask
    ) -> QueryDraft:
        """MATCH (Technique/SubTechnique)<-[:DETECTS]-(DetectionStrategy) with optional Analytic."""
        if _all_subtechnique(tuple(technique_ids)):
            anchor = "SubTechnique"
            match = f"MATCH (t:{anchor}) WHERE t.attack_id IN $ids "
        elif all(not _SUBTECHNIQUE_RE.match(i) for i in technique_ids):
            anchor = "Technique"
            match = f"MATCH (t:{anchor}) WHERE t.attack_id IN $ids "
        else:
            anchor = "Technique|SubTechnique"
            match = (
                "MATCH (t) WHERE (t:Technique OR t:SubTechnique) "
                "AND t.attack_id IN $ids "
            )
        query = (
            f"{match}"
            f"MATCH (t)<-[:DETECTS]-(d:DetectionStrategy) "
            f"OPTIONAL MATCH (d)-[:HAS_ANALYTIC]->(a:Analytic) "
            f"RETURN t.attack_id AS technique_id, t.name AS technique_name, "
            f"d.attack_id AS detection_id, d.name AS detection_name, "
            f"a.attack_id AS analytic_id, a.name AS analytic_name"
        )
        return QueryDraft(
            query=query,
            params={"ids": list(technique_ids)},
            template="technique_detection",
            expected_nonempty=True,
            meta={"anchor_label": anchor, "seed_ids": list(technique_ids)},
        )

    def _subtechnique_parent(self, resolved: ResolvedTask) -> QueryDraft:
        """MATCH (Technique)-[:HAS_SUBTECHNIQUE]->(SubTechnique) seeded by T or ST ids."""
        seed_ids = list(resolved.seed_ids)
        query = (
            "MATCH (t:Technique)-[:HAS_SUBTECHNIQUE]->(st:SubTechnique) "
            "WHERE t.attack_id IN $ids OR st.attack_id IN $ids "
            "RETURN t.attack_id AS parent_id, t.name AS parent_name, "
            "st.attack_id AS subtechnique_id, st.name AS subtechnique_name"
        )
        return QueryDraft(
            query=query,
            params={"ids": seed_ids},
            template="subtechnique_parent",
            meta={"seed_ids": seed_ids},
        )

    def _software_techniques(
        self, software_ids: list[str], resolved: ResolvedTask
    ) -> QueryDraft:
        """MATCH (Software)-[:USES]->(Technique/SubTechnique)."""
        query = (
            "MATCH (s:Software)-[:USES]->(t) "
            "WHERE (t:Technique OR t:SubTechnique) AND s.attack_id IN $ids "
            "RETURN s.attack_id AS software_id, s.name AS software_name, "
            "t.attack_id AS technique_id, t.name AS technique_name"
        )
        return QueryDraft(
            query=query,
            params={"ids": software_ids},
            template="software_techniques",
            meta={"seed_ids": software_ids},
        )

    def _tactic_technique_mitigations(
        self,
        tactic_ids: list[str],
        mitigation_ids: list[str],
        resolved: ResolvedTask,
    ) -> QueryDraft:
        """MATCH (Tactic)-[:HAS_TECHNIQUE]->(Technique)<-[:MITIGATES]-(Mitigation)."""
        query = (
            "MATCH (ta:Tactic)-[:HAS_TECHNIQUE]->(t:Technique) "
            "WHERE ta.attack_id IN $tactic_ids "
            "MATCH (t)<-[:MITIGATES]-(m:Mitigation) "
            "WHERE m.attack_id IN $mitigation_ids "
            "RETURN ta.attack_id AS tactic_id, ta.name AS tactic_name, "
            "t.attack_id AS technique_id, t.name AS technique_name, "
            "m.attack_id AS mitigation_id, m.name AS mitigation_name"
        )
        return QueryDraft(
            query=query,
            params={"tactic_ids": tactic_ids, "mitigation_ids": mitigation_ids},
            template="tactic_technique_mitigations",
            meta={"tactic_ids": tactic_ids, "mitigation_ids": mitigation_ids},
        )

    def _technique_tactics(
        self, technique_ids: list[str], resolved: ResolvedTask
    ) -> QueryDraft:
        """MATCH (Tactic)-[:HAS_TECHNIQUE]->(Technique/SubTechnique) — reverse rollup."""
        query = (
            "MATCH (ta:Tactic)-[:HAS_TECHNIQUE]->(t) "
            "WHERE (t:Technique OR t:SubTechnique) AND t.attack_id IN $ids "
            "RETURN t.attack_id AS technique_id, t.name AS technique_name, "
            "ta.attack_id AS in_tactic_id, ta.name AS in_tactic_name"
        )
        return QueryDraft(
            query=query,
            params={"ids": list(technique_ids)},
            template="technique_tactics",
            meta={"seed_ids": list(technique_ids)},
        )

    def _datacomponent_analytics(
        self, dc_ids: list[str], resolved: ResolvedTask
    ) -> QueryDraft:
        """MATCH (Analytic)-[:MONITORS]->(DataComponent)."""
        query = (
            "MATCH (a:Analytic)-[:MONITORS]->(dc:DataComponent) "
            "WHERE dc.attack_id IN $ids "
            "RETURN dc.attack_id AS datacomponent_id, dc.name AS datacomponent_name, "
            "a.attack_id AS analytic_id, a.name AS analytic_name"
        )
        return QueryDraft(
            query=query,
            params={"ids": dc_ids},
            template="datacomponent_analytics",
            meta={"seed_ids": dc_ids},
        )

    def _label_scan(self, resolved: ResolvedTask) -> QueryDraft:
        """MATCH (n:<Label>) RETURN attack_id and name — no seeds."""
        label = _preferred_scan_label(resolved)
        query = (
            f"MATCH (n:{label}) "
            f"RETURN n.attack_id AS id, n.name AS name"
        )
        return QueryDraft(
            query=query,
            params={},
            template="label_scan",
            meta={"label": label},
        )
