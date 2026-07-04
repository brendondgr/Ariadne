#!/usr/bin/env python3
"""Gremlin query builder for the CAPEC specialist.

Deterministically drafts bounded Gremlin traversals from a resolved task.
All value parameters go into the bindings dict (never string-interpolated);
structural identifiers (labels, relationship types) are inlined as literals
after card validation. Every query ends with an injected .limit(lim).
"""

from __future__ import annotations

import re
from typing import Any

from utils.graph_loader.stores.gremlin import gremlin_edge_label
from utils.specialists.resolve import ResolvedTask
from utils.specialists.validation import QueryDraft

# Relationships that fan out from AttackPattern to direct neighbours.
# The hierarchy natures (ChildOf, CanPrecede) are declared-direction only:
# the graph stores edges exactly as the CAPEC XML declares them and never
# materializes inverses, so out("ChildOf") answers "what is X's parent" and
# out("CanPrecede") answers "what can X precede". ParentOf/CanFollow stay
# unroutable until the builder learns in()-traversals.
_AP_NEIGHBOR_RELS = frozenset({
    "EXPLOITS_WEAKNESS",
    "HAS_MITIGATION",
    "HAS_EXECUTION_STEP",
    "HAS_CONSEQUENCE",
    "REQUIRES_SKILL",
    "ChildOf",
    "CanPrecede",
})

# Mapping from relationship name to expected target label (for meta).
_REL_TARGET_LABEL: dict[str, str] = {
    "EXPLOITS_WEAKNESS": "Weakness",
    "HAS_MITIGATION": "Mitigation",
    "HAS_EXECUTION_STEP": "ExecutionStep",
    "HAS_CONSEQUENCE": "Consequence",
    "REQUIRES_SKILL": "Skill",
    "MEMBER_OF": "Category",
    "ChildOf": "AttackPattern",
    "ParentOf": "AttackPattern",
    "CanFollow": "AttackPattern",
    "CanPrecede": "AttackPattern",
    "CanAlsoBe": "AttackPattern",
    "PeerOf": "AttackPattern",
}

_CAPEC_NUM_RE = re.compile(r"CAPEC-(\d+)", re.IGNORECASE)


def _capec_gremlin_id(capec_id: str) -> str:
    """Convert 'CAPEC-66' -> 'capec:attack-pattern:66'."""
    m = _CAPEC_NUM_RE.fullmatch(capec_id.strip())
    if m:
        return f"capec:attack-pattern:{m.group(1)}"
    # Already in gremlin form or unknown: return as-is.
    return capec_id


def _resolve_neighbor_rel(resolved: ResolvedTask) -> str | None:
    """Return the first resolved relationship that makes sense for a neighbour query."""
    for rel in resolved.relationships:
        if rel in _AP_NEIGHBOR_RELS:
            return rel
    return None


class GremlinQueryBuilder:
    """Deterministic Gremlin query builder (QueryBuilder protocol)."""

    def build(
        self,
        resolved: ResolvedTask,
        feedback: list[str] | None = None,
    ) -> QueryDraft:
        """Draft a bounded Gremlin query from *resolved* task context.

        Chooses template in priority order:
          1. capec_maps_to  — join_key is set (ATT&CK join)
          2. capec_lookup   — seed CAPEC ids present, no neighbour relationship
          3. capec_neighbors — seed ids + neighbour relationship in scope
          4. capec_scan     — fallback: scan by primary label
        """
        has_seeds = bool(resolved.seed_ids)
        has_join = resolved.has_join or resolved.join_key == "attack-technique-id"
        neighbor_rel = _resolve_neighbor_rel(resolved)

        if has_join:
            return self._capec_maps_to(resolved)
        if has_seeds and neighbor_rel:
            return self._capec_neighbors(resolved, neighbor_rel)
        if has_seeds:
            return self._capec_lookup(resolved)
        return self._capec_scan(resolved)

    # -- templates ----------------------------------------------------------

    def _capec_lookup(self, resolved: ResolvedTask) -> QueryDraft:
        ids = [_capec_gremlin_id(s) for s in resolved.seed_ids]
        lim = resolved.task.max_rows()
        params: dict[str, Any] = {"ids": ids}
        query = (
            'g.V().hasLabel("AttackPattern").has("id", within(ids))'
            f".elementMap().limit({lim})"
        )
        return QueryDraft(
            query=query,
            params=params,
            template="capec_lookup",
            expected_nonempty=bool(ids),
            meta={"anchor_label": "AttackPattern"},
        )

    def _capec_neighbors(self, resolved: ResolvedTask, rel: str) -> QueryDraft:
        ids = [_capec_gremlin_id(s) for s in resolved.seed_ids]
        target_label = _REL_TARGET_LABEL.get(rel, "")
        lim = resolved.task.max_rows()
        params: dict[str, Any] = {"ids": ids}

        edge = gremlin_edge_label(rel)  # loaded graphs use SCREAMING_SNAKE labels
        if target_label:
            query = (
                f'g.V().hasLabel("AttackPattern").has("id", within(ids)).as("ap")'
                f'.out("{edge}").hasLabel("{target_label}").as("nbr")'
                f'.select("ap","nbr").by(elementMap()).limit({lim})'
            )
        else:
            query = (
                f'g.V().hasLabel("AttackPattern").has("id", within(ids)).as("ap")'
                f'.out("{edge}").as("nbr")'
                f'.select("ap","nbr").by(elementMap()).limit({lim})'
            )
        return QueryDraft(
            query=query,
            params=params,
            template="capec_neighbors",
            expected_nonempty=bool(ids),
            meta={
                "anchor_label": "AttackPattern",
                "neighbor_label": target_label or "",
                "rel": rel,
            },
        )

    def _capec_maps_to(self, resolved: ResolvedTask) -> QueryDraft:
        lim = resolved.task.max_rows()
        params: dict[str, Any] = {}
        if resolved.seed_ids:
            params["ids"] = [_capec_gremlin_id(s) for s in resolved.seed_ids]
            anchor = 'g.V().hasLabel("AttackPattern").has("id", within(ids))'
        else:
            anchor = 'g.V().hasLabel("AttackPattern")'

        query = (
            f'{anchor}.as("ap")'
            '.out("MAPS_TO").hasLabel("TaxonomyEntry").has("taxonomy_name","ATTACK").as("tax")'
            f'.select("ap","tax").by(elementMap()).limit({lim})'
        )
        return QueryDraft(
            query=query,
            params=params,
            template="capec_maps_to",
            expected_nonempty=bool(resolved.seed_ids),
            meta={
                "anchor_label": "AttackPattern",
                "neighbor_label": "TaxonomyEntry",
                "rel": "MAPS_TO",
            },
        )

    def _capec_scan(self, resolved: ResolvedTask) -> QueryDraft:
        label = resolved.primary_label() or "AttackPattern"
        lim = resolved.task.max_rows()
        params: dict[str, Any] = {}
        query = f'g.V().hasLabel("{label}").elementMap().limit({lim})'
        return QueryDraft(
            query=query,
            params=params,
            template="capec_scan",
            expected_nonempty=False,
            meta={"anchor_label": label},
        )
