#!/usr/bin/env python3
"""Snapshot-derived gold for the federated credential-theft flow (Wk 10–11).

The proposal's flagship integration query is:

    "Which CAPEC patterns related to credential theft map to ATT&CK
     techniques, and what mitigations appear for those techniques?"

This module composes the expected answer from the already-derived gold bank
(itself computed from the pinned ATT&CK v19 / CAPEC 3.9 raw snapshot — never
hand-keyed): the credential-theft CAPEC set and its ATTACK-taxonomy ``MAPS_TO``
T-IDs, each T-ID's ``MITIGATES`` mitigations, and the expected cross-source
correlation set (T-IDs present on both sides).

The only authored input is ``ANCHOR_TERMS`` — a small, reviewable list of
credential-theft name anchors. Everything selected by it is derived.

Regenerate with:
    uv run python -m utils.specialists.evalset.federated_gold
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..concepts import CONCEPT_ANCHORS
from .gold_bank import GOLDEN_DIR, load_gold_bank

FEDERATED_GOLD_PATH = GOLDEN_DIR / "federated_gold.json"

# The committed selection rule: a CAPEC pattern is "credential-theft related"
# when its name contains one of these anchors (case-insensitive). The terms are
# the SAME committed vocabulary the pipeline's builder scopes its query with
# (utils/specialists/concepts.py), so gold and pipeline cannot drift.
ANCHOR_TERMS: tuple[str, ...] = CONCEPT_ANCHORS["credential theft"]


def select_credential_theft_patterns(capec: dict[str, Any]) -> dict[str, str]:
    """All non-retired CAPEC patterns whose name matches an anchor term."""
    return {
        cid: p["name"]
        for cid, p in capec["patterns"].items()
        if any(term in (p.get("name") or "").lower() for term in ANCHOR_TERMS)
    }


def build_federated_gold(bank: dict[str, Any] | None = None) -> dict[str, Any]:
    """Compose the expected credential-theft result from the gold bank."""
    bank = bank or load_gold_bank()
    capec, attack = bank["capec"], bank["attack"]

    selected = select_credential_theft_patterns(capec)
    # CAPEC sub-question gold: the selected patterns that carry ATTACK-taxonomy
    # MAPS_TO mappings, with their T-IDs.
    capec_to_techniques = {
        cid: capec["attack_mappings"][cid]
        for cid in sorted(selected, key=lambda c: int(c.split("-")[1]))
        if cid in capec["attack_mappings"]
    }
    technique_ids = sorted({t for tids in capec_to_techniques.values() for t in tids})

    # Cross-source gold: a T-ID correlates when it exists on the ATT&CK side.
    objects = attack["objects"]
    expected_correlation = [t for t in technique_ids if t in objects]

    # ATT&CK sub-question gold: MITIGATES mitigations per mapped T-ID. An empty
    # list is an honest "this technique has no mitigation edges" — kept, never
    # dropped, so silent-drop grading can see it.
    technique_mitigations = {
        t: attack["technique_mitigations"].get(t, []) for t in expected_correlation
    }

    return {
        "question": (
            "Which CAPEC patterns related to credential theft map to ATT&CK "
            "techniques, and what mitigations appear for those techniques?"
        ),
        "selection_rule": (
            "CAPEC pattern name contains one of the anchor terms (case-insensitive); "
            "all downstream ids derived from the pinned snapshot via the gold bank"
        ),
        "anchor_terms": list(ANCHOR_TERMS),
        "selected_patterns": {
            cid: selected[cid]
            for cid in sorted(selected, key=lambda c: int(c.split("-")[1]))
        },
        "capec_to_techniques": capec_to_techniques,
        "technique_ids": technique_ids,
        "expected_correlation": expected_correlation,
        "technique_mitigations": technique_mitigations,
    }


def load_federated_gold(path: Path = FEDERATED_GOLD_PATH) -> dict[str, Any]:
    return json.loads(path.read_text())


def main() -> None:
    gold = build_federated_gold()
    FEDERATED_GOLD_PATH.write_text(json.dumps(gold, indent=2) + "\n")
    with_mitigations = sum(1 for m in gold["technique_mitigations"].values() if m)
    print(
        f"Wrote {FEDERATED_GOLD_PATH}: {len(gold['selected_patterns'])} selected patterns, "
        f"{len(gold['capec_to_techniques'])} with ATT&CK mappings, "
        f"{len(gold['technique_ids'])} distinct T-IDs, "
        f"{len(gold['expected_correlation'])} expected correlations, "
        f"{with_mitigations} techniques with mitigations."
    )


if __name__ == "__main__":
    main()
