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

from typing import Any

from utils.conversation.store import TurnRecord
from utils.synthesis.contracts import SynthesizedAnswer


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
