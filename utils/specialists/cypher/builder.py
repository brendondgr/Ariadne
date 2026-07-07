#!/usr/bin/env python3
"""Deterministic Cypher query builder for the MITRE ATT&CK / Neo4j specialist.

Picks one of thirteen intent templates based on the resolved task and always
produces a query that will pass ``CypherValidator`` by construction — real
card labels/edges, parameterised values, an explicit LIMIT placeholder.
"""

from __future__ import annotations

import re
from typing import Any

from ..resolve import ResolvedTask
from ..validation import QueryDraft

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


def _is_technique_id(aid: str) -> bool:
    return bool(_TECHNIQUE_RE.match(aid))


def _all_subtechnique(ids: tuple[str, ...]) -> bool:
    return bool(ids) and all(bool(_SUBTECHNIQUE_RE.match(i)) for i in ids)


class CypherQueryBuilder:
    """Drafts a bounded Cypher query from a resolved task.

    The thirteen intent templates — ``technique_detection``,
    ``technique_mitigations``, ``campaign_attribution``, ``campaign_techniques``,
    ``group_techniques``, ``subtechnique_parent``, ``software_techniques``,
    ``tactic_technique_mitigations``, ``technique_tactics``,
    ``tactic_techniques``, ``datacomponent_analytics``, ``node_lookup``, and
    ``label_scan`` — cover the common ATT&CK query patterns.  The builder picks
    deterministically; ``feedback`` from a failed gate attempt is accepted but
    the deterministic path should already pass without needing it.
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

        # 5. Seed ids present but no compound edge intent → node lookup
        if resolved.seed_ids:
            return self._node_lookup(resolved)

        # 6. Fallback: label scan (no seeds)
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
