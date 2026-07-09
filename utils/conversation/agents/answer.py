#!/usr/bin/env python3
"""The final Answer agent.

Both paths converge here to produce the conversational reply the analyst reads:

* quick path — a memory-grounded answer that may use ONLY facts already
  established in the thread (or ask for clarification). No new graph facts.
* graph path — wraps the verified synthesis narrative in a conversation-aware
  reply, keeping the grounded synthesis card as the trust surface beneath it.

Deterministic fallbacks (LLM off or failing):

* graph path -> the synthesis narrative verbatim (identical to today's grounded
  answer — the LLM only adds conversational continuity, never facts).
* quick path -> a summary of the known facts, or an honest clarification prompt.
"""

from __future__ import annotations

from typing import Any

from utils.conversation.agents._common import (
    emit_event,
    known_facts,
    render_history_messages,
)
from utils.conversation.agents.router import ROUTE_QUICK
from utils.conversation.config import ConversationConfig
from utils.conversation.llm import ConversationLLM, LLMUnavailable
from utils.synthesis.contracts import SynthesizedAnswer

_QUICK_SYSTEM = (
    "You are a cybersecurity assistant continuing a conversation. Answer the "
    "user's latest message using ONLY facts already established earlier in this "
    "conversation (listed below) plus general conversational context. You must "
    "NOT introduce any new ATT&CK/CAPEC facts, technique names, mappings, or "
    "mitigations that are not in the established facts. If the answer requires "
    "information not present, say you'll need to look it up in the graphs and "
    "ask the user to confirm. Be concise and natural."
)

_GRAPH_SYSTEM = (
    "You are a cybersecurity assistant continuing a conversation. A grounded, "
    "verified answer to the user's question was produced from the knowledge "
    "graphs and is provided below as GROUNDED ANSWER, followed by GRAPH EVIDENCE "
    "DETAILS — the actual node/edge metadata retrieved from ATT&CK/CAPEC "
    "(names, descriptions, key attributes, and related entries). Write a natural, "
    "conversational reply that connects to what was discussed earlier and, when "
    "the user asks for more detail or context, draws on the EVIDENCE DETAILS "
    "(especially the descriptions) to be genuinely informative. If the primary "
    "entity's details have already been covered, offer a concrete next step by "
    "naming the specific related/mapped entities from the EVIDENCE DETAILS (e.g. "
    "the techniques it maps to) that you could look up next. Use ONLY the "
    "GROUNDED ANSWER and EVIDENCE DETAILS — do not add, drop, or alter any id, "
    "name, mapping, or mitigation, and do not invent anything beyond them."
)

# How much of each node description to include, and how many records to brief.
_MAX_DESC_CHARS = 600
_MAX_BRIEF_RECORDS = 10
# Total character budget for the whole evidence brief. Record-heavy turns (a
# query returning hundreds of nodes) are exactly where the brief would crowd the
# answer prompt out of the model's context window and force a truncation, so the
# brief is capped in aggregate — not just per-record — leaving headroom for the
# completion. At least the first record is always included.
_MAX_BRIEF_CHARS = 3000
# Short, human-meaningful attributes worth surfacing alongside a description.
_BRIEF_ATTRS = (
    "Abstraction",
    "Status",
    "tactic",
    "tactics",
    "platforms",
    "x_mitre_platforms",
    "detection",
)


def _grounded_text(answer: SynthesizedAnswer | None) -> str:
    if answer is None:
        return ""
    return (answer.narrative or answer.headline or "").strip()


def _truncate(text: str, limit: int) -> str:
    text = " ".join(str(text).split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",.;:") + "…"


# Appended to a reply the model cut off at its output limit, so the analyst sees
# an explicit, expected truncation instead of a sentence that just stops.
_TRUNCATION_NOTE = (
    "\n\n_(Response truncated at the model's output limit — increase "
    "`CONVERSATION_LLM_MAX_TOKENS` or the model's context window, or ask for "
    "fewer items at a time.)_"
)


def _mark_truncated(text: str) -> str:
    """Tidy a cut-off reply and append an explicit truncation note.

    Drops a trailing unbalanced ``(…`` — a hanging open paren after the last
    close paren is a truncated parenthetical/id (e.g. ``"(T1561."``) — then adds
    the note. Best-effort tidy only: the note is what makes the truncation
    unambiguous; the verified claim table below remains the trust surface.
    """
    text = text.rstrip()
    open_i, close_i = text.rfind("("), text.rfind(")")
    if open_i > close_i:
        text = text[:open_i].rstrip(" ,.;:—-")
    return text + _TRUNCATION_NOTE


def _llm_reply(
    client: ConversationLLM,
    messages: list[dict[str, str]],
    config: ConversationConfig,
) -> str | None:
    """The answer LLM's reply (truncation-marked if cut), or ``None`` to fall back.

    Returns ``None`` when the LLM is unavailable or produced no usable content —
    including a length stop that yielded nothing — so the caller keeps the
    deterministic answer. A truncated-but-non-empty reply is returned with an
    explicit note rather than as a bare mid-sentence chop.
    """
    try:
        result = client.complete_verbose(messages, max_tokens=config.llm.max_tokens)
    except LLMUnavailable:
        return None
    text = result.content.strip()
    if not text:
        return None
    return _mark_truncated(text) if result.truncated else text


def _unique_records(evidence: Any):
    """Yield each retrieved record once (deduped by primary id / name)."""
    seen: set[str] = set()
    for result in getattr(evidence, "results", []) or []:
        for rec in getattr(result, "records", []) or []:
            key = rec.primary_id or rec.name
            if key and key not in seen:
                seen.add(key)
                yield rec


def _record_brief_line(rec: Any) -> str:
    """One grounded detail line for a record: id/name/label + desc + attrs + links."""
    props = rec.properties or {}
    head = f"- {rec.primary_id or rec.name}"
    if rec.name and rec.name != rec.primary_id:
        head += f" ({rec.name})"
    if rec.label:
        head += f" [{rec.label}]"
    parts = [head]
    desc = str(props.get("description", "")).strip()
    if desc:
        parts.append(f": {_truncate(desc, _MAX_DESC_CHARS)}")
    attrs = [f"{k}: {_truncate(props[k], 80)}" for k in _BRIEF_ATTRS if props.get(k)]
    if attrs:
        parts.append(f" [{'; '.join(attrs)}]")
    related = [
        str(r.get("name") or r.get("id"))
        for r in (rec.related or [])
        if r.get("name") or r.get("id")
    ][:8]
    if related:
        parts.append(f" Related: {', '.join(related)}.")
    join_values = [str(v) for v in (rec.join_values or []) if str(v)][:8]
    if join_values:
        parts.append(f" Maps to: {', '.join(join_values)}.")
    return "".join(parts)


def evidence_brief(evidence: Any) -> str:
    """Distil the retrieved records into grounded detail lines for the answer LLM.

    Surfaces the node metadata the synthesis one-liner omits — descriptions, a
    few key attributes, and related entries — so a "tell me more" follow-up has
    real, provenance-backed material to draw on. Everything here came from the
    graph; the answer agent is told to use only it.

    Bounded twice: by record count (``_MAX_BRIEF_RECORDS``) and by total size
    (``_MAX_BRIEF_CHARS``), so a record-heavy turn can't inflate the answer
    prompt past the model's context window and force a truncation. The first
    record is always included; if anything is dropped, a trailing marker says so
    (so the LLM knows to offer the rest as a next step rather than imply it saw
    everything).
    """
    if evidence is None:
        return ""
    lines: list[str] = []
    total = 0
    omitted = False
    for rec in _unique_records(evidence):
        line = _record_brief_line(rec)
        if lines and (
            len(lines) >= _MAX_BRIEF_RECORDS or total + len(line) > _MAX_BRIEF_CHARS
        ):
            omitted = True
            break
        lines.append(line)
        total += len(line)
    if omitted:
        lines.append(
            "- …(more records retrieved but omitted here to keep the answer "
            "prompt within budget)"
        )
    return "\n".join(lines)


def compose_answer(
    state: dict[str, Any],
    config: ConversationConfig,
    client: ConversationLLM | None = None,
) -> tuple[str, str]:
    """Return ``(final_answer, composer)`` where composer is ``llm``/``deterministic``."""
    client = client or ConversationLLM(config.llm)
    route = state.get("route", "graph")
    question = state.get("question", "")
    history = state.get("history")
    facts = known_facts(history, config.history_turns)

    if route == ROUTE_QUICK:
        return _compose_quick(question, history, facts, config, client)
    return _compose_graph(
        question, history, state.get("answer"), state.get("evidence"), config, client
    )


def _compose_quick(question, history, facts, config, client) -> tuple[str, str]:
    if client.enabled:
        fact_block = (
            "Established facts:\n- " + "\n- ".join(facts)
            if facts
            else "No specific facts have been established yet."
        )
        messages = (
            [{"role": "system", "content": _QUICK_SYSTEM}]
            + render_history_messages(history, config.history_turns)
            + [{"role": "user", "content": f"{fact_block}\n\nMessage: {question}"}]
        )
        reply = _llm_reply(client, messages, config)
        if reply is not None:
            return reply, "llm"
    # Deterministic fallback.
    if facts:
        return "From what we've discussed:\n- " + "\n- ".join(facts), "deterministic"
    return (
        "Could you clarify what you'd like to know? I can look it up in the "
        "ATT&CK and CAPEC graphs.",
        "deterministic",
    )


def _compose_graph(
    question, history, answer, evidence, config, client
) -> tuple[str, str]:
    grounded = _grounded_text(answer)
    if not grounded:
        grounded = (
            "I couldn't find grounded evidence for that in the ATT&CK or CAPEC "
            "graphs."
        )
        return grounded, "deterministic"
    if client.enabled:
        brief = evidence_brief(evidence)
        user_content = f"Question: {question}\n\nGROUNDED ANSWER:\n{grounded}"
        if brief:
            user_content += (
                "\n\nGRAPH EVIDENCE DETAILS (retrieved node/edge metadata — use "
                "these for depth; do not go beyond them):\n" + brief
            )
        messages = (
            [{"role": "system", "content": _GRAPH_SYSTEM}]
            + render_history_messages(history, config.history_turns)
            + [{"role": "user", "content": user_content}]
        )
        reply = _llm_reply(client, messages, config)
        if reply is not None:
            return reply, "llm"
    # Deterministic fallback: the verified narrative verbatim.
    return grounded, "deterministic"


def make_answer_node(
    config: ConversationConfig, client: ConversationLLM | None = None
):
    """Build the LangGraph node that composes the final conversational reply."""

    def answer_node(state: dict[str, Any]) -> dict[str, Any]:
        final_answer, composer = compose_answer(state, config, client)
        answer = state.get("answer")
        final = {
            "final_answer": final_answer,
            "route": state.get("route", "graph"),
            "composer": composer,
            "grounded": bool(_grounded_text(answer)) or state.get("route") == ROUTE_QUICK,
        }
        emit_event(("final", final))
        return {
            "final_answer": final_answer,
            "final": final,
            "trace": [{"node": "answer", "composer": composer}],
        }

    return answer_node
