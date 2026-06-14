#!/usr/bin/env python3

from __future__ import annotations

from utils.kg_builder.models import CapecGraphMetadata, GraphMetadata, NormalizedGraph

DatasetName = str


def dataset_for_graph(graph: NormalizedGraph) -> DatasetName:
    """Infer dataset name from graph metadata."""
    if isinstance(graph.metadata, CapecGraphMetadata):
        return "capec"
    if isinstance(graph.metadata, GraphMetadata):
        return "attack"
    dataset = getattr(graph.metadata, "dataset", None)
    if dataset:
        return str(dataset)
    return "attack"
