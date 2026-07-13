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

from utils.planner.intent import is_definitional_request
from utils.specialists.contracts import SpecialistResult
from utils.specialists.federation import FederatedEvidence
from utils.specialists.resolve import definitional_name_terms

from .config import SynthesisConfig
from .contracts import Abstention, Citation, Claim, SynthesizedAnswer

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
    source: str, text: str, query: str = "", *, dependency: str = ""
) -> str:
    """The canonical abstention sentence for one empty-but-clean sub-question.

    Three honest-empty shapes exist: a query that ran cleanly and matched
    nothing (proof = the executed query), a schema boundary where no query
    could express the question at all (proof = the specialist's boundary
    trace; ``query`` is empty by design), and a dependency skip where the
    producing sub-question yielded no seed identifiers (proof = the
    federation's dependency trace; ``query`` again empty by design).
    """
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
    facts = [c.text.rstrip(".") for c in claims if c.kind == "fact"]
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
