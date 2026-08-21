#!/usr/bin/env python3
"""A read-only index over the committed ATT&CK canonical artifacts.

The oracle needs to answer "what does the graph itself hold for this anchor?"
without going through a Neo4j round trip, a specialist, or a plan. Reading the
canonical JSONL directly is the point: it is the *upper bound* on what any
retriever over this data could return, so nothing in the retrieval path may sit
between it and the answer.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

ATTACK_CANONICAL = Path("data/graphs/attack/canonical")


@dataclass
class AttackIndex:
    """ATT&CK nodes and edges, keyed the way the benchmarks name things."""

    label_of: dict[str, str] = field(default_factory=dict)
    name_of: dict[str, str] = field(default_factory=dict)
    #: (public id, relationship type, direction) -> public ids on the other end.
    #: Direction is "out" from the anchor or "in" toward it.
    edges: dict[tuple[str, str, str], set[str]] = field(default_factory=lambda: defaultdict(set))

    def has(self, public_id: str) -> bool:
        return public_id in self.label_of

    def neighbours(self, anchor: str, rel: str, direction: str, labels: tuple[str, ...]) -> set[str]:
        """Public ids reachable from ``anchor`` over ``rel``, kept to ``labels``."""
        found = self.edges.get((anchor, rel, direction), set())
        return {n for n in found if self.label_of.get(n) in labels}


@lru_cache(maxsize=4)
def load_attack(canonical: str = str(ATTACK_CANONICAL)) -> AttackIndex:
    """Build the index once per path. Cached: the run reads it thousands of times."""
    root = Path(canonical)
    index = AttackIndex()
    raw_to_public: dict[str, str] = {}

    for line in (root / "nodes.jsonl").open(encoding="utf-8"):
        node = json.loads(line)
        public = (node.get("properties") or {}).get("attack_id")
        if not public:
            continue
        raw_to_public[node["id"]] = public
        index.label_of[public] = node["label"]
        index.name_of[public] = node.get("name") or ""

    for line in (root / "relationships.jsonl").open(encoding="utf-8"):
        edge = json.loads(line)
        source = raw_to_public.get(edge.get("source_id"))
        target = raw_to_public.get(edge.get("target_id"))
        if not source or not target:
            continue
        rel = edge["type"]
        index.edges[(source, rel, "out")].add(target)
        index.edges[(target, rel, "in")].add(source)

    return index
