#!/usr/bin/env python3
"""Deterministic Cypher query builder for the MITRE ATT&CK / Neo4j specialist.

Picks one of seventeen templates based on the resolved task and always
produces a query that will pass ``CypherValidator`` by construction — real
card labels/edges, parameterised values, an explicit LIMIT placeholder.
"""

from __future__ import annotations

import os
import re
from typing import Any

from ...planner.intent import (
    asks_for_bulk_scan,
    is_definitional_request,
)
from ..primitives.expand import ExpandRequest
from ..direction import anchor_expression, resolve_anchor
from ..resolve import ResolvedTask
from ..validation import QueryDraft

_SAFE_LABEL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_SAFE_REL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")

# How far the generic branch will chase a declared path. Three hops covers every
# shape in the golden catalogue while keeping the emitted MATCH bounded; the
# traversal-depth cap (TASK_MAX_TRAVERSAL_DEPTH) is the operative limit above it.
_MAX_CHAIN_HOPS = 3

# The alphabetic prefix of an identifier ("TA" of TA0006, "M" of M1027). Used
# only to tell whether two seeds are the same *kind* of thing; it reads the id
# format the card declares and never what the entity means.
_ID_PREFIX_RE = re.compile(r"^([A-Za-z]+)[-]?\d")


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


def _schema_labels(resolved: ResolvedTask) -> tuple[str, ...]:
    """Every label this dataset declares, from the derived schema registry.

    The registry is already the generic path's source of structure; using it
    here too means the name-lookup and scan paths stop carrying ATT&CK label
    names as literals. Returns ``()`` when no registry is available, and every
    caller falls back to its previous behaviour in that case.
    """
    try:
        from ..schema.build import get_registry

        schema = get_registry().dataset(resolved.dataset)
    except Exception:
        return ()
    return tuple(sorted(schema.labels())) if schema is not None else ()


def _name_bearing_labels(resolved: ResolvedTask) -> tuple[str, ...]:
    """Labels that declare a ``name`` property, so a name lookup can match them.

    Replaces the hard-coded ``_NAME_DESCRIBE_LABELS`` list of eight ATT&CK
    labels. On a source whose labels are not ATT&CK's, that list produced a
    guard like ``n:Technique OR n:SubTechnique OR …`` against a graph
    containing none of them — so a name lookup could not match anything, ever,
    however well the name had been extracted.

    Deriving the guard from the declared schema is what makes a name lookup
    possible on any source. The MITRE list remains the fallback for a dataset
    with no registry entry.
    """
    try:
        from ..schema.build import get_registry

        schema = get_registry().dataset(resolved.dataset)
    except Exception:
        schema = None
    if schema is None:
        return _NAME_DESCRIBE_LABELS
    named = tuple(
        sorted(
            label
            for label in schema.labels()
            if "name" in schema.label_properties(label)
        )
    )
    return named or _NAME_DESCRIBE_LABELS


def _names_a_specific_entity(resolved: ResolvedTask) -> bool:
    """Does the text name a particular thing, rather than a kind of thing?

    A bare label scan is the weakest answer the builder can give: it returns a
    slice of a whole label and answers no question in particular. So whenever
    the alternative is a scan and the text names something specific, the name
    lookup should win.

    "Specific" is judged structurally, not by a verb. A multi-word proper name
    ("Database Admins", "Finance Readers") or a dotted identifier
    ("corp.example") names one entity; a single ordinary word does not, and is
    left on the definitional gate as before. That distinction is what keeps
    "List ATT&CK software entries" on the scan path -- the case the gate was
    put there to protect -- while letting a question that actually names its
    subject reach it.

    Before this, the only way past the gate was a "what is X" phrasing. Every
    question in EXP-2026-08-011's bank names its subject and none is phrased
    definitionally, so all 27 fell through to a scan of whatever label a stray
    word happened to match.
    """
    for term in resolved.name_terms:
        cleaned = term.strip()
        # Space: a multi-word proper name ("Database Admins").
        # Dot or hyphen: a structured identifier ("corp.example", "OU-tier2-11").
        # Digit: an instance name rather than a category ("srv063").
        # A single all-alphabetic lowercase word is none of these -- it is far
        # more likely a category word the question happens to use -- so it stays
        # on the definitional gate, which is what keeps "List ATT&CK software
        # entries" on the scan path.
        if any(ch in cleaned for ch in " .-") or any(ch.isdigit() for ch in cleaned):
            return True
    return False


def _preferred_scan_label(resolved: ResolvedTask) -> str:
    """Pick the most query-worthy resolved label for a seedless scan."""
    labels = set(resolved.labels)
    for label in _SCAN_LABEL_PRIORITY:
        if label in labels:
            return label
    if resolved.primary_label():
        return resolved.primary_label()
    # Last resort. It was the literal "Technique", which on a source with no
    # such label meant a seedless scan queried a label that does not exist —
    # observed 12 times in EXP-2026-08-011 against a graph holding none.
    declared = _schema_labels(resolved)
    return declared[0] if declared else "Technique"


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
    """Anchor label for describe: the seed id's own shape, else the resolved label.

    A seed id like ``T1566`` *is* a Technique — the identifier shape is
    authoritative, so it must win over a label the resolver attached from the
    question text or a planner fallback (which, for a bare "what is <id>?", is the
    card's first probe label, e.g. ``Analytic``). Only when there is no seed id do
    we fall back to the text-resolved label, then a Technique default.
    """
    for aid in resolved.seed_ids:
        for pattern, inferred in _ID_PREFIX_LABELS:
            if pattern.match(aid):
                return inferred
    return resolved.primary_label() or "Technique"



def _unanchored_abstains() -> bool:
    """Does an unanchored question abstain instead of scanning? Default **off**.

    Shares `ARIADNE_LEXICON`'s lifecycle deliberately: widening word matching
    without this fix makes the dumps *worse*, because questions that used to
    abstain now match a schema word and fall through to the scan. Arm 1 measured
    exactly that — catalogue dumps +0.125 at T4 and +0.135 at T5, with wrong
    entities up 0.087 and 0.115. The two changes are one change.
    """
    return os.environ.get("ARIADNE_LEXICON", "").strip().lower() in {"1", "true", "yes", "on"}


def _namesearch_on() -> bool:
    """Is name-based anchor resolution enabled? Default **off**.

    Separate from `ARIADNE_LEXICON` so its contribution can be attributed. Arm 2
    made the router honest and still empty-handed — 0.0000 record identity at
    T4/T5 — because declining is not retrieving. This is the retrieval half.
    """
    return os.environ.get("ARIADNE_NAMESEARCH", "").strip().lower() in {"1", "true", "yes", "on"}


def _seed_from_name(resolved: ResolvedTask) -> ResolvedTask | None:
    """Resolve the question's entity by name and return a re-seeded task.

    Returns ``None`` — the common case — when the index is not confident. That
    is deliberate and it is the same discipline as `nearest()` in the lexicon:
    an unconfident guess here would undo the honest abstention Arm 2 bought, and
    a confidently wrong anchor is worse than none.
    """
    if not _namesearch_on() or resolved.seed_ids:
        return None
    from dataclasses import replace

    from ..schema.namesearch import resolve_in

    labels = tuple(resolved.labels) or tuple(resolved.task.entities or ())
    hit = resolve_in(resolved.dataset, resolved.task.text, labels=labels)
    if hit is None:
        return None
    return replace(resolved, seed_ids=(hit.entity_id,))


def _generic_only() -> bool:
    """True when the MITRE-specific query templates are disabled.

    Set by ``SPECIALIST_GENERIC_ONLY`` for the "no hand-written templates"
    experiment: the pipeline must answer using only schema-driven primitives
    (describe / walk-one-declared-relationship / label scan), the way it would
    have to on a graph nobody has authored templates for. Off by default.
    """
    from utils.config import env_bool

    return env_bool("SPECIALIST_GENERIC_ONLY", False)


def _is_technique_id(aid: str) -> bool:
    return bool(_TECHNIQUE_RE.match(aid))


def _all_subtechnique(ids: tuple[str, ...]) -> bool:
    return bool(ids) and all(bool(_SUBTECHNIQUE_RE.match(i)) for i in ids)


class CypherQueryBuilder:
    """Drafts a bounded Cypher query from a resolved task.

    Seventeen template identifiers are declared here.  Fifteen are reachable
    from :meth:`build` — ``technique_detection``, ``technique_mitigations``,
    ``campaign_attribution``, ``campaign_techniques``, ``group_techniques``,
    ``subtechnique_parent``, ``software_techniques``,
    ``tactic_technique_mitigations``, ``technique_tactics``,
    ``tactic_techniques``, ``datacomponent_analytics``, ``describe``,
    ``describe_by_name``, ``generic_neighbors`` and ``label_scan`` — and cover
    the common ATT&CK query patterns.  ``expand`` is reached only from
    :meth:`expand`, the separate paging compiler.

    ``describe``/``describe_by_name`` replaced the former ``node_dossier`` and
    ``node_dossier_by_name`` templates; ``generic_neighbors`` is emitted only
    under ``SPECIALIST_GENERIC_ONLY``.

    The builder picks deterministically; ``feedback`` from a failed gate
    attempt is accepted but the deterministic path should already pass without
    needing it.
    """

    def build(
        self, resolved: ResolvedTask, feedback: list[str] | None = None
    ) -> QueryDraft:
        """Return a ``QueryDraft`` whose query string is valid Cypher."""
        if _generic_only():
            return self._build_generic(resolved)
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

        # 2b. Actor → software. Both of these sit ahead of the branches that
        # used to swallow them: a Campaign+Software task fell through every
        # campaign branch to `describe`, and a Group+Software task was captured
        # by the unconditional Group branch below and answered with the group's
        # techniques. `not has_technique_entity` keeps the existing
        # actor→technique paths untouched, so a task naming all three labels
        # still routes exactly where it did.
        if has_campaign and has_software_entity and not has_technique_entity:
            return self._campaign_software(resolved)
        if has_group and has_software_entity and not has_technique_entity:
            return self._group_software(resolved)

        # 3. Group → techniques
        if has_group:
            return self._group_techniques(resolved)

        # 4a. subtechnique_parent — HAS_SUBTECHNIQUE relationship in scope + seeds
        if has_subtechnique_rel and resolved.seed_ids:
            return self._subtechnique_parent(resolved)

        # 4b. software_techniques — Software + Technique/SubTechnique entities + S-seeds
        #     (must NOT capture label_scan with no seeds)
        # Either end may be the anchor: "what does S0154 use" and "what software
        # uses T1047" are the same edge asked from opposite sides, and the
        # second fell through to `describe` while there were no S-seeds.
        if has_software_entity and has_technique_entity and (
            software_seed_ids or technique_ids
        ):
            return self._software_techniques(
                software_seed_ids or technique_ids, resolved
            )

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
        #    every property + a bounded facet block. describe subsumed the old
        #    node_lookup and node_dossier (both since deleted) — it always returns
        #    the full record, so there is no cheap "lean lookup" path left to
        #    protect and no describe-verb intent left to gate on.
        if resolved.seed_ids:
            return self._describe(resolved)

        # 6. No seeds but a definitional question that names an entity ("What is
        #    User Training?") → describe by name. The definitional cue keeps a
        #    broad enumeration ("scan all techniques") on the label-scan path
        #    rather than mistaking an incidental capitalized word for an anchor.
        if (
            resolved.name_terms
            and not resolved.has_join
            and (
                is_definitional_request(resolved.task.text)
                or _names_a_specific_entity(resolved)
            )
        ):
            return self._describe(resolved)

        # 7. Nothing resolved by identifier. Before giving up, ask the canonical
        #    name index whether the question names an entity in ordinary
        #    English — "the mitigations for Software Extensions", "browser
        #    extension persistence". If it answers confidently, seed that id and
        #    re-enter this ladder, so the question reaches the *same* template it
        #    would have reached had the analyst typed the identifier.
        seeded = _seed_from_name(resolved)
        if seeded is not None:
            return self.build(seeded, feedback)

        #    Otherwise: scan the label only if a scan is what was asked for, and
        #    otherwise look for the anchor we do not have, find nothing, and let
        #    the enforced abstention carry that query as its proof.
        if _unanchored_abstains() and not asks_for_bulk_scan(resolved.task.text):
            return self._unanchored(resolved)
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
            # Which end was seeded is read from the schema rather than assumed:
            # a technique id anchors the Technique side. The projection already
            # returns both ends, so the answer shape is unchanged.
            bound = resolve_anchor(
                seed_ids,
                {"Group": "g", "Technique": "t", "SubTechnique": "t"},
                resolved.dataset,
            )
            anchor = bound.expression() if bound else "g.attack_id"
            # Groups use sub-techniques too, so a sub-technique anchor needs the
            # target label widened — the pinned (t:Technique) is what made the
            # pattern narrower than the edge it walks.
            target = "(t)" if bound and bound.label == "SubTechnique" else "(t:Technique)"
            predicate = (
                "(t:Technique OR t:SubTechnique) AND " if target == "(t)" else ""
            )
            query = (
                f"MATCH (g:Group)-[:USES]->{target} "
                f"WHERE {predicate}{anchor} IN $ids "
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
            bound = resolve_anchor(
                seed_ids,
                {"Campaign": "c", "Technique": "t", "SubTechnique": "t"},
                resolved.dataset,
            )
            anchor = bound.expression() if bound else "c.attack_id"
            target = "(t)" if bound and bound.label == "SubTechnique" else "(t:Technique)"
            predicate = (
                "(t:Technique OR t:SubTechnique) AND " if target == "(t)" else ""
            )
            query = (
                f"MATCH (c:Campaign)-[:USES]->{target} "
                f"WHERE {predicate}{anchor} IN $ids "
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

    def _actor_software(
        self, resolved: ResolvedTask, actor_label: str, alias: str, noun: str
    ) -> QueryDraft:
        """MATCH (Group|Campaign)-[:USES]->(Software).

        The edge exists in the graph and had no template, so every question
        over it was answered by whichever branch caught it first — for a Group
        that was `_group_techniques`, which returns the group's *techniques*
        and, for a group with none on record, returns nothing at all.
        EXP-2026-08-010 measured four question families at 0.000 against a
        1.000 ceiling for this.

        Either end may anchor, following `_software_techniques`: "what software
        does G0003 use" and "what groups use S0089" are one edge asked from
        opposite sides.
        """
        seed_ids = list(resolved.seed_ids)
        anchor = anchor_expression(
            seed_ids,
            {actor_label: alias, "Software": "s"},
            resolved.dataset,
            f"{alias}.attack_id",
        )
        where = f"WHERE {anchor} IN $ids " if seed_ids else ""
        query = (
            f"MATCH ({alias}:{actor_label})-[:USES]->(s:Software) "
            f"{where}"
            f"RETURN {alias}.attack_id AS {noun}_id, {alias}.name AS {noun}_name, "
            "s.attack_id AS software_id, s.name AS software_name"
        )
        return QueryDraft(
            query=query,
            params={"ids": seed_ids} if seed_ids else {},
            template=f"{noun}_software",
            meta={"seed_ids": seed_ids},
        )

    def _group_software(self, resolved: ResolvedTask) -> QueryDraft:
        """MATCH (Group)-[:USES]->(Software)."""
        return self._actor_software(resolved, "Group", "g", "group")

    def _campaign_software(self, resolved: ResolvedTask) -> QueryDraft:
        """MATCH (Campaign)-[:USES]->(Software)."""
        return self._actor_software(resolved, "Campaign", "c", "campaign")

    def _campaign_attribution(self, resolved: ResolvedTask) -> QueryDraft:
        """MATCH (Campaign)-[:ATTRIBUTED_TO]->(Group)."""
        seed_ids = list(resolved.seed_ids)
        if seed_ids:
            anchor = anchor_expression(
                seed_ids, {"Campaign": "c", "Group": "g"}, resolved.dataset, "c.attack_id"
            )
            query = (
                "MATCH (c:Campaign)-[:ATTRIBUTED_TO]->(g:Group) "
                f"WHERE {anchor} IN $ids "
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
            anchor = anchor_expression(
                seed_ids, {"Tactic": "ta", "Technique": "t"}, resolved.dataset, "ta.attack_id"
            )
            query = (
                "MATCH (ta:Tactic)-[:HAS_TECHNIQUE]->(t:Technique) "
                f"WHERE {anchor} IN $ids "
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

    # The facet-block aggregation shared by both describe shapes: group every
    # 1-hop edge by (rel type, direction, neighbour label) and count. Server-side
    # aggregation keeps the payload a fraction of a KB even for an 858-degree hub
    # — the facet block is a count, never a neighbour list. The untyped ``-[r]-``
    # surfaces every edge kind and sidesteps the gate's relationship-type check;
    # a zero-degree node yields an empty block (the CASE filters the null group).
    # Prefer an exact name, fall back to substring only when exact finds nothing.
    #
    # A bare ``CONTAINS`` is an unanchored substring match over a name space this
    # project does not control, so any source whose names prefix one another
    # defeats it: "App Access 070" matched all 54 "App Access NNN" groups
    # (ISSUES I-11). Widening the extractor alone does not fix that -- it fixes
    # the one case and leaves the class -- so the predicate itself now ranks.
    #
    # Expressed as collect/UNWIND rather than a subquery because the safety gate
    # validates a flat read-only statement, and this keeps it one.
    _NAME_EXACT_THEN_CONTAINS = (
        "WITH collect(n) AS cand "
        "WITH cand, [x IN cand WHERE any(t IN $names WHERE toLower(x.name) = t)] AS exact "
        "UNWIND (CASE WHEN size(exact) > 0 THEN exact ELSE cand END) AS n "
    )

    # The id column is ``coalesce(n.attack_id, n.id)`` for the reason ``_label_scan``
    # already records: ``attack_id`` does not exist outside ATT&CK, and a null id
    # is dropped by the normalizer, so describe returned nothing on a source that
    # keys its nodes any other way. Byte-identical on ATT&CK, where ``attack_id``
    # is never null on a describable label. This one survived EXP-2026-08-011's
    # first pass only because the anchor bug kept describe from firing at all --
    # every device question fell through to a label scan, which had already been
    # generalised, so the defect underneath had nothing to reveal it.
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
        "RETURN coalesce(n.attack_id, n.id) AS id, n.name AS name, "
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
            match = f"MATCH (n:{label}) WHERE coalesce(n.attack_id, n.id) IN $ids "
            return QueryDraft(
                query=match + self._FACET_AGGREGATION,
                params={"ids": list(resolved.seed_ids)},
                template="describe",
                expected_nonempty=True,
                meta={
                    "label": label,
                    "seed_ids": list(resolved.seed_ids),
                    # Declared, not parsed. ``coalesce(n.attack_id, n.id)`` is
                    # invisible to the binding parser's ``alias.prop IN $param``
                    # shape, so widening the id column silently emptied the
                    # binding audit for every describe draft -- 202 of them went
                    # from checked to "unchecked", which is the audit's own name
                    # for a query that filters on values nothing verified.
                    # ``extract_bindings`` prefers a declaration precisely so a
                    # builder can express a filter its parsers cannot read.
                    #
                    # Two entries, one parameter: the coalesce IS a disjunction,
                    # and ``unsatisfiable_bindings`` groups by parameter, so the
                    # filter is judged satisfiable when *either* property admits
                    # the seeds -- which is what the query means.
                    "bindings": [
                        {"label": label, "property": "attack_id", "param": "ids"},
                        {"label": label, "property": "id", "param": "ids"},
                    ],
                },
            )
        names = [term.lower() for term in resolved.name_terms]
        label_guard = " OR ".join(
            f"n:{label}" for label in _name_bearing_labels(resolved)
        )
        match = (
            f"MATCH (n) WHERE ({label_guard}) "
            "AND any(term IN $names WHERE toLower(n.name) CONTAINS term) "
        )
        return QueryDraft(
            query=match + self._NAME_EXACT_THEN_CONTAINS + self._FACET_AGGREGATION,
            params={"names": names},
            template="describe_by_name",
            expected_nonempty=False,
            meta={"name_terms": list(resolved.name_terms)},
        )

    def _build_generic(self, resolved: ResolvedTask) -> QueryDraft:
        """Route using ONLY schema-driven primitives — no MITRE question-shapes.

        This is the "point it at a graph nobody wrote templates for" path:
        describe an anchor, walk one declared relationship, or scan a label.
        Everything it knows comes from the source card and the derived schema
        registry; nothing encodes what a mitigation or a technique *means*.
        """
        rels = [r for r in resolved.relationships if r]
        if resolved.seed_ids:
            # Two anchors of different kinds ask for what they have in common,
            # not for each one's neighbourhood. Walking either alone answers a
            # different question — "techniques under TA0006" is 67 rows where
            # "techniques under TA0006 that M1027 mitigates" is 7.
            intersection = self._generic_intersect(resolved)
            if intersection is not None:
                return intersection
            # A requested label two or more declared hops away cannot be reached
            # by walking one relationship, and describe reports only facet
            # COUNTS — so the deeper entity (an Analytic behind a
            # DetectionStrategy) is never retrieved at all. Chain next.
            chain = self._generic_chain(resolved)
            if chain is not None:
                return chain
        if resolved.seed_ids and len(rels) == 1:
            return self._generic_neighbors(resolved, rels[0])
        if resolved.seed_ids:
            return self._describe(resolved)
        # No id, but the text names an entity and one declared relationship:
        # walk it. Describing the anchor instead would return facet counts and
        # never the related records the question asks for.
        if resolved.name_terms and rels and _names_a_specific_entity(resolved):
            return self._generic_neighbors(resolved, rels)
        # Only a *definitional* question ("What is Phishing?") is a name lookup.
        # Without that gate "List ATT&CK software entries" is read as a request
        # for an entity literally named that, and a bounded scan returns nothing
        # — which is how both of the catalogue's scan questions scored zero. The
        # default cascade already gates this; the generic branch did not.
        if resolved.name_terms and (
            is_definitional_request(resolved.task.text)
            or _names_a_specific_entity(resolved)
        ):
            return self._describe(resolved)
        return self._label_scan(resolved)

    def _generic_intersect(self, resolved: ResolvedTask) -> QueryDraft | None:
        """Nodes adjacent to **every** seed, when the seeds are of different kinds.

        The primitive is "what do these anchors have in common": group the
        neighbourhood by neighbour and keep only those reached from all of the
        seeds. No label, edge or id scheme is named — a node's adjacency to the
        full seed set is the whole predicate — so the same compiler answers any
        two-anchor question a future dataset poses.

        Gated on the seeds having **different identifier prefixes**. Six
        technique seeds are a fan-out ("the mitigations of each of these"), where
        intersecting would be wrong; a tactic seed alongside a mitigation seed is
        a conjunction. The prefix is a property of the id format the card
        declares, not of what the entities mean.

        Returns ``None`` when the seeds are homogeneous, leaving the fan-out
        shapes to the chain and neighbour primitives.
        """
        seeds = [s for s in resolved.seed_ids if s]
        if len(seeds) < 2:
            return None
        prefixes = {m.group(1) for s in seeds if (m := _ID_PREFIX_RE.match(s))}
        if len(prefixes) < 2:
            return None

        query = (
            "MATCH (n) WHERE coalesce(n.attack_id, n.id) IN $ids "
            "MATCH (n)-[r]-(m) "
            "WITH m, collect(DISTINCT coalesce(n.attack_id, n.id)) AS anchors, "
            "collect(DISTINCT {id: coalesce(n.attack_id, n.id), name: n.name, "
            "label: labels(n)[0], rel: type(r)}) AS sources "
            "WHERE size(anchors) = $anchorCount "
            "UNWIND sources AS source "
            "RETURN coalesce(m.attack_id, m.id) AS anchor_id, m.name AS anchor_name, "
            "labels(m)[0] AS anchor_label, "
            "source.id AS neighbour_id, source.name AS neighbour_name, "
            "source.label AS neighbour_label, source.rel AS rel_type"
        )
        return QueryDraft(
            query=query,
            params={"ids": seeds, "anchorCount": len(seeds)},
            template="generic_intersect",
            expected_nonempty=False,
            meta={"seed_ids": seeds, "anchor_count": len(seeds)},
        )

    def _declared_paths(
        self, resolved: ResolvedTask
    ) -> list[tuple[str, tuple[tuple[str, str], ...]]] | None:
        """Shortest declared path from the anchor label to the deepest requested one.

        Breadth-first over the derived schema registry's facets, which are a
        directed edge list of ``(rel_type, direction, neighbour_label)`` per
        label. Nothing about ATT&CK is consulted — only what the card's
        introspected structure declares — so the same search finds
        ``Technique -> DetectionStrategy -> Analytic`` and any equivalent path a
        future dataset brings.

        A one-hop path counts. ``_generic_neighbors`` only fires when the plan
        *named* a relationship, so "which analytics monitor DC0084" — which names
        two labels and no edge — otherwise falls through to ``describe`` and
        returns counts. Deriving the edge from the declared structure covers it,
        and carries the true direction with it.

        **Every** resolved label is tried as the anchor, not just the first.
        ``primary_label()`` returns ``labels[0]``, which is the order the *plan*
        listed entities in and says nothing about what the seed actually is: a
        sub-question seeded with ``T1110.001`` and resolving
        ``["Tactic", "Technique"]`` would otherwise be anchored as a Tactic and
        walk ``HAS_TECHNIQUE`` outbound, retrieving nothing and losing the tactic
        the question asked for. The query matches the anchor by identifier and
        never by label, so the seed's real label decides which branches match;
        branches rooted at the wrong label are an ``OPTIONAL MATCH`` that finds
        nothing, which costs a little breadth and cannot produce a wrong answer.
        """
        from utils.specialists.schema import get_registry
        from utils.specialists.schema.paths import edge_prefixes, shortest_paths

        try:
            registry = get_registry()
        except Exception:  # noqa: BLE001 — no registry, no chaining
            return None
        if registry is None:
            return None

        candidates = [label for label in resolved.labels if label]
        if not candidates:
            return None

        merged: dict[tuple[str, tuple[tuple[str, str], ...]], None] = {}
        for anchor in candidates:
            wanted = [label for label in candidates if label != anchor]
            if not wanted:
                continue
            paths = shortest_paths(
                registry, resolved.dataset, anchor, max_hops=_MAX_CHAIN_HOPS
            )
            for prefix in edge_prefixes(paths, wanted):
                merged.setdefault((anchor, prefix), None)
        return sorted(merged, key=lambda item: (len(item[1]), item[0])) or None

    def _generic_chain(self, resolved: ResolvedTask) -> QueryDraft | None:
        """Walk every declared path to every requested label, one row per hop.

        Each path is matched and aggregated **independently** — one
        ``OPTIONAL MATCH`` followed by its own ``collect``, never several
        patterns in one ``MATCH``. Combining them in a single pattern would take
        the cartesian product of the branches (4 Techniques x 13 SubTechniques =
        52 rows for one anchor) and duplicate every neighbour; collecting per
        branch and concatenating keeps it linear.

        Rows carry the ``generic_neighbors`` column contract, so intermediates
        and terminals alike land in the anchor's related set through the existing
        normalization path, unchanged.

        ``OPTIONAL MATCH`` keeps the anchor when a path does not exist, which is
        the honest empty-neighbourhood answer rather than a lost record.
        """
        paths = self._declared_paths(resolved)
        if not paths:
            return None

        # A branch derived from label L must not fire on an anchor that is
        # something else, or "which techniques does Mimikatz use" picks up the
        # inbound USES branch too and returns the fifty-one groups that use
        # Mimikatz as though they were techniques it uses.
        #
        # The second disjunct is what keeps the guard from being too strict: the
        # planner's labels are approximate, and a sub-technique seed resolving
        # ``["Tactic", "Technique"]`` carries none of them. When the anchor
        # matches no candidate at all, every branch is allowed rather than none.
        candidates = sorted({label for label, _ in paths})
        candidate_test = " OR ".join(f"n:{label}" for label in candidates)
        blocks: list[str] = []
        collected: list[str] = []
        for i, (root, path) in enumerate(paths):
            pattern: list[str] = []
            for j, (rel, direction) in enumerate(path):
                safe_rel = _safe_ident(rel, _SAFE_REL_RE, "relationship type")
                # Only the terminal node of the prefix is bound; the ones before
                # it are matched anonymously because a shorter prefix already
                # collects them in its own block. The far end is never
                # label-filtered — the edge decides what is on the other side.
                var = f"m{i}" if j == len(path) - 1 else ""
                arrow = (
                    f"<-[:{safe_rel}]-" if direction == "in" else f"-[:{safe_rel}]->"
                )
                pattern.append(f"{arrow}({var})")
            terminal_rel = _safe_ident(path[-1][0], _SAFE_REL_RE, "relationship type")
            carry = ", ".join(["n", *collected])
            guard = f"n:{root} OR NOT ({candidate_test})"
            blocks.append(
                f"OPTIONAL MATCH (n){''.join(pattern)} WHERE {guard} "
                f"WITH {carry}, collect(DISTINCT {{m: m{i}, r: '{terminal_rel}'}}) AS h{i}"
            )
            collected.append(f"h{i}")

        combined = " + ".join(collected)
        query = (
            "MATCH (n) WHERE coalesce(n.attack_id, n.id) IN $ids "
            + " ".join(blocks)
            + f" WITH n, {combined} AS hops "
            "UNWIND (CASE WHEN size(hops) = 0 THEN [{m: null, r: null}] ELSE hops END) AS hop "
            "RETURN coalesce(n.attack_id, n.id) AS anchor_id, n.name AS anchor_name, "
            "labels(n)[0] AS anchor_label, "
            "coalesce(hop.m.attack_id, hop.m.id) AS neighbour_id, "
            "hop.m.name AS neighbour_name, "
            "labels(hop.m)[0] AS neighbour_label, hop.r AS rel_type"
        )
        return QueryDraft(
            query=query,
            params={"ids": list(resolved.seed_ids)},
            template="generic_chain",
            expected_nonempty=False,
            meta={
                "paths": [
                    f"{root}|" + "->".join(f"{r}:{d}" for r, d in path)
                    for root, path in paths
                ],
                "seed_ids": list(resolved.seed_ids),
            },
        )

    def _generic_neighbors(
        self, resolved: ResolvedTask, rel: str | list[str], direction: str = "both"
    ) -> QueryDraft:
        """Walk ONE card-declared relationship from the seeded anchors.

        The schema-driven counterpart to the named ATT&CK templates: it knows
        only that ``rel`` is a relationship the source card declares, and returns
        the neighbours on the other side of it. Nothing about ATT&CK's meaning is
        encoded — the same compiler serves ``MITIGATES``, ``USES``, ``DETECTS`` or
        any edge a future dataset brings, which is what makes it the primitive a
        new schema can be answered with before anyone writes a template for it.

        The relationship is interpolated rather than parameterised because Cypher
        does not bind relationship types; the validator gates it against the
        card's declared types, so an undeclared edge never reaches the database.
        """
        # A question often names several candidate relationships rather than one
        # -- "what can X write" matches GENERIC_WRITE, WRITE_DACL, WRITE_OWNER,
        # WRITE_GP_LINK and WRITE_ACCOUNT_RESTRICTIONS, all of them declared and
        # all of them plausible. Requiring exactly one meant such a question fell
        # back to describing the anchor, which reports facet COUNTS and never the
        # related records. Walking the alternation answers it without choosing
        # between them on the question's behalf; `type(r)` travels on every row
        # so the composer can still report per relationship.
        rels = [rel] if isinstance(rel, str) else list(dict.fromkeys(rel))
        rel_pattern = "|".join(rels)
        arrow = {
            "out": f"-[r:{rel_pattern}]->",
            "in": f"<-[r:{rel_pattern}]-",
        }.get(direction, f"-[r:{rel_pattern}]-")
        projection = (
            f"OPTIONAL MATCH (n){arrow}(m) "
            "RETURN coalesce(n.attack_id, n.id) AS anchor_id, n.name AS anchor_name, "
            "labels(n)[0] AS anchor_label, "
            "coalesce(m.attack_id, m.id) AS neighbour_id, m.name AS neighbour_name, "
            "labels(m)[0] AS neighbour_label, type(r) AS rel_type"
        )

        # Anchor by id when the task carries one, by name when it does not.
        #
        # The name arm exists because the id arm cannot serve a source that has
        # no analyst-facing identifier. ATT&CK questions carry `T1055`; a
        # question about an identity graph carries "Database Admins", and the
        # only way to reach that node is its name. Without this, walking a
        # relationship was reachable ONLY from an id-resolved anchor, so on any
        # source keyed by opaque GUIDs the whole traversal primitive was
        # unreachable and every relationship question collapsed to describing
        # the anchor and reporting facet COUNTS instead of the related records
        # themselves. That is what held 11 of 27 questions at zero in
        # EXP-2026-08-011 after anchor resolution had been fixed.
        if resolved.seed_ids:
            return QueryDraft(
                query="MATCH (n) WHERE coalesce(n.attack_id, n.id) IN $ids " + projection,
                params={"ids": list(resolved.seed_ids)},
                template="generic_neighbors",
                expected_nonempty=False,
                meta={
                    "rel": rels[0] if len(rels) == 1 else rels,
                    "rels": rels,
                    "direction": direction,
                    "seed_ids": list(resolved.seed_ids),
                },
            )
        names = [term.lower() for term in resolved.name_terms]
        return QueryDraft(
            query=(
                "MATCH (n) WHERE any(term IN $names WHERE toLower(n.name) CONTAINS term) "
                + self._NAME_EXACT_THEN_CONTAINS
                + projection
            ),
            params={"names": names},
            template="generic_neighbors",
            expected_nonempty=False,
            meta={
                "rel": rels[0] if len(rels) == 1 else rels,
                "rels": rels,
                "direction": direction,
                "name_terms": names,
            },
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
        # Collect node refs, slice to the page, THEN build member maps with the
        # properties_json — so the description-bearing blob is materialized only for
        # the bounded page, never the whole fan-out (the primitive's scale guarantee).
        query = (
            f"MATCH (n:{anchor}) WHERE n.attack_id = $id "
            f"MATCH {hop} "
            "WITH m ORDER BY coalesce(m.attack_id, m.id) "
            "WITH collect(m) AS nodes "
            "WITH nodes[$skip..$end] AS page, size(nodes) AS total "
            "RETURN [x IN page | {id: coalesce(x.attack_id, x.id), name: x.name, "
            "label: head(labels(x)), props: x.properties_json}] AS members, total"
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
        anchor = anchor_expression(
            software_ids,
            {"Software": "s", "Technique": "t", "SubTechnique": "t"},
            resolved.dataset,
            "s.attack_id",
        )
        query = (
            "MATCH (s:Software)-[:USES]->(t) "
            f"WHERE (t:Technique OR t:SubTechnique) AND {anchor} IN $ids "
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

    def _unanchored(self, resolved: ResolvedTask) -> QueryDraft:
        """An honest empty result for a question whose anchor never resolved.

        **Not a no-op and not a stub.** It runs a real, safe, bounded query that
        looks for the anchor against an empty id set, so it legitimately returns
        zero rows — which makes the result *empty but ok*, which is precisely
        what `synthesis.composer.abstention_for` turns into an enforced
        abstention carrying its executed query. The proof that we could not find
        the entity is a query that looked for it.

        The alternative, `label_scan`, returns the whole label and the composer
        presents it as "all results for this question". Nothing downstream can
        catch that: every record is genuine, so the verifier has no claim to
        reject. Only the framing is false.
        """
        label = _preferred_scan_label(resolved)
        query = (
            f"MATCH (n:{label}) WHERE coalesce(n.attack_id, n.id) IN $ids "
            f"RETURN coalesce(n.attack_id, n.id) AS id, n.name AS name"
        )
        return QueryDraft(
            query=query,
            params={"ids": []},
            template="unanchored",
            expected_nonempty=False,
            meta={"anchor_label": label, "reason": "no anchor resolved"},
        )

    def _label_scan(self, resolved: ResolvedTask) -> QueryDraft:
        """MATCH (n:<Label>) RETURN the node's public id and name — no seeds.

        The id column is ``coalesce(n.attack_id, n.id)`` rather than
        ``n.attack_id``, which is the same idiom the merged build already uses
        (D-017) and is byte-identical on ATT&CK, where ``attack_id`` is never
        null on a scannable label.

        It was ``n.attack_id`` alone until EXP-2026-08-011 ran this template
        against a schema that has no such property, at which point every row
        came back with a null id, the normalizer rejected all of them for
        missing ``record_id``, and a perfectly good query returned nothing. That
        is a portability defect the AST-based count in EXP-2026-07-011 could not
        see: it classified templates by their question shape, and this one's
        MITRE-specificity is in the *property name it emits*, not in its shape.
        """
        label = _preferred_scan_label(resolved)
        query = (
            f"MATCH (n:{label}) "
            f"RETURN coalesce(n.attack_id, n.id) AS id, n.name AS name"
        )
        return QueryDraft(
            query=query,
            params={},
            template="label_scan",
            meta={"label": label},
        )
