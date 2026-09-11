#!/usr/bin/env python3
"""Gremlin query builder for the CAPEC specialist.

Deterministically drafts bounded Gremlin traversals from a resolved task.
All value parameters go into the bindings dict (never string-interpolated);
structural identifiers (labels, relationship types) are inlined as literals
after card validation. Every query ends with an injected .limit(lim).
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable
from typing import NamedTuple
from typing import Any

from utils.graph_loader.stores.gremlin import gremlin_edge_label
from utils.planner.intent import is_definitional_request
from utils.specialists.primitives.expand import ExpandRequest
from utils.specialists.resolve import ResolvedTask
from utils.specialists.validation import QueryDraft
from utils.planner.intent import asks_for_bulk_scan

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

#: Containment, as the graph actually stores it.
#:
#: The set above is the seven edges that leave an **AttackPattern**, and its name
#: says so. That made a View's or a Category's own containment edge invisible:
#: `_resolve_neighbor_rels` returned nothing for "which patterns does CAPEC-156
#: contain?", the ladder fell through to ``describe``, and the answer reported the
#: category's status. 63 questions in the expansion bank ask across this edge.
#:
#: **The census-derived bank and the graph name this edge from opposite ends.**
#: The bank asks in the source's vocabulary -- ``Category -[HAS_MEMBER]->
#: AttackPattern``, container to member -- while the build stores ``AttackPattern
#: -[MEMBER_OF]-> Category`` and ``AttackPattern -[IN_VIEW]-> View``, member to
#: container. ``HAS_MEMBER`` exists nowhere in the graph. Same edge, opposite
#: convention, and a traversal written in the bank's vocabulary returns nothing.
#:
#: So the edge is chosen by the **container's** kind and the direction by which
#: end the question anchors on. Both are resolved, never assumed; when neither
#: end identifies a container the question falls through to ``describe`` rather
#: than being answered with a guess.
_CONTAINMENT_EDGE_BY_CONTAINER = {"Category": "MEMBER_OF", "View": "IN_VIEW"}

#: Names a planner may reach containment by, in either vocabulary.
_MEMBERSHIP_ALIASES = frozenset({"HAS_MEMBER", "MEMBER_OF", "IN_VIEW"})

#: The CAPEC kinds that contain other kinds.
_CONTAINER_LABELS = frozenset(_CONTAINMENT_EDGE_BY_CONTAINER)

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

# How far the generic branch will chase a declared path. Matches the Cypher
# builder's cap; the traversal-depth limit is the operative bound above it.
_MAX_WALK_HOPS = 3

_CAPEC_NUM_RE = re.compile(r"CAPEC-(\d+)", re.IGNORECASE)
_CWE_NUM_RE = re.compile(r"^CWE-(\d+)$", re.IGNORECASE)
_ATTACK_ENTRY_RE = re.compile(r"^T(\d{4}(?:\.\d{3})?)$", re.IGNORECASE)


#: The vertex-id namespaces a bare ``CAPEC-<n>`` could name. CAPEC numbers one
#: sequence across all three kinds -- CAPEC-98 is an attack pattern, CAPEC-118 a
#: category, CAPEC-284 a view -- so the number alone cannot say which.
#:
#: ``cwe:`` is deliberately absent and must stay absent. ``cwe:284`` sits in the
#: same store as ``capec:view:284``, so resolving by number alone would let a
#: question about CAPEC-284 be answered by an unrelated weakness.
_CAPEC_ID_NAMESPACES = ("capec:attack-pattern:", "capec:view:", "capec:category:")

#: The vertex kinds a bare CAPEC name can refer to, for the name-anchored
#: describe. The seeded path needs no such list -- it anchors on the id.
_CAPEC_DESCRIBE_LABELS = ("AttackPattern", "View", "Category")


def _capec_id_bindings(param: str = "ids") -> list[dict[str, str]]:
    """Declared bindings for a label-free, id-anchored CAPEC query.

    `extract_bindings` prefers a declaration over parsing precisely so a builder
    can state a filter its parsers cannot read. Dropping ``hasLabel`` from these
    anchors is invisible to the Gremlin parser's ``hasLabel(...).has(prop, ...)``
    shape, and without this every affected draft turns "unchecked" -- the audit's
    own name for a query that filters on values nothing verified. 177 drafts went
    unchecked here before this was added, the same way 202 did on the Cypher side
    when ``describe`` widened its id column.

    One entry per candidate label, all on the same parameter: the anchor matches
    whichever kind holds the id, and `unsatisfiable_bindings` groups by
    parameter, so the filter is judged satisfiable when *any* of the three admits
    the seeds -- which is what the query means. Declaring a single label instead
    would assert something the builder deliberately does not know.
    """
    return [
        {"label": label, "property": "id", "param": param}
        for label in _CAPEC_DESCRIBE_LABELS
    ]


def _anchor_id_bindings(
    seed_ids: Iterable[str], anchor_label: str, param: str = "ids"
) -> list[dict[str, str]]:
    """Declared bindings for a label-free, id-anchored walk or bridge.

    Same reason as `_capec_id_bindings`: dropping ``hasLabel`` from an anchor
    makes the id filter invisible to the Gremlin parser's
    ``hasLabel(...).has(prop, ...)`` shape, so without a declaration the draft
    turns "unchecked" -- the audit's name for a query filtering on values
    nothing verified. The difference here is that a walk is not CAPEC-only: a
    ``CWE-<n>`` seed anchors on ``Weakness``, so the label the plan resolved is
    declared alongside the three CAPEC kinds a bare CAPEC number could name.

    `unsatisfiable_bindings` groups by parameter, so the filter is satisfiable
    when *any* declared label admits the seeds -- which is what the query means.
    """
    labels = list(_CAPEC_DESCRIBE_LABELS) if any(
        _CAPEC_NUM_RE.fullmatch(str(s).strip()) for s in seed_ids
    ) else []
    if anchor_label and anchor_label not in labels:
        labels.append(anchor_label)
    return [{"label": label, "property": "id", "param": param} for label in labels]


def _capec_gremlin_id(capec_id: str) -> str:
    """Convert 'CAPEC-66' -> 'capec:attack-pattern:66'.

    Retained for callers that mean an attack pattern specifically. Anything
    anchoring on a bare CAPEC id should use `_capec_candidate_ids`, because this
    function's assumption is wrong for roughly one CAPEC id in ten.
    """
    m = _CAPEC_NUM_RE.fullmatch(capec_id.strip())
    if m:
        return f"capec:attack-pattern:{m.group(1)}"
    # Already in gremlin form or unknown: return as-is.
    return capec_id


def _capec_candidate_ids(seeds: Iterable[str]) -> list[str]:
    """Every vertex id these CAPEC seeds could name, for an ``within(ids)`` anchor.

    ``CAPEC-284`` used to become ``capec:attack-pattern:284``, which no vertex
    has -- the view is ``capec:view:284`` -- so a question about a view searched
    for a pattern that did not exist and came back empty. The label filter on the
    anchor hid the shape of the failure but was not its cause: deleting it alone
    would have left the lookup missing in exactly the same way.

    Nothing here guesses. Ids are unique across the whole CAPEC store (6,374
    vertices, 6,374 distinct ids), so offering all three namespaces lets the
    graph disambiguate; at most one can match. Seeds already in URN form, and
    seeds in a scheme this does not know, pass through untouched so a wrong seed
    fails visibly instead of matching something else.
    """
    out: list[str] = []
    seen: set[str] = set()
    for seed in seeds:
        raw = str(seed).strip()
        match = _CAPEC_NUM_RE.fullmatch(raw)
        candidates = (
            [f"{ns}{match.group(1)}" for ns in _CAPEC_ID_NAMESPACES] if match else [raw]
        )
        for candidate in candidates:
            if candidate not in seen:
                seen.add(candidate)
                out.append(candidate)
    return out


def _walk_candidate_ids(seeds: Iterable[str]) -> list[str]:
    """Every vertex id a walk's seeds could name, across both catalogues.

    The generic walk used to build its anchor with ``_gremlin_vertex_id``, which
    sends every bare CAPEC number to ``capec:attack-pattern:<n>``. A Category or
    a View does not carry that id, so the anchor bound to nothing and the walk
    returned zero records before a single traversal step ran: all 21
    Category-anchored and 18 of the 20 View-anchored development questions
    (`EXP-2026-09-017` A-2, mechanism `ns`, 12.6% of the judged loss).

    The template path was given ``_capec_candidate_ids`` in July
    (`EXP-2026-09-003`) and the walk never adopted it. Swapping in that function
    alone would have been a regression, because it passes a ``CWE-<n>`` seed
    through untouched where ``_gremlin_vertex_id`` maps it to ``cwe:<n>`` -- the
    join-owner traversal depends on that. This composes the two: CAPEC seeds
    offer all three namespaces, everything else keeps the single canonical form.

    Nothing here guesses. Ids are unique across the CAPEC store, so at most one
    candidate can match and the graph does the disambiguating.
    """
    out: list[str] = []
    seen: set[str] = set()
    for seed in seeds:
        raw = str(seed).strip()
        candidates = (
            _capec_candidate_ids([raw])
            if _CAPEC_NUM_RE.fullmatch(raw)
            else [_gremlin_vertex_id(raw)]
        )
        for candidate in candidates:
            if candidate not in seen:
                seen.add(candidate)
                out.append(candidate)
    return out


def _gremlin_vertex_id(seed: str) -> str:
    """Normalise a seed identifier to the canonical vertex ``id`` property.

    The loaded graph keys every vertex by a URN the card's identity policy
    declares — ``capec:attack-pattern:<n>`` for a pattern, ``cwe:<n>`` for a
    weakness. This is id-*format* handling, the same category as the ``T``
    prefix on the declared join key: it says nothing about what a weakness means,
    only how the dataset spells its identifiers.

    Anything already in URN form, or in a scheme not declared here, is passed
    through untouched so the query fails visibly rather than silently matching
    the wrong vertex.
    """
    seed = seed.strip()
    m = _CAPEC_NUM_RE.fullmatch(seed)
    if m:
        return f"capec:attack-pattern:{m.group(1)}"
    m = _CWE_NUM_RE.match(seed)
    if m:
        return f"cwe:{m.group(1)}"
    return seed


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
    # The containment edge is not an AttackPattern facet, so it is resolved
    # separately -- and only when the question's ends actually say which way it
    # is being read. An undeterminable direction falls through to `describe`
    # rather than guessing, which is what the old behaviour did anyway, minus
    # the pretence of having routed.
    # Containment routes only when it is the *only* relation the question names.
    # A compound question names another edge first -- "which patterns are peers
    # of CAPEC-12, and what categories contain each of those?" carries
    # ``('PeerOf', 'MEMBER_OF')`` -- and routing on its second hop answers the
    # wrong one. That regression was real and measured: the question scored
    # 0.3333 through ``describe`` and 0.0000 through the containment traversal,
    # because CAPEC-12 is in no category and the peers were never fetched.
    named_rels = set(resolved.relationships)
    if named_rels and named_rels <= _MEMBERSHIP_ALIASES:
        plan = _membership_plan(resolved)
        if plan is not None and plan[0] not in rels:
            rels.append(plan[0])
    return rels


def _membership_plan(resolved: ResolvedTask) -> tuple[str, str] | None:
    """``(edge, step)`` for a containment question, or ``None`` if unclear.

    The **container's** kind picks the edge, because the graph stores a
    Category's membership as ``MEMBER_OF`` and a View's as ``IN_VIEW``. The
    anchor's role picks the direction: the graph runs member to container, so a
    question anchored on the container reads it ``in`` and one anchored on the
    member reads it ``out``.

    20 of the bank's 63 membership questions ask from the member's end, so a
    fixed direction would answer 43 and silently return nothing for the rest --
    one wrong answer traded for another. ``.both()`` is not the fix either: a
    Category has members *and* a containing View, so it would over-return on
    exactly the common case.

    ``labels[0]`` is the anchor -- the order the plan listed the entities in.
    A label the card does not declare never reaches ``labels``, so a question
    whose container end is unresolvable returns ``None`` and falls through to
    ``describe`` rather than being answered by a guess.
    """
    labels = [label for label in resolved.labels if label]
    if not labels:
        return None
    anchor, rest = labels[0], labels[1:]
    if anchor in _CONTAINER_LABELS:
        return _CONTAINMENT_EDGE_BY_CONTAINER[anchor], "in"
    for label in rest:
        if label in _CONTAINER_LABELS:
            return _CONTAINMENT_EDGE_BY_CONTAINER[label], "out"
    return None


# Names that signal a genuine CAPEC→ATT&CK bridge question ("…and what mitigations
# exist for the techniques it maps to"), so native-facet expansion must stand down
# and let ``_capec_maps_to`` handle the cross-source join.
_MAPPING_INTENT = frozenset({"MAPS_TO", "TaxonomyEntry", "Technique", "SubTechnique"})


def _has_mapping_intent(resolved: ResolvedTask) -> bool:
    """True when the task references the ATT&CK mapping (not just native facets)."""
    named = {*resolved.relationships, *resolved.labels, *resolved.task.entities}
    return bool(named & _MAPPING_INTENT)


def _seed_from_name(resolved: ResolvedTask):
    """Resolve the question's entity by name.

    Returns a re-seeded task, an ``AmbiguousName`` when the question names more
    than one entity, or ``None``.

    **Two tiers, gated separately, because they are different kinds of
    evidence.** An exact name is a lookup and needs no threshold; a ranked
    similarity match is a guess and needs one. EXP-2026-08-020 measured them
    welded together: 3 answers gained, 12 wrong bought — and **ten of the twelve
    came from tiers where no exact name appears at all**, so the ranked half
    caused them. Splitting the flags lets the clean win ship without the dirty
    one.
    """
    if resolved.seed_ids:
        return None
    # A bulk request names a category, not an entity. "List ATT&CK software
    # entries" matched a node called `enterprise-attack`, seeded it, and
    # returned 1 record against a gold of 821 (A-SCN-01, Arm 3).
    if asks_for_bulk_scan(resolved.task.text):
        return None
    from dataclasses import replace

    from ..schema.namesearch import exact_name_matches, resolve_in

    labels = tuple(resolved.labels) or tuple(resolved.task.entities or ())

    if _exactname_on_g():
        exact = exact_name_matches(resolved.dataset, resolved.task.text, labels=labels)
        if len(exact) == 1:
            return replace(resolved, seed_ids=(exact[0].entity_id,))
        if len(exact) > 1:
            # **Several exact names is a conjunction, not an ambiguity.**
            # "What exactly is User Training and Software Configuration
            # respectively?" names two entities and wants both, and the
            # existing describe-by-name path already serves several names in
            # one query. Treating that as "which did you mean?" would refuse a
            # question the system answers correctly today.
            #
            # Genuine ambiguity is one phrase that could denote several
            # entities — and with exact matching plus the subsumption filter
            # that case does not arise here: a surviving second match means the
            # question named a second thing, not that the first was unclear.
            # So this falls through, and the ambiguity surface belongs on the
            # fuzzy path where a name really can be under-determined.
            return None

    if _namesearch_on_g():
        hit = resolve_in(resolved.dataset, resolved.task.text, labels=labels)
        if hit is not None:
            return replace(resolved, seed_ids=(hit.entity_id,))
    return None


class AmbiguousName(NamedTuple):
    """The question names several entities; the analyst picks, not us."""

    candidates: tuple[tuple[str, str], ...]


def _exactname_on_g() -> bool:
    import os

    return os.environ.get("ARIADNE_EXACTNAME", "1").strip().lower() not in {"0", "false", "no", "off"}


def _namesearch_on_g() -> bool:
    import os

    return os.environ.get("ARIADNE_NAMESEARCH", "").strip().lower() in {"1", "true", "yes", "on"}


def _unanchored_abstains() -> bool:
    """Does an unanchored question abstain instead of scanning the label?

    Off by default, and shares `ARIADNE_LEXICON`'s lifecycle: widening word
    matching without this makes the dumps worse, not better. See the Cypher
    builder's copy for the measured numbers.
    """
    return os.environ.get("ARIADNE_LEXICON", "1").strip().lower() not in {"0", "false", "no", "off"}


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

        ``capec_lookup`` was subsumed by ``describe`` and is deleted;
        ``capec_dossier_by_name`` was replaced by ``describe_by_name``.
        Under ``SPECIALIST_GENERIC_ONLY`` the cascade is bypassed entirely for
        the generic-primitives branch below.
        """
        # Names are resolved before the template ladder — see the Cypher
        # builder for why. A question that names its entity should reach the
        # same template as one that gives the identifier.
        named = _seed_from_name(resolved)
        if isinstance(named, AmbiguousName):
            return self._ambiguous(resolved, named)
        if named is not None:
            return self.build(named, feedback)

        has_seeds = bool(resolved.seed_ids)
        has_join = resolved.has_join or resolved.join_key == "attack-technique-id"
        neighbor_rels = _resolve_neighbor_rels(resolved)

        if _generic_only():
            # Schema-driven primitives only — no CAPEC question-shapes. Everything
            # here is parameterised by a card-declared relationship, by the
            # declared canonical join key, or by nothing at all.
            #
            # The bridge comes first: a dependent federated sub-question is
            # skipped outright when its producer returns no join values, so a
            # describe that reports only facet COUNTS loses the second half of
            # the question. Walking the declared join edge is what turns the
            # anchor into seed identifiers the consumer can use.
            if has_seeds and resolved.has_join:
                bridge = self._generic_bridge(resolved)
                if bridge is not None:
                    return bridge
            if has_seeds:
                # Registry-driven, so it is not confined to the seven edges that
                # happen to leave an AttackPattern, and it resolves the anchor
                # label and the traversal direction rather than assuming both.
                walk = self._generic_walk(resolved)
                if walk is not None:
                    return walk
            if has_seeds and len(neighbor_rels) == 1:
                return self._capec_neighbors(resolved, neighbor_rels[0])
            if has_seeds and neighbor_rels:
                return self._capec_facets(resolved, neighbor_rels)
            if has_seeds:
                return self._describe(resolved)
            # Only a *definitional* question is a name lookup; "Scan CAPEC attack
            # patterns" is an enumeration. Without the gate it becomes a regex
            # lookup for a node named that, and returns nothing.
            if resolved.name_terms and is_definitional_request(resolved.task.text):
                return self._describe(resolved)
            if _unanchored_abstains() and not asks_for_bulk_scan(resolved.task.text):
                return self._unanchored(resolved)
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
            # describe the anchor: full vertex + bounded facet block. Subsumed the
            # old lean capec_lookup and the capec_dossier (both since deleted) —
            # describe always returns the full record, so there is no describe-verb
            # intent left to gate on.
            return self._describe(resolved)
        # Seedless definitional question that names an entity ("What is
        # Phishing?") → describe by name. The definitional cue keeps a broad
        # enumeration ("scan attack patterns") on the label-scan path.
        if resolved.name_terms and is_definitional_request(resolved.task.text):
            return self._describe(resolved)
        if _unanchored_abstains() and not asks_for_bulk_scan(resolved.task.text):
            return self._unanchored(resolved)
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
        across the CAPEC vertex kinds. Returns the vertex elementMap (unpacked
        whole by the normalizer — no allow-list) alongside the folded facet
        block.

        The seeded anchor carries **no label filter**. Identity is the id, which
        is unique across the store, so a label can only ever exclude the right
        vertex — and it did: this read ``hasLabel("AttackPattern")`` until
        2026-09-03, so every question about a View or a Category asked the graph
        for an attack pattern and got nothing.
        """
        lim = resolved.task.max_rows()
        if resolved.seed_ids:
            ids = _capec_candidate_ids(resolved.seed_ids)
            anchor = 'g.V().has("id", within(ids))'
            return QueryDraft(
                query=anchor + self._FACET_PROJECTION + f".limit({lim})",
                params={"ids": ids},
                template="describe",
                expected_nonempty=bool(ids),
                # Declared, not asserted: which kind of vertex the id turns out
                # to name is the graph's answer, not the builder's assumption.
                meta={
                    "anchor_label": None,
                    "seed_ids": list(resolved.seed_ids),
                    "bindings": _capec_id_bindings(),
                },
            )
        # Wildcard-sanitize each term (any run of non-alphanumerics -> a single
        # ``.``) so the embedded regex carries no backslashes: re.escape emits
        # ``\ `` for the spaces in a multi-word name, which the Gremlin server's
        # Groovy parser rejects. ``.`` still matches the original separator.
        patterns = [
            p for p in (re.sub(r"[^A-Za-z0-9]+", ".", t).strip(".") for t in resolved.name_terms) if p
        ]
        pattern = "|".join(patterns)
        # No id here, so the label IS the scope and dropping it would turn a name
        # regex loose over every vertex in the store. Widened from AttackPattern
        # alone to the three kinds a CAPEC question can name, so "what is
        # Detailed Abstractions?" reaches the view it asks about.
        kinds = ", ".join(f'"{k}"' for k in _CAPEC_DESCRIBE_LABELS)
        anchor = (
            f'g.V().hasLabel({kinds})'
            f'.has("name", TextP.regex("(?i).*({pattern}).*"))'
        )
        return QueryDraft(
            query=anchor + self._FACET_PROJECTION + f".limit({lim})",
            params={},
            template="describe_by_name",
            expected_nonempty=False,
            meta={
                "anchor_labels": list(_CAPEC_DESCRIBE_LABELS),
                "name_terms": list(resolved.name_terms),
            },
        )

    def _capec_neighbors(self, resolved: ResolvedTask, rel: str) -> QueryDraft:
        ids = _capec_candidate_ids(resolved.seed_ids)
        # No target label on a containment edge. ``_REL_TARGET_LABEL`` maps
        # ``MEMBER_OF`` to ``Category``, which is right only when reading the
        # edge from the member's side; read from the container's side the
        # neighbours are its members, and the filter removed every one of them.
        # A View's members are AttackPatterns *and* Categories in any case, so
        # there is no single correct label here -- filtering to one would
        # reintroduce the defect the anchor fix removed.
        containment = rel in _CONTAINMENT_EDGE_BY_CONTAINER.values()
        target_label = "" if containment else _REL_TARGET_LABEL.get(rel, "")
        lim = resolved.task.max_rows()
        params: dict[str, Any] = {"ids": ids}

        edge = gremlin_edge_label(rel)  # loaded graphs use SCREAMING_SNAKE labels
        # Every AttackPattern facet is read outward from the pattern. The
        # containment edge is the one that is genuinely asked from both ends, so
        # its direction is resolved rather than assumed; `_resolve_neighbor_rels`
        # only offers it when the ends make the direction legible.
        step = "out"
        if containment:
            plan = _membership_plan(resolved)
            step = plan[1] if plan else "out"
        # No ``hasLabel`` on the containment edge: ``View -[HAS_MEMBER]->``
        # legitimately reaches AttackPatterns *and* Categories, so filtering to
        # one would reintroduce exactly the defect the anchor fix removed.
        if target_label:
            query = (
                f'g.V().has("id", within(ids)).as("ap")'
                f'.{step}("{edge}").hasLabel("{target_label}").as("nbr")'
                f'.select("ap","nbr").by(elementMap()).limit({lim})'
            )
        else:
            query = (
                f'g.V().has("id", within(ids)).as("ap")'
                f'.{step}("{edge}").as("nbr")'
                f'.select("ap","nbr").by(elementMap()).limit({lim})'
            )
        return QueryDraft(
            query=query,
            params=params,
            template="capec_neighbors",
            expected_nonempty=bool(ids),
            meta={
                "anchor_label": None,
                "bindings": _capec_id_bindings(),
                "neighbor_label": target_label or "",
                "rel": rel,
                "direction": step,
            },
        )

    def _capec_facets(self, resolved: ResolvedTask, rels: list[str]) -> QueryDraft:
        """Expand several of the anchor's native facets in one query (union of edges).

        The intra-source answer to a multi-facet question ("the mitigations *and*
        weaknesses of X"): a union over each requested native edge yields the
        ``(anchor, neighbour)`` elementMap pairs the ``capec_neighbors`` normalizer
        already understands — no cross-source bridge, one round-trip.
        """
        ids = _capec_candidate_ids(resolved.seed_ids)
        lim = resolved.task.max_rows()
        branches: list[str] = []
        for rel in rels:
            edge = gremlin_edge_label(rel)
            target = _REL_TARGET_LABEL.get(rel, "")
            branches.append(
                f'out("{edge}").hasLabel("{target}")' if target else f'out("{edge}")'
            )
        query = (
            'g.V().has("id", within(ids)).as("ap")'
            f'.union({", ".join(branches)}).as("nbr")'
            f'.select("ap","nbr").by(elementMap()).limit({lim})'
        )
        return QueryDraft(
            query=query,
            params={"ids": ids},
            template="capec_facets",
            expected_nonempty=bool(ids),
            meta={
                "anchor_label": None,
                "rels": list(rels),
                "bindings": _capec_id_bindings(),
            },
        )

    def _capec_maps_to(self, resolved: ResolvedTask) -> QueryDraft:
        lim = resolved.task.max_rows()
        params: dict[str, Any] = {}
        if resolved.seed_ids:
            params["ids"] = _capec_candidate_ids(resolved.seed_ids)
            anchor = 'g.V().has("id", within(ids))'
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

        # An **outer** join, matching the generic bridge (EXP-2026-08-004): one
        # row per anchor with its mappings folded into a possibly-empty list.
        # ``.out(edge)`` dropped an anchor that maps to nothing, which is both a
        # recall bug and a grounding bug — "this pattern has no ATT&CK mapping"
        # is a real answer, and an inner join cannot return the record that
        # grounds it.
        query = (
            f'{anchor}'
            '.project("ap","tax").by(elementMap())'
            '.by(__.out("MAPS_TO").hasLabel("TaxonomyEntry")'
            '.has("taxonomy_name","ATTACK").elementMap().fold())'
            f'.limit({lim})'
        )
        return QueryDraft(
            query=query,
            params=params,
            template="capec_maps_to",
            expected_nonempty=bool(resolved.seed_ids),
            meta={
                "anchor_label": None,
                "bindings": _capec_id_bindings(),
                "neighbor_label": "TaxonomyEntry",
                "rel": "MAPS_TO",
            },
        )

    def _capec_hierarchy_chain(self, resolved: ResolvedTask) -> QueryDraft:
        ids = [_capec_gremlin_id(s) for s in resolved.seed_ids]
        lim = resolved.task.max_rows()
        params: dict[str, Any] = {"ids": ids}
        child_of_edge = gremlin_edge_label("ChildOf")
        # Both ancestor hops are OPTIONAL, and that is the whole point of this
        # shape (Q22). The original required a parent *and* a grandparent in one
        # `select`, which is an inner join over three positions: for a Standard
        # anchor whose parent is already Meta there is no grandparent, so the
        # select matched nothing and the query returned **not even the parent the
        # question asked for**. Three questions across two banks retrieved zero
        # records that way (EXP-2026-08-015), and holdout-v1 missed it only
        # because its abstraction anchors happened to sit three levels down.
        #
        # This is the same outer-join correction EXP-2026-08-004/006 applied to
        # the bridge templates, in the one template those fixes did not reach.
        #
        # `optional()` leaves the traverser where it was when the hop finds
        # nothing, so a missing ancestor re-labels the previous vertex rather
        # than dropping the row. The normalizer de-duplicates by id and skips an
        # "ancestor" equal to the anchor, so a chain of length 0, 1 or 2 all
        # normalise correctly and the anchor is always returned.
        query = (
            'g.V().hasLabel("AttackPattern").has("id", within(ids)).as("ap")'
            f'.optional(__.out("{child_of_edge}").hasLabel("AttackPattern")).as("parent")'
            f'.optional(__.out("{child_of_edge}").hasLabel("AttackPattern")).as("grandparent")'
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
        # Asymmetric, exactly as the generic chain is: the first hop stays an
        # inner join because only patterns that genuinely exploit this weakness
        # belong in the answer, and the second becomes outer so a pattern that
        # exploits the CWE but maps to no technique is still returned. CAPEC-116
        # is precisely that case.
        query = (
            'g.V().hasLabel("Weakness").has("id", within(cweIds)).as("w")'
            '.in("EXPLOITS_WEAKNESS").hasLabel("AttackPattern").as("ap")'
            '.project("w","ap","tax")'
            '.by(__.select("w").elementMap()).by(__.select("ap").elementMap())'
            '.by(__.out("MAPS_TO").hasLabel("TaxonomyEntry")'
            '.has("taxonomy_name","ATTACK").elementMap().fold())'
            f'.limit({lim})'
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

    # -- generic-only primitives -------------------------------------------
    #
    # Everything below is reachable ONLY under SPECIALIST_GENERIC_ONLY. None of
    # it is used by the default cascade, so arms A-F and production are
    # unaffected — see utils/specialists/tests/test_generic_only_isolation.py.

    def _bound_filter(self, resolved: ResolvedTask):
        """``(label, property, value)`` the question asked to restrict to.

        Read from the sub-question's words against the card's declared
        properties and the registry's observed values
        (``utils.planner.canonical.requested_slots``). A CAPEC filter is always
        a scalar — ``Abstraction``, ``Status`` — so the emitted predicate is a
        plain ``has(prop, value)``; the list-valued properties are ATT&CK's and
        live on the Cypher side.
        """
        try:
            from utils.planner.cards import load_source_cards
            from utils.planner.canonical import requested_slots
            from utils.specialists.schema import get_registry

            card = load_source_cards().get(resolved.dataset)
            if card is None:
                return None
            registry = get_registry()
            slots = requested_slots(
                resolved.task.text or "",
                resolved.task.entities or (),
                card,
                registry,
                labels=resolved.labels,
            )
        except Exception:  # noqa: BLE001 — no filter is the old behaviour
            return None
        if slots.filter is None:
            return None
        label, prop, value = slots.filter
        try:
            if registry.is_list_property(label, prop, dataset=resolved.dataset):
                # A list-valued property needs membership, not equality, and
                # `has(prop, value)` compares the whole value. Emitting it would
                # match nothing silently, which is worse than not filtering.
                return None
        except Exception:  # noqa: BLE001
            return None
        return label, prop, value

    def _chain_route(
        self, resolved: ResolvedTask
    ) -> tuple[str, tuple[tuple[str, str], ...]] | None:
        """The ordered route through the plan's labels, when it names one.

        ``resolved.labels`` preserves the plan's ordering of the graph
        vocabulary, so three or more labels is a request to visit them in that
        order. Returns ``(root_label, ((rel, direction), ...))`` or ``None``;
        ``None`` leaves the star walk exactly as it was.
        """
        from utils.specialists.schema.paths import chain_paths, relation_chain

        labels = [label for label in resolved.labels if label]
        rels = [rel for rel in resolved.relationships if rel]
        if not labels or (len(labels) < 3 and len(rels) < 2):
            return None
        registry = self._generic_registry(resolved)
        if registry is None:
            return None
        # Named relationships first — see the Cypher builder's `_chain_route`
        # for why: they are the only signal that can express a two-hop request
        # whose intermediate carries the anchor's own label.
        route = relation_chain(
            registry,
            resolved.dataset,
            labels[0],
            rels,
            wanted_labels=tuple(labels),
        ) or chain_paths(
            registry, resolved.dataset, labels, max_hops=_MAX_WALK_HOPS
        )
        if not route:
            return None
        return labels[0], tuple((rel, direction) for rel, direction, _ in route)

    def _generic_registry(self, resolved: ResolvedTask) -> Any | None:
        """The derived schema registry, or ``None`` when it cannot be loaded."""
        from utils.specialists.schema import get_registry

        try:
            return get_registry()
        except Exception:  # noqa: BLE001 — no registry, no schema-driven routing
            return None

    def _self_referential_prefixes(
        self, resolved: ResolvedTask, registry: Any
    ) -> list[tuple[str, tuple[tuple[str, str], ...]]]:
        """Transitive repetitions of a named edge that loops on the anchor label.

        ``AttackPattern -ChildOf-> AttackPattern`` is a hierarchy: asked for the
        ancestors of a pattern, one hop returns the parent and stops, leaving the
        grandparent unretrieved. The caller turns each of these into a bounded
        ``repeat(...).times(n).emit()``, which returns every level.

        Only edges the task actually named are repeated. Walking every self-loop
        the schema declares would turn any lookup into a full hierarchy crawl.

        **Both** declared directions are emitted. A self-loop appears in the
        registry twice — as ``out`` and as ``in`` — and nothing in the schema
        says which one means "up". Ancestor-versus-descendant is precisely the
        domain nuance a hand-written template encodes and a generic primitive
        must not guess, so it returns both and lets the answer be over-complete
        rather than silently half-missing.
        """
        out: list[tuple[str, tuple[str, str]]] = []
        for anchor_label in [label for label in resolved.labels if label]:
            for rel in resolved.relationships:
                for facet in (
                    registry.label_facets(anchor_label, dataset=resolved.dataset) or []
                ):
                    if facet.rel_type != rel or facet.neighbour_label != anchor_label:
                        continue
                    candidate = (anchor_label, (facet.rel_type, facet.direction))
                    if candidate not in out:
                        out.append(candidate)
        return out

    def _generic_walk(self, resolved: ResolvedTask) -> QueryDraft | None:
        """Walk every declared path from the resolved anchor to the wanted labels.

        The Gremlin counterpart to the Cypher chain. Three things it does that
        ``_capec_neighbors`` cannot, each of which cost Arm G whole categories:

        * the anchor label comes from the resolved task, so a ``CWE``-seeded
          question anchors on ``Weakness`` instead of matching zero
          ``AttackPattern`` vertices and returning nothing at all;
        * the direction comes from the declared facet, so ``ParentOf`` and
          ``CanFollow`` are reachable rather than unroutable;
        * it is not restricted to the seven edges that leave an ``AttackPattern``.

        Branches are combined with ``union`` so each is evaluated against the
        anchor independently — the traversal fans out and re-converges rather
        than multiplying the branches together.
        """
        registry = self._generic_registry(resolved)
        if registry is None:
            return None
        candidates = [label for label in resolved.labels if label]
        if not candidates:
            return None

        from utils.specialists.schema.paths import edge_prefixes, shortest_paths

        # Every resolved label is tried as the anchor. ``primary_label()`` is
        # ``labels[0]`` — the order the plan listed entities in — which says
        # nothing about what the seed actually is. Anchoring on the wrong one
        # walks the right edge the wrong way and returns nothing.
        merged: dict[tuple[str, tuple[tuple[str, str], ...]], None] = {}
        for anchor in candidates:
            wanted = [label for label in candidates if label != anchor]
            if not wanted:
                continue
            paths = shortest_paths(
                registry, resolved.dataset, anchor, max_hops=_MAX_WALK_HOPS
            )
            for prefix in edge_prefixes(paths, wanted):
                merged.setdefault((anchor, prefix), None)
        prefixes = sorted(merged, key=lambda item: (len(item[1]), item[0]))

        # A named edge that lands back on the anchor's own label is a hierarchy,
        # and the answer to "walk up from here" is the whole ancestry, not the
        # first step of it. Breadth-first search cannot express that: it stops at
        # the anchor label because it has already been visited. Repeating the
        # edge is the transitive walk — the parent, then the grandparent — which
        # is what an abstraction question asks for.
        transitive = self._self_referential_prefixes(resolved, registry)
        if not prefixes and not transitive:
            return None

        # Same guard as the Cypher chain: a branch derived from label L fires on
        # an anchor of that label, or on an anchor carrying none of the candidate
        # labels at all — the planner's labels are approximate and a seed's real
        # label is often a subtype it never named.
        roots = {root for root, _ in prefixes} | {root for root, _ in transitive}
        guard_labels = ", ".join(
            f'"{_safe_gremlin_ident(label, "candidate label")}"'
            for label in sorted(roots)
        )

        def _guard(root: str) -> str:
            safe_root = _safe_gremlin_ident(root, "anchor label")
            return (
                f'or(__.hasLabel("{safe_root}"), __.not(__.hasLabel({guard_labels})))'
            )

        def _edge(rel: str) -> str:
            return gremlin_edge_label(_safe_gremlin_ident(rel, "relationship type"))

        # A hierarchy is one bounded ``repeat``, not one branch per depth. Per
        # depth would be correct and unshippable: the validator counts every
        # out/in step in the whole query against max_traversal_depth, so six
        # unrolled branches read as depth 12 and the draft is rejected before it
        # reaches the database — which is exactly how eight CAPEC hierarchy
        # questions retrieved nothing at all.
        branch_specs: list[tuple[int, str]] = []
        for root, (rel, direction) in transitive:
            step = "out" if direction == "out" else "in"
            branch_specs.append(
                (
                    1,
                    f'{_guard(root)}.repeat(__.{step}("{_edge(rel)}"))'
                    f".times({_MAX_WALK_HOPS}).emit()",
                )
            )
        for root, path in prefixes:
            steps = [
                f'{"out" if direction == "out" else "in"}("{_edge(rel)}")'
                for rel, direction in path
            ]
            branch_specs.append((len(steps), f'{_guard(root)}.{".".join(steps)}'))

        # -- the chained route, when the plan named one ---------------------
        #
        # `prefixes` comes from the shortest path to each requested label taken
        # independently, which answers the wrong question whenever the request
        # names an intermediate: "which techniques do this campaign's tools use"
        # becomes the campaign's own techniques over the direct edge. One branch
        # per leg of the ordered route binds every named label, and the shorter
        # leg retrieves the intermediate in its own right rather than traversing
        # past it. See `chain_paths`.
        chain = self._chain_route(resolved)
        chain_branches: set[str] = set()
        if chain:
            chain_root, legs = chain
            for i in range(1, len(legs) + 1):
                steps = [
                    f'{"out" if direction == "out" else "in"}("{_edge(rel)}")'
                    for rel, direction in legs[:i]
                ]
                branch = f'{_guard(chain_root)}.{".".join(steps)}'
                chain_branches.add(branch)
                branch_specs.append((len(steps), branch))

        # Fit the traversal-step budget. Anything dropped is named in meta — a
        # silently truncated walk reads as a complete answer when it is not.
        #
        # Chain legs are spent first and star branches compete for what is left.
        # Without that, the budget's cheapest-first order drops the two-step leg
        # that carries the answer in favour of one-step branches that do not,
        # which is the defect this is here to repair. Within each group the
        # cheapest still go first.
        budget = resolved.task.max_depth()
        branches: list[str] = []
        dropped: list[str] = []
        seen_branches: set[str] = set()
        spent = 0
        ordered = sorted(
            branch_specs, key=lambda spec: (spec[1] not in chain_branches, spec[0])
        )
        for cost, branch in ordered:
            if branch in seen_branches:
                continue
            seen_branches.add(branch)
            if spent + cost > budget:
                dropped.append(branch)
                continue
            branches.append(branch)
            spent += cost
        if not branches:
            return None

        ids = _walk_candidate_ids(resolved.seed_ids)
        lim = resolved.task.max_rows()
        bound = self._bound_filter(resolved)
        union = ", ".join(f"__.{b}" for b in branches)
        # The filter restricts the neighbours the question asked to restrict,
        # and ONLY those. Applied to every branch it also kills the ones landing
        # on another label: "which patterns can precede CAPEC-107, and what WASC
        # entries does each correspond to" restricts the taxonomy entries, and
        # appending `has("taxonomy_name", …)` to the pattern branch too deleted
        # the patterns, which cost five questions their whole gold coverage in
        # the first measurement of this step.
        #
        # So the predicate is "if it is one of these, it must match; otherwise
        # keep it", applied once after the union. `has`/`hasLabel` are filters
        # rather than traversal steps, so this costs nothing against the
        # traversal-depth cap.
        #
        # The property name is interpolated and guarded like every other
        # facet-sourced identifier; the VALUE is bound as a parameter and never
        # inlined, because Groovy rejects some escapes outright and a quoted
        # literal is a class of failure this does not need to have.
        scope = ""
        if bound is not None:
            filter_label, prop, _value = bound
            safe_prop = _safe_gremlin_ident(prop, "property")
            safe_label = _safe_gremlin_ident(filter_label, "filter label")
            scope = (
                f'.or(__.not(__.hasLabel("{safe_label}")), '
                f'__.has("{safe_prop}", filterValue))'
            )
        # Anchored by identifier alone. The canonical vertex id is unique across
        # labels, so a hasLabel() filter adds nothing but a way to be wrong: it
        # matches zero vertices whenever the guessed label is not the seed's.
        query = (
            'g.V().has("id", within(ids)).as("ap")'
            f".union({union}){scope}.as(\"nbr\")"
            f'.select("ap","nbr").by(elementMap()).limit({lim})'
        )
        walk_params: dict = {"ids": ids}
        if bound is not None:
            walk_params["filterValue"] = bound[2]
        return QueryDraft(
            query=query,
            params=walk_params,
            template="generic_walk",
            expected_nonempty=False,
            meta={
                "anchor_candidates": candidates,
                "paths": [
                    *(f"{root}|{r}:{d}*" for root, (r, d) in transitive),
                    *(
                        f"{root}|" + "->".join(f"{r}:{d}" for r, d in p)
                        for root, p in prefixes
                    ),
                ],
                "dropped_branches": dropped,
                "seed_ids": list(resolved.seed_ids),
                "bindings": _anchor_id_bindings(
                    resolved.seed_ids, resolved.primary_label() or ""
                ),
                **(
                    {"chain": f"{chain[0]}|"
                     + "->".join(f"{r}:{d}" for r, d in chain[1])}
                    if chain
                    else {}
                ),
                **({"filter": f"{bound[0]}.{bound[1]}={bound[2]}"} if bound else {}),
            },
        )

    def _generic_bridge(self, resolved: ResolvedTask) -> QueryDraft | None:
        """Walk the declared cross-source join edge and project the key property.

        The bridging edge, the endpoint label and the key property all come from
        the ``JoinKeyEndpoint`` the planner already resolved
        (:mod:`utils.planner.join_keys`) — nothing here encodes that CAPEC maps
        to ATT&CK, only that the registry declares *some* edge reaching *some*
        label carrying *some* key. The same compiler bridges any future pair of
        sources whose join key is declared.

        This is the primitive whose absence cost Arm G 40% of its lost
        correctness: without it a bridge question routes to ``describe``, which
        returns facet **counts** rather than neighbour ids, so the dependent
        sub-question is skipped for want of seeds.

        Emits the ``{"ap", "tax"}`` row shape so the existing maps_to
        normalization path applies; that path owns the key's id-format concern
        (the ``T`` prefix), which is a property of the declared key, not a
        question shape.
        """
        endpoint = resolved.join_endpoint
        assert endpoint is not None and endpoint.via_edge  # guarded by has_join
        edge = gremlin_edge_label(_safe_gremlin_ident(endpoint.via_edge, "join edge"))
        key_label = _safe_gremlin_ident(endpoint.labels[0], "join endpoint label")
        key_prop = _safe_gremlin_ident(endpoint.property, "join key property")
        anchor_label = _safe_gremlin_ident(
            resolved.primary_label() or "AttackPattern", "anchor label"
        )
        lim = resolved.task.max_rows()

        # Seeded on the key's own values (ATT&CK ids) rather than on the anchor:
        # enter at the key endpoint and walk the edge backwards. This is the
        # reverse-mapping shape C-MAP and F-REV need.
        entry_ids = [
            m.group(1)
            for m in (_ATTACK_ENTRY_RE.match(s) for s in resolved.seed_ids)
            if m
        ]
        if entry_ids and len(entry_ids) == len(resolved.seed_ids):
            query = (
                f'g.V().hasLabel("{key_label}").has("{key_prop}", within(entryIds))'
                f'.as("tax").in("{edge}").hasLabel("{anchor_label}").as("ap")'
                f'.select("ap","tax").by(elementMap()).limit({lim})'
            )
            return QueryDraft(
                query=query,
                params={"entryIds": entry_ids},
                template="generic_bridge",
                expected_nonempty=True,
                meta={
                    "anchor_label": key_label,
                    "neighbor_label": anchor_label,
                    "rel": endpoint.via_edge,
                    "direction": "in",
                },
            )

        ids = _walk_candidate_ids(resolved.seed_ids)

        # The seed need not sit on the edge that carries the key. A CWE-seeded
        # question anchors on Weakness, and the pattern that owns the MAPS_TO
        # edge is one declared hop away; without that prefix the traversal
        # anchors on the wrong label and matches nothing at all — five F-CWE
        # questions scored exactly zero in Arm G for this reason.
        prefix, owner_label = self._path_to_join_owner(
            resolved, key_label, endpoint.via_edge, anchor_label
        )
        if prefix is None:
            return None

        if prefix:
            # The *first* hop stays an inner join: only patterns that genuinely
            # exploit this weakness belong in the answer. The *second* becomes
            # outer, so a pattern that exploits the CWE but maps to no technique
            # is still returned — CAPEC-116 is exactly that, and the inner join
            # was silently deleting it.
            query = (
                # Anchored by identifier alone, as the generic walk is. The
                # canonical vertex id is unique across labels, so hasLabel() on
                # the *seed* adds nothing but a way to be wrong: a Category seed
                # whose plan says "AttackPattern" matches zero vertices. The
                # label filter on the far side of the hop stays, because that one
                # constrains where the traversal may land rather than where it
                # starts.
                f'g.V().has("id", within(ids)).as("w")'
                f'.{prefix}.hasLabel("{owner_label}").as("ap")'
                f'.project("w","ap","tax")'
                f'.by(__.select("w").elementMap()).by(__.select("ap").elementMap())'
                f'.by(__.out("{edge}").hasLabel("{key_label}").elementMap().fold())'
                f".limit({lim})"
            )
        else:
            # An **outer** join: one row per anchor, with its mappings folded
            # into a list that may be empty. ``.out(edge)`` would be an inner
            # join and drop the anchor entirely when it has no mapping — which
            # is both a recall bug (CAPEC-116 exploits CWE-1243 and maps to
            # nothing, so it vanished) and a grounding bug. "This pattern has no
            # ATT&CK mapping" is a real answer, and an inner join cannot return
            # the record needed to ground it.
            query = (
                # Identifier-only anchor, for the same reason as the branch above.
                f'g.V().has("id", within(ids))'
                f'.project("ap","tax").by(elementMap())'
                f'.by(__.out("{edge}").hasLabel("{key_label}").elementMap().fold())'
                f".limit({lim})"
            )
        return QueryDraft(
            query=query,
            params={"ids": ids},
            template="generic_bridge",
            expected_nonempty=False,
            meta={
                "anchor_label": anchor_label,
                "owner_label": owner_label,
                "neighbor_label": key_label,
                "rel": endpoint.via_edge,
                "direction": "out",
                "bindings": _anchor_id_bindings(resolved.seed_ids, anchor_label),
            },
        )

    def _path_to_join_owner(
        self,
        resolved: ResolvedTask,
        key_label: str,
        via_edge: str,
        anchor_label: str,
    ) -> tuple[str | None, str]:
        """Traversal steps from the anchor to the label that owns the join edge.

        The owner is read off the registry rather than assumed: it is the label
        on the far side of an inbound ``via_edge`` facet of the key's label. From
        there a breadth-first search gives the route from wherever the question
        is seeded.

        Returns ``("", owner)`` when the anchor already owns the edge, a
        dot-joined step string when it is reachable, and ``(None, owner)`` when
        it is not — in which case the caller declines to bridge rather than
        emitting a traversal that cannot match.
        """
        registry = self._generic_registry(resolved)
        if registry is None:
            return "", anchor_label

        owner = anchor_label
        for facet in registry.label_facets(key_label, dataset=resolved.dataset) or []:
            if facet.rel_type == via_edge and facet.direction == "in":
                owner = facet.neighbour_label
                break
        if owner == anchor_label:
            return "", owner

        from utils.specialists.schema.paths import shortest_paths

        paths = shortest_paths(
            registry, resolved.dataset, anchor_label, max_hops=_MAX_WALK_HOPS
        )
        route = paths.get(owner)
        if not route:
            return None, owner
        steps = []
        for rel, direction, _ in route:
            hop = gremlin_edge_label(_safe_gremlin_ident(rel, "relationship type"))
            steps.append(f'{"out" if direction == "out" else "in"}("{hop}")')
        return ".".join(steps), owner

    def _ambiguous(self, resolved: ResolvedTask, amb) -> QueryDraft:
        """Empty result carrying the candidates, so the answer can ask."""
        draft = self._unanchored(resolved)
        return QueryDraft(
            query=draft.query, params=draft.params, template="ambiguous-name",
            expected_nonempty=False,
            meta={**draft.meta, "ambiguous_candidates": list(amb.candidates)},
        )

    def _unanchored(self, resolved: ResolvedTask) -> QueryDraft:
        """Honest empty result for a question whose anchor never resolved.

        Runs a real bounded traversal against an empty id set, so it returns
        zero rows legitimately and the enforced abstention carries the executed
        query as its proof. The alternative -- `capec_scan` -- returned 558
        records, essentially the whole catalogue, for an invented attack pattern
        and let the composer call it "all results for this question"
        (EXP-2026-08-020).
        """
        label = resolved.primary_label() or "AttackPattern"
        lim = resolved.task.max_rows()
        query = (
            f'g.V().hasLabel("{label}").has("id", within(ids))'
            f'.elementMap().limit({lim})'
        )
        return QueryDraft(
            query=query,
            params={"ids": []},
            template="unanchored",
            expected_nonempty=False,
            meta={"anchor_label": label, "reason": "no anchor resolved"},
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
