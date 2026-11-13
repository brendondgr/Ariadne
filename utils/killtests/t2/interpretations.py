"""Interpretations: (anchor, facet) pairs a question could mean.

Facets come from the schema registry's plausible facets for the anchor's label
(``SourceCardView.label_facets``), plus ``describe``. Two ways of choosing which
to keep:

- **raw** (no model): a facet is kept when the question lexically supports it —
  a token of its relationship or neighbour label appears in the question —
  plus ``describe``; with no supported facet, every facet is kept.
- **filtered**: the decider's anchor and facet probabilities, each pruned at
  the floor (``KILLTESTS_T2_FILTER_FLOOR``, default 0.05).
"""

from __future__ import annotations

import json
import re
from functools import lru_cache

from utils.planner.cards import SourceCardView
from utils.specialists.schema import get_registry

from ..config import REPO
from ..graph import DESCRIBE, facet_key, parse_facet

_STOP = {"has", "of", "in", "to", "can", "is", "by", "also", "be", "the", "a", "an", "and", "or"}
_WORD = re.compile(r"[a-z0-9]+")


def _split(name: str) -> list[str]:
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", name or "").replace("_", " ")
    return [w for w in _WORD.findall(spaced.lower()) if w not in _STOP]


def _stem(w: str) -> str:
    return w[:5] if len(w) >= 5 else w


@lru_cache(maxsize=None)
def facets_for(dataset: str, label: str) -> tuple[str, ...]:
    reg = get_registry()
    keys = [facet_key(f.rel_type, f.direction, f.neighbour_label) for f in reg.label_facets(label, dataset=dataset)]
    return (DESCRIBE, *keys)


def lexically_supported(question: str, facet: str) -> bool:
    if facet == DESCRIBE:
        return False
    rel, _direction, target = parse_facet(facet)
    q = {_stem(w) for w in _WORD.findall(question.lower())}
    toks = {_stem(w) for w in _split(rel) + _split(target)}
    return bool(q & toks)


def raw_facets(question: str, dataset: str, label: str) -> list[str]:
    all_f = facets_for(dataset, label)
    sup = [f for f in all_f if lexically_supported(question, f)]
    return [DESCRIBE, *sup] if sup else list(all_f)


@lru_cache(maxsize=None)
def _glosses(dataset: str) -> dict[str, str]:
    with open(REPO / "data" / "source_cards" / f"{dataset}.json") as fh:
        view = SourceCardView.from_card_dict(json.load(fh))
    rels = (view.entity_descriptions or {}).get("relationships") or {}
    return {str(k): str(v) for k, v in rels.items()}


def facet_description(dataset: str, label: str, facet: str) -> str:
    if facet == DESCRIBE:
        return (f"the {label}'s own details: its description, properties, dates, aliases or "
                f"credits; not a list of related entities")
    rel, direction, target = parse_facet(facet)
    gloss = _glosses(dataset).get(rel, "")
    words = " ".join(_split(rel)) or rel
    if direction == "out":
        core = f"the {target} entities this {label} points to by '{rel}' ({words})"
    else:
        core = f"the {target} entities that point to this {label} by '{rel}' ({words})"
    return f"{core}. Schema note: {gloss}" if gloss else core


def entity_option(c: dict, description: str) -> str:
    desc = " ".join((description or "").split())[:240]
    return f"{c['name']} ({c['label']} {c['entity_id']}, {c['dataset']}): {desc}".strip()
