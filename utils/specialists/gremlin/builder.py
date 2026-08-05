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
from utils.planner.intent import is_definitional_request
from utils.specialists.primitives.expand import ExpandRequest
from utils.specialists.resolve import ResolvedTask
from utils.specialists.validation import QueryDraft

_SAFE_GREMLIN_IDENT = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def _safe_gremlin_ident(value: str, kind: str) -> str:
    if not _SAFE_GREMLIN_IDENT.match(value or ""):
        raise ValueError(f"unsafe {kind} for expand: {value!r}")
    return value

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


# Reverse of the AttackPattern-native subset of ``_REL_TARGET_LABEL``: a requested
# neighbour *label* ("Mitigation") implies the edge that reaches it
# ("HAS_MITIGATION"), so a plan that named only the label still expands the facet.
_AP_LABEL_TO_REL: dict[str, str] = {
    "Weakness": "EXPLOITS_WEAKNESS",
    "Mitigation": "HAS_MITIGATION",
    "ExecutionStep": "HAS_EXECUTION_STEP",
    "Consequence": "HAS_CONSEQUENCE",
    "Skill": "REQUIRES_SKILL",
}


def _generic_only() -> bool:
    """True when the MITRE-specific query templates are disabled.

    Set by ``SPECIALIST_GENERIC_ONLY`` for the "no hand-written templates"
    experiment: the pipeline must answer using only schema-driven primitives
    (describe / walk-one-declared-relationship / label scan), the way it would
    have to on a graph nobody has authored templates for. Off by default.
    """
    from utils.config import env_bool

    return env_bool("SPECIALIST_GENERIC_ONLY", False)


def _resolve_neighbor_rels(resolved: ResolvedTask) -> list[str]:
    """Every native AttackPattern facet relationship the task names, in order.

    Reads the resolved relationships *and* any requested neighbour label mapped
    back to its edge, so "the mitigations and weaknesses of X" expands both
    HAS_MITIGATION and EXPLOITS_WEAKNESS whether the planner named the edges or
    the labels. These native facets are the entity's own answer — preferred over a
    cross-source join the planner may have added spuriously.
    """
    rels: list[str] = []

    def _add(rel: str | None) -> None:
        if rel in _AP_NEIGHBOR_RELS and rel not in rels:
            rels.append(rel)

    for rel in resolved.relationships:
        _add(rel)
    for name in (*resolved.labels, *resolved.task.entities):
        _add(_AP_LABEL_TO_REL.get(name))
    return rels


# Names that signal a genuine CAPEC→ATT&CK bridge question ("…and what mitigations
# exist for the techniques it maps to"), so native-facet expansion must stand down
# and let ``_capec_maps_to`` handle the cross-source join.
_MAPPING_INTENT = frozenset({"MAPS_TO", "TaxonomyEntry", "Technique", "SubTechnique"})


def _has_mapping_intent(resolved: ResolvedTask) -> bool:
    """True when the task references the ATT&CK mapping (not just native facets)."""
    named = {*resolved.relationships, *resolved.labels, *resolved.task.entities}
    return bool(named & _MAPPING_INTENT)


class GremlinQueryBuilder:
    """Deterministic Gremlin query builder (QueryBuilder protocol)."""

    def build(
        self,
        resolved: ResolvedTask,
        feedback: list[str] | None = None,
    ) -> QueryDraft:
        """Draft a bounded Gremlin query from *resolved* task context.

        Chooses template in priority order:
          1. capec_hierarchy_chain — seeds + two or more ``ChildOf`` entities
          2. capec_neighbors / capec_facets — CAPEC-seeded, neighbour
             relationships in scope, and no mapping intent: one rel takes
             ``capec_neighbors``, several take ``capec_facets``
          3. join branch, when a join key is declared —
             cwe_chain (CWE-shaped seeds), capec_reverse_maps (ATT&CK-shaped
             seeds), else capec_maps_to
          4. describe — any remaining seeded task
          5. describe_by_name — seedless *definitional* question naming an
             entity (both emitted by :meth:`_describe`, which picks by whether
             seeds are present)
          6. capec_scan — fallback: scan by primary label

        ``capec_lookup`` was subsumed by ``describe`` and has no caller;
        ``capec_dossier_by_name`` was replaced by ``describe_by_name``.
        Under ``SPECIALIST_GENERIC_ONLY`` the cascade is bypassed entirely for
        the generic-primitives branch below.
        """
        has_seeds = bool(resolved.seed_ids)
        has_join = resolved.has_join or resolved.join_key == "attack-technique-id"
        neighbor_rels = _resolve_neighbor_rels(resolved)

        if _generic_only():
            # Schema-driven primitives only — no CAPEC question-shapes (no
            # MAPS_TO bridge, no hierarchy chain, no CWE chain). Everything here
            # is parameterised by a card-declared relationship or nothing at all.
            if has_seeds and len(neighbor_rels) == 1:
                return self._capec_neighbors(resolved, neighbor_rels[0])
            if has_seeds and neighbor_rels:
                return self._capec_facets(resolved, neighbor_rels)
            if has_seeds:
                return self._describe(resolved)
            if resolved.name_terms:
                return self._describe(resolved)
            return self._capec_scan(resolved)

        # NEW: capec_hierarchy_chain — two or more "ChildOf" in raw entities AND seeds.
        if (
            has_seeds
            and resolved.task.entities.count("ChildOf") >= 2
        ):
            return self._capec_hierarchy_chain(resolved)

        # Native facet expansion beats a spuriously-declared join: when the anchor
        # is a CAPEC pattern and the question is about its OWN edges (mitigations,
        # weaknesses, execution steps… of X), traverse them directly instead of
        # bridging to ATT&CK — which for a pattern with no MAPS_TO edge silently
        # returns nothing. Stands down for a genuine bridge question (one that names
        # the mapping/techniques), which _capec_maps_to handles, and for CWE- or
        # ATT&CK-seeded tasks (those anchor elsewhere and route via the join branch).
        capec_seeds = has_seeds and all(
            _CAPEC_NUM_RE.fullmatch(s.strip()) for s in resolved.seed_ids
        )
        if capec_seeds and neighbor_rels and not _has_mapping_intent(resolved):
            if len(neighbor_rels) == 1:
                return self._capec_neighbors(resolved, neighbor_rels[0])
            return self._capec_facets(resolved, neighbor_rels)

        if has_join:
            # Split by seed shape before falling through to existing capec_maps_to.
            if has_seeds and all(_CWE_NUM_RE.match(s) for s in resolved.seed_ids):
                return self._cwe_chain(resolved)
            if has_seeds and all(_ATTACK_ENTRY_RE.match(s) for s in resolved.seed_ids):
                return self._capec_reverse_maps(resolved)
            return self._capec_maps_to(resolved)
        if has_seeds:
            # describe the anchor: full vertex + bounded facet block. Subsumes the
            # old lean capec_lookup and the capec_dossier — describe always returns
            # the full record, so there is no describe-verb intent left to gate on.
            return self._describe(resolved)
        # Seedless definitional question that names an entity ("What is
        # Phishing?") → describe by name. The definitional cue keeps a broad
        # enumeration ("scan attack patterns") on the label-scan path.
        if resolved.name_terms and is_definitional_request(resolved.task.text):
            return self._describe(resolved)
        return self._capec_scan(resolved)

    # -- templates ----------------------------------------------------------

    def expand(self, request: ExpandRequest) -> QueryDraft:
        """The ``expand`` compiler: the members of one facet with a bounded description.

        Returns every member's ``(id, name, label, description)`` (CAPEC's max degree
        is 59, so the page is bounded even before slicing); the normalizer paginates,
        bounds the description, and computes the true total + truncation signal. The
        description is what lets a follow-up read a member's substance (an unnamed
        CAPEC mitigation node carries only a description) without a second hop; it is
        truncated so a fan-out stays a page of summaries, not full records.
        """
        anchor = _safe_gremlin_ident(request.anchor_label, "anchor label")
        rel = _safe_gremlin_ident(request.rel_type, "relationship type")
        target = _safe_gremlin_ident(request.target_label, "target label")
        step = "out" if request.direction == "out" else "in"
        query = (
            f'g.V().hasLabel("{anchor}").has("id", within(ids))'
            f'.{step}("{rel}").hasLabel("{target}")'
            '.project("id","name","label","description")'
            '.by(coalesce(values("id"), constant("")))'
            '.by(coalesce(values("name"), constant("")))'
            ".by(label())"
            '.by(coalesce(values("description"), constant("")))'
        )
        return QueryDraft(
            query=query,
            params={"ids": [_capec_gremlin_id(request.anchor_id)]},
            template="expand",
            expected_nonempty=False,
            meta=request.to_dict(),
        )

    # Dead: no production caller — `build()` routes every seeded task to
    # `_describe`, which subsumes this shape. Still referenced by
    # `utils/specialists/tests/test_gremlin_validator.py:215`, so it is kept
    # rather than deleted; removing it is a behavioural change, not tidying.
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

    # The facet-shaped projection shared by both describe forms. Unlike the old
    # dossier it returns only the neighbour's *label* per edge — never its
    # elementMap — so the normalizer can fold every edge into a bounded
    # ``(rel, direction, neighbour label)`` count without ever materialising a
    # neighbour list. The untyped ``outE()``/``inE()`` surface every edge kind
    # and sidestep the schema gate's relationship-type check (CAPEC's max degree
    # is 59, so folding client-side stays cheap).
    _FACET_PROJECTION = (
        '.project("node","out","in")'
        ".by(elementMap())"
        '.by(outE().project("rel","label").by(label()).by(inV().label()).fold())'
        '.by(inE().project("rel","label").by(label()).by(outV().label()).fold())'
    )

    def _describe(self, resolved: ResolvedTask) -> QueryDraft:
        """The universal ``describe`` compiler: full vertex + bounded facet block.

        By id when the task carries seeds, else by a case-insensitive name match
        across ``AttackPattern``. Returns the vertex elementMap (unpacked whole by
        the normalizer — no allow-list) alongside the folded facet block.
        """
        lim = resolved.task.max_rows()
        if resolved.seed_ids:
            ids = [_capec_gremlin_id(s) for s in resolved.seed_ids]
            anchor = 'g.V().hasLabel("AttackPattern").has("id", within(ids))'
            return QueryDraft(
                query=anchor + self._FACET_PROJECTION + f".limit({lim})",
                params={"ids": ids},
                template="describe",
                expected_nonempty=bool(ids),
                meta={"anchor_label": "AttackPattern", "seed_ids": list(resolved.seed_ids)},
            )
        # Wildcard-sanitize each term (any run of non-alphanumerics -> a single
        # ``.``) so the embedded regex carries no backslashes: re.escape emits
        # ``\ `` for the spaces in a multi-word name, which the Gremlin server's
        # Groovy parser rejects. ``.`` still matches the original separator.
        patterns = [
            p for p in (re.sub(r"[^A-Za-z0-9]+", ".", t).strip(".") for t in resolved.name_terms) if p
        ]
        pattern = "|".join(patterns)
        anchor = (
            'g.V().hasLabel("AttackPattern")'
            f'.has("name", TextP.regex("(?i).*({pattern}).*"))'
        )
        return QueryDraft(
            query=anchor + self._FACET_PROJECTION + f".limit({lim})",
            params={},
            template="describe_by_name",
            expected_nonempty=False,
            meta={"anchor_label": "AttackPattern", "name_terms": list(resolved.name_terms)},
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

    def _capec_facets(self, resolved: ResolvedTask, rels: list[str]) -> QueryDraft:
        """Expand several of the anchor's native facets in one query (union of edges).

        The intra-source answer to a multi-facet question ("the mitigations *and*
        weaknesses of X"): a union over each requested native edge yields the
        ``(anchor, neighbour)`` elementMap pairs the ``capec_neighbors`` normalizer
        already understands — no cross-source bridge, one round-trip.
        """
        ids = [_capec_gremlin_id(s) for s in resolved.seed_ids]
        lim = resolved.task.max_rows()
        branches: list[str] = []
        for rel in rels:
            edge = gremlin_edge_label(rel)
            target = _REL_TARGET_LABEL.get(rel, "")
            branches.append(
                f'out("{edge}").hasLabel("{target}")' if target else f'out("{edge}")'
            )
        query = (
            'g.V().hasLabel("AttackPattern").has("id", within(ids)).as("ap")'
            f'.union({", ".join(branches)}).as("nbr")'
            f'.select("ap","nbr").by(elementMap()).limit({lim})'
        )
        return QueryDraft(
            query=query,
            params={"ids": ids},
            template="capec_facets",
            expected_nonempty=bool(ids),
            meta={"anchor_label": "AttackPattern", "rels": list(rels)},
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
