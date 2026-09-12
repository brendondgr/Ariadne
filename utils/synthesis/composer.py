#!/usr/bin/env python3
"""The deterministic composer: claims-with-citations from federated evidence.

Always available (no model, no network) and correct by construction — every
claim it emits cites the records it was built from, so the verifier's pass
over its output is a consistency check rather than a leap of faith. This is
the composer the API seam uses when ``SYNTHESIS_LLM_ENABLED`` is off and the
fallback the hybrid path degrades to when the LLM is unreachable.

Composition rules:

- Each specialist result with records becomes one *fact* claim: the
  specialist's grounded summary, cited against up to ``max_citations`` of the
  records that produced it.
- Each cross-source join value becomes one *correlation* claim cited against
  the records on both sides of the join index.
- Each result that ran cleanly but returned zero records becomes an
  ``Abstention`` carrying the executed query as proof.
- Failed specialists and planner-unsupported parts become ``notes`` — visible,
  but never phrased as evidence.
"""

from __future__ import annotations

import re

from utils.planner.intent import is_definitional_request
from utils.specialists.contracts import EvidenceRecord, SpecialistResult
from utils.specialists.federation import FederatedEvidence
from utils.specialists.resolve import definitional_name_terms

from .config import SynthesisConfig
from .contracts import Abstention, Citation, Claim, SynthesizedAnswer

# An enumeration claim's id list is bounded generously — far above any real
# related set in the catalogue — so the answer stays complete without an
# unbounded claim. Every record with a related set gets one: the bound exists to
# stop a pathological set, not to decide which sets are worth stating.
_MAX_ENUMERATION_IDS = 200
_MAX_ENUMERATION_CLAIMS_PER_RESULT = 25


def _enum_bound(name: str, default: int) -> int:
    """This bound's live value: ``SYNTHESIS_<NAME>`` when set, else the default.

    Read at call time so an un-truncated profile can enumerate a whole related
    set without the module's committed defaults changing.
    """
    from utils.config import env_int

    return env_int(f"SYNTHESIS_{name}", default)

# Example ids offered when asking the analyst to disambiguate by identifier.
_ID_EXAMPLES = "e.g. T1566, M1017, or CAPEC-98"

# Markers of a clean, source-availability unsupported reason authored by the
# deterministic drafter (safe to surface verbatim). Anything else is treated as
# model-authored free text and is NOT echoed (it is often garbled).
_CLEAN_REASON_MARKERS = ("not live", "no live source", "schema", "down")


def _is_name_lookup(query: str) -> bool:
    """True when ``query`` is one of the name-dossier templates (Cypher/Gremlin).

    Keyed on each template's unique name-match signature so the name-aware
    abstention/clarification fires only for an actual by-name lookup — never for
    an ordinary empty result (which keeps its canonical honest-empty wording).
    """
    q = query or ""
    if "toLower(n.name) CONTAINS" in q:  # Cypher _node_dossier_by_name
        return True
    if 'has("name", TextP.regex' in q and 'project("node"' in q:  # Gremlin
        return True
    return False


# The datasets whose entities carry an analyst-facing identifier worth quoting.
# Naming an id format is only helpful when the source actually has one: an
# identity graph keys on opaque GUIDs, so telling an analyst to "give its id
# (e.g. T1566)" is advice that cannot be followed, attached to a source that
# does not work that way.
_ID_BEARING_SOURCES = frozenset({"attack", "capec", "merged"})


def _routed_sources(evidence: FederatedEvidence) -> tuple[str, ...]:
    """The sources this request was actually routed to, in order, deduplicated."""
    seen: dict[str, None] = {}
    for result in evidence.results:
        source = str(getattr(result.task, "source", "") or "").strip()
        if source:
            seen.setdefault(source, None)
    return tuple(seen)


def _sources_phrase(evidence: FederatedEvidence) -> str:
    """How to name the searched sources in an abstention.

    Hardcoded as "the live ATT&CK/CAPEC graphs" until 2026-08-22, which was true
    of every deployment that existed and false the moment a third source joined:
    a question routed to the identity graph was told, in the answer, that ATT&CK
    and CAPEC had been searched. Same species as I-9 -- a dataset name welded
    into text that is asserted as fact -- and it surfaced the same way, by
    running against a source the sentence was not written for.
    """
    routed = _routed_sources(evidence)
    if not routed:
        return "the live graph sources"
    if len(routed) == 1:
        return f"the live {routed[0]} graph"
    return "the live " + ", ".join(routed[:-1]) + f" and {routed[-1]} graphs"


def _id_hint(evidence: FederatedEvidence) -> str:
    """`" or tell me its id (…)"`-style clause, only where ids mean something."""
    if any(s in _ID_BEARING_SOURCES for s in _routed_sources(evidence)):
        return f" ({_ID_EXAMPLES})"
    return ""


def _name_lookup_terms(evidence: FederatedEvidence) -> tuple[str, ...]:
    """Distinct entity names searched by the name-lookup results in ``evidence``."""
    names: list[str] = []
    for result in evidence.results:
        if _is_name_lookup(result.query):
            names.extend(definitional_name_terms(result.task.text))
    return tuple(dict.fromkeys(names))


def abstention_statement(
    source: str,
    text: str,
    query: str = "",
    *,
    dependency: str = "",
    unlinked_anchors: tuple[str, ...] = (),
) -> str:
    """The canonical abstention sentence for one empty-but-clean sub-question.

    Three honest-empty shapes exist: a query that ran cleanly and matched
    nothing (proof = the executed query), a schema boundary where no query
    could express the question at all (proof = the specialist's boundary
    trace; ``query`` is empty by design), and a dependency skip where the
    producing sub-question yielded no seed identifiers (proof = the
    federation's dependency trace; ``query`` again empty by design).

    A fourth shape arrived with the outer-join bridges: the query *did* return
    the anchor, and the anchor links to nothing. "Returned no matching records"
    would be false there, and the difference matters to an analyst — "I found
    the pattern and it maps to nothing" is a stronger statement than "I found
    nothing", and it is the one the retrieved record actually supports.
    """
    if query and unlinked_anchors:
        anchors = ", ".join(unlinked_anchors)
        return (
            f"The {source} source doesn't establish this — the executed query ran "
            f"cleanly and returned {anchors} with no linked records for: {text}"
        )
    if query:
        return (
            f"The {source} source doesn't establish this — the executed query ran "
            f"cleanly and returned no matching records for: {text}"
        )
    if dependency:
        return (
            f"The {source} source doesn't establish this — the sub-question it "
            f"depends on ({dependency}) produced no seed identifiers, so no query "
            f"was executed for: {text}"
        )
    return (
        f"The {source} source doesn't establish this — it doesn't model the "
        f"entities this question asks about, so no query was executed for: {text}"
    )


def _dependency_producer(result: SpecialistResult) -> str:
    for trace in result.traces:
        if trace.step == "dependency":
            return str((trace.detail or {}).get("producer", ""))
    return ""


def _name_miss_statement(source: str, names: tuple[str, ...]) -> str:
    """A specific, actionable abstention for a name lookup that matched nothing.

    The id advice is conditional on the source having ids an analyst can quote.
    It read "give its ATT&CK/CAPEC id (e.g. T1566, M1017, or CAPEC-98)" for
    every source, which on an identity graph keyed by opaque GUIDs is an
    instruction that cannot be followed, attached to a catalogue that was not
    consulted.
    """
    quoted = " or ".join(f"'{n}'" for n in names)
    if source in _ID_BEARING_SOURCES:
        return (
            f"No entity named {quoted} was found in the {source} source. Check the "
            f"name, or give its id ({_ID_EXAMPLES})."
        )
    return f"No entity named {quoted} was found in the {source} source. Check the name."


def _ambiguous_candidates(result: SpecialistResult) -> list[tuple[str, str]]:
    """Candidates the specialist declined to choose between, from its traces."""
    for trace in (result.traces or ()):
        detail = getattr(trace, "detail", None) or {}
        found = detail.get("ambiguous_candidates")
        if found:
            return [tuple(c) if isinstance(c, (list, tuple)) else (str(c), "")
                    for c in found]
    return []


def abstention_for(result: SpecialistResult) -> Abstention:
    """The enforced abstention for one empty-but-ok specialist result.

    When the empty result came from a definitional name lookup, the statement
    names the entity that could not be found (and how to disambiguate) instead
    of the generic "no matching records" wording — the analyst asked to define
    something by name, so the honest empty answer should say what it looked for.
    """
    # An ambiguous anchor gets the most useful abstention available: the
    # choice itself. Guessing here is the failure EXP-2026-08-020 named -- a
    # confident answer about the wrong entity, grounded in real records, that no
    # downstream check can reject -- so the honest output is to hand the
    # decision back rather than to make it silently.
    candidates = _ambiguous_candidates(result)
    if candidates:
        shown = ", ".join(
            f"{cid} ({cname})" if cname else str(cid) for cid, cname in candidates[:5]
        )
        return Abstention(
            sub_question_id=result.task.sub_question_id,
            source=result.task.source,
            statement=(
                f"The question names more than one entity in {result.task.source}, "
                f"so it was not answered rather than guessed. Did you mean: {shown}?"
            ),
            query=result.query,
        )

    names = definitional_name_terms(result.task.text)
    if _is_name_lookup(result.query) and names:
        statement = _name_miss_statement(result.task.source, names)
    else:
        statement = abstention_statement(
            result.task.source,
            result.task.text,
            result.query,
            dependency=_dependency_producer(result),
            unlinked_anchors=tuple(
                str(record.primary_id)
                for record in (result.records or ())
                if record.primary_id
            )[:5],
        )
    return Abstention(
        sub_question_id=result.task.sub_question_id,
        source=result.task.source,
        statement=statement,
        query=result.query,
    )


def _fact_claim(result: SpecialistResult, cap: int) -> Claim:
    cited = [r for r in result.records if r.primary_id][:cap]
    text = result.summary or (
        f"{len(result.records)} record(s) retrieved from {result.task.source} "
        f"for: {result.task.text}"
    )
    return Claim(
        text=text,
        citations=tuple(
            Citation(
                source=result.task.source,
                primary_id=r.primary_id,
                record_id=r.provenance.record_id if r.provenance else "",
            )
            for r in cited
        ),
        entity_ids=tuple(r.primary_id for r in cited),
        kind="fact",
        sub_question_id=result.task.sub_question_id,
    )


# A record's own scalar attributes ARE the answer to a lookup question ("what is
# CAPEC-555's abstraction and status?"), but the fact claim's text is the
# normalizer's id-line summary, which never reads them. Identity/prose keys are
# excluded: they are either already in the claim or are not attribute answers.
_NON_ATTRIBUTE_PROPERTIES = frozenset({
    "description", "name", "id", "attack_id", "properties_json",
    "external_references", "created", "modified",
})
_MAX_ATTRIBUTE_RECORDS = 10
_MAX_ATTRIBUTES_PER_RECORD = 12
_MAX_ATTRIBUTE_VALUE_CHARS = 120


# -- the answer contract ----------------------------------------------------
#
# What the question asked for, as opposed to which records to fetch. The plan
# carries neither, so the composer used to enumerate whatever came back and
# never state the field that was asked for. Three gaps, one cause:
#
#   * a requested property whose value is a LIST (``x_mitre_platforms``,
#     ``x_mitre_contributors``) is skipped by ``_attribute_pairs``, so the value
#     sits in the evidence and never reaches a claim;
#   * a bound filter is never mentioned, so a reader cannot tell a filtered
#     answer from an unfiltered one;
#   * when the requested relation returns nothing, the answer lists whatever
#     else came back and never says the requested set is EMPTY.
#
# The narrator usually papered over the first. That is not a property `C-017`
# can rest on, and 43% of the development run's narrators had timed out
# (`EXP-2026-09-016` A-8). Stating it as a verified claim is what turns a habit
# into a construction guarantee.

#: A list-valued property is joined into one readable value, capped so a
#: 40-platform list does not become the answer.
_MAX_REQUESTED_VALUES = 12


def _slots_for(result: SpecialistResult):
    """The requested slots for this result's sub-question, or all-unbound.

    Loaded lazily and failing soft: a missing card or registry must degrade to
    the composer's previous behaviour, never to an exception in the one path
    that is supposed to work without anything else being up.
    """
    from utils.planner.canonical import RequestedSlots

    try:
        from utils.planner.cards import load_source_cards
        from utils.specialists.schema import get_registry
        from utils.planner.canonical import requested_slots

        card = load_source_cards().get(result.task.source)
        if card is None:
            return RequestedSlots()
        return requested_slots(
            result.task.text or "",
            result.task.entities or (),
            card,
            get_registry(),
        )
    except Exception:  # noqa: BLE001 — no slots is the old behaviour, not an error
        return RequestedSlots()


def _requested_values(record: EvidenceRecord, prop: str) -> list[str]:
    """The record's value(s) for ``prop``, list-valued or not, as strings."""
    value = (record.properties or {}).get(prop)
    if value is None:
        return []
    items = value if isinstance(value, (list, tuple)) else [value]
    out: list[str] = []
    for item in items:
        text = str(item).strip()
        if text and text not in out:
            out.append(text)
    return out[:_MAX_REQUESTED_VALUES]


def _requested_property_claim(
    result: SpecialistResult, record: EvidenceRecord, prop: str
) -> Claim | None:
    """State the property the question asked for, whatever shape its value is.

    ``_attribute_pairs`` deliberately skips lists — a generic attribute listing
    of every list a record carries is noise. But the *requested* property is the
    answer, and two of the development half's exhibited failures are exactly
    this: the platforms of T1027.006 and the contributors of T1530 were in the
    evidence and absent from the claims.
    """
    values = _requested_values(record, prop)
    if not values:
        return None
    anchor = f"{record.primary_id} ({record.name})" if record.name else record.primary_id
    label = " ".join(w for w in _PROPERTY_LABEL_RE.split(prop) if w and w != "x") or prop
    return Claim(
        text=f"{anchor} {label}: {', '.join(values)}.",
        citations=(
            Citation(
                source=result.task.source,
                primary_id=record.primary_id,
                record_id=record.provenance.record_id if record.provenance else "",
            ),
        ),
        entity_ids=(record.primary_id,),
        kind="fact",
        sub_question_id=result.task.sub_question_id,
    )


#: ``x_mitre_platforms`` -> "mitre platforms"; ``Typical_Severity`` -> "Typical
#: Severity". The property's own identifier, not a gloss, for the same reason the
#: renderer uses the identifier: it is the vocabulary the source declares.
_PROPERTY_LABEL_RE = re.compile(r"[_\s]+")


def _facet_counts_zero(result: SpecialistResult, relation: str) -> bool:
    """Did ``describe`` report this relation with a count of zero?

    ``describe`` answers with facet COUNTS rather than materialised neighbours,
    so a zero count is a direct measurement of the thing being asked — stronger
    than an empty neighbour list, which only says none were fetched. A non-zero
    count already suppresses the claim in the caller; this is the same field
    read the other way.
    """
    wanted = _normalise_rel(relation)
    seen = False
    for record in result.records:
        for facet in record.facets or ():
            if not isinstance(facet, dict):
                continue
            if _normalise_rel(str(facet.get("rel") or "")) == wanted:
                if facet.get("count") or 0:
                    return False
                seen = True
    return seen


def _schema_denies(result: SpecialistResult, relation: str) -> bool:
    """Does the declared schema say this anchor's label has no such edge at all?

    A second, stronger warrant than "we looked and found none". "Which techniques
    does campaign C0046 mitigate" names ``MITIGATES``, and ``Campaign`` has no
    ``MITIGATES`` facet in either direction — so the walk never emitted that
    branch and `_query_asked_about` refused the claim, leaving the answer to
    enumerate the campaign's ``USES`` techniques instead and say nothing about
    what was asked. All 16 questions in the `empty` slice were that shape.

    The registry is being read for STRUCTURE, not for permission: it is the same
    declared facet list the builders route on, and "this label has no edge of
    this type" is a fact about the schema rather than about one query. Failing
    to load it returns False, which is the old behaviour.
    """
    labels = {record.label for record in result.records if record.label}
    if not labels:
        return False
    try:
        from utils.specialists.schema import get_registry

        registry = get_registry()
    except Exception:  # noqa: BLE001 — no registry, no claim
        return False
    if registry is None:
        return False
    wanted = _normalise_rel(relation)
    for label in labels:
        try:
            facets = registry.label_facets(label, dataset=result.task.source) or []
        except Exception:  # noqa: BLE001
            return False
        if any(_normalise_rel(str(f.rel_type)) == wanted for f in facets):
            return False
    return True


def _query_asked_about(result: SpecialistResult, relation: str) -> bool:
    """Did the executed query traverse ``relation``?

    Folded across the card's CamelCase and the graph's SCREAMING_SNAKE, because
    the query carries whichever the store uses. Necessary, not sufficient: a
    relation named nowhere in the query was certainly not asked about, which is
    the direction that matters.
    """
    wanted = _normalise_rel(relation)
    if not wanted:
        return False
    # The EXECUTED query only. The gate's traces carry rejected drafts too, and
    # a draft that named the relation and was refused is evidence the system
    # tried, not evidence it looked.
    return wanted in _normalise_rel(result.query or "")


#: Relationship identifiers begin with a verb the sentence already supplies.
#: ``HAS_PREREQUISITE`` rendered literally gives "has no has prerequisite".
_RELATION_VERBS = frozenset({"has", "have", "requires", "require", "exploits"})
#: A name ending in one of these is not a noun phrase: ``MAPS_TO``, ``MEMBER_OF``.
_TRAILING_PREPOSITIONS = frozenset({"to", "of", "for", "with", "in", "on", "by"})
#: CamelCase and SCREAMING_SNAKE alike, into lowercase words.
_WORD_SPLIT_RE = re.compile(r"[_\s]+|(?<=[a-z0-9])(?=[A-Z])")


def _relation_noun(relation: str) -> str:
    """``HAS_PREREQUISITE`` -> "prerequisites"; ``MAPS_TO`` -> "MAPS_TO relationships".

    The identifier's own words minus the verb the surrounding sentence already
    carries, pluralised — still the source's vocabulary rather than a gloss,
    which is the rule the renderer follows too.

    When that does not yield a clean noun the identifier is used verbatim.
    ``MAPS_TO`` and ``MEMBER_OF`` end in a preposition and ``CanAlsoBe`` is not a
    noun phrase at all; forcing them gave "no tos", "no member ofs" and "no
    canalsobes". An unambiguous identifier reads better than a mangled word and
    cannot be misread.
    """
    words = [w.lower() for w in _WORD_SPLIT_RE.split(relation) if w]
    if words and words[0] in _RELATION_VERBS and len(words) > 1:
        rest = words[1:]
        if rest[-1] not in _TRAILING_PREPOSITIONS:
            rest[-1] = _plural_word(rest[-1])
            return " ".join(rest)
    return f"{relation} relationships"


def _plural_word(word: str) -> str:
    if word.endswith(("s", "x", "ch", "sh")):
        return word + "es"
    if word.endswith("y") and len(word) > 1 and word[-2] not in "aeiou":
        return word[:-1] + "ies"
    return word + "s"


def _normalise_rel(name: str) -> str:
    """``CanAlsoBe`` and ``CAN_ALSO_BE`` are the same edge.

    The card declares CAPEC's natures in the source's CamelCase and the loaded
    graph carries the SCREAMING_SNAKE form, so a comparison that does not fold
    the two reads a present edge as absent.
    """
    return "".join(ch for ch in (name or "").upper() if ch.isalnum())


def _relation_is_empty(result: SpecialistResult, relation: str) -> bool:
    """Did the requested relation genuinely return nothing?

    Two ways this was wrong, both caught by the judge in Step 6:

    * It asked whether the record had **any** related entries, not whether it
      had any of *this* relation. A Category asked for its prerequisites carries
      its members in `related`, so the set was non-empty and the answer never
      said the requested set was empty — it enumerated the members instead, and
      answered a different question.
    * It ignored **facets**. `describe` returns facet counts without
      materialising neighbours, so a record can have an empty `related` list and
      a facet saying the edge exists. Asserting absence there is a false
      statement with full provenance, which is the worst thing this system can
      emit, and it is what produced the first `fabricated_mapping` flags against
      the repaired arm.

    Absence of materialised neighbours is not absence of the edge. All three
    checks are one-way: they can only suppress an absence claim, never
    manufacture one.

    The third is the warrant. "CAPEC-33 has no MAPS_TO" was stated off a query
    that walked ``PEER_OF`` and never asked about ``MAPS_TO`` at all — an
    absence asserted from a retrieval that did not look. As with the
    enumeration's scope line, the claim's warrant is the executed query, so the
    relation must appear in it before its emptiness means anything.
    """
    wanted = _normalise_rel(relation)
    if not wanted:
        return False
    # Three warrants, any one of which makes an emptiness meaningful. Without
    # one, "X has no Y" is asserted from a retrieval that never looked.
    if not (
        _query_asked_about(result, relation)
        or _schema_denies(result, relation)
        or _facet_counts_zero(result, relation)
    ):
        return False
    for record in result.records:
        for rel in record.related or ():
            if not isinstance(rel, dict):
                continue
            if _normalise_rel(str(rel.get("type") or "")) == wanted:
                return False
        for facet in record.facets or ():
            if not isinstance(facet, dict):
                continue
            if _normalise_rel(str(facet.get("rel") or "")) == wanted and (
                facet.get("count") or 0
            ):
                return False
    return True


def _absence_claim(result: SpecialistResult, relation: str) -> Claim:
    """State that the requested set is empty, with the executed query as proof.

    An anchor that resolved and a requested relation that returned no rows is a
    real answer — "CAPEC-513 has no execution steps" — and the composer used to
    list whatever else came back instead. It carries its query exactly as an
    ``Abstention`` does, and the verifier admits it only when that query ran
    clean, so an absence can never be asserted from a failed lookup.
    """
    anchor_ids = [r.primary_id for r in result.records if r.primary_id]
    anchor = anchor_ids[0] if anchor_ids else (result.task.seed_ids or ("the anchor",))[0]
    phrase = _relation_noun(relation)
    return Claim(
        text=f"{anchor} has no {phrase} in this catalogue.",
        citations=tuple(
            Citation(
                source=result.task.source,
                primary_id=record.primary_id,
                record_id=record.provenance.record_id if record.provenance else "",
            )
            for record in result.records[:1]
            if record.primary_id
        ),
        entity_ids=tuple(anchor_ids[:1]),
        kind="absence",
        sub_question_id=result.task.sub_question_id,
    )


def _attribute_pairs(record: EvidenceRecord) -> list[tuple[str, str]]:
    """The record's own short scalar attributes, in a stable order."""
    pairs: list[tuple[str, str]] = []
    for key, value in sorted((record.properties or {}).items()):
        if key in _NON_ATTRIBUTE_PROPERTIES or key.startswith("_"):
            continue
        if value is None or isinstance(value, (list, dict, tuple)):
            continue
        text = str(value).strip()
        if not text or len(text) > _MAX_ATTRIBUTE_VALUE_CHARS:
            continue
        pairs.append((key, text))
        if len(pairs) >= _MAX_ATTRIBUTES_PER_RECORD:
            break
    return pairs


def _attribute_claim(result: SpecialistResult, record: EvidenceRecord) -> Claim | None:
    """One citation-backed claim stating a record's own attribute values.

    Closes the projection gap the independent panel found: the evidence carried
    ``Abstraction``/``Status`` and the answer said only "Found 1 CAPEC record(s)",
    because ``summarize()`` templates ids and never reads a record's properties.
    """
    pairs = _attribute_pairs(record)
    if not pairs:
        return None
    anchor = f"{record.primary_id} ({record.name})" if record.name else record.primary_id
    body = "; ".join(f"{key}: {value}" for key, value in pairs)
    return Claim(
        text=f"{anchor} has {body}.",
        citations=(
            Citation(
                source=result.task.source,
                primary_id=record.primary_id,
                record_id=record.provenance.record_id if record.provenance else "",
            ),
        ),
        entity_ids=(record.primary_id,),
        kind="fact",
        sub_question_id=result.task.sub_question_id,
    )


def _attribute_claims(result: SpecialistResult) -> list[Claim]:
    """Attribute claims for the records of a lookup-shaped result.

    Bounded to the first few records: on a 300-row scan the per-record attributes
    are noise, but on the 1-3 records a lookup returns they are the answer.
    """
    records = [r for r in result.records if r.primary_id][:_MAX_ATTRIBUTE_RECORDS]
    if len(result.records) > _MAX_ATTRIBUTE_RECORDS:
        return []
    claims = []
    for record in records:
        claim = _attribute_claim(result, record)
        if claim is not None:
            claims.append(claim)
    return claims


def _correlation_claim(
    value: str, entries: list[dict[str, str]], cap: int
) -> Claim:
    sources = sorted({e["source"] for e in entries})
    seen: dict[tuple[str, str], None] = {}
    for e in entries:
        seen.setdefault((e["source"], e["primary_id"]), None)
    citations = tuple(
        Citation(source=source, primary_id=primary_id)
        for source, primary_id in list(seen)[:cap]
    )
    return Claim(
        text=(
            f"The identifier {value} is corroborated across "
            f"{' and '.join(sources)} ({len(entries)} record(s) share it)."
        ),
        citations=citations,
        entity_ids=(value,),
        kind="correlation",
    )


def _related_ids(record: EvidenceRecord) -> list[str]:
    """Ordered, de-duplicated ids of a record's related neighbours.

    No id-shape filter: a related id may be a MITRE id (``M1041``) or a
    structured child id (``capec:attack-pattern:66:consequence:1``) — the gold's
    ``must_include_related`` uses whichever the graph exposes, so both must
    survive verbatim.
    """
    seen: dict[str, None] = {}
    for rel in record.related:
        if not isinstance(rel, dict):
            continue
        rid = rel.get("id") or rel.get("entry_id")
        if rid:
            seen.setdefault(str(rid), None)
    return list(seen)


#: Edge types whose plain-English name is the answer to the question that asked
#: for them. "CAPEC-98 has 1 AttackPatterns: CAPEC-151" is true but useless — it
#: never says CAPEC-151 is the *parent*, so an answer bound to this claim cannot
#: name the relationship and will honestly report it cannot confirm one.
_REL_NOUNS = {
    "CHILD_OF": "ChildOf parent",
    "PARENT_OF": "ParentOf child",
    # Direction matters and these were inverted. The neighbours template walks
    # OUT from the anchor, so `A -CAN_PRECEDE-> B` means A precedes B: B is the
    # **successor**. Likewise `A -CAN_FOLLOW-> B` means A follows B, so B is the
    # **predecessor**. Naming them the other way round states the relationship
    # backwards — a grounded id with an ungrounded claim about it, which the
    # independent judge correctly flagged as a hallucination on C-LKP-02/05.
    "CAN_FOLLOW": "CanFollow predecessor",
    "CAN_PRECEDE": "CanPrecede successor",
    "PEER_OF": "PeerOf peer",
    "HAS_MITIGATION": "mitigation",
    "HAS_CONSEQUENCE": "consequence",
    "HAS_EXECUTION_STEP": "execution step",
    "HAS_PREREQUISITE": "prerequisite",
    "HAS_SKILL": "required skill",
    "EXPLOITS_WEAKNESS": "exploited weakness",
    "MAPS_TO": "ATT&CK mapping",
    "SUBTECHNIQUE_OF": "parent technique",
    "USES": "used technique",
    "MITIGATES": "mitigated technique",
}


def _plural(noun: str, count: int) -> str:
    """Pluralise the head word, respecting the sibilant and -y endings."""
    if count == 1:
        return noun
    head, sep, tail = noun.rpartition(" ")
    word = tail or noun
    if word.endswith(("s", "x", "z", "ch", "sh")):
        plural = f"{word}es"
    elif word.endswith("y") and not word.endswith(("ay", "ey", "iy", "oy", "uy")):
        plural = f"{word[:-1]}ies"
    else:
        plural = f"{word}s"
    return f"{head}{sep}{plural}" if tail else plural


#: Nouns from :data:`_REL_NOUNS` that assert what KIND the neighbour is, and the
#: labels each one is true of.
#:
#: ATT&CK's ``USES`` is the reason this exists. It joins Group->Software,
#: Campaign->Software and Software->Technique alike, so "used technique" is
#: right for one of those and a false statement about a grounded identifier for
#: the others — EXP-2026-08-010 caught the composer writing "S0512 (FatDuke) has
#: 2 used techniques: G0016, C0023", where G0016 is a Group and C0023 a
#: Campaign. Naming an id and mis-stating what it is has been this project's
#: only remaining fabrication source in an otherwise deterministic path.
#:
#: A noun absent from this map is unconstrained and behaves exactly as before,
#: so the CAPEC hierarchy roles (ChildOf/CanPrecede/PeerOf, all
#: AttackPattern->AttackPattern) are untouched.
_NOUN_EXPECTS: dict[str, frozenset[str]] = {
    "used technique": frozenset({"Technique", "SubTechnique"}),
    "mitigated technique": frozenset({"Technique", "SubTechnique"}),
    "parent technique": frozenset({"Technique"}),
    "exploited weakness": frozenset({"Weakness"}),
    "mitigation": frozenset({"Mitigation"}),
    "consequence": frozenset({"Consequence"}),
    "execution step": frozenset({"ExecutionStep"}),
    "required skill": frozenset({"Skill"}),
    "ATT&CK mapping": frozenset({"TaxonomyEntry"}),
}


#: Readable English for a label used as a noun, as (singular, plural). Without
#: this the fallback appends an "s" to the label verbatim and writes
#: "2 Softwares" — a type name with a plural bolted on, which reads as a leaked
#: internal identifier rather than an answer.
#:
#: The plural is spelled out rather than derived because ``_plural`` inflects the
#: last word of a phrase, which is right for "used technique" and wrong for
#: "piece of software". Only labels whose bare form is wrong need an entry.
_LABEL_NOUNS: dict[str, tuple[str, str]] = {
    "Software": ("piece of software", "pieces of software"),
    "Group": ("group", "groups"),
    "Campaign": ("campaign", "campaigns"),
    "Technique": ("technique", "techniques"),
    "SubTechnique": ("sub-technique", "sub-techniques"),
    "Mitigation": ("mitigation", "mitigations"),
    "Tactic": ("tactic", "tactics"),
    "AttackPattern": ("attack pattern", "attack patterns"),
    "Weakness": ("weakness", "weaknesses"),
    "TaxonomyEntry": ("taxonomy entry", "taxonomy entries"),
    "DataComponent": ("data component", "data components"),
    "DetectionStrategy": ("detection strategy", "detection strategies"),
}


def _related_noun(record: EvidenceRecord, count: int = 0) -> str:
    """A readable plural for a record's related set.

    Prefers the *relationship* over the neighbour's label: the edge is what the
    question asked about, and a label-only noun ("AttackPatterns") silently drops
    the semantics a hierarchy or mitigation question turns on.

    The preference yields when the relationship's noun would assert a kind the
    neighbours are not — see :data:`_NOUN_EXPECTS`. A slightly flatter noun is
    always better than a confident wrong one, because the identifiers beside it
    are correct and a reader has no way to tell the label is the part that lied.
    """
    labels = {
        str(rel.get("label")).strip()
        for rel in record.related
        if isinstance(rel, dict) and rel.get("label")
    }
    rel_types = {
        str(rel.get("type")).strip().upper()
        for rel in record.related
        if isinstance(rel, dict) and rel.get("type")
    }
    if len(rel_types) == 1:
        noun = _REL_NOUNS.get(next(iter(rel_types)))
        expected = _NOUN_EXPECTS.get(noun or "")
        # Unlabelled neighbours cannot contradict the noun, so they keep the old
        # behaviour rather than being demoted on missing evidence.
        if noun and (expected is None or not labels or labels <= expected):
            return _plural(noun, count)
    # A per-neighbour role (an abstraction ancestor's "standard"/"meta") is
    # annotated on each id already; fall back to the neighbour label.
    if len(labels) == 1:
        label = next(iter(labels))
        if label:
            spelled = _LABEL_NOUNS.get(label)
            if spelled:
                return spelled[0] if count == 1 else spelled[1]
            return _plural(label, count)
    return "related item(s)"


#: How much of a record's description a definitional claim carries. Descriptions
#: run to several paragraphs; the first part carries the mechanism, which is what
#: a "how does this work" question is asking for.
_MAX_DESCRIPTION_CHARS = 700

_MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")


def _strip_markdown_links(text: str) -> str:
    """``[Create Account](https://attack.mitre.org/techniques/T1136)`` → ``Create Account``.

    MITRE descriptions cross-reference other entities as markdown links whose
    *URL* carries an identifier. Emitting them verbatim would put ids into the
    answer that are not in the claim's ``entity_ids`` and are not grounded by the
    cited record — manufacturing exactly the ungrounded-mention problem this
    claim exists to reduce. The link text is the readable part and carries no id.
    """
    return _MARKDOWN_LINK.sub(r"\1", text or "")


def _trim_to_sentence(text: str, limit: int) -> str:
    """Cut at the last sentence boundary within ``limit``, never mid-word."""
    if len(text) <= limit:
        return text
    window = text[:limit]
    cut = max(window.rfind(". "), window.rfind(".\n"))
    if cut > limit // 3:
        return window[: cut + 1]
    return window.rsplit(" ", 1)[0] + "…"


def _description_claim(result: SpecialistResult, record: EvidenceRecord) -> Claim | None:
    """State what an entity *is*, for a result that is about one entity.

    The composer's attribute claims deliberately exclude ``description`` (it is
    prose, not a scalar attribute), and the normalizer summaries are id-lines. So
    a question like "What is T1036.010 — how does this technique actually work?"
    was answered with STIX bookkeeping — ``revoked: False``, ``stix_type``,
    ``x_mitre_version`` — while the description explaining the mechanism sat
    unread in the same record.

    Three blind-holdout lookups (H-LKP-01/02/03) were judged 0.5 for exactly
    this, each with the judge noting the description was present in the evidence.
    They were filed under ``ungrounded`` by the gap classifier only because it
    has no category for "answered with the wrong field".

    Gated on the *shape* of the result rather than on the question's phrasing:
    a single-record result is a question about that record. Phrasing gating was
    tried and rejected — ``is_definitional_request`` matches "What is T1036.010…"
    but not "CAPEC-321 … what does this attack pattern actually involve?", and
    both are the same kind of question.
    """
    # `description` lives in `properties`, not as a field on EvidenceRecord —
    # the serialized artifact hoists it to the top level, the dataclass does not.
    text = str((record.properties or {}).get("description") or "").strip()
    if not text:
        return None
    body = _trim_to_sentence(_strip_markdown_links(text).strip(), _MAX_DESCRIPTION_CHARS)
    anchor = f"{record.primary_id} ({record.name})" if record.name else record.primary_id
    return Claim(
        text=f"{anchor}: {body}",
        citations=(
            Citation(
                source=result.task.source,
                primary_id=record.primary_id,
                record_id=record.provenance.record_id if record.provenance else "",
            ),
        ),
        entity_ids=(record.primary_id,),
        kind="fact",
        sub_question_id=result.task.sub_question_id,
    )


def _query_carries(result: SpecialistResult, prop: str) -> bool:
    """Did the query that produced this result filter on ``prop``?

    Necessary, not sufficient: a property named nowhere in the executed query
    cannot have been filtered on, which is the direction that matters. Used to
    decide whether an enumeration may *state* a restriction, never to decide
    whether one was applied.
    """
    if not prop:
        return False
    # The EXECUTED query only, for the same reason as `_query_asked_about`: a
    # rejected draft that named the property never filtered anything.
    return prop in (result.query or "")


def _enumeration_claim(
    result: SpecialistResult,
    record: EvidenceRecord,
    bound_filter: tuple[str, str, str] | None = None,
) -> Claim:
    """A structured claim naming *every* id in a record's related set.

    The completeness surface for "which techniques / what mitigations /
    consequences" questions: the fact claim samples a few ids for readable prose,
    this claim carries the whole set so the answer is complete and the analyst
    can audit it. Cited to the anchor record, whose ``id_pool`` grounds every
    listed id (``grounding.id_pool`` includes related ids).
    """
    ids: list[str] = []
    parts: list[str] = []
    seen: set[str] = set()
    for rel in record.related:
        if not isinstance(rel, dict):
            continue
        rid = rel.get("id") or rel.get("entry_id")
        if not rid:
            continue
        rid = str(rid)
        if rid in seen:
            continue
        seen.add(rid)
        ids.append(rid)
        # A role (e.g. an abstraction ancestor's "standard"/"meta") is annotated
        # in the prose so the answer says *which* is which, not just that both
        # exist — the distinction the hierarchy questions demand.
        # A chained neighbour names the hop it was reached through, so the
        # answer states the mapping instead of leaving two sets beside each
        # other for a reader — or a narrator — to pair up.
        role = rel.get("role")
        via = rel.get("via")
        if via and via != rid:
            parts.append(f"{rid} (via {via})")
        elif role:
            parts.append(f"{rid} ({role})")
        else:
            parts.append(rid)
        if len(ids) >= _enum_bound("MAX_ENUMERATION_IDS", _MAX_ENUMERATION_IDS):
            break
    noun = _related_noun(record, len(ids))
    anchor = record.name and f"{record.primary_id} ({record.name})" or record.primary_id
    # Say what the set was restricted to — but only when the executed query
    # actually carried the restriction.
    #
    # Stating it unconditionally was wrong and the judge caught it. On evidence
    # retrieved before the filter push-down existed, the claim "restricted to
    # taxonomy name WASC" sat over records that were not WASC, and the grader
    # correctly recorded a fabricated mapping — the first non-zero
    # `fabricated_mapping` this project has produced, and the same defect
    # accounts for the rise in flagged statements from 36 to 202
    # (`EXP-2026-09-018` Step 5).
    #
    # A claim's warrant here is the QUERY, not the records: a related neighbour
    # carries no properties, so the composer can never verify a neighbour-side
    # filter from the evidence it cites. The property name appearing in the
    # executed query is a necessary condition for the filter to have been
    # applied, so its absence is proof the restriction did not happen. One-way
    # and conservative: it can only withhold a true scope line, never assert a
    # false one.
    scope = ""
    if bound_filter is not None and _query_carries(result, bound_filter[1]):
        _, prop, value = bound_filter
        label = " ".join(
            w for w in _PROPERTY_LABEL_RE.split(prop) if w and w != "x"
        ) or prop
        scope = f", restricted to {label} {value}"
    text = f"{anchor} has {len(ids)} {noun}{scope}: {', '.join(parts)}."
    return Claim(
        text=text,
        citations=(
            Citation(
                source=result.task.source,
                primary_id=record.primary_id,
                record_id=record.provenance.record_id if record.provenance else "",
            ),
        ),
        entity_ids=tuple(ids),
        kind="enumeration",
        sub_question_id=result.task.sub_question_id,
    )


def _primary_enumeration_claim(result: SpecialistResult) -> Claim:
    """A claim naming *every* primary id a multi-record result returned.

    The second under-enumeration shape: the answer is the set of records
    themselves (e.g. the 37 techniques a group uses, each its own record), and
    the fact claim cites only the first ``cap``. This lists them all, each cited
    to its own record so every id is grounded."""
    records = [r for r in result.records if r.primary_id]
    ids: list[str] = list(dict.fromkeys(r.primary_id for r in records))[
        : _enum_bound("MAX_ENUMERATION_IDS", _MAX_ENUMERATION_IDS)
    ]
    idset = set(ids)
    citations: list[Citation] = []
    seen: set[str] = set()
    for r in records:
        if r.primary_id in idset and r.primary_id not in seen:
            seen.add(r.primary_id)
            citations.append(
                Citation(
                    source=result.task.source,
                    primary_id=r.primary_id,
                    record_id=r.provenance.record_id if r.provenance else "",
                )
            )
    listed = _summarize_ids(ids, cap=len(ids))
    return Claim(
        text=f"All {len(ids)} result(s) for this question: {listed}.",
        citations=tuple(citations),
        entity_ids=tuple(ids),
        kind="enumeration",
        sub_question_id=result.task.sub_question_id,
    )


def _enumeration_claims(
    result: SpecialistResult,
    cap: int,
    bound_filter: tuple[str, str, str] | None = None,
) -> list[Claim]:
    """Enumeration claims for a single-source result, when the answer must list a
    full set the fact claim only samples. Two shapes:

    A. an anchor record with a large ``related`` set (techniques of a software,
       mitigations of a technique, consequences of a pattern); or
    B. a multi-record result whose *primary ids* are themselves the answer set
       (the techniques a group uses).

    Shape A fires for *any* non-empty related set. Correlation is handled
    separately, so cross-source join values are left to the join logic.
    """
    claims: list[Claim] = []
    # Shape A: per-anchor related sets.
    #
    # This used to fire only on `enumerative or len(ids) > cap`, on the
    # assumption that a set small enough not to be truncated was already named
    # in the fact claim's prose. That assumption holds for one normalizer and
    # not the other. `cypher/normalizer.summarize` does name a few related ids
    # ("Found 3 item(s) related to T1055 (e.g. …)"); `gremlin/normalizer`
    # summarizes only the *primary* ids ("Found 1 CAPEC record(s): CAPEC-606.")
    # and never mentions the related set at all.
    #
    # So for a CAPEC record with a small related set and a question the
    # enumerative regex did not match, the related ids were retrieved, grounded,
    # and then stated nowhere — not in a claim, not in the narrative. All three
    # of the blind holdout's `under_enumeration` cases were exactly this shape:
    # CAPEC single records with related sets of 1, 2 and 3.
    #
    # There is no reason to suppress the completeness surface for a small set.
    # A set of two costs one short claim; leaving it out costs the answer.
    for record in result.records:
        ids = _related_ids(record)
        if ids:
            claims.append(_enumeration_claim(result, record, bound_filter))
        if len(claims) >= _enum_bound(
            "MAX_ENUMERATION_CLAIMS", _MAX_ENUMERATION_CLAIMS_PER_RESULT
        ):
            return claims
    # Shape B: many primary records the fact claim would truncate. Skipped when A
    # already enumerated (the related sets are the answer, not the anchors).
    if not claims:
        distinct_primary = {r.primary_id for r in result.records if r.primary_id}
        if len(distinct_primary) > cap:
            claims.append(_primary_enumeration_claim(result))
    return claims


class DeterministicComposer:
    """Compose a ``SynthesizedAnswer`` draft mechanically from evidence."""

    name = "deterministic"

    def __init__(self, config: SynthesisConfig | None = None) -> None:
        self._config = config or SynthesisConfig()

    def compose(self, evidence: FederatedEvidence) -> SynthesizedAnswer:
        cap = self._config.max_citations
        claims: list[Claim] = []
        abstentions: list[Abstention] = []
        notes: list[str] = []

        for result in evidence.results:
            slots = _slots_for(result)
            if result.records:
                claims.append(_fact_claim(result, cap))
                # A result about exactly one entity should say what that entity
                # is, before it lists the entity's bookkeeping fields.
                if len(result.records) == 1:
                    described = _description_claim(result, result.records[0])
                    if described is not None:
                        claims.append(described)
                claims.extend(_attribute_claims(result))
                # The requested property, whatever shape its value is. Placed
                # after the generic attribute listing so the answer reads
                # "what it is, then what you asked about".
                if slots.property:
                    for record in result.records[:_MAX_ATTRIBUTE_RECORDS]:
                        requested = _requested_property_claim(
                            result, record, slots.property
                        )
                        if requested is not None:
                            claims.append(requested)
                claims.extend(_enumeration_claims(result, cap, slots.filter))
                # The requested relation came back empty while the anchor
                # resolved: an answer, not an absence of one.
                # Judged on THAT relation, and never against a facet that says
                # the edge is there — see `_relation_is_empty`.
                if slots.relation and _relation_is_empty(result, slots.relation):
                    claims.append(_absence_claim(result, slots.relation))
            elif result.ok:
                abstentions.append(abstention_for(result))
            else:
                notes.append(
                    f"The {result.task.source} specialist failed and contributed "
                    f"no evidence: {result.error or 'unknown error'}"
                )

        join_index = evidence.join_index()
        for value in evidence.cross_source_join_values():
            claims.append(_correlation_claim(value, join_index.get(value, []), cap))

        # An iterative run re-describes the same anchor on every hop, so the
        # identical fact/attribute claim is composed once per hop — C-HIE-01 came
        # back with four copies of "Found 1 CAPEC record(s): CAPEC-98". The text
        # is the claim's identity for a reader, so collapse exact repeats while
        # keeping the first occurrence's citations and order.
        deduped: list[Claim] = []
        seen_text: set[str] = set()
        for claim in claims:
            key = (claim.text or "").strip()
            if key and key in seen_text:
                continue
            seen_text.add(key)
            deduped.append(claim)
        claims = deduped

        for part in evidence.unsupported:
            notes.append(_unsupported_note(part, evidence.request))
        for skip in evidence.skipped:
            notes.append(
                f"Skipped {skip.get('source', '?')}: {skip.get('reason', 'unknown')}"
            )

        # With no grounded fact, the top-line must be an honest, actionable
        # statement — naming what was searched and how to disambiguate — rather
        # than a bare "no evidence" line or a leaked model reason.
        narrative = _narrative(claims, abstentions)
        if not claims:
            narrative = _clarification_narrative(evidence, abstentions)

        return SynthesizedAnswer(
            request=evidence.request,
            headline=_headline(evidence, claims, abstentions),
            narrative=narrative,
            claims=claims,
            abstentions=abstentions,
            notes=notes,
            composer=self.name,
        )


def _summarize_ids(ids: list[str], cap: int = 8) -> str:
    """`"A, B, C, and 5 more"` — a compact, readable identifier list."""
    seen: dict[str, None] = {}
    for i in ids:
        seen.setdefault(i, None)
    uniq = list(seen)
    shown = uniq[:cap]
    listed = ", ".join(shown)
    extra = len(uniq) - len(shown)
    return f"{listed}, and {extra} more" if extra > 0 else listed


def _unsupported_note(part: dict[str, str], request: str) -> str:
    """A note for one planner-unsupported part, sanitized.

    A clean source-availability reason (authored by the deterministic drafter)
    is surfaced verbatim. A model-authored reason — often garbled, e.g. "the
    request 'What' is incomplete" — is NOT echoed; instead the note states
    plainly that no live source matched and asks the analyst to name a specific
    entity or give an id.
    """
    reason = str(part.get("reason", "")).strip()
    desc = str(part.get("description", "")).strip()
    if reason and any(m in reason.lower() for m in _CLEAN_REASON_MARKERS):
        return f"Unsupported by the available sources: {desc or request} ({reason})"
    return (
        f"The available graph sources could not be matched to this request: "
        f"'{request}'. If you meant a specific entity, name it or give its id "
        f"({_ID_EXAMPLES})."
    )


def _clarification_narrative(
    evidence: FederatedEvidence, abstentions: list[Abstention]
) -> str:
    """An honest, actionable top-line for an answer with no grounded fact.

    Names the entity the analyst tried to define (when the request was
    definitional) and how to disambiguate, so an empty result reads as a clear
    request for specificity rather than a flat "I can't get any information".
    """
    # Names actually searched by a name lookup; else the request's own
    # definitional names — but only when the request actually reads as
    # definitional, so a non-definitional dead end ("test question") keeps the
    # generic honest-empty wording rather than naming incidental words.
    names = _name_lookup_terms(evidence) or (
        definitional_name_terms(evidence.request)
        if is_definitional_request(evidence.request)
        else ()
    )
    where = _sources_phrase(evidence)
    hint = _id_hint(evidence)
    if names:
        quoted = " or ".join(f"'{n}'" for n in names)
        tail = f", or tell me the entity's id{hint} and I'll look it up" if hint else ""
        return f"I couldn't find {quoted} in {where}. Check the name{tail}."
    if abstentions:
        tail = f" or give its id{hint}" if hint else ""
        return (
            f"The routed sources returned no matching records for this question. "
            f"If you're after a specific entity, name it{tail}."
        )
    tail = f" or give its id{hint}" if hint else ""
    return (
        f"None of the live graph sources cover this request. If you meant a "
        f"specific entity, name it{tail}."
    )


def _narrative(claims: list[Claim], abstentions: list[Abstention]) -> str:
    """A readable prose answer assembled from the grounded claims.

    The LLM narrator writes the fluent answer when the LLM is on; without it this
    is the fallback. It keeps each source's one-line fact summary, then collapses
    the (often many) cross-source correlations into a single sentence naming a few
    identifiers instead of repeating "X is corroborated …" once per id, and adds
    honest abstentions — so the UI always has a readable answer above the table.
    """
    # Enumeration claims carry the *complete* related set — include them so the
    # deterministic narrative (LLM-off) is as complete as the claim table, not a
    # sample. The LLM narrator may keep prose short since the full list lives in
    # the structured claims regardless.
    facts = [c.text.rstrip(".") for c in claims if c.kind in ("fact", "enumeration")]
    correlation_ids = [i for c in claims if c.kind == "correlation" for i in c.entity_ids]

    # An absence claim LEADS. It is the answer to the question that was asked,
    # and everything else is context about the anchor. Omitting it from the
    # prose — which is what happened until 2026-09-12 — left a reader of
    # "what prerequisites does CAPEC-689 require" with a sentence about the
    # category's members and no answer at all. Four D0 questions lost between
    # 0.45 and 0.75 of their score to exactly that (`EXP-2026-09-018` Step 6).
    absences = [c.text.rstrip(".") for c in claims if c.kind == "absence"]

    sentences = absences + list(facts)
    if correlation_ids:
        n = len(set(correlation_ids))
        sentences.append(
            f"{n} identifier{'' if n == 1 else 's'} are corroborated across both "
            f"CAPEC and ATT&CK ({_summarize_ids(correlation_ids)})"
        )

    if not sentences and not abstentions:
        return "The routed sources returned no evidence for this question."
    body = ". ".join(s for s in sentences if s)
    if body:
        body += "."
    if abstentions:
        body = (body + " " + " ".join(a.statement for a in abstentions)).strip()
    return body


def _headline(
    evidence: FederatedEvidence,
    claims: list[Claim],
    abstentions: list[Abstention],
) -> str:
    record_total = sum(len(r.records) for r in evidence.results)
    source_total = len({r.task.source for r in evidence.results})
    correlations = sum(1 for c in claims if c.kind == "correlation")
    parts = [
        f"Gathered {record_total} record(s) from {source_total} source(s)"
        if record_total
        else "No records were returned by the routed specialists",
    ]
    if correlations:
        parts.append(f"{correlations} cross-source correlation(s) on shared identifiers")
    if abstentions:
        parts.append(f"{len(abstentions)} question(s) the sources don't establish")
    if evidence.unsupported:
        parts.append(f"{len(evidence.unsupported)} part(s) unsupported")
    return "; ".join(parts) + "."
