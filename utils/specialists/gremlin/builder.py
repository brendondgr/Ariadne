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
from utils.specialists.resolve import (
    ResolvedTask,
    is_definitional_intent,
    is_dossier_intent,
)
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
_CWE_NUM_RE = re.compile(r"^CWE-(\d+)$", re.IGNORECASE)
_ATTACK_ENTRY_RE = re.compile(r"^T(\d{4}(?:\.\d{3})?)$", re.IGNORECASE)


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
          4. capec_dossier_by_name — seedless definitional name lookup
          5. capec_scan     — fallback: scan by primary label
        """
        has_seeds = bool(resolved.seed_ids)
        has_join = resolved.has_join or resolved.join_key == "attack-technique-id"
        neighbor_rel = _resolve_neighbor_rel(resolved)

        # NEW: capec_hierarchy_chain — two or more "ChildOf" in raw entities AND seeds.
        if (
            has_seeds
            and resolved.task.entities.count("ChildOf") >= 2
        ):
            return self._capec_hierarchy_chain(resolved)

        if has_join:
            # Split by seed shape before falling through to existing capec_maps_to.
            if has_seeds and all(_CWE_NUM_RE.match(s) for s in resolved.seed_ids):
                return self._cwe_chain(resolved)
            if has_seeds and all(_ATTACK_ENTRY_RE.match(s) for s in resolved.seed_ids):
                return self._capec_reverse_maps(resolved)
            return self._capec_maps_to(resolved)
        if has_seeds and neighbor_rel:
            return self._capec_neighbors(resolved, neighbor_rel)
        if has_seeds:
            # A single-entity deep dive fetches the full node + a typed 1-hop
            # neighborhood; a bare lookup stays lean (elementMap only).
            if is_dossier_intent(resolved.task.text):
                return self._capec_dossier(resolved)
            return self._capec_lookup(resolved)
        # Seedless definitional name lookup ("What is Phishing?"): anchor an
        # AttackPattern dossier on the extracted name terms instead of scanning
        # every pattern.
        if resolved.name_terms and is_definitional_intent(resolved.task.text):
            return self._capec_dossier_by_name(resolved)
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

    def _capec_dossier(self, resolved: ResolvedTask) -> QueryDraft:
        """Full vertex (elementMap, incl. description) + its typed 1-hop neighbors.

        ``project`` returns, per anchor, the node's elementMap and its outgoing
        and incoming edges (each as ``{rel: <label>, other: <elementMap>}``). The
        untyped ``outE()``/``inE()`` surface every edge kind and, having no label
        argument, sidestep the schema gate's relationship-type/direction checks —
        the Gremlin analogue of the Cypher dossier's untyped ``-[r]-``.
        """
        ids = [_capec_gremlin_id(s) for s in resolved.seed_ids]
        lim = resolved.task.max_rows()
        query = (
            'g.V().hasLabel("AttackPattern").has("id", within(ids))'
            '.project("node","out","in")'
            ".by(elementMap())"
            '.by(outE().project("rel","other").by(label()).by(inV().elementMap()).fold())'
            '.by(inE().project("rel","other").by(label()).by(outV().elementMap()).fold())'
            f".limit({lim})"
        )
        return QueryDraft(
            query=query,
            params={"ids": ids},
            template="capec_dossier",
            expected_nonempty=bool(ids),
            meta={"anchor_label": "AttackPattern", "seed_ids": list(resolved.seed_ids)},
        )

    def _capec_dossier_by_name(self, resolved: ResolvedTask) -> QueryDraft:
        """Name-anchored CAPEC dossier: the definitional counterpart of ``_capec_dossier``.

        Anchors ``AttackPattern`` by a case-insensitive name match on the
        extracted name terms (no id needed), reusing the concept-scan's
        ``TextP.regex`` machinery, and returns the identical
        ``project("node","out","in")`` shape so the shape-dispatched dossier
        normalizer surfaces the pattern's description + typed neighbors unchanged.
        ``expected_nonempty`` is False because a name that matches no pattern is
        a legitimate miss, handled as an honest abstention downstream.
        """
        terms = [t for t in resolved.name_terms if t]
        # Escape regex metacharacters; drop any embedded quote defensively so the
        # literal cannot break out of the Gremlin string.
        pattern = "|".join(re.escape(t.replace('"', "")) for t in terms)
        lim = resolved.task.max_rows()
        query = (
            'g.V().hasLabel("AttackPattern")'
            f'.has("name", TextP.regex("(?i).*({pattern}).*"))'
            '.project("node","out","in")'
            ".by(elementMap())"
            '.by(outE().project("rel","other").by(label()).by(inV().elementMap()).fold())'
            '.by(inE().project("rel","other").by(label()).by(outV().elementMap()).fold())'
            f".limit({lim})"
        )
        return QueryDraft(
            query=query,
            params={},
            template="capec_dossier_by_name",
            expected_nonempty=False,
            meta={"anchor_label": "AttackPattern", "name_terms": list(terms)},
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
        elif resolved.concept_terms:
            # Scope the mapping scan to the concept the question names
            # (committed vocabulary in concepts.py) instead of every pattern.
            pattern = "|".join(resolved.concept_terms)
            anchor = (
                'g.V().hasLabel("AttackPattern")'
                f'.has("name", TextP.regex("(?i).*({pattern}).*"))'
            )
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

    def _capec_hierarchy_chain(self, resolved: ResolvedTask) -> QueryDraft:
        ids = [_capec_gremlin_id(s) for s in resolved.seed_ids]
        lim = resolved.task.max_rows()
        params: dict[str, Any] = {"ids": ids}
        child_of_edge = gremlin_edge_label("ChildOf")
        query = (
            'g.V().hasLabel("AttackPattern").has("id", within(ids)).as("ap")'
            f'.out("{child_of_edge}").hasLabel("AttackPattern").as("parent")'
            f'.out("{child_of_edge}").hasLabel("AttackPattern").as("grandparent")'
            f'.select("ap","parent","grandparent").by(elementMap()).limit({lim})'
        )
        return QueryDraft(
            query=query,
            params=params,
            template="capec_hierarchy_chain",
            expected_nonempty=bool(ids),
            meta={
                "anchor_label": "AttackPattern",
                "rel": child_of_edge,
            },
        )

    def _cwe_chain(self, resolved: ResolvedTask) -> QueryDraft:
        cwe_ids = [
            f"cwe:{_CWE_NUM_RE.match(s).group(1)}"  # type: ignore[union-attr]
            for s in resolved.seed_ids
        ]
        lim = resolved.task.max_rows()
        params: dict[str, Any] = {"cweIds": cwe_ids}
        query = (
            'g.V().hasLabel("Weakness").has("id", within(cweIds)).as("w")'
            '.in("EXPLOITS_WEAKNESS").hasLabel("AttackPattern").as("ap")'
            '.out("MAPS_TO").hasLabel("TaxonomyEntry").has("taxonomy_name","ATTACK").as("tax")'
            f'.select("w","ap","tax").by(elementMap()).limit({lim})'
        )
        return QueryDraft(
            query=query,
            params=params,
            template="cwe_chain",
            expected_nonempty=bool(cwe_ids),
            meta={
                "anchor_label": "Weakness",
                "neighbor_label": "TaxonomyEntry",
                "rel": "EXPLOITS_WEAKNESS",
            },
        )

    def _capec_reverse_maps(self, resolved: ResolvedTask) -> QueryDraft:
        entry_ids = [
            _ATTACK_ENTRY_RE.match(s).group(1)  # type: ignore[union-attr]
            for s in resolved.seed_ids
        ]
        lim = resolved.task.max_rows()
        params: dict[str, Any] = {"entryIds": entry_ids}
        query = (
            'g.V().hasLabel("TaxonomyEntry").has("taxonomy_name","ATTACK")'
            '.has("entry_id", within(entryIds)).as("tax")'
            '.in("MAPS_TO").hasLabel("AttackPattern").as("ap")'
            f'.select("ap","tax").by(elementMap()).limit({lim})'
        )
        return QueryDraft(
            query=query,
            params=params,
            template="capec_reverse_maps",
            expected_nonempty=bool(entry_ids),
            meta={
                "anchor_label": "TaxonomyEntry",
                "neighbor_label": "AttackPattern",
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
