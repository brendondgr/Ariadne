#!/usr/bin/env python3
"""Contracts for the synthesis layer: claims, citations, verdicts, abstentions.

The composer (deterministic or LLM) never emits free prose — it emits
``Claim`` objects whose ``citations`` point at concrete retrieved records and
whose ``entity_ids`` name the identifiers the sentence asserts. That structure
is what makes verification *mechanical*: the verifier resolves every citation
against the actual ``EvidenceRecord``s and checks every named identifier
appears in the cited records, without having to parse prose.

Everything here is a pure JSON-serialisable dataclass, matching the style of
``utils.specialists.contracts`` (the schema synthesis reads from).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Citation:
    """One pointer from a claim to a concrete retrieved evidence record."""

    source: str          # registry dataset key, e.g. "attack"
    primary_id: str      # the record's join-relevant identifier, e.g. "T1047"
    record_id: str = ""  # backend node/edge id from provenance (optional)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "primary_id": self.primary_id,
            "record_id": self.record_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Citation":
        return cls(
            source=str(data.get("source", "")),
            primary_id=str(data.get("primary_id", "")),
            record_id=str(data.get("record_id", "") or ""),
        )


@dataclass(frozen=True)
class Claim:
    """One checkable sentence of the answer.

    ``kind`` is ``"fact"`` for single-source statements and ``"correlation"``
    for cross-source statements (which must additionally be backed by the
    federation's join index). ``entity_ids`` are the identifiers the sentence
    asserts; every one must be grounded in the cited records or the claim is
    cut.
    """

    text: str
    citations: tuple[Citation, ...] = ()
    entity_ids: tuple[str, ...] = ()
    kind: str = "fact"           # "fact" | "correlation"
    sub_question_id: str = ""    # originating sub-question, when known

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "citations": [c.to_dict() for c in self.citations],
            "entity_ids": list(self.entity_ids),
            "kind": self.kind,
            "sub_question_id": self.sub_question_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Claim":
        return cls(
            text=str(data.get("text", "")),
            citations=tuple(
                Citation.from_dict(c) for c in data.get("citations", []) or []
            ),
            entity_ids=tuple(str(e) for e in data.get("entity_ids", []) or []),
            kind=str(data.get("kind", "fact") or "fact"),
            sub_question_id=str(data.get("sub_question_id", "") or ""),
        )


@dataclass(frozen=True)
class SynthesisEdge:
    """One provenance-exact relationship between two cited entities.

    Derived mechanically during the verification pass and pruned against the
    supported claims — so the per-answer network plot draws only topology the
    verifier stands behind, with no frontend cross-product guessing. ``rel``
    names the relationship: ``mapsTo`` (CAPEC pattern → ATT&CK technique, from
    the cross-source join index, both endpoints supported) or ``mitigatedBy``
    (ATT&CK technique → mitigation, from the technique record's ``related``
    ``MITIGATES`` entries; the technique endpoint must be supported).
    """

    source_id: str       # e.g. "CAPEC-555"
    target_id: str       # e.g. "T1021"
    rel: str = "mapsTo"  # "mapsTo" | "mitigatedBy"

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "rel": self.rel,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SynthesisEdge":
        return cls(
            source_id=str(data.get("source_id", "")),
            target_id=str(data.get("target_id", "")),
            rel=str(data.get("rel", "mapsTo") or "mapsTo"),
        )


@dataclass(frozen=True)
class Abstention:
    """An honest "the sources don't establish this", with the query as proof.

    Emitted when a specialist ran cleanly (``ok=True``) and returned zero
    records: the correct answer is the absence itself, demonstrated by the
    exact query that was executed — never a plausible-sounding invention.
    """

    sub_question_id: str
    source: str
    statement: str
    query: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "sub_question_id": self.sub_question_id,
            "source": self.source,
            "statement": self.statement,
            "query": self.query,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Abstention":
        return cls(
            sub_question_id=str(data.get("sub_question_id", "")),
            source=str(data.get("source", "")),
            statement=str(data.get("statement", "")),
            query=str(data.get("query", "")),
        )


@dataclass(frozen=True)
class Conflict:
    """A cross-source contradiction: two sources that both carry a canonical
    join value yet assert *incompatible* facts about it.

    Unlike a groundedness failure, both underlying records are genuinely
    retrieved — so a conflict never *cuts* a claim; it flags the affected
    claims **contested** and surfaces both asserted values with provenance.
    ``kind`` is one of:

    - ``"name"`` — the sources give a materially different canonical name for
      the same id (e.g. ATT&CK's technique name vs. the name CAPEC embeds in
      its mapping).
    - ``"status"`` — the authoritative source marks the entity
      deprecated/revoked while another source still maps to it as current
      (a stale cross-source reference).

    ``values`` maps each involved source to the value it asserts.
    ``authoritative_source`` names the source that owns the id's scheme
    (ATT&CK for technique ids, CAPEC for attack-pattern ids), or ``None`` when
    neither is canonically authoritative — surfaced, never used to silently
    pick a winner.
    """

    join_value: str
    kind: str                                 # "name" | "status"
    sources: tuple[str, ...] = ()
    values: dict[str, str] = field(default_factory=dict)
    authoritative_source: str | None = None
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "join_value": self.join_value,
            "kind": self.kind,
            "sources": list(self.sources),
            "values": dict(self.values),
            "authoritative_source": self.authoritative_source,
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Conflict":
        return cls(
            join_value=str(data.get("join_value", "")),
            kind=str(data.get("kind", "") or ""),
            sources=tuple(str(s) for s in data.get("sources", []) or []),
            values={str(k): str(v) for k, v in (data.get("values", {}) or {}).items()},
            authoritative_source=data.get("authoritative_source") or None,
            detail=str(data.get("detail", "") or ""),
        )


@dataclass(frozen=True)
class ClaimVerdict:
    """The verifier's ruling on one claim.

    ``contested`` names the conflicted join values this (still-supported) claim
    touches — the "flag, don't cut" surface: the claim is real and rendered,
    but the analyst is told a source disagrees about one of its identifiers.
    """

    verdict: str                              # "supported" | "unsupported"
    reasons: list[str] = field(default_factory=list)
    contested: tuple[str, ...] = ()

    @property
    def supported(self) -> bool:
        return self.verdict == "supported"

    @property
    def is_contested(self) -> bool:
        return bool(self.contested)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"verdict": self.verdict, "reasons": list(self.reasons)}
        if self.contested:
            out["contested"] = list(self.contested)
        return out


@dataclass
class VerificationReport:
    """Per-claim verdicts plus the roll-up metrics goals.md asks for."""

    verdicts: list[ClaimVerdict] = field(default_factory=list)
    # Abstentions the verifier had to add because the composer omitted them
    # (the deterministic guard the LLM path cannot skip past).
    repaired_abstentions: int = 0
    # Cross-source contradictions the reconciliation pass detected. Empty on a
    # single-source or fully-consistent answer (omitted from ``to_dict`` then,
    # so pre-reconciliation payloads stay byte-identical).
    conflicts: list["Conflict"] = field(default_factory=list)

    @property
    def supported_count(self) -> int:
        return sum(1 for v in self.verdicts if v.supported)

    @property
    def unsupported_count(self) -> int:
        return len(self.verdicts) - self.supported_count

    @property
    def unsupported_claim_rate(self) -> float:
        return self.unsupported_count / len(self.verdicts) if self.verdicts else 0.0

    @property
    def conflict_count(self) -> int:
        return len(self.conflicts)

    @property
    def contested_count(self) -> int:
        return sum(1 for v in self.verdicts if v.is_contested)

    @property
    def ok(self) -> bool:
        return self.unsupported_count == 0

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "verdicts": [v.to_dict() for v in self.verdicts],
            "claim_count": len(self.verdicts),
            "supported_count": self.supported_count,
            "unsupported_count": self.unsupported_count,
            "unsupported_claim_rate": self.unsupported_claim_rate,
            "repaired_abstentions": self.repaired_abstentions,
            "ok": self.ok,
        }
        if self.conflicts:
            out["conflicts"] = [c.to_dict() for c in self.conflicts]
            out["conflict_count"] = self.conflict_count
        return out


@dataclass
class SynthesizedAnswer:
    """The synthesis agent's output: claims, abstentions, and (after the
    verification pass) the per-claim verdicts.

    ``verification`` is ``None`` for an unverified draft; the API seam and the
    golden suites only ever render verified answers. ``rendered_claims`` is the
    prose surface: verified-supported claims only — unsupported claims stay in
    ``claims``/``verification`` as flagged, auditable, but never shown as fact.
    """

    request: str
    headline: str = ""
    # A direct, natural-language answer to the analyst's question, grounded in
    # the gathered evidence — the LLM composer writes it; the deterministic
    # composer assembles it from the claim sentences. The verified claim table
    # remains the trust surface; this is the readable answer above it.
    narrative: str = ""
    claims: list[Claim] = field(default_factory=list)
    abstentions: list[Abstention] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    composer: str = "deterministic"      # "deterministic" | "llm"
    fallback_reason: str | None = None   # set when the LLM path fell back
    verification: VerificationReport | None = None
    # Provenance-exact relationships for the per-answer network plot, derived
    # and pruned during verification. Empty on an unverified draft.
    edges: list[SynthesisEdge] = field(default_factory=list)

    def rendered_claims(self) -> list[Claim]:
        """Claims safe to show as fact: verified and supported.

        An unverified draft renders no claims at all — the answer must prove
        itself before it speaks.
        """
        if self.verification is None:
            return []
        return [
            claim
            for claim, verdict in zip(self.claims, self.verification.verdicts)
            if verdict.supported
        ]

    def flagged_claims(self) -> list[tuple[Claim, ClaimVerdict]]:
        """Claims the verifier cut, paired with the reasons — the audit trail."""
        if self.verification is None:
            return []
        return [
            (claim, verdict)
            for claim, verdict in zip(self.claims, self.verification.verdicts)
            if not verdict.supported
        ]

    def to_dict(self) -> dict[str, Any]:
        verdicts = self.verification.verdicts if self.verification else []
        claims = []
        rendered = []
        for i, claim in enumerate(self.claims):
            entry = claim.to_dict()
            verdict = verdicts[i] if i < len(verdicts) else None
            entry["verdict"] = verdict.to_dict() if verdict else None
            claims.append(entry)
            # Rendered (supported) claims carry the contested flag so the UI can
            # badge them without cross-referencing the full verdict list. Omitted
            # when not contested, so a conflict-free payload stays byte-identical.
            if verdict is not None and verdict.supported:
                shown = claim.to_dict()
                if verdict.contested:
                    shown["contested"] = list(verdict.contested)
                rendered.append(shown)
        return {
            "request": self.request,
            "headline": self.headline,
            "narrative": self.narrative,
            "claims": claims,
            "rendered_claims": rendered,
            "abstentions": [a.to_dict() for a in self.abstentions],
            "notes": list(self.notes),
            "composer": self.composer,
            "fallback_reason": self.fallback_reason,
            "verification": self.verification.to_dict() if self.verification else None,
            "edges": [e.to_dict() for e in self.edges],
        }
