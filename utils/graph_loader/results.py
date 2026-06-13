#!/usr/bin/env python3

from __future__ import annotations

from dataclasses import dataclass, field

from .models import CountSummary, VerifyLoadedGraphResult


@dataclass
class BackendLoadResult:
    """Outcome of loading one backend projection."""

    backend: str
    success: bool
    nodes_loaded: int = 0
    edges_loaded: int = 0
    verification: VerifyLoadedGraphResult | None = None
    runtime_manifest_path: str | None = None
    error: str | None = None


@dataclass
class DatasetLoadResult:
    """Combined outcome for a dataset load request."""

    dataset: str
    graph_action: str
    backends: list[BackendLoadResult] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return bool(self.backends) and all(result.success for result in self.backends)
