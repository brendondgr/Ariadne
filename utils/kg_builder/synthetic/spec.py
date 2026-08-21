#!/usr/bin/env python3
"""The blueprint: what the generator decided, written down before it is loaded.

This module exists to keep EXP-2026-08-011 from being circular. If gold answers
were computed by querying the graph the system also queries, the two would agree
whenever the load was faithful *and* whenever it was not — a dropped edge would
cancel out on both sides and be invisible.

The repository already solved this once. ``utils/specialists/evalset/gold_bank.py``
parses the raw STIX bundle deliberately **not** through ``kg_builder``, so gold
is an independent derivation and the golden suite doubles as an ingestion check.
A synthetic dataset has no raw source to fall back on, so it manufactures one:
the generator records every entity and every edge it decided on, and gold is
computed from that record.

The blueprint is therefore upstream of the graph, not a summary of it. Nothing
here ever reads ``nodes.jsonl``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..catalog.declared import DECLARED, INFERRED


@dataclass
class PlantedPath:
    """One attack chain the generator deliberately created.

    Recorded as an ordered list of ``(node_id, edge_label, node_id)`` steps so a
    gold answer for "what can this user reach" is a lookup rather than a
    traversal. ``uses_inferred`` is precomputed because every result touching an
    inferred edge must be reportable separately.
    """

    name: str
    steps: list[tuple[str, str, str]]
    uses_inferred: bool

    @property
    def start(self) -> str:
        return self.steps[0][0]

    @property
    def end(self) -> str:
        return self.steps[-1][2]

    @property
    def length(self) -> int:
        return len(self.steps)


@dataclass
class TenantSpec:
    """Everything the generator decided, independent of what was loaded."""

    seed: int
    catalog_name: str
    nodes: dict[str, dict[str, Any]] = field(default_factory=dict)
    edges: list[dict[str, Any]] = field(default_factory=list)
    planted_paths: list[PlantedPath] = field(default_factory=list)

    # -- recording ---------------------------------------------------------

    def add_node(self, node_id: str, label: str, name: str, properties: dict[str, Any]) -> None:
        self.nodes[node_id] = {"label": label, "name": name, "properties": properties}

    def add_edge(self, source_id: str, edge: str, target_id: str, origin: str) -> None:
        self.edges.append(
            {"source_id": source_id, "edge": edge, "target_id": target_id, "origin": origin}
        )

    # -- queries the gold builder needs ------------------------------------

    def label_of(self, node_id: str) -> str:
        return self.nodes[node_id]["label"]

    def name_of(self, node_id: str) -> str:
        return self.nodes[node_id]["name"]

    def nodes_of_label(self, label: str) -> list[str]:
        return sorted(n for n, v in self.nodes.items() if v["label"] == label)

    def neighbours(
        self,
        node_id: str,
        edge: str | None = None,
        direction: str = "out",
    ) -> list[str]:
        """Neighbours of ``node_id``, optionally restricted to one edge label.

        ``direction`` is from the anchor's point of view, matching
        :class:`utils.specialists.schema.registry.PlausibleFacet`.
        """
        out: list[str] = []
        for record in self.edges:
            if edge is not None and record["edge"] != edge:
                continue
            if direction == "out" and record["source_id"] == node_id:
                out.append(record["target_id"])
            elif direction == "in" and record["target_id"] == node_id:
                out.append(record["source_id"])
        return sorted(set(out))

    def edges_of(self, edge: str) -> list[dict[str, Any]]:
        return [e for e in self.edges if e["edge"] == edge]

    def triple_of(self, record: dict[str, Any]) -> tuple[str, str, str]:
        return (
            self.label_of(record["source_id"]),
            record["edge"],
            self.label_of(record["target_id"]),
        )

    def uses_inferred(self, record: dict[str, Any]) -> bool:
        return record["origin"] == INFERRED

    # -- counts ------------------------------------------------------------

    def counts(self) -> dict[str, Any]:
        by_label: dict[str, int] = {}
        for value in self.nodes.values():
            by_label[value["label"]] = by_label.get(value["label"], 0) + 1
        by_edge: dict[str, int] = {}
        for record in self.edges:
            by_edge[record["edge"]] = by_edge.get(record["edge"], 0) + 1
        return {
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "edges_declared": sum(1 for e in self.edges if e["origin"] == DECLARED),
            "edges_inferred": sum(1 for e in self.edges if e["origin"] == INFERRED),
            "planted_paths": len(self.planted_paths),
            "nodes_by_label": dict(sorted(by_label.items())),
            "edges_by_label": dict(sorted(by_edge.items())),
        }

    # -- serialization -----------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "catalog_name": self.catalog_name,
            "counts": self.counts(),
            "nodes": self.nodes,
            "edges": self.edges,
            "planted_paths": [
                {
                    "name": p.name,
                    "steps": [list(s) for s in p.steps],
                    "uses_inferred": p.uses_inferred,
                    "start": p.start,
                    "end": p.end,
                    "length": p.length,
                }
                for p in self.planted_paths
            ],
        }

    def write(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")
        return out

    @classmethod
    def read(cls, path: str | Path) -> "TenantSpec":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        spec = cls(seed=payload["seed"], catalog_name=payload["catalog_name"])
        spec.nodes = payload["nodes"]
        spec.edges = payload["edges"]
        spec.planted_paths = [
            PlantedPath(
                name=p["name"],
                steps=[tuple(s) for s in p["steps"]],
                uses_inferred=p["uses_inferred"],
            )
            for p in payload["planted_paths"]
        ]
        return spec
