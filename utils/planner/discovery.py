#!/usr/bin/env python3
"""Discovery / liveness — the planner's "what graphs are running right now" view.

This is where the planner reads the **active** graphs in the Docker stack. It
must reflect reality at planning time, not registry intent, so:

* It runs a **content probe**, not a bare socket open: connect, confirm a
  non-trivial node count, and confirm a couple of expected labels exist. A
  backend that is up but holds the wrong/empty graph is treated as down
  (briefing §2.2).
* Each probe runs in its **own short-timeout** worker thread so a slow or
  half-dead backend cannot stall planning (briefing §2.3).
* It **re-probes per request** with a short TTL cache, so the live-source view
  tracks the current state rather than a startup snapshot (briefing §2.1/§2.4).

Anything not confirmed live — unreachable, unauthorized, empty, or timed out —
is reported with a reason so the planner can mark the dependent part
unsupported instead of failing the whole request.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Callable, Protocol

from .cards import SourceCardView
from .config import PlannerConfig

logger = logging.getLogger("ariadne.planner.discovery")


class ProbeTimeout(Exception):
    """Raised when a liveness probe exceeds its own short timeout."""


class ProbeStore(Protocol):
    """The minimal store surface the content probe needs (subset of GraphStore)."""

    def connect(self) -> None: ...
    def close(self) -> None: ...
    def count_nodes(self) -> int: ...
    def count_by_label(self, label: str) -> int: ...


# A factory builds a fresh probe store for one card. Injectable for testing.
StoreFactory = Callable[[SourceCardView, PlannerConfig], ProbeStore]


@dataclass(frozen=True)
class LiveSource:
    """The liveness verdict for one source at probe time."""

    dataset: str
    backend: str
    endpoint: str
    reachable: bool
    node_count: int = 0
    observed_labels: tuple[str, ...] = ()
    reason: str = ""

    @property
    def live(self) -> bool:
        return self.reachable


@dataclass(frozen=True)
class LiveSourceView:
    """A snapshot of every source's liveness, consumed as ground truth."""

    sources: dict[str, LiveSource] = field(default_factory=dict)

    def is_live(self, dataset: str) -> bool:
        source = self.sources.get(dataset)
        return bool(source and source.reachable)

    def get(self, dataset: str) -> LiveSource | None:
        return self.sources.get(dataset)

    def live_datasets(self) -> list[str]:
        return sorted(ds for ds, src in self.sources.items() if src.reachable)

    def down_datasets(self) -> list[str]:
        return sorted(ds for ds, src in self.sources.items() if not src.reachable)


def _run_with_timeout(fn: Callable[[], object], timeout: float) -> object:
    """Run ``fn`` in a daemon thread, raising ProbeTimeout if it overruns.

    A daemon thread is used (not ThreadPoolExecutor) so a genuinely hung
    backend leaves an abandoned thread rather than blocking process exit.
    """
    box: dict[str, object] = {}

    def target() -> None:
        try:
            box["value"] = fn()
        except BaseException as exc:  # noqa: BLE001 - re-raised on the caller thread
            box["error"] = exc

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        raise ProbeTimeout(f"probe exceeded {timeout:.1f}s")
    if "error" in box:
        raise box["error"]  # type: ignore[misc]
    return box.get("value")


def _default_store_factory(card: SourceCardView, config: PlannerConfig) -> ProbeStore:
    """Build a real GraphStore for the card's runtime backend."""
    from utils.graph_loader.stores.gremlin import GremlinGraphStore
    from utils.graph_loader.stores.neo4j import Neo4jGraphStore

    backend = card.runtime_backend
    if backend == "neo4j":
        return Neo4jGraphStore(
            uri=config.neo4j_uri,
            user=config.neo4j_user,
            password=config.neo4j_password,
            export_files={},
        )
    if backend == "gremlin":
        return GremlinGraphStore(uri=config.gremlin_uri, export_files={})
    raise ValueError(f"Unknown runtime backend {backend!r} for {card.dataset!r}")


class LiveSourceProbe:
    """Probes source liveness with a content check and a short TTL cache."""

    def __init__(
        self,
        config: PlannerConfig,
        *,
        store_factory: StoreFactory = _default_store_factory,
        clock: Callable[[], float] = None,  # type: ignore[assignment]
    ) -> None:
        import time

        self._config = config
        self._store_factory = store_factory
        self._clock = clock or time.monotonic
        self._cache: LiveSourceView | None = None
        self._cached_at: float = float("-inf")

    # -- single-source content probe ---------------------------------------

    def probe_source(self, card: SourceCardView) -> LiveSource:
        backend = card.runtime_backend
        try:
            endpoint = self._config.endpoint_for(backend)
        except ValueError as exc:
            return LiveSource(card.dataset, backend, "", False, reason=str(exc))

        expected = card.expected_probe_labels()
        min_nodes = self._config.min_live_nodes

        def _probe() -> tuple[int, tuple[str, ...]]:
            store = self._store_factory(card, self._config)
            store.connect()
            try:
                total = store.count_nodes()
                observed: list[str] = []
                for label in expected:
                    if store.count_by_label(label) > 0:
                        observed.append(label)
                return total, tuple(observed)
            finally:
                try:
                    store.close()
                except Exception:  # noqa: BLE001 - close failures must not mask result
                    pass

        try:
            total, observed = _run_with_timeout(_probe, self._config.probe_timeout_s)  # type: ignore[misc]
        except ProbeTimeout as exc:
            logger.info("probe timeout for %s: %s", card.dataset, exc)
            return LiveSource(card.dataset, backend, endpoint, False, reason=f"probe timed out: {exc}")
        except Exception as exc:  # noqa: BLE001 - any connect/query failure ⇒ down
            logger.info("probe failed for %s: %s", card.dataset, exc)
            return LiveSource(
                card.dataset, backend, endpoint, False,
                reason=f"backend unreachable or unauthorized: {type(exc).__name__}: {exc}",
            )

        if total < min_nodes:
            return LiveSource(
                card.dataset, backend, endpoint, False, node_count=total,
                reason=f"backend up but graph empty (nodes={total} < {min_nodes})",
            )
        if expected and not observed:
            return LiveSource(
                card.dataset, backend, endpoint, False, node_count=total,
                reason=f"backend up with {total} nodes but none of the expected labels {expected} present",
            )
        return LiveSource(
            card.dataset, backend, endpoint, True, node_count=total,
            observed_labels=observed, reason="live",
        )

    # -- per-request view with short TTL cache -----------------------------

    def get_live_sources(
        self, cards: dict[str, SourceCardView], *, force: bool = False
    ) -> LiveSourceView:
        now = self._clock()
        if (
            not force
            and self._cache is not None
            and (now - self._cached_at) < self._config.cache_ttl_s
        ):
            return self._cache
        view = LiveSourceView({ds: self.probe_source(card) for ds, card in cards.items()})
        self._cache = view
        self._cached_at = now
        return view


def get_live_sources(
    cards: dict[str, SourceCardView],
    config: PlannerConfig,
    *,
    store_factory: StoreFactory = _default_store_factory,
) -> LiveSourceView:
    """One-shot probe of every card's liveness (no persistent cache)."""
    probe = LiveSourceProbe(config, store_factory=store_factory)
    return probe.get_live_sources(cards, force=True)


def stub_live_view(
    cards: dict[str, SourceCardView], live: tuple[str, ...] | list[str]
) -> LiveSourceView:
    """Build a deterministic live-source view without probing any backend.

    Datasets named in ``live`` are reported reachable. Useful for evaluation and
    tests, where liveness must be fixed independent of the running stack.
    """
    live_set = set(live)
    sources: dict[str, LiveSource] = {}
    for ds, card in cards.items():
        reachable = ds in live_set
        sources[ds] = LiveSource(
            dataset=ds,
            backend=card.runtime_backend,
            endpoint=f"stub://{ds}",
            reachable=reachable,
            node_count=100 if reachable else 0,
            observed_labels=tuple(card.expected_probe_labels()) if reachable else (),
            reason="live" if reachable else "stubbed down",
        )
    return LiveSourceView(sources)
