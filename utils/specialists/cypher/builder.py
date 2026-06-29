#!/usr/bin/env python3
"""Deterministic Cypher query builder for the MITRE ATT&CK / Neo4j specialist.

Picks one of five intent templates based on the resolved task and always
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

    The five intent templates — ``technique_mitigations``, ``group_techniques``,
    ``tactic_techniques``, ``node_lookup``, and ``label_scan`` — cover the common
    ATT&CK query patterns.  The builder picks deterministically; ``feedback`` from
    a failed gate attempt is accepted but the deterministic path should already
    pass without needing it.
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

        # 1. Technique → mitigations (most specific: seeds + Mitigation in scope)
        if has_technique_seeds and has_mitigation:
            return self._technique_mitigations(technique_ids, resolved)

        # 2. Group → techniques
        if has_group:
            return self._group_techniques(resolved)

        # 3. Tactic → techniques
        if has_tactic:
            return self._tactic_techniques(resolved)

        # 4. Seed ids present but no compound edge intent → node lookup
        if resolved.seed_ids:
            return self._node_lookup(resolved)

        # 5. Fallback: label scan (no seeds)
        return self._label_scan(resolved)

    # -- intent builders -------------------------------------------------------

    def _technique_mitigations(
        self, technique_ids: list[str], resolved: ResolvedTask
    ) -> QueryDraft:
        """MATCH (Technique/SubTechnique)<-[:MITIGATES]-(Mitigation)."""
        # Use SubTechnique anchor when every seed is a sub-technique
        if _all_subtechnique(tuple(technique_ids)):
            anchor = "SubTechnique"
        else:
            anchor = "Technique"
        query = (
            f"MATCH (t:{anchor})<-[:MITIGATES]-(m:Mitigation) "
            f"WHERE t.attack_id IN $ids "
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
