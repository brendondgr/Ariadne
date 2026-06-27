#!/usr/bin/env python3
"""Shared test helpers: load the committed fixture source cards."""

from __future__ import annotations

from pathlib import Path

from utils.planner.cards import SourceCardView, load_source_cards
from utils.planner.discovery import LiveSource, LiveSourceView

FIXTURES_DIR = Path(__file__).parent / "fixtures"
FIXTURE_DATA_DIR = FIXTURES_DIR  # contains a ``source_cards/`` subdirectory


def load_fixture_cards() -> dict[str, SourceCardView]:
    """Load and enrich the small committed fixture cards (attack + capec)."""
    return load_source_cards(FIXTURE_DATA_DIR)


def fixture_card(dataset: str) -> SourceCardView:
    return load_fixture_cards()[dataset]


def make_live_view(*, live: tuple[str, ...] = ("attack", "capec")) -> LiveSourceView:
    """Build a LiveSourceView for tests: datasets in ``live`` are reachable."""
    cards = load_fixture_cards()
    sources: dict[str, LiveSource] = {}
    for ds, card in cards.items():
        reachable = ds in live
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
