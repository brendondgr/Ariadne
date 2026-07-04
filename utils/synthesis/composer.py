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

from utils.specialists.contracts import SpecialistResult
from utils.specialists.federation import FederatedEvidence

from .config import SynthesisConfig
from .contracts import Abstention, Citation, Claim, SynthesizedAnswer


def abstention_statement(source: str, text: str, query: str = "") -> str:
    """The canonical abstention sentence for one empty-but-clean sub-question.

    Two honest-empty shapes exist: a query that ran cleanly and matched
    nothing (proof = the executed query), and a schema boundary where no
    query could express the question at all (proof = the specialist's
    boundary trace; ``query`` is empty by design).
    """
    if query:
        return (
            f"The {source} source doesn't establish this — the executed query ran "
            f"cleanly and returned no matching records for: {text}"
        )
    return (
        f"The {source} source doesn't establish this — it doesn't model the "
        f"entities this question asks about, so no query was executed for: {text}"
    )


def abstention_for(result: SpecialistResult) -> Abstention:
    """The enforced abstention for one empty-but-ok specialist result."""
    return Abstention(
        sub_question_id=result.task.sub_question_id,
        source=result.task.source,
        statement=abstention_statement(
            result.task.source, result.task.text, result.query
        ),
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
            desc = part.get("description", "(unspecified)")
            reason = part.get("reason", "no reason recorded")
            notes.append(f"Unsupported by the available sources: {desc} ({reason})")
        for skip in evidence.skipped:
            notes.append(
                f"Skipped {skip.get('source', '?')}: {skip.get('reason', 'unknown')}"
            )

        return SynthesizedAnswer(
            request=evidence.request,
            headline=_headline(evidence, claims, abstentions),
            claims=claims,
            abstentions=abstentions,
            notes=notes,
            composer=self.name,
        )


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
