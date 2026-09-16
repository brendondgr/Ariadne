#!/usr/bin/env python3
"""The answer says which entity it resolved a described question to (EXP-2026-09-028).

When the planner's closed-choice rung picked the anchor — the question named
no identifier and no complete name, and the model chose from a reranked list —
the analyst has to be able to see that, because a third of such picks were
wrong when D-034 let them through silently. So the first line of the answer
names the resolution, and the claim table carries it as a checkable claim
grounded in the anchor's own record.

Pure function over the synthesized answer and the plan's rewrite block; it
adds one claim and one sentence and changes nothing else.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from .contracts import SynthesizedAnswer


def disclosure_text(block: dict[str, Any]) -> str:
    ident = str(block.get("id") or "").strip()
    name = str(block.get("name") or "").strip()
    label = str(block.get("label") or "").strip()
    who = f"{ident} ({name})" if name else ident
    kind = f" {label}" if label else ""
    return f"Resolved your description to the{kind} {who}; the answer below is about that entity."


def apply_disclosure(answer: SynthesizedAnswer, rewrite: dict[str, Any] | None) -> SynthesizedAnswer:
    """Prefix the headline with the resolution line when ``rewrite`` carries a disclosed anchor.

    The headline only: the claim table is aligned with the verifier's verdicts
    and rendered from them, so a sentence added after verification belongs on
    the prose surface, not among the checked claims.
    """
    block = (rewrite or {}).get("disclosed_anchor") if isinstance(rewrite, dict) else None
    if not block or not block.get("id"):
        return answer
    text = disclosure_text(block)
    headline = str(getattr(answer, "headline", "") or "")
    return replace(answer, headline=f"{text} {headline}".strip())
