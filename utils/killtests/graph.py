"""Exact execution of one interpretation through the shipped compilers.

An interpretation's record set is the sorted list of member ids of one facet of
one anchor — every member, never a page (``page_size`` is set past any degree in
either store, and the connector's row cap is lifted to match). ``describe`` is
the anchor itself.

Two shipped defects in ``GremlinQueryBuilder.expand`` are worked around here,
not fixed in the shipped code (the tree is frozen for these comparisons; see
EXP-2026-11-001 ISSUES.md):

1. it inlines the registry's relationship name (``ChildOf``) while the CAPEC
   store's edges carry the loader's label (``CHILD_OF``) — translated with
   ``gremlin_edge_label``;
2. it anchors with ``_capec_gremlin_id``, which assumes an attack pattern and
   misses views and categories — replaced with ``_capec_candidate_ids``.
"""

from __future__ import annotations

import threading
from typing import Any

from utils.graph_loader.stores.gremlin import gremlin_edge_label
from utils.specialists.config import SpecialistConfig
from utils.specialists.cypher.builder import CypherQueryBuilder
from utils.specialists.cypher.connector import CypherConnector
from utils.specialists.gremlin.builder import GremlinQueryBuilder, _capec_candidate_ids
from utils.specialists.gremlin.connector import GremlinConnector
from utils.specialists.gremlin.normalizer import _expand_member_id
from utils.specialists.primitives.expand import ExpandRequest

DESCRIBE = "describe"
_ALL = 1_000_000
_LIMITS = {"max_result_rows": _ALL, "query_timeout_ms": 60_000}


def facet_key(rel: str | None, direction: str | None, target: str | None) -> str:
    return DESCRIBE if not rel else f"{rel}|{direction}|{target}"


def parse_facet(key: str) -> tuple[str | None, str | None, str | None]:
    if key == DESCRIBE:
        return None, None, None
    rel, direction, target = key.split("|")
    return rel, direction, target


class GraphExecutor:
    """Thread-safe: one connector per thread per backend, results memoised."""

    def __init__(self, config: SpecialistConfig | None = None) -> None:
        self.config = config or SpecialistConfig.from_env()
        self._local = threading.local()
        self._memo: dict[tuple, tuple[str, ...]] = {}
        self._memo_lock = threading.Lock()
        self.calls = 0

    def _cypher(self) -> CypherConnector:
        c = getattr(self._local, "cypher", None)
        if c is None:
            c = CypherConnector(self.config, "attack")
            c.connect()
            self._local.cypher = c
        return c

    def _gremlin(self) -> GremlinConnector:
        c = getattr(self._local, "gremlin", None)
        if c is None:
            c = GremlinConnector(self.config.gremlin_uri)
            c.connect()
            self._local.gremlin = c
        return c

    def compile(self, dataset: str, anchor_id: str, anchor_label: str, facet: str) -> tuple[str, dict[str, Any]]:
        rel, direction, target = parse_facet(facet)
        if dataset == "attack":
            req = ExpandRequest(dataset, anchor_id, anchor_label, rel, direction, target, 0, _ALL)
            d = CypherQueryBuilder().expand(req)
            return d.query, d.params
        req = ExpandRequest(dataset, anchor_id, anchor_label, gremlin_edge_label(rel), direction, target, 0, _ALL)
        d = GremlinQueryBuilder().expand(req)
        params = dict(d.params)
        params["ids"] = _capec_candidate_ids([anchor_id])
        return d.query, params

    def records(self, dataset: str, anchor_id: str, anchor_label: str, facet: str) -> tuple[str, ...]:
        """Sorted member ids of ``facet`` of ``anchor_id`` (``describe`` -> the anchor)."""
        if facet == DESCRIBE:
            return (anchor_id,)
        key = (dataset, anchor_id, anchor_label, facet)
        with self._memo_lock:
            if key in self._memo:
                return self._memo[key]
        query, params = self.compile(dataset, anchor_id, anchor_label, facet)
        self.calls += 1
        if dataset == "attack":
            rows = self._cypher().run(query, params, _LIMITS)
            ids = [str(m.get("id")) for r in rows for m in (r.get("members") or [])]
            if rows and rows[0].get("total") is not None and int(rows[0]["total"]) != len(ids):
                raise RuntimeError(f"truncated expand: {len(ids)} of {rows[0]['total']}")
        else:
            rows = self._gremlin().run(query, params, _LIMITS)
            ids = [_expand_member_id(str(r.get("id", ""))) for r in rows]
        out = tuple(sorted(set(ids)))
        with self._memo_lock:
            self._memo[key] = out
        return out
