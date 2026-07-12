#!/usr/bin/env python3
"""Cross-source contradiction detection — the consistency axis of trust.

The verifier's other checks prove a claim is *grounded* (it cites a real
retrieved record). Reconciliation proves the retrieved records are *consistent
with each other*: when two sources both carry a canonical join value yet assert
incompatible facts about it, both records pass groundedness, so nothing else
catches the disagreement.

Always deterministic — the reconciler, like the rest of the verifier, does not
trust the model it audits. It walks the same evidence the federation already
indexed and compares a **conservative allow-list** of fields, so false
positives stay near zero:

- **name** — two sources give a materially different canonical name for the
  same id (case/whitespace/punctuation-normalized so cosmetic differences do
  not fire).
- **status** — the *authoritative* source (ATT&CK for technique ids, CAPEC for
  attack-pattern ids) marks the entity deprecated/revoked while another source
  still maps to it as current — a stale cross-source reference.

For *this* federation the mapping bridge (CAPEC ``MAPS_TO`` ATT&CK) is
single-sourced — only CAPEC asserts it — so a symmetric *mapping* contradiction
cannot arise and is deliberately out of scope. ``name`` and ``status`` are the
two contradiction classes the two graphs can actually produce.
"""

from __future__ import annotations

import re

from utils.specialists.contracts import EvidenceRecord
from utils.specialists.federation import FederatedEvidence

from .contracts import Conflict
from .grounding import normalize_id

_TECHNIQUE_RE = re.compile(r"^t\d{4}(?:\.\d{3})?$", re.IGNORECASE)
_CAPEC_RE = re.compile(r"^capec-\d+$", re.IGNORECASE)

# Property keys, across both backends, that flag an entity as retired.
_DEPRECATION_KEYS = ("x_mitre_deprecated", "deprecated", "revoked")
_RETIRED_STATUS = {"deprecated", "revoked", "obsolete", "retired"}
_TRUTHY = {"true", "1", "yes"}

_PUNCT_RE = re.compile(r"[^\w\s]")
_WS_RE = re.compile(r"\s+")


def _authoritative_source(join_value: str) -> str | None:
    """The source that canonically owns an id's scheme, or None."""
    value = normalize_id(join_value)
    if _TECHNIQUE_RE.match(value):
        return "attack"
    if _CAPEC_RE.match(value):
        return "capec"
    return None


def _norm_name(name: str) -> str:
    """Fold case, strip punctuation, collapse whitespace — so only a *material*
    name difference counts, not 'Process Injection' vs 'process injection'."""
    folded = _PUNCT_RE.sub(" ", (name or "").casefold())
    return _WS_RE.sub(" ", folded).strip()


def _is_retired(record: EvidenceRecord) -> bool:
    props = record.properties or {}
    for key in _DEPRECATION_KEYS:
        val = props.get(key)
        if val is True:
            return True
        if isinstance(val, str) and val.strip().lower() in _TRUTHY:
            return True
    return str(props.get("status", "")).strip().lower() in _RETIRED_STATUS


def _related_id(entry: dict) -> str:
    for key in ("id", "entry_id"):
        raw = entry.get(key)
        if raw:
            return normalize_id(str(raw))
    return ""


def detect_conflicts(evidence: FederatedEvidence) -> list[Conflict]:
    """Deterministic cross-source contradiction pass over the evidence.

    Returns conflicts sorted by (kind, join_value) for stable output.
    """
    # Per normalized join value: the name each source asserts for it, the
    # entity record each source owns for it, and which sources merely
    # reference it (map to it without owning it).
    names: dict[str, dict[str, str]] = {}
    entity_records: dict[str, dict[str, EvidenceRecord]] = {}
    referencers: dict[str, set[str]] = {}

    for result in evidence.results:
        src = result.task.source
        for rec in result.records:
            pid = normalize_id(rec.primary_id)
            if pid:
                entity_records.setdefault(pid, {}).setdefault(src, rec)
                if rec.name:
                    names.setdefault(pid, {}).setdefault(src, rec.name)

            referenced: set[str] = set()
            for jv in rec.join_values:
                nv = normalize_id(jv)
                if nv and nv != pid:
                    referenced.add(nv)
            for entry in rec.related:
                eid = _related_id(entry)
                if not eid:
                    continue
                if eid != pid:
                    referenced.add(eid)
                ename = str(entry.get("name", "")).strip()
                if ename:
                    names.setdefault(eid, {}).setdefault(src, ename)
            for nv in referenced:
                referencers.setdefault(nv, set()).add(src)

    conflicts: list[Conflict] = []

    # -- name disagreement --------------------------------------------------
    for value, by_source in names.items():
        if len(by_source) < 2:
            continue
        distinct = {_norm_name(n) for n in by_source.values() if _norm_name(n)}
        if len(distinct) < 2:
            continue
        srcs = sorted(by_source)
        conflicts.append(
            Conflict(
                join_value=value,
                kind="name",
                sources=tuple(srcs),
                values={s: by_source[s] for s in srcs},
                authoritative_source=_authoritative_source(value),
                detail=f"sources disagree on the name of {value}",
            )
        )

    # -- deprecated-yet-referenced -----------------------------------------
    for value, by_source in entity_records.items():
        auth = _authoritative_source(value)
        if auth is None or auth not in by_source:
            continue
        if not _is_retired(by_source[auth]):
            continue
        others = sorted(referencers.get(value, set()) - {auth})
        if not others:
            continue
        values = {auth: "deprecated/revoked"}
        for other in others:
            values[other] = "referenced as current"
        conflicts.append(
            Conflict(
                join_value=value,
                kind="status",
                sources=tuple([auth, *others]),
                values=values,
                authoritative_source=auth,
                detail=(
                    f"{auth} marks {value} deprecated/revoked, but "
                    f"{', '.join(others)} still maps to it as current"
                ),
            )
        )

    conflicts.sort(key=lambda c: (c.kind, c.join_value))
    return conflicts


def conflicted_values(conflicts: list[Conflict]) -> set[str]:
    """The normalized join values any conflict touches — used to flag the
    claims that assert them as contested."""
    return {normalize_id(c.join_value) for c in conflicts}
