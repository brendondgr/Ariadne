#!/usr/bin/env python3
"""Golden-set loader for the harness.

Normalises the three committed banks (``attack``, ``capec``, ``federated``) into
one uniform list of :class:`GoldenEntry`, each carrying the *raw* bank entry (the
runner needs ``task`` / ``sub_questions`` to drive the pipeline) plus the
extracted **gold expected-id set** the judge grades against.

Gold extraction, per the bank ``assertions`` schema:

* single-source (attack/capec): the expected answer is the set of primary +
  related ids — ``must_include_ids | must_include_related``. ``expect_empty`` or
  ``expect_boundary`` mark entries whose correct answer is an honest abstention
  (empty gold).
* federated: the expected answer is the required cross-source correlation set —
  ``must_correlate``. ``expect_no_correlation`` (or ``expect_empty``) mark
  negative entries whose correct answer is *no* correlation (empty gold).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# The three source sets and how each maps to a runner "kind".
SET_KINDS = {"attack": "single", "capec": "single", "federated": "federated"}
ALL_SETS = ("attack", "capec", "federated")


@dataclass
class GoldenEntry:
    """One normalised golden question plus its extracted gold answer."""

    question_id: str
    set_name: str
    tier: str
    kind: str  # "single" | "federated"
    source: str  # "attack" | "capec" | "federated"
    question: str
    entry: dict[str, Any]  # the raw bank entry (drives the pipeline)
    gold_expected_ids: frozenset[str] = field(default_factory=frozenset)
    gold_kind: str = "ids"  # "ids" | "correlate"
    expect_empty: bool = False


def extract_gold(entry: dict[str, Any], set_name: str) -> tuple[frozenset[str], str, bool]:
    """Return ``(expected_ids, gold_kind, expect_empty)`` for one bank entry."""
    assertions = entry.get("assertions", {})
    if set_name == "federated":
        expect_empty = bool(
            assertions.get("expect_no_correlation") or assertions.get("expect_empty")
        )
        ids = frozenset(assertions.get("must_correlate", []))
        return ids, "correlate", expect_empty

    # single-source: attack / capec
    expect_empty = bool(
        assertions.get("expect_empty") or assertions.get("expect_boundary")
    )
    ids = frozenset(assertions.get("must_include_ids", [])) | frozenset(
        assertions.get("must_include_related", [])
    )
    return ids, "ids", expect_empty


def _source_of(entry: dict[str, Any], set_name: str) -> str:
    if set_name == "federated":
        return "federated"
    task = entry.get("task", {})
    return task.get("source", set_name)


def _bank_questions(set_name: str) -> list[dict[str, Any]]:
    from utils.specialists.evalset.compile_banks import (
        ATTACK_BANK_PATH,
        CAPEC_BANK_PATH,
        FEDERATED_BANK_PATH,
        load_bank,
    )

    path = {
        "attack": ATTACK_BANK_PATH,
        "capec": CAPEC_BANK_PATH,
        "federated": FEDERATED_BANK_PATH,
    }[set_name]
    return load_bank(path)["questions"]


def load_entries(
    sets: list[str] | tuple[str, ...] | None = None,
    *,
    limit: int | None = None,
    tiers: set[str] | None = None,
) -> list[GoldenEntry]:
    """Load and normalise the requested golden sets into :class:`GoldenEntry`.

    ``sets`` is any subset of ``ALL_SETS`` (default all). ``limit`` caps entries
    *per set* (for smoke runs); ``tiers`` keeps only the named difficulty tiers.
    """
    chosen = list(sets) if sets else list(ALL_SETS)
    out: list[GoldenEntry] = []
    for set_name in chosen:
        if set_name not in SET_KINDS:
            raise ValueError(f"unknown golden set: {set_name!r}")
        questions = _bank_questions(set_name)
        kept = [q for q in questions if tiers is None or q.get("tier") in tiers]
        if limit is not None:
            kept = kept[:limit]
        for entry in kept:
            ids, gold_kind, expect_empty = extract_gold(entry, set_name)
            out.append(
                GoldenEntry(
                    question_id=entry["id"],
                    set_name=set_name,
                    tier=entry.get("tier", ""),
                    kind=SET_KINDS[set_name],
                    source=_source_of(entry, set_name),
                    question=entry.get("question", ""),
                    entry=entry,
                    gold_expected_ids=ids,
                    gold_kind=gold_kind,
                    expect_empty=expect_empty,
                )
            )
    return out
