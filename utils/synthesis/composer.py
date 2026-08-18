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

from utils.planner.intent import is_definitional_request, is_enumerative_request
from utils.specialists.contracts import EvidenceRecord, SpecialistResult
from utils.specialists.federation import FederatedEvidence
from utils.specialists.resolve import definitional_name_terms

from .config import SynthesisConfig
from .contracts import Abstention, Citation, Claim, SynthesizedAnswer

# An enumeration claim's id list is bounded generously — far above any real
# related set in the catalogue — so the answer stays complete without an
# unbounded claim. Only records with more related ids than the fact claim would
# sample, or an explicitly enumerative question, get one.
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
    """A specific, actionable abstention for a name lookup that matched nothing."""
    quoted = " or ".join(f"'{n}'" for n in names)
    return (
        f"No entity named {quoted} was found in the {source} source. Check the "
        f"name, or give its ATT&CK/CAPEC id ({_ID_EXAMPLES})."
    )


def abstention_for(result: SpecialistResult) -> Abstention:
    """The enforced abstention for one empty-but-ok specialist result.

    When the empty result came from a definitional name lookup, the statement
    names the entity that could not be found (and how to disambiguate) instead
    of the generic "no matching records" wording — the analyst asked to define
    something by name, so the honest empty answer should say what it looked for.
    """
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


def _related_noun(record: EvidenceRecord, count: int = 0) -> str:
    """A readable plural for a record's related set.

    Prefers the *relationship* over the neighbour's label: the edge is what the
    question asked about, and a label-only noun ("AttackPatterns") silently drops
    the semantics a hierarchy or mitigation question turns on.
    """
    rel_types = {
        str(rel.get("type")).strip().upper()
        for rel in record.related
        if isinstance(rel, dict) and rel.get("type")
    }
    if len(rel_types) == 1:
        noun = _REL_NOUNS.get(next(iter(rel_types)))
        if noun:
            return _plural(noun, count)
    # A per-neighbour role (an abstraction ancestor's "standard"/"meta") is
    # annotated on each id already; fall back to the neighbour label.
    labels = {
        str(rel.get("label")).strip()
        for rel in record.related
        if isinstance(rel, dict) and rel.get("label")
    }
    if len(labels) == 1:
        label = next(iter(labels))
        if label:
            return label if label.lower().endswith("s") else f"{label}s"
    return "related item(s)"


def _enumeration_claim(result: SpecialistResult, record: EvidenceRecord) -> Claim:
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
        role = rel.get("role")
        parts.append(f"{rid} ({role})" if role else rid)
        if len(ids) >= _enum_bound("MAX_ENUMERATION_IDS", _MAX_ENUMERATION_IDS):
            break
    noun = _related_noun(record, len(ids))
    anchor = record.name and f"{record.primary_id} ({record.name})" or record.primary_id
    text = f"{anchor} has {len(ids)} {noun}: {', '.join(parts)}."
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


def _enumeration_claims(result: SpecialistResult, cap: int) -> list[Claim]:
    """Enumeration claims for a single-source result, when the answer must list a
    full set the fact claim only samples. Two shapes:

    A. an anchor record with a large ``related`` set (techniques of a software,
       mitigations of a technique, consequences of a pattern); or
    B. a multi-record result whose *primary ids* are themselves the answer set
       (the techniques a group uses).

    Fires on an explicitly enumerative question, or whenever the set outnumbers
    the fact claim's ``cap`` sample (objective truncation). Correlation is
    handled separately, so cross-source join values are left to the join logic.
    """
    enumerative = is_enumerative_request(result.task.text)
    claims: list[Claim] = []
    # Shape A: per-anchor related sets.
    for record in result.records:
        ids = _related_ids(record)
        if ids and (enumerative or len(ids) > cap):
            claims.append(_enumeration_claim(result, record))
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
            if result.records:
                claims.append(_fact_claim(result, cap))
                claims.extend(_attribute_claims(result))
                claims.extend(_enumeration_claims(result, cap))
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
        f"'{request}'. If you meant a specific ATT&CK or CAPEC entity, name it "
        f"or give its id ({_ID_EXAMPLES})."
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
    if names:
        quoted = " or ".join(f"'{n}'" for n in names)
        return (
            f"I couldn't find {quoted} in the live ATT&CK/CAPEC graphs. Check the "
            f"name, or tell me the entity's id ({_ID_EXAMPLES}) and I'll look it up."
        )
    if abstentions:
        return (
            "The routed sources returned no matching records for this question. "
            f"If you're after a specific entity, name it or give its id ({_ID_EXAMPLES})."
        )
    return (
        "None of the live graph sources cover this request. If you meant a "
        f"specific ATT&CK or CAPEC entity, name it or give its id ({_ID_EXAMPLES})."
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

    sentences = list(facts)
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
