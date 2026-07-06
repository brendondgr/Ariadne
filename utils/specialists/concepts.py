#!/usr/bin/env python3
"""Committed concept vocabulary shared by the pipeline and the gold derivation.

Some analyst questions name a *concept* ("credential theft") rather than
concrete graph entities or ids. A deterministic pipeline can only scope a
query by what the question says, so each concept gets a small, reviewable
anchor-term list here. The Gremlin builder uses the terms to scope a name
filter; ``evalset.federated_gold`` selects the expected pattern set with the
*same* terms — one source of truth, so the pipeline and its gold cannot drift.

Adding a concept is a deliberate, reviewed edit — never something a model
fabricates at runtime.
"""

from __future__ import annotations

# concept phrase (matched case-insensitively in the sub-question text)
#   -> anchor terms (matched case-insensitively against entity names)
CONCEPT_ANCHORS: dict[str, tuple[str, ...]] = {
    "credential theft": ("credential", "password", "authentication"),
}


def concept_terms(text: str) -> tuple[str, ...]:
    """Anchor terms for every concept phrase mentioned in ``text`` (deduped)."""
    lowered = (text or "").lower()
    out: dict[str, None] = {}
    for phrase, terms in CONCEPT_ANCHORS.items():
        if phrase in lowered:
            for term in terms:
                out.setdefault(term, None)
    return tuple(out)
