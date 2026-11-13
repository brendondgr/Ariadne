"""Anchor candidates and entity facts, shared by T2 and T3.

Candidates for a question:

1. **Pinned** — identifiers written in the text, in any MITRE scheme, kept only
   if the id exists in a store (an invented ``T9999`` pins nothing);
2. otherwise the BM25 name index's top ``k`` per dataset
   (``utils.specialists.schema.namesearch``), merged and sorted by score.

The shipped ``extract_attack_ids`` reads technique ids only (it does not see
``G0016``), so this module has its own pattern covering every ATT&CK and CAPEC
id kind the stores carry.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from utils.specialists.schema.namesearch import descriptions_for, index_for

DATASETS = ("attack", "capec")

_ID_RE = re.compile(
    r"\b(?:T\d{4}(?:\.\d{3})?|TA\d{4}|G\d{4}|S\d{4}|M\d{4}|C\d{4}|DS\d{4}|DC\d{4}|DET\d{4}|AN\d{4}|CAPEC-\d+)\b"
)


@dataclass(frozen=True)
class Entity:
    entity_id: str
    dataset: str
    label: str
    name: str
    description: str


@lru_cache(maxsize=None)
def _entities(dataset: str) -> dict[str, Entity]:
    docs = index_for(dataset)._docs  # (entity_id, label, name, tokens)
    desc = descriptions_for(dataset)
    return {d[0]: Entity(d[0], dataset, d[1], d[2], desc.get(d[0], "") or "") for d in docs}


def entity(entity_id: str) -> Entity | None:
    for ds in DATASETS:
        e = _entities(ds).get(entity_id)
        if e is not None:
            return e
    return None


def entities(dataset: str) -> dict[str, Entity]:
    return _entities(dataset)


def pinned_ids(text: str) -> list[str]:
    seen: list[str] = []
    for m in _ID_RE.findall(text or ""):
        if m not in seen and entity(m) is not None:
            seen.append(m)
    return seen


def anchor_candidates(text: str, k: int = 5) -> list[dict]:
    """``[{entity_id, dataset, label, name, score, pinned}]``, best first."""
    pins = pinned_ids(text)
    if pins:
        out = []
        for i in pins:
            e = entity(i)
            out.append({"entity_id": i, "dataset": e.dataset, "label": e.label, "name": e.name,
                        "score": None, "pinned": True})
        return out
    hits = []
    for ds in DATASETS:
        for c in index_for(ds).search(text, top_k=k):
            hits.append({"entity_id": c.entity_id, "dataset": ds, "label": c.label, "name": c.name,
                         "score": c.score, "pinned": False})
    hits.sort(key=lambda h: (-h["score"], h["entity_id"]))
    return hits  # up to k per dataset, as the protocol states
