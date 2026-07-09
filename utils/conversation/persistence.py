#!/usr/bin/env python3
"""Domain helpers for persisting and rehydrating conversation turns.

These are pure functions the API service composes when it records a turn and
when it rebuilds a thread's memory for the next turn. They own two concerns:

* extracting the verified facts a turn established (so a later memory-grounded
  quick answer may reuse them), and
* reconstructing the chat-history list fed back into ``iter_conversation``.

Persistence itself (writing to :class:`ConversationStore`) stays in the API
service, which already serializes the SSE events it stores.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from utils.conversation.store import TurnRecord
from utils.synthesis.contracts import SynthesizedAnswer

# ---------------------------------------------------------------------------
# Entity dossier: a single entity's description + a compact typed adjacency,
# held handy so a follow-up can be answered without re-querying the graph.
# ---------------------------------------------------------------------------

# How much of a description to keep in memory (the full text stays re-queryable).
_DOSSIER_DESC_CHARS = 240
# How many adjacency lines to spell out in a detail block before "+N more".
_DOSSIER_ADJ_LINES = 15

# Entity-id shapes for detecting which held entity a later turn refers to.
_ENTITY_ID_RE = re.compile(
    r"\b(?:T\d{4}(?:\.\d{3})?|TA\d{4}|M\d{4}|G\d{4}|S\d{4}|DET\d{4}|DC\d{4}|C\d{4}|CAPEC[-\s]?\d+|CWE[-\s]?\d+)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class DossierEdge:
    """One typed, directional neighbor of an entity."""

    title: str  # humanized relationship, e.g. "Mitigates"
    rel_type: str  # raw type, e.g. "MITIGATES"
    direction: str  # "out" | "in"
    node_name: str
    node_id: str


@dataclass(frozen=True)
class EntityDossier:
    """An entity's held memory: id, name, a description summary, capped adjacency."""

    id: str
    name: str
    description: str
    edges: tuple[DossierEdge, ...]
    neighbor_total: int


def _truncate(text: str, limit: int) -> str:
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",.;:") + "…"


def _humanize_rel(rel_type: str) -> str:
    """MITIGATES -> 'Mitigates'; HAS_SUBTECHNIQUE -> 'Has Subtechnique'."""
    return (rel_type or "").replace("_", " ").strip().title() or "Related"


def entity_ids_in(text: str) -> set[str]:
    """Every ATT&CK/CAPEC/CWE entity id mentioned in ``text`` (normalized upper)."""
    out: set[str] = set()
    for m in _ENTITY_ID_RE.finditer(text or ""):
        token = m.group(0).upper()
        token = re.sub(r"(CAPEC|CWE)\s+", r"\1-", token)  # normalize "CAPEC 98" -> "CAPEC-98"
        out.add(token)
    return out


def dossiers_from_records(records: list[Any]) -> dict[str, EntityDossier]:
    """Build entity dossiers from the dossier-shaped evidence records, keyed by id.

    Only records the dossier normalizer produced participate — identified by the
    ``neighbor_total`` marker in ``properties`` — so ordinary evidence rows are
    never mistaken for held entities.
    """
    dossiers: dict[str, EntityDossier] = {}
    for rec in records or []:
        props = getattr(rec, "properties", None) or {}
        if "neighbor_total" not in props:
            continue
        entity_id = str(getattr(rec, "primary_id", "") or "").strip()
        if not entity_id:
            continue
        edges: list[DossierEdge] = []
        for r in getattr(rec, "related", None) or []:
            node_id = str(r.get("id") or "").strip()
            node_name = str(r.get("name") or "").strip()
            if not node_id and not node_name:
                continue
            rel_type = str(r.get("type") or "").strip()
            edges.append(
                DossierEdge(
                    title=_humanize_rel(rel_type),
                    rel_type=rel_type,
                    direction="in" if r.get("direction") == "in" else "out",
                    node_name=node_name,
                    node_id=node_id,
                )
            )
        try:
            total = int(props.get("neighbor_total"))
        except (TypeError, ValueError):
            total = len(edges)
        dossiers[entity_id] = EntityDossier(
            id=entity_id,
            name=str(getattr(rec, "name", "") or "").strip(),
            description=_truncate(props.get("description", ""), _DOSSIER_DESC_CHARS),
            edges=tuple(edges),
            neighbor_total=total,
        )
    return dossiers


def dossier_payload(dossiers: dict[str, EntityDossier]) -> dict[str, dict[str, Any]]:
    """Serialize dossiers for the assistant turn payload (keyed by entity id)."""
    return {eid: asdict(d) for eid, d in dossiers.items()}


def _dossier_from_payload(data: dict[str, Any]) -> EntityDossier:
    edges = tuple(
        DossierEdge(
            title=str(e.get("title", "")),
            rel_type=str(e.get("rel_type", "")),
            direction="in" if e.get("direction") == "in" else "out",
            node_name=str(e.get("node_name", "")),
            node_id=str(e.get("node_id", "")),
        )
        for e in data.get("edges", []) or []
    )
    try:
        total = int(data.get("neighbor_total", len(edges)))
    except (TypeError, ValueError):
        total = len(edges)
    return EntityDossier(
        id=str(data.get("id", "")),
        name=str(data.get("name", "")),
        description=str(data.get("description", "")),
        edges=edges,
        neighbor_total=total,
    )


def dossiers_from_turns(turns: list[TurnRecord]) -> dict[str, EntityDossier]:
    """Rebuild the per-conversation dossier cache from stored turns (latest wins)."""
    cache: dict[str, EntityDossier] = {}
    for turn in turns:
        if turn.role != "assistant":
            continue
        stored = (turn.payload or {}).get("entity_dossiers") or {}
        for eid, data in stored.items():
            if isinstance(data, dict):
                cache[str(eid)] = _dossier_from_payload(data)
    return cache


def _recent_dossier_ids(turns: list[TurnRecord]) -> list[str]:
    """Entity ids hydrated by the most recent turn that held any (recency anchor)."""
    for turn in reversed(turns):
        if turn.role != "assistant":
            continue
        stored = (turn.payload or {}).get("entity_dossiers") or {}
        if stored:
            return [str(eid) for eid in stored]
    return []


def memory_injection(
    question: str, turns: list[TurnRecord], *, max_blocks: int = 3
) -> list[str]:
    """Assemble the hybrid memory facts for the next turn.

    Returns an always-on index line naming every held entity, plus the full
    detail block for the entities relevant to *this* turn — those named by id in
    the question, plus the most-recently hydrated entity (so a pronoun follow-up
    like "what does it mitigate?" still resolves). Everything else stays handy but
    unspent, keeping per-turn context lean.
    """
    cache = dossiers_from_turns(turns)
    if not cache:
        return []
    facts: list[str] = []
    index = dossier_index_line(cache)
    if index:
        facts.append(index)

    referenced = [eid for eid in entity_ids_in(question) if eid in cache]
    chosen: list[str] = list(referenced)
    for eid in _recent_dossier_ids(turns):
        if eid not in chosen:
            chosen.append(eid)
    for eid in chosen[:max_blocks]:
        facts.append(dossier_detail_block(cache[eid]))
    return facts


def dossier_index_line(dossiers: dict[str, EntityDossier]) -> str:
    """The tiny always-on index: which entities are held in memory."""
    if not dossiers:
        return ""
    parts = [f"{d.id} ({d.name})" if d.name else d.id for d in dossiers.values()]
    return "Entities held in memory: " + ", ".join(parts) + "."


def dossier_detail_block(dossier: EntityDossier) -> str:
    """The full on-demand block: entity line + the requested adjacency format.

        M1049 (Antivirus/Antimalware): <description summary>
        adjacent:
        * Mitigates (MITIGATES) -> Phishing (T1566)
        * ...
        * (+8 more)
    """
    head = f"{dossier.id} ({dossier.name})" if dossier.name else dossier.id
    if dossier.description:
        head += f": {dossier.description}"
    lines = [head]
    if dossier.edges:
        lines.append("adjacent:")
        for edge in dossier.edges[:_DOSSIER_ADJ_LINES]:
            arrow = "->" if edge.direction == "out" else "<-"
            node = f"{edge.node_name} ({edge.node_id})" if edge.node_name else edge.node_id
            lines.append(f"* {edge.title} ({edge.rel_type}) {arrow} {node}")
        remaining = dossier.neighbor_total - min(len(dossier.edges), _DOSSIER_ADJ_LINES)
        if remaining > 0:
            lines.append(f"* (+{remaining} more)")
    return "\n".join(lines)


def facts_from_synthesized(answer: SynthesizedAnswer | None) -> list[str]:
    """Return the verified (supported) claim texts a turn established.

    Only rendered (verified-and-supported) claims count — an unverified draft
    contributes no facts, matching the project's provenance guarantee. These
    become the assistant turn's ``facts`` so a future quick answer can reuse
    them without a fresh graph query.
    """
    if answer is None:
        return []
    facts: list[str] = []
    for claim in answer.rendered_claims():
        text = str(claim.text).strip()
        if text and text not in facts:
            facts.append(text)
    return facts


def history_from_turns(
    turns: list[TurnRecord], *, limit: int | None = None
) -> list[dict[str, Any]]:
    """Rebuild the chat-history list (memory) fed into the next turn.

    * user turns  -> ``{"role": "user", "content": <question>}``
    * assistant turns -> ``{"role": "assistant", "content": <final answer>,
      "facts": [<verified facts>]}``

    ``limit`` bounds the number of *most recent* turns kept.
    """
    selected = turns if limit is None or limit <= 0 else turns[-limit:]
    history: list[dict[str, Any]] = []
    for turn in selected:
        if turn.role == "user":
            content = turn.question or ""
            if content:
                history.append({"role": "user", "content": content})
        elif turn.role == "assistant":
            payload = turn.payload or {}
            content = str(payload.get("final_answer", "") or "")
            entry: dict[str, Any] = {"role": "assistant", "content": content}
            facts = [str(f) for f in (payload.get("facts") or []) if str(f).strip()]
            if facts:
                entry["facts"] = facts
            history.append(entry)
    return history
